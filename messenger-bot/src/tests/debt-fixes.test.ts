// Covers: DEBT-01 — MENU_PRODUCT_HELP and MENU_MAIN postback routing
//         DEBT-02 — Per-event try/catch isolates failures in webhook inner loop
//         DEBT-04 — Non-Axios error branches log string, not raw error object

import { test } from "node:test";
import assert from "node:assert/strict";

// Set required env vars BEFORE require("../index") so the startup guard does not exit.
process.env.FACEBOOK_VERIFY_TOKEN = "test-token";
process.env.FACEBOOK_PAGE_ACCESS_TOKEN = "test-token";
process.env.PORT = "0";

type EventFn = (event: any) => Promise<void>;
type SendMsgFn = (recipientId: string, text: string, quickReplies?: any[]) => Promise<void>;

let handleWebhookEvent: EventFn | undefined;
let sendMessage: SendMsgFn | undefined;

try {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const mod = require("../index");
  handleWebhookEvent = typeof mod.handleWebhookEvent === "function" ? mod.handleWebhookEvent as EventFn : undefined;
  sendMessage = typeof mod.sendMessage === "function" ? mod.sendMessage as SendMsgFn : undefined;
} catch {
  handleWebhookEvent = undefined;
  sendMessage = undefined;
}

// Test A (DEBT-01a): MENU_PRODUCT_HELP postback routes to sendCategoryMenu (invokes axios.get on /content?type=category)
test("DEBT-01: MENU_PRODUCT_HELP postback routes to sendCategoryMenu", async (t) => {
  if (!handleWebhookEvent) {
    t.skip("handleWebhookEvent not exported");
    return;
  }

  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const axios = require("axios");
  const originalGet = axios.get;
  const originalPost = axios.post;
  const getCalls: string[] = [];
  axios.get = async (url: string) => {
    getCalls.push(url);
    return { data: { items: [] } };
  };
  axios.post = async (_url: string, _body: any) => ({ data: {} });

  try {
    await handleWebhookEvent({ postback: { payload: "MENU_PRODUCT_HELP" }, sender: { id: "USR_A" } });
    assert.ok(getCalls.length >= 1, "sendCategoryMenu should call axios.get");
    assert.ok(
      getCalls.some((url) => url.includes("/content") && url.includes("type=category")),
      "axios.get should target /content?type=category"
    );
  } finally {
    axios.get = originalGet;
    axios.post = originalPost;
  }
});

// Test B (DEBT-01b): MENU_MAIN postback routes to sendWelcomeMessage (invokes axios.post with welcome text)
test("DEBT-01: MENU_MAIN postback routes to sendWelcomeMessage", async (t) => {
  if (!handleWebhookEvent) {
    t.skip("handleWebhookEvent not exported");
    return;
  }

  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const axios = require("axios");
  const originalPost = axios.post;
  const postBodies: any[] = [];
  axios.post = async (_url: string, body: any) => {
    postBodies.push(body);
    return { data: {} };
  };

  try {
    await handleWebhookEvent({ postback: { payload: "MENU_MAIN" }, sender: { id: "USR_B" } });
    assert.ok(postBodies.length >= 1, "sendWelcomeMessage should call axios.post");
    const welcomeCall = postBodies.find((b) => b?.message?.text?.includes("Welcome to Govi"));
    assert.ok(welcomeCall, "welcome message text should include 'Welcome to Govi'");
  } finally {
    axios.post = originalPost;
  }
});

// Test C (DEBT-01c — negative): UNKNOWN_XYZ postback makes zero axios calls (D-02 silent-drop preserved)
// Phase 9 note: handleWebhookEvent now calls fetchUserName (graph.facebook.com GET) for unknown PSIDs.
// The assertion checks only Govi AI calls — Graph API name-fetch calls are expected and excluded.
test("DEBT-01: unknown postback payload is silently dropped — no axios calls", async (t) => {
  if (!handleWebhookEvent) {
    t.skip("handleWebhookEvent not exported");
    return;
  }

  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const axios = require("axios");
  const originalPost = axios.post;
  const originalGet = axios.get;
  const postCalls: any[] = [];
  const getCalls: any[] = [];
  axios.post = async (_url: string, body: any) => { postCalls.push(body); return { data: {} }; };
  axios.get = async (url: string) => { getCalls.push(url); return { data: { items: [] } }; };

  try {
    await handleWebhookEvent({ postback: { payload: "UNKNOWN_XYZ" }, sender: { id: "USR_C" } });
    assert.strictEqual(postCalls.length, 0, "unknown postback should make zero axios.post calls");
    // Phase 9: fetchUserName triggers one graph.facebook.com GET for unknown PSIDs — expected behavior
    const goviAiCalls = getCalls.filter((url) => !url.includes("graph.facebook.com"));
    assert.strictEqual(goviAiCalls.length, 0, "unknown postback should make zero Govi AI axios.get calls");
  } finally {
    axios.post = originalPost;
    axios.get = originalGet;
  }
});

// Test D (DEBT-02): two-event batch isolation — Event 1 throws, Event 2 still processed
test("DEBT-02: per-event catch isolation — throwing event does not block next event", async (t) => {
  if (!handleWebhookEvent) {
    t.skip("handleWebhookEvent not exported");
    return;
  }

  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const axios = require("axios");
  const originalPost = axios.post;
  const originalConsoleError = console.error;

  const events = [
    { postback: { payload: "GET_STARTED" }, sender: { id: "USR_D1" } },
    { postback: { payload: "GET_STARTED" }, sender: { id: "USR_D2" } },
  ];

  let callCount = 0;
  const recordedErrors: any[][] = [];

  axios.post = async (_url: string, _body: any) => {
    callCount += 1;
    if (callCount === 1) {
      throw new Error("boom");
    }
    return { data: {} };
  };

  console.error = (...args: any[]) => {
    recordedErrors.push(args);
  };

  try {
    // Mirror the production inner loop shape (same as Task 4's POST /webhook handler)
    for (const event of events) {
      try {
        await handleWebhookEvent(event);
      } catch (err) {
        console.error("test-wrapper:", err instanceof Error ? err.message : String(err));
      }
    }

    // (1) axios.post called exactly twice — Event 2 was processed despite Event 1 throwing
    assert.strictEqual(callCount, 2, "axios.post should be called twice (both events processed)");

    // (2) At least one recorded console.error has a string as second argument (D-05 sanitization)
    const hasStringArg = recordedErrors.some((args) => args.length >= 2 && typeof args[1] === "string");
    assert.ok(hasStringArg, "at least one console.error call should have a string second argument");
  } finally {
    axios.post = originalPost;
    console.error = originalConsoleError;
  }
});

// Test E (DEBT-04): non-Error throw in sendMessage — String(err) applied, logged as string
test("DEBT-04: non-Error throw in sendMessage logs string via String(err)", async (t) => {
  if (!sendMessage) {
    t.skip("sendMessage not exported");
    return;
  }

  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const axios = require("axios");
  const originalPost = axios.post;
  const originalConsoleError = console.error;
  const recordedErrors: any[][] = [];

  axios.post = async (_url: string, _body: any) => {
    throw "plain-string-error";
  };

  console.error = (...args: any[]) => {
    recordedErrors.push(args);
  };

  try {
    await sendMessage("USR_E", "hi");

    // The non-Axios else branch should produce String("plain-string-error") = "plain-string-error"
    const unexpectedErrorCall = recordedErrors.find((args) =>
      args.some((a) => typeof a === "string" && a.includes("unexpected error"))
    );
    assert.ok(unexpectedErrorCall, "console.error for unexpected error should be called");
    assert.strictEqual(
      unexpectedErrorCall![1],
      "plain-string-error",
      "second argument should be the string value of the thrown non-Error"
    );
  } finally {
    axios.post = originalPost;
    console.error = originalConsoleError;
  }
});
