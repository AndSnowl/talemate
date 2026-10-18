<template>
    <div class="people-view">
        <div v-if="characters.length === 0" class="text-center text-muted pa-8">
            <v-icon size="32" color="success">mdi-check-circle-outline</v-icon>
            <div class="mt-2">No characters in this scene yet.</div>
        </div>
        <v-table v-else density="compact">
            <thead>
                <tr>
                    <th>Name</th>
                    <th>Culture</th>
                    <th>Who set it</th>
                    <th></th>
                </tr>
            </thead>
            <tbody>
                <tr
                    v-for="character in characters"
                    :key="character.name"
                    class="people-row"
                    :class="{ 'people-row-focus': character.name === localFocusName }"
                >
                    <td>
                        <span v-if="isUnsure(character)" class="unsure-dot mr-1"></span>
                        {{ character.name }}
                    </td>
                    <td>
                        <v-select
                            :model-value="cultureIdFor(character)"
                            :items="cultureOptions"
                            item-title="title"
                            item-value="value"
                            density="compact"
                            variant="outlined"
                            hide-details
                            style="max-width: 220px"
                            @update:model-value="(value) => setCulture(character, value)"
                        ></v-select>
                    </td>
                    <td class="text-muted text-caption">
                        {{ whoSetIt(character) }}
                    </td>
                    <td>
                        <v-btn
                            v-if="isUnsure(character)"
                            size="small"
                            variant="tonal"
                            color="primary"
                            prepend-icon="mdi-check"
                            @click="reviewCulture(character)"
                        >
                            Looks right
                        </v-btn>
                    </td>
                </tr>
            </tbody>
        </v-table>
    </div>
</template>

<script>
export default {
    name: 'PeopleView',
    props: {
        characters: {
            type: Array,
            default: () => [],
        },
        cultures: {
            type: Array,
            default: () => [],
        },
        send: {
            type: Function,
            required: true,
        },
        focusName: {
            type: String,
            default: null,
        },
    },
    emits: [
        'focus-applied',
    ],
    data() {
        return {
            // Copied from `focusName` below rather than read live: the
            // parent clears `focusName` right after `focus-applied` (so a
            // later, unrelated visit doesn't re-highlight a stale row),
            // which would otherwise erase this row's highlight the moment
            // it appeared, since the class binding would lose its match.
            localFocusName: null,
        }
    },
    watch: {
        focusName: {
            immediate: true,
            handler(name) {
                if (!name) return;
                this.localFocusName = name;
                this.$nextTick(() => {
                    const el = this.$el.querySelector('.people-row-focus');
                    if (el) el.scrollIntoView({ block: 'center' });
                });
                // Tell the parent this jump has been applied, so it clears
                // its own `peopleFocusName` — otherwise it would stay
                // highlighted on every later, unrelated visit to this view.
                this.$emit('focus-applied');
            },
        },
    },
    computed: {
        cultureOptions() {
            const options = this.cultures.map(c => ({ title: c.name, value: c.id }));
            options.push({ title: 'No culture', value: null });
            return options;
        },
    },
    methods: {
        cultureIdFor(character) {
            return character.culture ? character.culture.culture_id : null;
        },
        isUnsure(character) {
            return !!(character.culture && character.culture.set_by === 'ai' && character.culture.unsure);
        },
        whoSetIt(character) {
            const culture = character.culture;
            if (!culture) {
                return '';
            }
            if (culture.set_by === 'owner') {
                return "Set by you · the AI won't change it";
            }
            return culture.reason
                ? `Worked out by the AI · ${culture.reason}`
                : 'Worked out by the AI';
        },
        setCulture(character, cultureId) {
            this.send('set_character_culture', {
                character_name: character.name,
                culture_id: cultureId,
            });
        },
        reviewCulture(character) {
            this.send('review_character_culture', { character_name: character.name });
        },
    },
}
</script>

<style scoped>
.unsure-dot {
    display: inline-block;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: rgb(var(--v-theme-unsaved));
    vertical-align: middle;
}

.people-row-focus {
    background: rgba(var(--v-theme-highlight7), 0.12);
}
</style>
