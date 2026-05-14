// Covers: CORE-02 — Messenger profile setup (get_started + persistent_menu)
// Plan 03 will export setupMessengerProfile from ../index and make this test green.

import { test } from "node:test";
import assert from "node:assert/strict";
// Type-only side-effect import — Plan 03 will add setupMessengerProfile export here
import type {} from "../index";

// Wave-0: setupMessengerProfile is not yet exported from ../index.
// Test skips gracefully until Plan 03 lands.
// Set PORT=0 so index.ts binds to an OS-assigned port rather than conflicting with port 3000.
process.env.PORT = "0";

type SetupFn = () => Promise<void>;
let setupMessengerProfile: SetupFn | undefined;
try {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const mod = require("../index");
  setupMessengerProfile = typeof mod.setupMessengerProfile === "function" ? mod.setupMessengerProfile as SetupFn : undefined;
} catch {
  setupMessengerProfile = undefined;
}

test("setupMessengerProfile posts get_started + persistent_menu to /me/messenger_profile", async (t) => {
  if (!setupMessengerProfile) {
    t.skip("pending Plan 03 implementation");
    return;
  }

  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const axios = require("axios");
  const originalPost = axios.post;
  const calls: { url: string; body: any }[] = [];
  axios.post = async (url: string, body: any) => {
    calls.push({ url, body });
    return { data: { result: "success" } };
  };

  try {
    await setupMessengerProfile();

    assert.ok(calls.length >= 1, "axios.post should be called at least once");
    const [call] = calls;

    // URL assertions — CORE-02
    assert.ok(
      call.url.includes("graph.facebook.com/v21.0"),
      `URL should use graph.facebook.com/v21.0; got: ${call.url}`
    );
    assert.ok(
      call.url.endsWith("/me/messenger_profile"),
      `URL should end with /me/messenger_profile; got: ${call.url}`
    );

    // get_started assertion
    assert.strictEqual(
      call.body?.get_started?.payload,
      "GET_STARTED",
      'get_started.payload should be "GET_STARTED"'
    );

    // persistent_menu assertions
    const menu = call.body?.persistent_menu;
    assert.ok(Array.isArray(menu) && menu.length >= 1, "persistent_menu should be a non-empty array");
    const actions = menu[0]?.call_to_actions;
    assert.ok(
      Array.isArray(actions) && actions.length >= 1 && actions.length <= 3,
      `call_to_actions length should be 1-3 (CORE-02 max-3 constraint); got: ${actions?.length}`
    );

    // Title length constraint — RESEARCH.md A2 conservative safe limit (≤20 chars)
    for (const action of actions) {
      assert.ok(
        typeof action.title === "string" && action.title.length <= 20,
        `Menu item title "${action.title}" exceeds 20-character limit`
      );
    }
  } finally {
    axios.post = originalPost;
  }
});
