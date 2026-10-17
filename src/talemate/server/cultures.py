"""Websocket plugin exposing `talemate.cultures` to the frontend.

Reply contract (task-6 brief, spec 9.2):

- Every handler that writes replies with a ``world`` message:
  ``{"type": "cultures", "action": "world", "data": {"available": bool,
  "world_name": str, **store.snapshot()}}``. With no shared context linked
  to the scene, only ``{"available": False}`` is sent.
- Errors are reported through ``signal_operation_failed`` without writing
  anything. ``ImportFormatError``, ``PlaceError`` and ``GeneratorError`` are
  all ``ValueError`` subclasses, and so is pydantic's ``ValidationError``,
  so a single ``except ValueError`` catches all of them.
- The store is re-opened from disk on every request, so edits made to the
  same shared world from another scene are never shadowed by a stale
  in-memory cache.
"""

import datetime
from typing import Literal

import pydantic

from talemate.cultures import generator
from talemate.cultures.exchange import apply_import, export_culture, preview_import
from talemate.cultures.models import Culture, GlossaryEntry, Place, new_id
from talemate.cultures.places import delete_place, reparent, set_shares
from talemate.cultures.store import WorldStore, world_dir_for_scene
from talemate.server.websocket_plugin import Plugin

__all__ = ["CulturesPlugin"]


class SaveCulturePayload(pydantic.BaseModel):
    culture: dict


class DeleteCulturePayload(pydantic.BaseModel):
    culture_id: str


class AdditionPayload(pydantic.BaseModel):
    culture_id: str
    addition_id: str
    op: Literal["keep", "edit", "drop"]
    text: str | None = None


class SavePlacePayload(pydantic.BaseModel):
    place: dict


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


class RollPayload(pydantic.BaseModel):
    culture_id: str
    generator_id: str
    count: int = 20
    # Client-generated, echoed back unchanged in the `rolled` reply so the
    # frontend can route the reply to whichever widget asked for it (several
    # components can have a roll outstanding for the same generator at
    # once). Optional so other/older callers keep working.
    request_id: str | None = None


class ImportContentPayload(pydantic.BaseModel):
    content: str


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

    def _world_name(self) -> str:
        return self.scene.shared_context.filepath.stem

    async def _send_world(self, store: WorldStore | None) -> None:
        if store is None:
            data = {"available": False}
        else:
            data = {
                "available": True,
                "world_name": self._world_name(),
                **store.snapshot(),
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
                if incoming.cultures != existing.cultures:
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
            await self.signal_operation_failed(str(e))
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

        try:
            payload = ImportContentPayload(**data)
            preview = preview_import(store, payload.content)
        except ValueError as e:
            await self.signal_operation_failed(str(e))
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

        try:
            payload = ImportContentPayload(**data)
            today = datetime.date.today().isoformat()
            culture = apply_import(store, payload.content, today)
        except ValueError as e:
            await self.signal_operation_failed(str(e))
            return

        await self._send_world(store)
        await self.signal_operation_done(
            emit_status_message=f"Imported {culture.name} into {self._world_name()}"
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
