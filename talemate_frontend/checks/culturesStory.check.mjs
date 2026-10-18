// Node-only checks for the pure cultures story logic (storyLexicon.js) and
// the renderer's `foreign` highlight kind. No Vue, no test framework — run
// directly with `node checks/culturesStory.check.mjs` (see
// tests/dev/test_frontend_checks.py for the pytest wrapper).

import assert from 'node:assert/strict';

import {
    FOREIGN_KIND,
    emptyStoryState,
    matchVariants,
    foreignMentions,
    nameKey,
    buildNameIndex,
    markUnreviewed,
    combineMentions,
    findLexiconEntry,
    applyCulturesMessage,
    nameSection,
} from '../src/components/cultures/storyLexicon.js';
import { SceneTextParser, compileEntityMentions } from '../src/utils/sceneMessageRenderer.js';

let passed = 0;
const failures = [];

function check(name, fn) {
    try {
        fn();
        passed += 1;
    } catch (err) {
        failures.push({ name, err });
    }
}

// Fixture: a stored curse phrase.
const curse = {
    id: 'phrase:taelrik:curse-rot',
    text: "Rhok tal'dun!",
    kind: 'curse',
    culture_id: 'taelrik',
    culture_name: 'Taelrik',
    language_name: 'Taelrik Tongue',
    color: '#ff0000',
    translation: 'may your roots rot',
    breakdown: [],
    usage: '',
    target: { type: 'phrase', culture_id: 'taelrik', phrase_id: 'curse-rot' },
};

check('variants', () => {
    assert.deepEqual(matchVariants("Rhok tal'dun!"), ["Rhok tal'dun", 'Rhok tal’dun']);
    assert.deepEqual(matchVariants('Rhok tal’dun'), ["Rhok tal'dun", 'Rhok tal’dun']);
    assert.deepEqual(matchVariants('  saervik '), ['saervik']);
    assert.equal(matchVariants("Dhun sa'ver, kaeth sa'ver.")[0], "Dhun sa'ver, kaeth sa'ver");
    assert.deepEqual(matchVariants('!!'), []);
});

check('case_and_quotes', () => {
    const parser = new SceneTextParser();
    const html = parser.parse('"rhok TAL’DUN," he said.', { mentions: foreignMentions([curse]) });
    assert.ok(html.includes('class="scene-foreign"'), html);
    assert.ok(html.includes('data-foreign-id="phrase:taelrik:curse-rot"'), html);
    assert.ok(html.includes('data-foreign-kind="curse"'), html);
    assert.ok(html.includes('font-style: italic'), html);
    const match = html.match(/<span class="scene-foreign"[^>]*>([^<]*)<\/span>/);
    assert.ok(match, 'expected a scene-foreign span');
    assert.equal(match[1], 'rhok TAL’DUN');
});

check('word_boundary', () => {
    const saervikMention = { name: 'word:saervik', kind: FOREIGN_KIND, subkind: 'word', phrases: ['saervik'] };
    const mentions = [saervikMention, ...foreignMentions([curse])];
    const parser = new SceneTextParser();
    const html = parser.parse("saerviking roams the hills. Rhokbert tal'dunny arrives.", { mentions });
    assert.ok(!html.includes('scene-foreign'), html);
});

check('overlap', () => {
    const dhunEntity = { name: 'Dhun', kind: 'place', phrases: ['Dhun'] };
    const dhunPhrase = {
        id: 'phrase:taelrik:dhun-greeting',
        text: "Dhun sa'ver, kaeth sa'ver.",
        kind: 'greeting',
    };
    const foreign = foreignMentions([dhunPhrase]);

    // R2: combineMentions(names, foreign) — names first, so a name wins on
    // equal text (checked below), and a future argument-order swap fails
    // this assertion first.
    const combined = combineMentions([dhunEntity], foreign);
    assert.deepEqual(combined.slice(0, 1), [dhunEntity]);
    assert.deepEqual(combined.slice(1), foreign);

    const parser = new SceneTextParser();
    const html = parser.parse('Dhun sa\'ver, kaeth sa\'ver. Later, Dhun again.', { mentions: combined });
    const foreignSpans = html.match(/<span class="scene-foreign"[^>]*>.*?<\/span>/g) || [];
    const entitySpans = html.match(/<span class="scene-entity"[^>]*>.*?<\/span>/g) || [];
    assert.equal(foreignSpans.length, 1, html);
    assert.equal(entitySpans.length, 1, html);
    assert.ok(html.indexOf(foreignSpans[0]) < html.indexOf(entitySpans[0]), html);
    assert.ok(!foreignSpans[0].includes('scene-entity'), foreignSpans[0]);

    // A name and a foreign entry with the same text: the name wins.
    const veldhaerEntity = { name: 'Veldhaer', kind: 'place', phrases: ['Veldhaer'] };
    const veldhaerWord = { id: 'word:taelrik:veldhaer', text: 'Veldhaer', kind: 'word' };
    const combined2 = combineMentions([veldhaerEntity], foreignMentions([veldhaerWord]));
    const html2 = parser.parse('Veldhaer stands at the gate.', { mentions: combined2 });
    assert.ok(html2.includes('scene-entity'), html2);
    assert.ok(!html2.includes('scene-foreign'), html2);
});

check('first_occurrence_only', () => {
    const parser = new SceneTextParser();
    const html = parser.parse("Rhok tal'dun! He said it again: Rhok tal'dun!", { mentions: foreignMentions([curse]) });
    const spans = html.match(/class="scene-foreign"/g) || [];
    assert.equal(spans.length, 1, html);
});

check('unreviewed', () => {
    const mentions = [{ name: 'Kethrun', kind: 'person', phrases: ['Kethrun'] }];
    const parser = new SceneTextParser();

    const unreviewedIndex = buildNameIndex([{ text: 'Kethrun', status: 'unreviewed' }]);
    const html1 = parser.parse('Kethrun arrives.', { mentions: markUnreviewed(mentions, unreviewedIndex) });
    assert.ok(html1.includes('data-entity-unreviewed="true"'), html1);

    const reviewedIndex = buildNameIndex([{ text: 'Kethrun', status: 'reviewed' }]);
    const html2 = parser.parse('Kethrun arrives.', { mentions: markUnreviewed(mentions, reviewedIndex) });
    assert.ok(!html2.includes('data-entity-unreviewed'), html2);
});

check('show_false', () => {
    const parser = new SceneTextParser({ entities: { show: false } });
    const html = parser.parse("Rhok tal'dun!", { mentions: foreignMentions([curse]) });
    assert.ok(!html.includes('scene-foreign'), html);
    assert.ok(html.includes("Rhok tal'dun"), html);
});

check('name_key_and_index', () => {
    assert.equal(nameKey('Tovrin’s'), 'tovrin');
    assert.equal(nameKey(' Kethrun. '), 'kethrun');

    const khazRull = {
        id: 'glossary:khaz-rull',
        text: 'Khazrul',
        status: 'reviewed',
        writable: false,
        renderings: [{ culture_id: 'taelrik', culture_name: 'Taelrik', text: 'Khaz-Rull' }],
        character_name: null,
    };
    const index = buildNameIndex([khazRull]);
    assert.equal(index.get(nameKey('Khaz-Rull')), khazRull);
});

check('compile_cache', () => {
    const arr = foreignMentions([curse]);
    assert.equal(compileEntityMentions(arr), compileEntityMentions(arr));
});

check('perf', () => {
    const many = [];
    for (let i = 0; i < 1500; i++) {
        many.push({ id: `word:zq${i}vek`, text: `zq${i}vek`, kind: 'word' });
    }
    const mentions = foreignMentions(many);
    const parser = new SceneTextParser();
    const text = 'The quick brown fox jumps over the lazy dog near the old stone bridge while the river hums softly and the wind sighs through the pines above the quiet, winding path that leads down toward the village gates where the watchmen'.slice(0, 400);
    const start = Date.now();
    for (let i = 0; i < 200; i++) {
        parser.parse(text, { mentions });
    }
    const elapsed = Date.now() - start;
    assert.ok(elapsed < 5000, `perf took ${elapsed}ms`);
});

check('ingest_resets_on_scene_loading', () => {
    const s = emptyStoryState();
    s.reviewSeq = 7;

    let result = applyCulturesMessage(s, { type: 'cultures', action: 'counts', data: { unreviewed_total: 3 } });
    assert.equal(result, null);
    assert.equal(s.counts.unreviewed_total, 3);

    result = applyCulturesMessage(s, { type: 'cultures', action: 'story', data: { available: true, lexicon: [curse] } });
    assert.equal(result, null);
    assert.equal(s.story.available, true);
    assert.deepEqual(s.story.lexicon, [curse]);

    result = applyCulturesMessage(s, { type: 'system', id: 'scene.loading' });
    assert.equal(result, null);
    assert.deepEqual(s.counts, {});
    assert.equal(s.story.available, false);
    assert.deepEqual(s.story.lexicon, []);
    assert.equal(s.pendingReview, null);
    assert.equal(s.reviewSeq, 7);

    result = applyCulturesMessage(s, { type: 'system', id: 'scene.loaded' });
    assert.deepEqual(result, { type: 'cultures', action: 'get_story' });

    result = applyCulturesMessage(s, { type: 'cultures', action: 'world', data: { counts: { unreviewed_total: 9 } } });
    assert.equal(result, null);
    assert.equal(s.counts.unreviewed_total, 9);
});

check('find_lexicon_entry', () => {
    const story = { lexicon: [curse] };
    assert.equal(findLexiconEntry(story, curse.id), curse);
    assert.equal(findLexiconEntry(story, 'nope'), null);
    assert.equal(findLexiconEntry({}, 'nope'), null);
});

// Fixtures: task 5's seed (tests/e2e/cultures/test_story.py's _seed_story),
// shaped as Task 2's NameInfo/CharacterInfo/PlaceInfo dumps.
const kethrunInfo = {
    id: 'g-kethrun',
    text: 'Kethrun',
    kind: 'person',
    status: 'unreviewed',
    culture_id: 'taelrik',
    culture_name: 'Taelrik',
    language_name: 'Taelrik',
    color: '#FF8A65',
    writable: true,
    meaning: 'ford-born',
    true_name: '',
    renderings: [],
    origin_by: 'ai',
    generator_name: 'Given names (male)',
    doesnt_fit: false,
    character_name: 'Kethrun',
    place_id: null,
};
const kethrunCharacter = {
    name: 'Kethrun',
    culture_id: 'taelrik',
    culture_name: 'Taelrik',
    color: '#FF8A65',
    set_by: 'ai',
    unsure: false,
    reason: 'picked from the Veldhaer mix',
};
const veldhaerInfo = {
    id: 'g-veldhaer',
    text: 'Veldhaer',
    kind: 'place',
    status: 'reviewed',
    culture_id: 'taelrik',
    culture_name: 'Taelrik',
    language_name: 'Taelrik',
    color: '#FF8A65',
    writable: true,
    meaning: 'grey ford',
    true_name: '',
    renderings: [],
    origin_by: 'import',
    generator_name: null,
    doesnt_fit: false,
    character_name: null,
    place_id: 'veldhaer',
};
const veldhaerPlace = {
    id: 'veldhaer',
    name: 'Veldhaer',
    kind: 'town',
    own: false,
    source_name: 'The Taelrik Reach',
    mix: [{ culture_id: 'taelrik', culture_name: 'Taelrik', color: '#FF8A65', share: 100 }],
    set_by: 'ai',
    unsure: false,
};
const khazRullInfo = {
    id: 'g-khaz',
    text: 'Khaz-Rull',
    kind: 'place',
    status: 'reviewed',
    culture_id: 'ghun',
    culture_name: 'Ghûn',
    language_name: 'Ghûn',
    color: '#B0BEC5',
    writable: false,
    meaning: '',
    true_name: 'three falling hums ending in a tongue-click',
    renderings: [{ culture_id: 'taelrik', culture_name: 'Taelrik', text: 'Khaz-Rull' }],
    origin_by: 'import',
    generator_name: null,
    doesnt_fit: false,
    character_name: null,
    place_id: 'khaz',
};
const quillisterInfo = {
    id: 'g-quillister',
    text: 'Quillister House',
    kind: 'place',
    status: 'unreviewed',
    culture_id: null,
    culture_name: null,
    language_name: null,
    color: null,
    writable: true,
    meaning: '',
    true_name: '',
    renderings: [],
    origin_by: 'ai_free',
    generator_name: null,
    doesnt_fit: false,
    character_name: null,
    place_id: 'quillister',
};

const storyFixture = {
    names: [kethrunInfo, veldhaerInfo, khazRullInfo, quillisterInfo],
    characters: [kethrunCharacter],
    places: [veldhaerPlace],
};

check('name_section_character', () => {
    const section = nameSection(storyFixture, { name: 'Kethrun', kind: 'character' });
    assert.equal(section.culture.note, 'Worked out by the AI · picked from the Veldhaer mix');
    assert.equal(section.review.note, 'Added by the AI, not reviewed yet. Picked from Given names (male).');
    assert.deepEqual(section.review.target, { type: 'glossary', entry_id: 'g-kethrun' });
});

check('name_section_place_inherited', () => {
    const section = nameSection(storyFixture, { name: 'Veldhaer', kind: 'place' });
    assert.equal(section.culture.note, 'From The Taelrik Reach');
    assert.deepEqual(section.culture.chips, [{ name: 'Taelrik', color: '#FF8A65', share: 100 }]);
    assert.equal(section.review, null);
});

check('name_section_unwritable', () => {
    const section = nameSection(storyFixture, { name: 'Khaz-Rull', kind: 'place' });
    assert.equal(section.trueName.text, 'three falling hums ending in a tongue-click');
    assert.equal(section.trueName.renderings[0].text, 'Khaz-Rull');
});

check('name_section_unassigned', () => {
    const section = nameSection(storyFixture, { name: 'Quillister House', kind: 'place' });
    assert.equal(section.language, null);
    assert.equal(section.languageNote, 'invented freely by the AI');
    assert.equal(section.review.note, 'Added by the AI, not reviewed yet.');
});

check('name_section_none', () => {
    const section = nameSection(storyFixture, { name: 'A Rusty Lantern', kind: 'item' });
    assert.equal(section, null);
});

if (failures.length > 0) {
    for (const { name, err } of failures) {
        console.error(`FAIL ${name}`);
        console.error(err && err.stack ? err.stack : err);
    }
    process.exit(1);
} else {
    console.log(`ok ${passed} checks`);
    process.exit(0);
}
