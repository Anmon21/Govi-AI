// Covers: UX-04 — answer truncation preview with [Read more] quick reply
//         UX-05 — [Read more] tap re-fetches full answer with FEEDBACK_QUICK_REPLIES

import { test } from "node:test";
import assert from "node:assert/strict";
import type {} from "../index";

process.env.FACEBOOK_VERIFY_TOKEN = "test-token";
process.env.PORT = "0";

type EventFn = (event: any) => Promise<void>;
type SendAnswerFn = (recipientId: string, questionId: string) => Promise<void>;
type SendReadMoreAnswerFn = (recipientId: string, questionId: string) => Promise<void>;

let handleWebhookEvent: EventFn | undefined;
let sendAnswer: SendAnswerFn | undefined;
let sendReadMoreAnswer: SendReadMoreAnswerFn | undefined;
let FEEDBACK_QUICK_REPLIES: any[] | undefined;
let MAIN_MENU_QUICK_REPLIES: any[] | undefined;
let PAYLOAD_PREFIX_READ_MORE: string | undefined;
let _readMoreExported = false;

try {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const mod = require("../index");
  handleWebhookEvent = typeof mod.handleWebhookEvent === "function" ? mod.handleWebhookEvent as EventFn : undefined;
  sendAnswer = typeof mod.sendAnswer === "function" ? mod.sendAnswer as SendAnswerFn : undefined;
  sendReadMoreAnswer = typeof mod.sendReadMoreAnswer === "function" ? mod.sendReadMoreAnswer as SendReadMoreAnswerFn : undefined;
  FEEDBACK_QUICK_REPLIES = Array.isArray(mod.FEEDBACK_QUICK_REPLIES) ? mod.FEEDBACK_QUICK_REPLIES : undefined;
  MAIN_MENU_QUICK_REPLIES = Array.isArray(mod.MAIN_MENU_QUICK_REPLIES) ? mod.MAIN_MENU_QUICK_REPLIES : undefined;
  PAYLOAD_PREFIX_READ_MORE = typeof mod.PAYLOAD_PREFIX_READ_MORE === "string" ? mod.PAYLOAD_PREFIX_READ_MORE : undefined;
  _readMoreExported = typeof mod.PAYLOAD_PREFIX_READ_MORE === "string";
} catch {
  handleWebhookEvent = undefined;
  sendAnswer = undefined;
  sendReadMoreAnswer = undefined;
  FEEDBACK_QUICK_REPLIES = undefined;
  MAIN_MENU_QUICK_REPLIES = undefined;
  PAYLOAD_PREFIX_READ_MORE = undefined;
  _readMoreExported = false;
}

function withAxiosStubs(opts: { onGet?: (url: string) => any; onPost?: (url: string, body: any) => any }) {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const axios = require("axios");
  const originalPost = axios.post;
  const originalGet = axios.get;
  const getCalls: { url: string }[] = [];
  const postCalls: { url: string; body: any }[] = [];
  axios.get = async (url: string) => {
    getCalls.push({ url });
    if (opts.onGet) return opts.onGet(url);
    return { data: {} };
  };
  axios.post = async (url: string, body: any) => {
    postCalls.push({ url, body });
    if (opts.onPost) return opts.onPost(url, body);
    return { data: {} };
  };
  return {
    getCalls,
    postCalls,
    restore() { axios.post = originalPost; axios.get = originalGet; },
  };
}

test("UX-04: sendAnswer body exactly 200 chars sends as-is with FEEDBACK_QUICK_REPLIES", async (t) => {
  if (!sendAnswer || !sendReadMoreAnswer || !_readMoreExported) { t.skip("pending Phase 8 implementation"); return; }
  const exactBody = "A".repeat(200);
  const stubs = withAxiosStubs({
    onGet: (url) => {
      if (url.includes("/content/q1")) return { data: { body: exactBody } };
      return { data: {} };
    },
  });
  try {
    await sendAnswer!("USR_1", "q1");
    // postCalls[0] = typing_on, postCalls[1] = message, postCalls[2] = typing_off
    assert.strictEqual(stubs.postCalls[1].body.message.text, exactBody,
      "body of exactly 200 chars must be sent as-is");
    assert.deepStrictEqual(stubs.postCalls[1].body.message.quick_replies, FEEDBACK_QUICK_REPLIES,
      "FEEDBACK_QUICK_REPLIES must be attached when body is exactly 200 chars");
    assert.ok(!exactBody.endsWith("..."), "200-char body must NOT be truncated");
  } finally { stubs.restore(); }
});

test("UX-04: sendAnswer body 250 chars sends truncated preview with single [Read more] quick reply", async (t) => {
  if (!sendAnswer || !sendReadMoreAnswer || !_readMoreExported) { t.skip("pending Phase 8 implementation"); return; }
  // Build a word-spaced string so lastIndexOf(" ", 200) finds a space boundary
  const longBody = "The quick brown fox jumps over the lazy dog. ".repeat(8).slice(0, 250);
  const stubs = withAxiosStubs({
    onGet: (url) => {
      if (url.includes("/content/q1")) return { data: { body: longBody } };
      return { data: {} };
    },
  });
  try {
    await sendAnswer!("USR_1", "q1");
    const msgCall = stubs.postCalls[1];
    const sentText: string = msgCall.body.message.text;
    assert.ok(sentText.endsWith("..."), "truncated preview must end with '...'");
    assert.strictEqual(msgCall.body.message.quick_replies.length, 1,
      "truncated preview must carry exactly 1 quick reply");
    assert.strictEqual(msgCall.body.message.quick_replies[0].title, "Read more",
      "quick reply title must be 'Read more'");
    assert.strictEqual(msgCall.body.message.quick_replies[0].payload, "READ_MORE:q1",
      "quick reply payload must be 'READ_MORE:q1'");
  } finally { stubs.restore(); }
});

test("UX-04: sendAnswer truncation cuts at last word boundary before 200 chars", async (t) => {
  if (!sendAnswer || !sendReadMoreAnswer || !_readMoreExported) { t.skip("pending Phase 8 implementation"); return; }
  const longBody = "The quick brown fox jumps over the lazy dog. ".repeat(8).slice(0, 250);
  const expectedCutIndex = longBody.lastIndexOf(" ", 200);
  const expectedPreview = longBody.slice(0, expectedCutIndex) + "...";
  const stubs = withAxiosStubs({
    onGet: (url) => {
      if (url.includes("/content/q1")) return { data: { body: longBody } };
      return { data: {} };
    },
  });
  try {
    await sendAnswer!("USR_1", "q1");
    const sentText: string = stubs.postCalls[1].body.message.text;
    assert.strictEqual(sentText, expectedPreview,
      "preview must cut at last word boundary before index 200");
  } finally { stubs.restore(); }
});

test("UX-04: sendAnswer body with no space before index 200 hard-cuts at 200", async (t) => {
  if (!sendAnswer || !sendReadMoreAnswer || !_readMoreExported) { t.skip("pending Phase 8 implementation"); return; }
  const noSpaceBody = "A".repeat(201);
  const expectedPreview = "A".repeat(200) + "...";
  const stubs = withAxiosStubs({
    onGet: (url) => {
      if (url.includes("/content/q1")) return { data: { body: noSpaceBody } };
      return { data: {} };
    },
  });
  try {
    await sendAnswer!("USR_1", "q1");
    const sentText: string = stubs.postCalls[1].body.message.text;
    assert.strictEqual(sentText, expectedPreview,
      "when no space before index 200, must hard-cut at exactly 200 chars and append '...'");
  } finally { stubs.restore(); }
});

test("UX-05: READ_MORE:q1 quick reply tap calls vault GET and posts full body with FEEDBACK_QUICK_REPLIES", async (t) => {
  if (!handleWebhookEvent || !_readMoreExported) { t.skip("pending Phase 8 implementation"); return; }
  const fullBody = "FULL ANSWER TEXT";
  const stubs = withAxiosStubs({
    onGet: (url) => {
      if (url.includes("/content/q1")) return { data: { body: fullBody } };
      return { data: {} };
    },
  });
  try {
    await handleWebhookEvent!({
      message: { quick_reply: { payload: "READ_MORE:q1" }, text: "x" },
      sender: { id: "USR_1" },
    });
    // postCalls[0] = typing_on, postCalls[1] = full answer message, postCalls[2] = typing_off
    assert.strictEqual(stubs.postCalls[1].body.message.text, fullBody,
      "full body must be sent after Read more tap");
    assert.deepStrictEqual(stubs.postCalls[1].body.message.quick_replies, FEEDBACK_QUICK_REPLIES,
      "FEEDBACK_QUICK_REPLIES must be attached to full answer message");
    const hasVaultGet = stubs.getCalls.some((c) => c.url.includes("/content/q1"));
    assert.ok(hasVaultGet, "sendReadMoreAnswer must call vault GET /content/q1");
  } finally { stubs.restore(); }
});

test("UX-05: sendReadMoreAnswer re-fetch failure calls sendApologyWithMenu", async (t) => {
  if (!sendAnswer || !sendReadMoreAnswer || !_readMoreExported) { t.skip("pending Phase 8 implementation"); return; }
  const stubs = withAxiosStubs({
    onGet: async () => { throw new Error("ECONNREFUSED"); },
  });
  const originalError = console.error;
  console.error = () => {};
  try {
    await sendReadMoreAnswer!("USR_1", "q1");
    // postCalls: typing_on (0), apology (1), typing_off (2)
    assert.strictEqual(stubs.postCalls.length, 3,
      "sendReadMoreAnswer error path must produce typing_on + apology + typing_off (3 calls)");
    assert.deepStrictEqual(stubs.postCalls[1].body.message.quick_replies, MAIN_MENU_QUICK_REPLIES,
      "apology must carry MAIN_MENU_QUICK_REPLIES");
  } finally {
    stubs.restore();
    console.error = originalError;
  }
});

test("UX-04 regression: sendAnswer empty body response calls sendApologyWithMenu", async (t) => {
  if (!sendAnswer || !sendReadMoreAnswer || !_readMoreExported) { t.skip("pending Phase 8 implementation"); return; }
  const stubs = withAxiosStubs({
    onGet: (url) => {
      if (url.includes("/content/q1")) return { data: { body: "" } };
      return { data: {} };
    },
  });
  try {
    await sendAnswer!("USR_1", "q1");
    // postCalls[0] = typing_on, postCalls[1] = apology, postCalls[2] = typing_off
    assert.deepStrictEqual(stubs.postCalls[1].body.message.quick_replies, MAIN_MENU_QUICK_REPLIES,
      "empty body must trigger apology with MAIN_MENU_QUICK_REPLIES — no truncation");
  } finally { stubs.restore(); }
});

test("UX-04 regression: sendAnswer axios.get throws calls sendApologyWithMenu", async (t) => {
  if (!sendAnswer || !sendReadMoreAnswer || !_readMoreExported) { t.skip("pending Phase 8 implementation"); return; }
  const stubs = withAxiosStubs({
    onGet: async () => { throw new Error("ECONNREFUSED"); },
  });
  const originalError = console.error;
  console.error = () => {};
  try {
    await sendAnswer!("USR_1", "q1");
    // postCalls[0] = typing_on, postCalls[1] = apology, postCalls[2] = typing_off
    assert.deepStrictEqual(stubs.postCalls[1].body.message.quick_replies, MAIN_MENU_QUICK_REPLIES,
      "fetch error must trigger apology with MAIN_MENU_QUICK_REPLIES — no truncation");
  } finally {
    stubs.restore();
    console.error = originalError;
  }
});

test("UX-04 regression: READ_MORE: payload with empty questionId falls through to sendFallbackMessage", async (t) => {
  if (!handleWebhookEvent || !_readMoreExported) { t.skip("pending Phase 8 implementation"); return; }
  const stubs = withAxiosStubs({});
  try {
    await handleWebhookEvent!({
      message: { quick_reply: { payload: "READ_MORE:" }, text: "x" },
      sender: { id: "USR_1" },
    });
    // sendFallbackMessage fires — no vault GET call
    const hasVaultGet = stubs.getCalls.some((c) => c.url.includes("/content/"));
    assert.ok(!hasVaultGet, "empty questionId must NOT trigger a vault GET call");
    assert.strictEqual(stubs.postCalls.length, 1, "exactly 1 postCall for fallback message");
    assert.ok(
      typeof stubs.postCalls[0].body.message.text === "string" &&
      stubs.postCalls[0].body.message.text.includes("buttons below"),
      "sendFallbackMessage text must include 'buttons below'"
    );
  } finally { stubs.restore(); }
});
