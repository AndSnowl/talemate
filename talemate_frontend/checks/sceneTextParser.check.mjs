// Node-only checks for the renderer's name highlighting
// (SceneTextParser and compileEntityMentions in sceneMessageRenderer.js):
// word boundaries, Unicode names, escaping, overlaps, first occurrence
// only, the show switch and the compile cache. The name half of the old
// culturesStory check, kept when cultures were removed. No Vue, no test
// framework — run directly with `node checks/sceneTextParser.check.mjs`
// (see tests/dev/test_frontend_checks.py for the pytest wrapper).

import assert from 'node:assert/strict';

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

const place = (name, phrases = [name]) => ({ name, kind: 'place', phrases });
const highlights = (mentions, text, config) =>
    new SceneTextParser(config).parse(text, { mentions }).includes('scene-entity');

check('word_boundary', () => {
    const mentions = [place('Saervik')];
    // Inside a longer word, at either end, nothing is highlighted.
    for (const text of ['Saerviking roams the hills.', 'xSaervik roams the hills.']) {
        assert.ok(!highlights(mentions, text), text);
    }
    // The same name standing alone is highlighted, so the cases above can fail.
    assert.ok(highlights(mentions, 'Saervik roams the hills.'));
});

check('word_boundary_unicode', () => {
    const dhune = [place('Dhuné')];
    assert.ok(!highlights(dhune, 'They crossed into Dhunéra at dusk.'));
    assert.ok(highlights(dhune, 'Dhuné, they called it.'));

    const aerin = [place('Ærin')];
    assert.ok(!highlights(aerin, 'The Ærinvar woke.'));
    assert.ok(!highlights(aerin, 'The vÆrin woke.'));
    assert.ok(highlights(aerin, 'The Ærin woke.'));

    const veld = [place('Veld')];
    assert.ok(!highlights(veld, 'The Veldé woke.'));
    assert.ok(!highlights(veld, 'The éVeld woke.'));
});

check('apostrophes_and_hyphens', () => {
    const names = [
        { name: "Kel'dor", kind: 'character', phrases: ["Kel'dor", 'Kel’dor'] },
        place('Khaz-Rull'),
    ];
    const html = new SceneTextParser().parse(
        "Kel’dor rode for Khaz-Rull, and Kel'dor's horse tired.",
        { mentions: names },
    );
    assert.ok(html.includes('data-entity-name="Kel\'dor"'), html);
    assert.ok(html.includes('data-entity-name="Khaz-Rull"'), html);
    assert.ok(!highlights(names, 'Khaz-Rullan stands.'));
});

check('regex_characters_escaped', () => {
    // Every regex syntax character in a phrase is escaped validly for the
    // `u` flag, and the phrase matches literally.
    const odd = [{ name: 'odd', kind: 'item', phrases: ['a.b*c+d?e^f$g{h}i(j)k|l[m]n\\o-p/q\'r'] }];
    assert.ok(compileEntityMentions(odd).startRegex.flags.includes('u'));
    assert.ok(highlights(odd, 'See a.b*c+d?e^f$g{h}i(j)k|l[m]n\\o-p/q\'r here.'));
    assert.ok(!highlights(odd, 'See aXb here.'));
});

check('longest_phrase_wins', () => {
    const mentions = [place('Dhun'), place('Dhun Gate')];
    const html = new SceneTextParser().parse('They rode to Dhun Gate.', { mentions });
    assert.ok(html.includes('data-entity-name="Dhun Gate"'), html);
    assert.ok(!html.includes('data-entity-name="Dhun"'), html);
});

check('first_occurrence_only', () => {
    const html = new SceneTextParser().parse(
        'Veldhaer stands. Later, Veldhaer falls.',
        { mentions: [place('Veldhaer')] },
    );
    assert.equal((html.match(/class="scene-entity"/g) || []).length, 1, html);
});

check('show_false', () => {
    const mentions = [place('Veldhaer')];
    assert.ok(!highlights(mentions, 'Veldhaer stands.', { entities: { show: false } }));
    const html = new SceneTextParser({ entities: { show: false } })
        .parse('Veldhaer stands.', { mentions });
    assert.ok(html.includes('Veldhaer stands.'), html);
});

check('compile_cache', () => {
    const mentions = [place('Veldhaer')];
    assert.equal(compileEntityMentions(mentions), compileEntityMentions(mentions));
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
