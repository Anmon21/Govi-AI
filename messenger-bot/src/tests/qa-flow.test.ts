// Covers: QA-01 — Category menu via quick replies
//         QA-02 — Question sub-menu via quick replies
//         QA-03 — Answer text delivery from vault
// Plan 03-02 will export sendCategoryMenu, sendQuestionMenu, sendAnswer, and extend handleWebhookEvent's
// quick_reply dispatcher. Tests skip gracefully until that implementation lands.

import { test } from "node:test";
import assert from "node:assert/strict";
import type {} from "../index";

process.env.PORT = "0";

type EventFn = (event: any) => Promise<void>;

let handleWebhookEvent: EventFn | undefined;
let MAIN_MENU_QUICK_REPLIES: any[] | undefined;
// sendCategoryMenu is the sentinel for Task 2 implementation — tests skip until it is exported
let _sendCategoryMenuExported = false;

try {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const mod = require("../index");
  handleWebhookEvent = typeof mod.handleWebhookEvent === "function" ? mod.handleWebhookEvent as EventFn : undefined;
  MAIN_MENU_QUICK_REPLIES = Array.isArray(mod.MAIN_MENU_QUICK_REPLIES) ? mod.MAIN_MENU_QUICK_REPLIES : undefined;
  _sendCategoryMenuExported = typeof mod.sendCategoryMenu === "function";
} catch {
  handleWebhookEvent = undefined;
  MAIN_MENU_QUICK_REPLIES = undefined;
  _sendCategoryMenuExported = false;
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

test("qa-flow: MENU_PRODUCT_HELP triggers sendCategoryMenu with CATEGORY: payloads", async (t) => {
  if (!handleWebhookEvent || !_sendCategoryMenuExported) { t.skip("pending Plan 03-02 implementation"); return; }
  const stubs = withAxiosStubs({
    onGet: (url) => {
      if (url.includes("type=category")) {
        return { data: { items: [
          { id: "cat-products", type: "category", title: "Products" },
          { id: "cat-shipping", type: "category", title: "Shipping" },
        ]}};
      }
      return { data: { items: [] } };
    },
  });
  try {
    await handleWebhookEvent!({
      message: { quick_reply: { payload: "MENU_PRODUCT_HELP" }, text: "Product Help" },
      sender: { id: "USR_1" },
    });
    // One GET for categories
    assert.ok(stubs.getCalls.some((c) => c.url.includes("type=category")), "should GET /content?type=category");
    // Exactly one POST to the user
    assert.strictEqual(stubs.postCalls.length, 1, "exactly one sendMessage to the customer");
    const qrs = stubs.postCalls[0].body?.message?.quick_replies;
    assert.ok(Array.isArray(qrs) && qrs.length === 2, "two category quick replies expected");
    for (const qr of qrs) {
      assert.ok(typeof qr.payload === "string" && qr.payload.startsWith("CATEGORY:"),
        `every payload must start with CATEGORY: — got ${qr.payload}`);
    }
  } finally { stubs.restore(); }
});

test("qa-flow: CATEGORY:<id> triggers sendQuestionMenu with QUESTION: payloads", async (t) => {
  if (!handleWebhookEvent || !_sendCategoryMenuExported) { t.skip("pending Plan 03-02 implementation"); return; }
  const stubs = withAxiosStubs({
    onGet: (url) => {
      if (url.includes("type=question") && url.includes("category=cat-shipping")) {
        return { data: { items: [
          { id: "q-shipping-01", type: "question", title: "Shipping time?" },
          { id: "q-shipping-02", type: "question", title: "Ship abroad?" },
        ]}};
      }
      return { data: { items: [] } };
    },
  });
  try {
    await handleWebhookEvent!({
      message: { quick_reply: { payload: "CATEGORY:cat-shipping" }, text: "Shipping" },
      sender: { id: "USR_1" },
    });
    assert.ok(stubs.getCalls.some((c) => c.url.includes("type=question") && c.url.includes("category=cat-shipping")),
      "should GET /content?type=question&category=cat-shipping");
    assert.strictEqual(stubs.postCalls.length, 1);
    const qrs = stubs.postCalls[0].body?.message?.quick_replies;
    assert.ok(Array.isArray(qrs) && qrs.length === 2);
    for (const qr of qrs) {
      assert.ok(typeof qr.payload === "string" && qr.payload.startsWith("QUESTION:"),
        `every payload must start with QUESTION: — got ${qr.payload}`);
    }
  } finally { stubs.restore(); }
});

test("qa-flow: QUESTION:<id> triggers sendAnswer with body text and main menu re-anchor", async (t) => {
  if (!handleWebhookEvent || !MAIN_MENU_QUICK_REPLIES || !_sendCategoryMenuExported) { t.skip("pending Plan 03-02 implementation"); return; }
  const ANSWER_BODY = "Standard orders ship within 1-2 business days.";
  const stubs = withAxiosStubs({
    onGet: (url) => {
      if (url.includes("/content/q-shipping-01")) {
        return { data: { id: "q-shipping-01", type: "question", title: "Shipping time?", body: ANSWER_BODY } };
      }
      return { data: {} };
    },
  });
  try {
    await handleWebhookEvent!({
      message: { quick_reply: { payload: "QUESTION:q-shipping-01" }, text: "Shipping time?" },
      sender: { id: "USR_1" },
    });
    assert.ok(stubs.getCalls.some((c) => c.url.includes("/content/q-shipping-01")),
      "should GET /content/q-shipping-01");
    assert.strictEqual(stubs.postCalls.length, 3, "typing_on + sendMessage + typing_off for answer delivery");
    assert.ok(stubs.postCalls[0].body?.sender_action === "typing_on", "typing_on must be the first POST");
    assert.ok(stubs.postCalls[2].body?.sender_action === "typing_off", "typing_off must be the third POST (after sendMessage resolves)");
    const msg = stubs.postCalls[1].body?.message;
    assert.strictEqual(msg?.text, ANSWER_BODY, "message text must equal the answer body");
    assert.deepStrictEqual(msg?.quick_replies, MAIN_MENU_QUICK_REPLIES,
      "main menu quick replies must be re-attached after every answer");
  } finally { stubs.restore(); }
});

test("qa-flow: API error sends apology + MAIN_MENU_QUICK_REPLIES (no crash)", async (t) => {
  if (!handleWebhookEvent || !MAIN_MENU_QUICK_REPLIES || !_sendCategoryMenuExported) { t.skip("pending Plan 03-02 implementation"); return; }
  const stubs = withAxiosStubs({
    onGet: async () => { throw new Error("ECONNREFUSED"); },
  });
  // Silence the expected console.error so test output stays clean
  const originalError = console.error;
  console.error = () => {};
  try {
    await handleWebhookEvent!({
      message: { quick_reply: { payload: "MENU_PRODUCT_HELP" }, text: "Product Help" },
      sender: { id: "USR_1" },
    });
    assert.strictEqual(stubs.postCalls.length, 1, "exactly one user-facing message on API failure");
    const msg = stubs.postCalls[0].body?.message;
    assert.ok(typeof msg?.text === "string" && msg.text.length > 0, "apology text must be non-empty");
    assert.deepStrictEqual(msg?.quick_replies, MAIN_MENU_QUICK_REPLIES,
      "main menu quick replies must be re-attached on error");
  } finally {
    stubs.restore();
    console.error = originalError;
  }
});

test("qa-flow: sendAnswer typing_off fires even when API fetch fails", async (t) => {
  if (!handleWebhookEvent || !MAIN_MENU_QUICK_REPLIES || !_sendCategoryMenuExported) { t.skip("pending Plan 03-02 implementation"); return; }
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
    assert.strictEqual(stubs.postCalls.length, 3, "typing_on + apology + typing_off when fetch fails");
    assert.strictEqual(stubs.postCalls[0].body?.sender_action, "typing_on", "first POST must be typing_on");
    assert.ok(
      typeof stubs.postCalls[1].body?.message?.text === "string" && stubs.postCalls[1].body.message.text.length > 0,
      "apology text must be non-empty"
    );
    assert.deepStrictEqual(stubs.postCalls[1].body?.message?.quick_replies, MAIN_MENU_QUICK_REPLIES,
      "apology must re-attach main menu quick replies");
    assert.strictEqual(stubs.postCalls[2].body?.sender_action, "typing_off", "typing_off must fire even when fetch threw (finally block)");
  } finally {
    stubs.restore();
    console.error = originalError;
  }
});
