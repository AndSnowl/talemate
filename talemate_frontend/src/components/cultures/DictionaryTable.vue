<template>
    <div class="dictionary-table">
        <div class="d-flex align-center flex-wrap ga-2 mb-3">
            <span class="text-muted text-caption">
                {{ local.dictionary.length }} words · showing {{ filteredRows.length }}
            </span>
            <v-spacer></v-spacer>
            <v-text-field
                v-model="search"
                density="compact"
                variant="outlined"
                hide-details
                clearable
                prepend-inner-icon="mdi-magnify"
                placeholder="Word or meaning"
                style="max-width: 280px"
                class="flex-grow-0"
            ></v-text-field>
        </div>

        <v-table density="compact">
            <thead>
                <tr>
                    <th>Word</th>
                    <th>Meaning</th>
                    <th>Part</th>
                    <th></th>
                </tr>
            </thead>
            <tbody>
                <tr v-for="row in filteredRows" :key="row._i">
                    <td style="min-width: 140px">
                        <v-text-field
                            v-model="local.dictionary[row._i].word"
                            density="compact"
                            variant="plain"
                            hide-details
                            class="font-italic text-highlight7"
                            @blur="save()"
                        ></v-text-field>
                    </td>
                    <td style="min-width: 220px">
                        <v-text-field
                            v-model="local.dictionary[row._i].meaning"
                            density="compact"
                            variant="plain"
                            hide-details
                            @blur="save()"
                        ></v-text-field>
                    </td>
                    <td style="min-width: 100px">
                        <v-text-field
                            v-model="local.dictionary[row._i].part"
                            density="compact"
                            variant="plain"
                            hide-details
                            @blur="save()"
                        ></v-text-field>
                    </td>
                    <td class="text-right">
                        <v-btn icon size="small" variant="text" @click="removeWord(row._i)">
                            <v-icon size="small" color="delete">mdi-close</v-icon>
                        </v-btn>
                    </td>
                </tr>
                <tr v-if="filteredRows.length === 0">
                    <td colspan="4" class="text-center text-muted">No words found.</td>
                </tr>
            </tbody>
        </v-table>

        <v-btn variant="text" size="small" prepend-icon="mdi-plus" class="mt-2" @click="addWord()">
            Add word
        </v-btn>
    </div>
</template>

<script>
import { dirtyLocalClone } from './dirtyLocalClone';

export default {
    name: 'DictionaryTable',
    mixins: [
        dirtyLocalClone({
            watchPath: 'culture',
            // Only `language.dictionary`: saves patch just that field.
            source: vm => ({ dictionary: vm.culture.language.dictionary }),
            identity: vm => vm.culture && vm.culture.id,
        }),
    ],
    props: {
        culture: {
            type: Object,
            required: true,
        },
        send: {
            type: Function,
            required: true,
        },
    },
    data() {
        return {
            search: '',
        }
    },
    computed: {
        filteredRows() {
            const q = (this.search || '').toLowerCase();
            return this.local.dictionary
                .map((entry, i) => ({ ...entry, _i: i }))
                .filter(row => !q || `${row.word} ${row.meaning} ${row.part}`.toLowerCase().includes(q));
        },
    },
    methods: {
        save() {
            this.send('patch_culture', { culture_id: this.culture.id, language: { dictionary: this.local.dictionary } });
            this.clearLocalDirty();
        },
        addWord() {
            this.local.dictionary.push({ word: '', meaning: '', part: '', notes: '' });
        },
        removeWord(i) {
            this.local.dictionary.splice(i, 1);
            this.save();
        },
    },
}
</script>
