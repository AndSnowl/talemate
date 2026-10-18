// Shared reactive state for the Cultures-in-the-story feature: the small
// piece of app-wide state the scene renderer (foreign-word highlights),
// the app-level World Editor badge and the Cultures tab all read from.
//
// A single module-level `reactive()` instance, so every consumer (the
// entity-highlight mixin, TalemateApp's tab badge, WorldStateManager's
// Cultures tab badge) shares the same live object without prop-drilling
// or an event bus.

import { reactive } from 'vue';
import { emptyStoryState, applyCulturesMessage } from './storyLexicon.js';

export const culturesStory = reactive(emptyStoryState());

// Fold one `cultures`/`system` websocket message into `culturesStory`, and
// `send` the follow-up payload `applyCulturesMessage` returns, if any
// (e.g. a `get_story` request after the scene finishes loading).
//
// `handleMessage` is the app's only websocket dispatcher, so this can never
// throw out to it — an unexpected payload shape is logged and swallowed
// instead of breaking every other message handler on the same event.
export function ingestCulturesMessage(data, send) {
    try {
        const payload = applyCulturesMessage(culturesStory, data);
        if (payload) {
            send(payload);
        }
    } catch (e) {
        console.error('ingestCulturesMessage failed', e);
    }
}

// Request that the Cultures tab (once opened) jump to `target` — consumed
// by `takePendingReview()`.
export function requestReview(target) {
    culturesStory.pendingReview = target;
    culturesStory.reviewSeq += 1;
}

// Return the pending review target, clearing it, or `null` when there is
// none.
export function takePendingReview() {
    const target = culturesStory.pendingReview;
    culturesStory.pendingReview = null;
    return target ?? null;
}
