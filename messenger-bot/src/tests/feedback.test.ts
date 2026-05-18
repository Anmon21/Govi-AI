// Covers: UX-01 — FEEDBACK_QUICK_REPLIES attached after every Q&A answer
//         UX-02 — HELPFUL_YES quick reply sends thank-you with MAIN_MENU_QUICK_REPLIES
//         UX-03 — HELPFUL_NO quick reply enters escalation flow

import { test } from "node:test";
import assert from "node:assert/strict";
import type {} from "../index";

process.env.FACEBOOK_VERIFY_TOKEN = "test-token";
process.env.PORT = "0";

type EventFn = (event: any) => Promise<void>;

let handleWebhookEvent: EventFn | undefined;
let FEEDBACK_QUICK_REPLIES: any[] | undefined;
let MAIN_MENU_QUICK_REPLIES: any[] | undefined;
let _feedbackExported = false;

try {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const mod = require("../index");
  handleWebhookEvent = typeof mod.handleWebhookEvent === "function" ? mod.handleWebhookEvent as EventFn : undefined;
  FEEDBACK_QUICK_REPLIES = Array.isArray(mod.FEEDBACK_QUICK_REPLIES) ? mod.FEEDBACK_QUICK_REPLIES : undefined;
  MAIN_MENU_QUICK_REPLIES = Array.isArray(mod.MAIN_MENU_QUICK_REPLIES) ? mod.MAIN_MENU_QUICK_REPLIES : undefined;
  _feedbackExported = Array.isArray(mod.FEEDBACK_QUICK_REPLIES);
} catch {
  handleWebhookEvent = undefined;
  FEEDBACK_QUICK_REPLIES = undefined;
  MAIN_MENU_QUICK_REPLIES = undefined;
  _feedbackExported = false;
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

test("UX-01: sendAnswer attaches FEEDBACK_QUICK_REPLIES on success", async (t) => {
  if (!handleWebhookEvent || !_feedbackExported) { t.skip("pending Phase 7 implementation"); return; }
  const stubs = withAxiosStubs({
    onGet: (url) => {
      if (url.includes("/content/q-shipping-01")) {
        return { data: { body: "ANSWER_TEXT" } };
      }
      return { data: {} };
    },
  });
  try {
    await handleWebhookEvent!({
      message: { quick_reply: { payload: "QUESTION:q-shipping-01" }, text: "Shipping time?" },
      sender: { id: "USR_1" },
    });
    // typing_on (postCalls[0]), sendMessage (postCalls[1]), typing_off (postCalls[2])
    assert.strictEqual(stubs.postCalls.length, 3, "typing_on + sendMessage + typing_off for answer delivery");
    assert.deepStrictEqual(stubs.postCalls[1].body.message.quick_replies, FEEDBACK_QUICK_REPLIES,
      "sendAnswer must attach FEEDBACK_QUICK_REPLIES on success");
  } finally { stubs.restore(); }
});

test("UX-01 regression: sendAnswer error path still uses MAIN_MENU_QUICK_REPLIES (apology)", async (t) => {
  if (!handleWebhookEvent || !_feedbackExported) { t.skip("pending Phase 7 implementation"); return; }
  const stubs = withAxiosStubs({
    onGet: async () => { throw new Error("ECONNREFUSED"); },
  });
  const originalError = console.error;
  console.error = () => {};
  try {
    await handleWebhookEvent!({
      message: { quick_reply: { payload: "QUESTION:q-shipping-01" }, text: "Shipping time?" },
      sender: { id: "USR_1" },
    });
    // typing_on (postCalls[0]), apology (postCalls[1]), typing_off (postCalls[2])
    assert.strictEqual(stubs.postCalls.length, 3, "typing_on + apology + typing_off on error");
    assert.deepStrictEqual(stubs.postCalls[1].body.message.quick_replies, MAIN_MENU_QUICK_REPLIES,
      "apology path must still use MAIN_MENU_QUICK_REPLIES — must not change");
  } finally {
    stubs.restore();
    console.error = originalError;
  }
});

test("UX-02: HELPFUL_YES quick reply sends thank-you with MAIN_MENU_QUICK_REPLIES", async (t) => {
  if (!handleWebhookEvent || !_feedbackExported) { t.skip("pending Phase 7 implementation"); return; }
  const stubs = withAxiosStubs({});
  try {
    await handleWebhookEvent!({
      message: { quick_reply: { payload: "HELPFUL_YES" }, text: "Was it helpful? Yes" },
      sender: { id: "USR_X" },
    });
    assert.strictEqual(stubs.postCalls.length, 1, "exactly 1 postCall for HELPFUL_YES");
    assert.strictEqual(stubs.postCalls[0].body.message.text,
      "Glad that helped! Let me know if you need anything else.",
      "thank-you text must match exactly");
    assert.deepStrictEqual(stubs.postCalls[0].body.message.quick_replies, MAIN_MENU_QUICK_REPLIES,
      "HELPFUL_YES must re-anchor with MAIN_MENU_QUICK_REPLIES");
  } finally { stubs.restore(); }
});

test("UX-03: HELPFUL_NO quick reply calls handleEscalation (admin notify + Connecting message)", async (t) => {
  if (!handleWebhookEvent || !_feedbackExported) { t.skip("pending Phase 7 implementation"); return; }
  process.env.ADMIN_PSID = "ADMIN_1";
  const stubs = withAxiosStubs({});
  const originalError = console.error;
  console.error = () => {};
  try {
    await handleWebhookEvent!({
      message: { quick_reply: { payload: "HELPFUL_NO" }, text: "Was it helpful? No" },
      sender: { id: "USR_X" },
    });
    const recipients = stubs.postCalls.map((c) => c.body?.recipient?.id);
    assert.ok(recipients.includes("ADMIN_1"), "handleEscalation must notify ADMIN_PSID");
    const connectingCall = stubs.postCalls.find((c) =>
      typeof c.body?.message?.text === "string" && c.body.message.text.includes("Connecting")
    );
    assert.ok(connectingCall, "handleEscalation must send 'Connecting' message to user");
  } finally {
    stubs.restore();
    console.error = originalError;
    delete process.env.ADMIN_PSID;
  }
});

test("Regression: unknown payload after feedback falls through to sendFallbackMessage", async (t) => {
  if (!handleWebhookEvent || !_feedbackExported) { t.skip("pending Phase 7 implementation"); return; }
  const stubs = withAxiosStubs({});
  try {
    await handleWebhookEvent!({
      message: { quick_reply: { payload: "UNKNOWN_FEEDBACK_XYZ" }, text: "unknown" },
      sender: { id: "USR_X" },
    });
    assert.strictEqual(stubs.postCalls.length, 1, "exactly 1 postCall for unknown payload");
    assert.ok(
      typeof stubs.postCalls[0].body.message.text === "string" &&
      stubs.postCalls[0].body.message.text.includes("buttons below"),
      "sendFallbackMessage text must include 'buttons below'"
    );
  } finally { stubs.restore(); }
});
