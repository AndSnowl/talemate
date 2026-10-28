// Node-only checks for the right-click naming menu's pure helpers
// (src/components/worlds/languageMenu.js, languages 3a). Run directly with
// `node checks/languageMenu.check.mjs` (tests/dev/test_frontend_checks.py
// wraps it).

import assert from 'node:assert/strict';

import {
    defaultLanguageId,
    menuLanguages,
    replaceSelection,
    savedRow,
} from '../src/components/worlds/languageMenu.js';

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

check('replace_selection_keeps_the_rest', () => {
    assert.equal(replaceSelection('Free Provinces of Sorau', [18, 23], 'Velka'), 'Free Provinces of Velka');
    assert.equal(replaceSelection('Tsardom of ', [11, 11], 'Moscavia'), 'Tsardom of Moscavia');
});

check('default_language_prefers_official_then_largest_share', () => {
    const rows = [
        { language_id: 'a', role: 'spoken', share: 25 },
        { language_id: 'b', role: 'official', share: null },
    ];
    assert.equal(defaultLanguageId(rows), 'b');
    assert.equal(defaultLanguageId([{ language_id: 'a', role: 'spoken', share: 25 }, { language_id: 'c', role: 'spoken', share: 70 }]), 'c');
    assert.equal(defaultLanguageId([]), null);
});

check('menu_languages_put_the_ones_in_reach_first', () => {
    const menu = {
        rows: [{ language_id: 'b', name: 'Sorauan', role: 'official' }],
        languages: [{ id: 'a', name: 'Moscavian' }, { id: 'b', name: 'Sorauan' }],
    };
    assert.deepEqual(menuLanguages(menu).map((l) => [l.id, l.inReach]), [['b', true], ['a', false]]);
});

check('saved_row_is_a_spoken_row', () => {
    assert.deepEqual(savedRow('a'), { language: 'a', role: 'spoken' });
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
