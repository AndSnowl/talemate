"""Websocket plugin exposing `talemate.cultures` to the frontend.

Reply contract (task-6 brief, spec 9.2):

- Every handler that writes replies with a ``world`` message:
  ``{"type": "cultures", "action": "world", "data": {"available": bool,
  "world_name": str, **store.snapshot()}}``. With no shared context linked
  to the scene, only ``{"available": False}`` is sent.
- Errors are reported through ``signal_operation_failed`` without writing
  anything. ``ImportFormatError``, ``PlaceError``, ``GeneratorError`` and
  ``WorldFileError`` are all ``ValueError`` subclasses, and so is
  pydantic's ``ValidationError``, so a single ``except ValueError`` catches
  all of them. Roll and import errors also carry the request's
  ``request_id`` (``error.request_id``) so the widget that asked can clear
  its spinner.
- Culture edits from the frontend use ``patch_culture``, which replaces
  only the fields it names; ``save_culture`` replaces a whole culture but
  always keeps ``additions``, ``source_file`` and ``imported_at`` from
  disk.
- The store is re-opened from disk on every request, so edits made to the
  same shared world from another scene are never shadowed by a stale
  in-memory cache.
"""

import datetime
from typing import Literal

import pydantic
import structlog

from talemate.cultures import generator
from talemate.cultures.exchange import apply_import, export_culture, preview_import
from talemate.cultures.models import Culture, GlossaryEntry, Language, Place, new_id
from talemate.cultures.places import delete_place, reparent, set_share, set_shares
from talemate.cultures.store import WorldStore, world_dir_for_scene
from talemate.emit import emit
from talemate.server.websocket_plugin import Plugin

__all__ = ["CulturesPlugin"]

log = structlog.get_logger("talemate.server.cultures")


class SaveCulturePayload(pydantic.BaseModel):
    culture: dict


class PatchCulturePayload(pydantic.BaseModel):
    """Replace only the named fields of a stored culture.

    Each frontend editor owns a few fields (the culture page owns
    description/customs/food/holidays, the dictionary table owns
    `language.dictionary`, ...) and sends only those, so a stale local copy
    can never overwrite fields edited elsewhere, or the play additions.
    """

    culture_id: str
    culture: dict = pydantic.Field(default_factory=dict)
    language: dict = pydantic.Field(default_factory=dict)


# Fields `patch_culture` may replace. Identity, play additions and import
# provenance are never taken from a client payload.
PATCHABLE_CULTURE_FIELDS = frozenset(
    {"name", "color", "description", "customs", "food", "holidays"}
)
PATCHABLE_LANGUAGE_FIELDS = frozenset(Language.model_fields)


class DeleteCulturePayload(pydantic.BaseModel):
    culture_id: str


class AdditionPayload(pydantic.BaseModel):
    culture_id: str
    addition_id: str
    op: Literal["keep", "edit", "drop"]
    text: str | None = None


class SetSharePayload(pydantic.BaseModel):
    culture_id: str
    share: int


class SavePlacePayload(pydantic.BaseModel):
    place: dict
    # One-slider editing: keep this culture's share exactly and scale the
    # place's other shares to fill the remainder (`places.set_share`),
    # instead of replacing the whole list via `places.set_shares`. Set by
    # the places-view slider, which sends on release with a single changed
    # value rather than the full, already-renormalised mix.
    set_share: SetSharePayload | None = None


class DeletePlacePayload(pydantic.BaseModel):
    place_id: str
    move_children_to: str | None = None


class SaveGlossaryEntryPayload(pydantic.BaseModel):
    entry: dict


class ReviewGlossaryEntryPayload(pydantic.BaseModel):
    entry_id: str
    status: Literal["unreviewed", "reviewed"]


class DeleteGlossaryEntryPayload(pydantic.BaseModel):
    entry_id: str


MAX_ROLL_COUNT = 100


def _require_text(value: str, what: str) -> None:
    if not value.strip():
        raise ValueError(f"{what} can't be empty")


class RollPayload(pydantic.BaseModel):
    culture_id: str
    generator_id: str
    count: int = 20
    # Client-generated, echoed back unchanged in the `rolled` reply so the
    # frontend can route the reply to whichever widget asked for it (several
    # components can have a roll outstanding for the same generator at
    # once). Optional so other/older callers keep working.
    request_id: str | None = None

    @pydantic.field_validator("count")
    @classmethod
    def _clamp_count(cls, value: int) -> int:
        return max(1, min(MAX_ROLL_COUNT, value))


class ImportContentPayload(pydantic.BaseModel):
    content: str
    # Echoed back in an error reply, so the import dialog only clears its
    # own spinner (see `RollPayload.request_id`).
    request_id: str | None = None


class ExportPayload(pydantic.BaseModel):
    culture_id: str


class CulturesPlugin(Plugin):
    router = "cultures"

    def _store(self) -> WorldStore | None:
        world_dir = world_dir_for_scene(self.scene)
        if world_dir is None:
            return None
        return WorldStore(world_dir)

    async def _require_store(self) -> WorldStore | None:
        store = self._store()
        if store is None:
            await self.signal_operation_failed("This scene has no shared world linked.")
        return store

    async def _fail(self, message: str, request_id: str | None) -> None:
        """Like `signal_operation_failed`, tagging the error with `request_id`.

        Lets the widget that sent the request (a Roll button, the import
        dialog) clear its own busy state on failure, not just on success.
        """
        self.websocket_handler.queue_put(
            {
                "type": self.router,
                "action": "operation_done",
                "error": {"message": message, "request_id": request_id},
            }
        )
        emit("status", message=message, status="error")

    async def _fail_unexpected(
        self, action: str, exc: Exception, request_id: str | None
    ) -> None:
        log.exception("cultures: unexpected error", action=action)
        await self._fail(f"Error during {action}: {exc}", request_id)

    def _world_name(self) -> str:
        return self.scene.shared_context.filepath.stem

    async def _send_world(self, store: WorldStore | None) -> None:
        """Send the `world` reply. Always replies, even if loading fails.

        A world file that can't be read is reported as ``{"available":
        True, "error": message}`` (with empty lists), so the tab shows the
        problem instead of claiming no shared world is linked.
        """
        if store is None:
            data = {"available": False}
        else:
            try:
                data = {
                    "available": True,
                    "world_name": self._world_name(),
                    **store.snapshot(),
                }
            except Exception as e:
                log.exception("cultures: could not load the shared world")
                data = {
                    "available": True,
                    "world_name": self._world_name(),
                    "error": f"The shared world's files couldn't be loaded: {e}",
                    "cultures": [],
                    "places": [],
                    "glossary": [],
                    "counts": {},
                }
        self.websocket_handler.queue_put(
            {"type": self.router, "action": "world", "data": data}
        )

    async def handle_get_world(self, data: dict):
        await self._send_world(self._store())

    async def handle_save_culture(self, data: dict):
        store = await self._require_store()
        if store is None:
            return

        try:
            payload = SaveCulturePayload(**data)
            culture = Culture.model_validate(payload.culture)
            _require_text(culture.name, "A culture's name")
            # Play additions and import provenance are owned by the copy on
            # disk (changed only through `addition` and imports), never by
            # a client payload, which may be a stale local copy.
            existing = store.load_cultures().get(culture.id) or Culture(
                id=culture.id, name=culture.name, language=culture.language
            )
            culture = culture.model_copy(
                update={
                    "additions": existing.additions,
                    "source_file": existing.source_file,
                    "imported_at": existing.imported_at,
                }
            )
            generator.validate_language(culture.language)
            store.save_culture(culture)
        except ValueError as e:
            await self.signal_operation_failed(str(e))
            return

        await self._send_world(store)

    async def handle_patch_culture(self, data: dict):
        store = await self._require_store()
        if store is None:
            return

        try:
            payload = PatchCulturePayload(**data)
            unknown = set(payload.culture) - PATCHABLE_CULTURE_FIELDS
            if unknown:
                raise ValueError(
                    f"culture fields can't be patched: {', '.join(sorted(unknown))}"
                )
            unknown = set(payload.language) - PATCHABLE_LANGUAGE_FIELDS
            if unknown:
                raise ValueError(
                    f"language fields can't be patched: {', '.join(sorted(unknown))}"
                )

            existing = store.load_cultures().get(payload.culture_id)
            if existing is None:
                raise ValueError(f"unknown culture: {payload.culture_id}")

            merged = existing.model_dump(mode="json")
            merged.update(payload.culture)
            merged["language"].update(payload.language)
            culture = Culture.model_validate(merged)
            _require_text(culture.name, "A culture's name")
            generator.validate_language(culture.language)
            store.save_culture(culture)
        except ValueError as e:
            await self.signal_operation_failed(str(e))
            return

        await self._send_world(store)

    async def handle_delete_culture(self, data: dict):
        store = await self._require_store()
        if store is None:
            return

        try:
            payload = DeleteCulturePayload(**data)
            culture_id = payload.culture_id

            store.delete_culture(culture_id)

            glossary = store.load_glossary()
            glossary = [
                entry.model_copy(update={"language": None})
                if entry.language == culture_id
                else entry
                for entry in glossary
            ]
            store.save_glossary(glossary)

            places = store.load_places()
            for place in list(places):
                if any(cs.culture_id == culture_id for cs in place.cultures):
                    remaining = [
                        cs for cs in place.cultures if cs.culture_id != culture_id
                    ]
                    places = set_shares(places, place.id, remaining)
            store.save_places(places)
        except ValueError as e:
            await self.signal_operation_failed(str(e))
            return

        await self._send_world(store)

    async def handle_addition(self, data: dict):
        store = await self._require_store()
        if store is None:
            return

        try:
            payload = AdditionPayload(**data)
            cultures = store.load_cultures()
            culture = cultures.get(payload.culture_id)
            if culture is None:
                raise ValueError(f"unknown culture: {payload.culture_id}")

            existing = next(
                (a for a in culture.additions if a.id == payload.addition_id), None
            )
            if existing is None:
                raise ValueError(f"unknown addition: {payload.addition_id}")

            if payload.op == "drop":
                additions = [
                    a for a in culture.additions if a.id != payload.addition_id
                ]
            else:
                updates = {"status": "reviewed"}
                if payload.op == "edit":
                    if payload.text is None:
                        raise ValueError("edit requires text")
                    updates["text"] = payload.text
                additions = [
                    a.model_copy(update=updates) if a.id == payload.addition_id else a
                    for a in culture.additions
                ]

            culture = culture.model_copy(update={"additions": additions})
            store.save_culture(culture)
        except ValueError as e:
            await self.signal_operation_failed(str(e))
            return

        await self._send_world(store)

    async def handle_save_place(self, data: dict):
        store = await self._require_store()
        if store is None:
            return

        try:
            payload = SavePlacePayload(**data)
            place_data = dict(payload.place)
            creating = not place_data.get("id")
            if creating:
                place_data["id"] = new_id()
            incoming = Place.model_validate(place_data)
            _require_text(incoming.name, "A place's name")

            places = store.load_places()
            if creating:
                bare = incoming.model_copy(update={"parent_id": None, "cultures": []})
                places = places + [bare]
                if incoming.parent_id is not None:
                    places = reparent(places, bare.id, incoming.parent_id)
                if incoming.cultures:
                    places = set_shares(places, bare.id, incoming.cultures)
            else:
                existing = next((p for p in places if p.id == incoming.id), None)
                if existing is None:
                    raise ValueError(f"unknown place: {incoming.id}")

                places = [
                    p.model_copy(
                        update={
                            "name": incoming.name,
                            "kind": incoming.kind,
                            "world_entry_id": incoming.world_entry_id,
                            "set_by": incoming.set_by,
                            "unsure": incoming.unsure,
                            "note": incoming.note,
                        }
                    )
                    if p.id == incoming.id
                    else p
                    for p in places
                ]

                if incoming.parent_id != existing.parent_id:
                    places = reparent(places, incoming.id, incoming.parent_id)
                if payload.set_share is not None:
                    places = set_share(
                        places,
                        incoming.id,
                        payload.set_share.culture_id,
                        payload.set_share.share,
                    )
                elif incoming.cultures != existing.cultures:
                    places = set_shares(places, incoming.id, incoming.cultures)

            store.save_places(places)
        except ValueError as e:
            await self.signal_operation_failed(str(e))
            return

        await self._send_world(store)

    async def handle_delete_place(self, data: dict):
        store = await self._require_store()
        if store is None:
            return

        try:
            payload = DeletePlacePayload(**data)
            places = store.load_places()
            places = delete_place(places, payload.place_id, payload.move_children_to)
            store.save_places(places)
        except ValueError as e:
            await self.signal_operation_failed(str(e))
            return

        await self._send_world(store)

    async def handle_save_glossary_entry(self, data: dict):
        store = await self._require_store()
        if store is None:
            return

        try:
            payload = SaveGlossaryEntryPayload(**data)
            entry_data = dict(payload.entry)
            creating = not entry_data.get("id")
            if creating:
                entry_data["id"] = new_id()
                entry_data["origin"] = {
                    **entry_data.get("origin", {}),
                    "by": "owner",
                }
                entry_data["status"] = "reviewed"
            entry = GlossaryEntry.model_validate(entry_data)
            _require_text(entry.text, "A glossary entry's text")

            entries = store.load_glossary()
            if creating:
                entries.append(entry)
            else:
                existing = next((e for e in entries if e.id == entry.id), None)
                if existing is None:
                    raise ValueError(f"unknown glossary entry: {entry.id}")

                if (
                    existing.text != entry.text
                    or existing.meaning != entry.meaning
                    or existing.language != entry.language
                ):
                    entry = entry.model_copy(update={"edited_by_owner": True})

                entries = [entry if e.id == entry.id else e for e in entries]

            store.save_glossary(entries)
        except ValueError as e:
            await self.signal_operation_failed(str(e))
            return

        await self._send_world(store)

    async def handle_review_glossary_entry(self, data: dict):
        store = await self._require_store()
        if store is None:
            return

        try:
            payload = ReviewGlossaryEntryPayload(**data)
            entries = store.load_glossary()
            existing = next((e for e in entries if e.id == payload.entry_id), None)
            if existing is None:
                raise ValueError(f"unknown glossary entry: {payload.entry_id}")

            entries = [
                e.model_copy(update={"status": payload.status})
                if e.id == payload.entry_id
                else e
                for e in entries
            ]
            store.save_glossary(entries)
        except ValueError as e:
            await self.signal_operation_failed(str(e))
            return

        await self._send_world(store)

    async def handle_delete_glossary_entry(self, data: dict):
        store = await self._require_store()
        if store is None:
            return

        try:
            payload = DeleteGlossaryEntryPayload(**data)
            entries = [e for e in store.load_glossary() if e.id != payload.entry_id]
            store.save_glossary(entries)
        except ValueError as e:
            await self.signal_operation_failed(str(e))
            return

        await self._send_world(store)

    async def handle_roll(self, data: dict):
        store = await self._require_store()
        if store is None:
            return

        request_id = data.get("request_id")
        try:
            payload = RollPayload(**data)
            cultures = store.load_cultures()
            culture = cultures.get(payload.culture_id)
            if culture is None:
                raise ValueError(f"unknown culture: {payload.culture_id}")

            exclude = {entry.text.lower() for entry in store.load_glossary()}
            names = generator.roll(
                culture.language,
                payload.generator_id,
                count=payload.count,
                exclude=exclude,
            )
            # Belt and suspenders: re-filter the result in case the
            # generator didn't honour `exclude` (names already in the
            # glossary must never be offered as rolls).
            names = [name for name in names if name.lower() not in exclude]
        except ValueError as e:
            await self._fail(str(e), request_id)
            return
        except Exception as e:
            await self._fail_unexpected("roll", e, request_id)
            return

        self.websocket_handler.queue_put(
            {
                "type": self.router,
                "action": "rolled",
                "data": {
                    "generator_id": payload.generator_id,
                    "names": names,
                    "request_id": payload.request_id,
                },
            }
        )

    async def handle_import_preview(self, data: dict):
        store = await self._require_store()
        if store is None:
            return

        request_id = data.get("request_id")
        try:
            payload = ImportContentPayload(**data)
            preview = preview_import(store, payload.content)
        except ValueError as e:
            await self._fail(str(e), request_id)
            return
        except Exception as e:
            await self._fail_unexpected("import_preview", e, request_id)
            return

        self.websocket_handler.queue_put(
            {
                "type": self.router,
                "action": "import_preview",
                "data": preview.model_dump(mode="json"),
            }
        )

    async def handle_import_apply(self, data: dict):
        store = await self._require_store()
        if store is None:
            return

        request_id = data.get("request_id")
        try:
            payload = ImportContentPayload(**data)
            today = datetime.date.today().isoformat()
            culture = apply_import(store, payload.content, today)
        except ValueError as e:
            await self._fail(str(e), request_id)
            return
        except Exception as e:
            await self._fail_unexpected("import_apply", e, request_id)
            return

        await self._send_world(store)
        # The import writes to the shared world's own files, not the scene:
        # like every other write here, it must not mark the scene unsaved
        # or trigger an autosave.
        await self.signal_operation_done(
            signal_only=True,
            emit_status_message=f"Imported {culture.name} into {self._world_name()}",
        )

    async def handle_export(self, data: dict):
        store = await self._require_store()
        if store is None:
            return

        try:
            payload = ExportPayload(**data)
            content = export_culture(store, payload.culture_id)
        except ValueError as e:
            await self.signal_operation_failed(str(e))
            return

        self.websocket_handler.queue_put(
            {
                "type": self.router,
                "action": "exported",
                "data": {
                    "filename": f"{payload.culture_id}.culture.json",
                    "content": content,
                },
            }
        )
