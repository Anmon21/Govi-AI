// Covers: CORE-01 — GET_STARTED postback handler
//         CORE-03 — Quick reply attachment on sendWelcomeMessage
//         CORE-04 — Free-text fallback handler; quick_reply tap does NOT trigger fallback
// Plan 03 will export handleWebhookEvent, sendWelcomeMessage, sendFallbackMessage from ../index.

import { test } from "node:test";
import assert from "node:assert/strict";
// Type-only side-effect import — Plan 03 will add handler exports here
import type {} from "../index";

// Wave-0: these handlers are not yet exported from ../index.
// Tests skip gracefully until Plan 03 lands.
// Set PORT=0 so index.ts binds to an OS-assigned port rather than conflicting with port 3000.
process.env.PORT = "0";

type EventFn = (event: any) => Promise<void>;
type SendFn = (recipientId: string) => Promise<void>;

let handleWebhookEvent: EventFn | undefined;
let sendWelcomeMessage: SendFn | undefined;
let sendFallbackMessage: SendFn | undefined;

try {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const mod = require("../index");
  handleWebhookEvent = typeof mod.handleWebhookEvent === "function" ? mod.handleWebhookEvent as EventFn : undefined;
  sendWelcomeMessage = typeof mod.sendWelcomeMessage === "function" ? mod.sendWelcomeMessage as SendFn : undefined;
  sendFallbackMessage = typeof mod.sendFallbackMessage === "function" ? mod.sendFallbackMessage as SendFn : undefined;
} catch {
  handleWebhookEvent = undefined;
  sendWelcomeMessage = undefined;
  sendFallbackMessage = undefined;
}

test("handleWebhookEvent: GET_STARTED postback invokes sendWelcomeMessage", async (t) => {
  if (!handleWebhookEvent) {
    t.skip("pending Plan 03 implementation");
    return;
  }

  // Mock axios so sendMessage does not make real HTTP calls
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const axios = require("axios");
  const originalPost = axios.post;
  const calls: { recipientId: string; body: any }[] = [];
  axios.post = async (_url: string, body: any) => {
    calls.push({ recipientId: body?.recipient?.id, body });
    return { data: {} };
  };

  try {
    await handleWebhookEvent({ postback: { payload: "GET_STARTED" }, sender: { id: "USR_1" } });
    assert.ok(calls.length >= 1, "sendMessage should be called at least once");
    assert.strictEqual(calls[0].recipientId, "USR_1", "should send to the correct recipient");
    // CORE-03: quick_replies must be present (length >= 1)
    const quickReplies = calls[0].body?.message?.quick_replies;
    assert.ok(Array.isArray(quickReplies) && quickReplies.length >= 1,
      "sendWelcomeMessage should attach quick_replies");
  } finally {
    axios.post = originalPost;
  }
});

test("sendWelcomeMessage call includes quick_replies in payload", async (t) => {
  if (!sendWelcomeMessage) {
    t.skip("pending Plan 03 implementation");
    return;
  }

  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const axios = require("axios");
  const originalPost = axios.post;
  const calls: any[] = [];
  axios.post = async (_url: string, body: any) => {
    calls.push(body);
    return { data: {} };
  };

  try {
    await sendWelcomeMessage("USR_1");
    assert.ok(calls.length >= 1, "axios.post should be called");
    const quickReplies = calls[0]?.message?.quick_replies;
    assert.ok(Array.isArray(quickReplies) && quickReplies.length >= 1,
      "quick_replies should be present");
    assert.strictEqual(quickReplies[0].content_type, "text",
      'quick_reply content_type should be "text"');
  } finally {
    axios.post = originalPost;
  }
});

test("handleWebhookEvent: free text triggers sendFallbackMessage", async (t) => {
  if (!handleWebhookEvent) {
    t.skip("pending Plan 03 implementation");
    return;
  }

  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const axios = require("axios");
  const originalPost = axios.post;
  const calls: { recipientId: string; body: any }[] = [];
  axios.post = async (_url: string, body: any) => {
    calls.push({ recipientId: body?.recipient?.id, body });
    return { data: {} };
  };

  try {
    await handleWebhookEvent({ message: { text: "hi" }, sender: { id: "USR_1" } });
    assert.ok(calls.length >= 1, "sendFallbackMessage should trigger a sendMessage call");
    assert.strictEqual(calls[0].recipientId, "USR_1", "fallback should send to the correct recipient");
  } finally {
    axios.post = originalPost;
  }
});

test("handleWebhookEvent: quick_reply tap does NOT trigger fallback", async (t) => {
  if (!handleWebhookEvent) {
    t.skip("pending Plan 03 implementation");
    return;
  }

  // PITFALLS.md pitfall 6: quick_reply dispatch must check quick_reply BEFORE text
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const axios = require("axios");
  const originalPost = axios.post;
  const originalGet = axios.get;
  const postCalls: any[] = [];
  // Stub axios.get so sendCategoryMenu succeeds without a real HTTP call (Phase 3)
  axios.get = async (_url: string) => ({ data: { items: [
    { id: "cat-products", type: "category", title: "Products" },
  ]}});
  axios.post = async (_url: string, body: any) => {
    postCalls.push(body);
    return { data: {} };
  };

  try {
    await handleWebhookEvent({
      message: { quick_reply: { payload: "MENU_PRODUCT_HELP" }, text: "Product Help" },
      sender: { id: "USR_1" },
    });
    // sendFallbackMessage must NOT be called; MENU_PRODUCT_HELP routes to sendCategoryMenu
    // Phase 3: one sendMessage (category menu) is expected — but fallback text must NOT appear
    const fallbackCalls = postCalls.filter(
      (b) => b?.message?.text?.includes("I work best with the buttons below")
    );
    assert.strictEqual(fallbackCalls.length, 0,
      "Quick reply tap should NOT trigger sendFallbackMessage");
  } finally {
    axios.post = originalPost;
    axios.get = originalGet;
  }
});
