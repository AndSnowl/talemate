/**
 * Shared mixin for the cultures components that keep a locally-editable
 * clone of a server-sent object (`CultureOverview`, `LanguageOverview`,
 * `GlossaryDetail`, `DictionaryTable`, `GeneratorList`, `PhraseList`).
 *
 * The culture editors clone only the fields they own (`source`) and save
 * them with `patch_culture`, so even a stale local copy can only ever
 * write back its own fields.
 *
 * The problem this solves: every save of *anything* under a shared world
 * re-broadcasts the whole `world` payload, which refreshes the `culture` /
 * `entry` prop on every one of these components at once. A naive
 * `watch(prop, (v) => { this.local = clone(v) })` therefore clobbers
 * whatever the owner is mid-typing in an unrelated field, or even in the
 * same field, whenever *any* other edit anywhere lands first.
 *
 * The fix: only re-clone from the prop when
 *   - the edited item's identity changed (a different culture/entry is now
 *     selected: there is nothing of the old item's local edits worth
 *     keeping), or
 *   - the local copy isn't dirty (no unsaved edits to protect).
 * A broadcast for the *same* item while the local copy is dirty is ignored
 * outright, leaving the owner's in-progress edits alone. The local copy is
 * marked dirty by a deep watch (so every keystroke, push/splice, etc. counts,
 * not just a blur), and is cleared by the component itself once it has sent
 * its own save.
 */
export function dirtyLocalClone({ watchPath, source, identity, clone = (raw) => JSON.parse(JSON.stringify(raw)) } = {}) {
    if (!watchPath) {
        throw new Error('dirtyLocalClone requires a `watchPath` (the prop name to watch for broadcasts)');
    }

    const getSource = source || (vm => vm[watchPath]);
    const getIdentity = identity || (vm => {
        const value = getSource(vm);
        return value && value.id;
    });

    return {
        data() {
            return {
                local: clone(getSource(this), this),
                localDirty: false,
                _localIdentity: getIdentity(this),
                _suppressLocalDirty: false,
            };
        },
        watch: {
            [watchPath]: {
                handler() {
                    const newIdentity = getIdentity(this);
                    const identityChanged = newIdentity !== this._localIdentity;
                    if (identityChanged || !this.localDirty) {
                        this._suppressLocalDirty = true;
                        this.local = clone(getSource(this), this);
                        this._localIdentity = newIdentity;
                        this.localDirty = false;
                        this.$nextTick(() => {
                            this._suppressLocalDirty = false;
                        });
                        // `identityChanged` is false for a same-item re-clone
                        // (e.g. the `world` reply to our own save), so hooks can
                        // keep per-item UI state such as an outstanding roll.
                        if (typeof this.onLocalReset === 'function') {
                            this.onLocalReset(this.local, identityChanged);
                        }
                        return;
                    }
                    // Same item, unsaved local edits: ignore this broadcast
                    // rather than clobbering them. It will be picked up
                    // again (or superseded by the owner's own save) once
                    // `clearLocalDirty()` runs.
                },
            },
            local: {
                deep: true,
                handler() {
                    if (this._suppressLocalDirty) {
                        return;
                    }
                    this.localDirty = true;
                },
            },
        },
        methods: {
            // Call this right after sending a save. Deferred to nextTick so
            // it always runs after the deep watcher's own (already pending)
            // reaction to that same edit, instead of racing it.
            clearLocalDirty() {
                this.$nextTick(() => {
                    this.localDirty = false;
                });
            },
        },
    };
}
