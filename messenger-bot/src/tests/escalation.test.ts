// Covers: ESC-01 — MENU_CONTACT_HUMAN quick_reply and postback invoke handleEscalation
//         ESC-02 — handleEscalation posts admin notification to ADMIN_PSID
//         ESC-03 — passThreadControl POSTs to /me/pass_thread_control with correct body
//         ESC-04 — admin notification includes customer's last message; lastMessageCache updated on free text only
// Plan 02 will export handleEscalation, passThreadControl, lastMessageCache, PAGE_INBOX_APP_ID from ../index.

import { test } from "node:test";
import assert from "node:assert/strict";
// Type-only side-effect import — Plan 02 will add escalation exports here
import type {} from "../index";

// Wave-0: escalation exports are not yet present in ../index.
// Tests skip gracefully until Plan 02 lands.
// Set PORT=0 so index.ts binds to an OS-assigned port rather than conflicting with port 3000.
process.env.PORT = "0";

type EscalationFn = (senderId: string) => Promise<void>;
type PassThreadFn = (recipientId: string) => Promise<void>;
type EventFn = (event: any) => Promise<void>;

let handleEscalation: EscalationFn | undefined;
let passThreadControl: PassThreadFn | undefined;
let handleWebhookEvent: EventFn | undefined;
let lastMessageCache: Map<string, string> | undefined;
let PAGE_INBOX_APP_ID: string | undefined;

try {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const mod = require("../index");
  handleEscalation = typeof mod.handleEscalation === "function" ? mod.handleEscalation as EscalationFn : undefined;
  passThreadControl = typeof mod.passThreadControl === "function" ? mod.passThreadControl as PassThreadFn : undefined;
  handleWebhookEvent = typeof mod.handleWebhookEvent === "function" ? mod.handleWebhookEvent as EventFn : undefined;
  lastMessageCache = mod.lastMessageCache instanceof Map ? mod.lastMessageCache as Map<string, string> : undefined;
  PAGE_INBOX_APP_ID = typeof mod.PAGE_INBOX_APP_ID === "string" ? mod.PAGE_INBOX_APP_ID as string : undefined;
} catch {
  handleEscalation = undefined;
  passThreadControl = undefined;
  handleWebhookEvent = undefined;
  lastMessageCache = undefined;
  PAGE_INBOX_APP_ID = undefined;
}

test("ESC-01: MENU_CONTACT_HUMAN quick_reply invokes handleEscalation flow", async (t) => {
  if (!handleWebhookEvent || !handleEscalation) {
    t.skip("pending Plan 02 implementation");
    return;
  }

  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const axios = require("axios");
  const originalPost = axios.post;
  const calls: { url: string; body: any }[] = [];
  axios.post = async (url: string, body: any) => {
    calls.push({ url, body });
    return { data: {} };
  };
  const savedPsid = process.env.ADMIN_PSID;
  process.env.ADMIN_PSID = "ADM_1";

  try {
    await handleWebhookEvent({
      message: { quick_reply: { payload: "MENU_CONTACT_HUMAN" }, text: "Contact Human" },
      sender: { id: "USR_ESC_1" },
    });
    const recipientIds = calls.map((c) => c.body?.recipient?.id);
    assert.ok(recipientIds.includes("ADM_1"), "admin notification should be sent to ADM_1");
    assert.ok(recipientIds.includes("USR_ESC_1"), "customer confirmation should be sent to USR_ESC_1");
    const fallbackCalls = calls.filter((c) => c.body?.message?.text?.includes("I work best with the buttons below"));
    assert.strictEqual(fallbackCalls.length, 0, "fallback text must not appear in escalation flow");
  } finally {
    axios.post = originalPost;
    if (savedPsid === undefined) {
      delete process.env.ADMIN_PSID;
    } else {
      process.env.ADMIN_PSID = savedPsid;
    }
  }
});

test("ESC-01: MENU_CONTACT_HUMAN postback invokes handleEscalation flow", async (t) => {
  if (!handleWebhookEvent || !handleEscalation) {
    t.skip("pending Plan 02 implementation");
    return;
  }

  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const axios = require("axios");
  const originalPost = axios.post;
  const calls: { url: string; body: any }[] = [];
  axios.post = async (url: string, body: any) => {
    calls.push({ url, body });
    return { data: {} };
  };
  const savedPsid = process.env.ADMIN_PSID;
  process.env.ADMIN_PSID = "ADM_1";

  try {
    await handleWebhookEvent({
      postback: { payload: "MENU_CONTACT_HUMAN" },
      sender: { id: "USR_ESC_2" },
    });
    const recipientIds = calls.map((c) => c.body?.recipient?.id);
    assert.ok(recipientIds.includes("ADM_1"), "admin notification should be sent to ADM_1");
    assert.ok(recipientIds.includes("USR_ESC_2"), "customer confirmation should be sent to USR_ESC_2");
  } finally {
    axios.post = originalPost;
    if (savedPsid === undefined) {
      delete process.env.ADMIN_PSID;
    } else {
      process.env.ADMIN_PSID = savedPsid;
    }
  }
});

test("ESC-02: handleEscalation posts an admin notification to ADMIN_PSID", async (t) => {
  if (!handleEscalation) {
    t.skip("pending Plan 02 implementation");
    return;
  }

  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const axios = require("axios");
  const originalPost = axios.post;
  const calls: { url: string; body: any }[] = [];
  axios.post = async (url: string, body: any) => {
    calls.push({ url, body });
    return { data: {} };
  };
  const savedPsid = process.env.ADMIN_PSID;
  process.env.ADMIN_PSID = "ADM_2";

  try {
    await handleEscalation("USR_ESC_3");
    const adminCalls = calls.filter((c) => c.body?.recipient?.id === "ADM_2");
    assert.ok(adminCalls.length >= 1, "at least one message should be sent to ADM_2");
    const adminText: string = adminCalls[0].body?.message?.text ?? "";
    assert.ok(adminText.length >= 10, "admin notification message text should be at least 10 chars");
  } finally {
    axios.post = originalPost;
    if (savedPsid === undefined) {
      delete process.env.ADMIN_PSID;
    } else {
      process.env.ADMIN_PSID = savedPsid;
    }
  }
});

test("ESC-03: passThreadControl POSTs to /me/pass_thread_control with target_app_id 263902037430900", async (t) => {
  if (!passThreadControl) {
    t.skip("pending Plan 02 implementation");
    return;
  }

  assert.strictEqual(PAGE_INBOX_APP_ID, "263902037430900", "PAGE_INBOX_APP_ID constant must equal the canonical Page Inbox app ID");

  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const axios = require("axios");
  const originalPost = axios.post;
  const calls: { url: string; body: any }[] = [];
  axios.post = async (url: string, body: any) => {
    calls.push({ url, body });
    return { data: {} };
  };

  try {
    await passThreadControl("USR_ESC_4");
    assert.ok(calls.length >= 1, "axios.post should be called");
    const call = calls[0];
    assert.ok(call.url.includes("/me/pass_thread_control"), "URL must contain /me/pass_thread_control");
    assert.ok(call.url.includes("v21.0"), "URL must include graph API version v21.0");
    assert.deepStrictEqual(
      call.body,
      { recipient: { id: "USR_ESC_4" }, target_app_id: PAGE_INBOX_APP_ID },
      "body must match pass_thread_control spec"
    );
  } finally {
    axios.post = originalPost;
  }
});

test("ESC-04: admin notification body includes the customer's last text message", async (t) => {
  if (!handleEscalation || !lastMessageCache) {
    t.skip("pending Plan 02 implementation");
    return;
  }

  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const axios = require("axios");
  const originalPost = axios.post;
  const calls: { url: string; body: any }[] = [];
  axios.post = async (url: string, body: any) => {
    calls.push({ url, body });
    return { data: {} };
  };
  const savedPsid = process.env.ADMIN_PSID;
  process.env.ADMIN_PSID = "ADM_3";
  lastMessageCache.set("USR_ESC_5", "where is my order");

  try {
    await handleEscalation("USR_ESC_5");
    const adminCalls = calls.filter((c) => c.body?.recipient?.id === "ADM_3");
    assert.ok(adminCalls.length >= 1, "at least one message should be sent to ADM_3");
    const adminText: string = adminCalls[0].body?.message?.text ?? "";
    assert.ok(
      adminText.includes("where is my order"),
      `admin notification should contain customer's last message; got: "${adminText}"`
    );
  } finally {
    axios.post = originalPost;
    lastMessageCache.delete("USR_ESC_5");
    if (savedPsid === undefined) {
      delete process.env.ADMIN_PSID;
    } else {
      process.env.ADMIN_PSID = savedPsid;
    }
  }
});

test("ESC-04: lastMessageCache is updated when handleWebhookEvent receives free text, NOT when it receives a quick_reply", async (t) => {
  if (!handleWebhookEvent || !lastMessageCache) {
    t.skip("pending Plan 02 implementation");
    return;
  }

  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const axios = require("axios");
  const originalPost = axios.post;
  const originalGet = axios.get;
  // Stub axios so dispatcher does not fail when it branches into menu/escalation code
  axios.post = async (_url: string, _body: any) => ({ data: {} });
  axios.get = async (_url: string) => ({ data: { items: [] } });

  try {
    // Free text event — cache should be updated
    lastMessageCache.clear();
    await handleWebhookEvent({ message: { text: "real free text" }, sender: { id: "USR_ESC_6" } });
    assert.strictEqual(
      lastMessageCache.get("USR_ESC_6"),
      "real free text",
      "lastMessageCache should store the user's free text"
    );

    // Quick reply event — cache should NOT be updated (quick_reply.text is just the button label)
    lastMessageCache.clear();
    await handleWebhookEvent({
      message: { quick_reply: { payload: "MENU_CONTACT_HUMAN" }, text: "Contact Human" },
      sender: { id: "USR_ESC_7" },
    });
    assert.strictEqual(
      lastMessageCache.get("USR_ESC_7"),
      undefined,
      "lastMessageCache should NOT be updated for quick_reply events"
    );
  } finally {
    axios.post = originalPost;
    axios.get = originalGet;
    lastMessageCache.delete("USR_ESC_6");
    lastMessageCache.delete("USR_ESC_7");
  }
});

test("Soft-fail: ADMIN_PSID absent → handleEscalation sends customer fallback and does NOT crash or call pass_thread_control", async (t) => {
  if (!handleEscalation) {
    t.skip("pending Plan 02 implementation");
    return;
  }

  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const axios = require("axios");
  const originalPost = axios.post;
  const calls: { url: string; body: any }[] = [];
  axios.post = async (url: string, body: any) => {
    calls.push({ url, body });
    return { data: {} };
  };
  const savedPsid = process.env.ADMIN_PSID;
  delete process.env.ADMIN_PSID;

  try {
    await handleEscalation("USR_ESC_8");
    assert.strictEqual(calls.length, 1, "exactly one axios.post should be called (customer fallback only)");
    assert.strictEqual(calls[0].body?.recipient?.id, "USR_ESC_8", "fallback should be sent to the customer");
    const fallbackText: string = calls[0].body?.message?.text ?? "";
    assert.ok(
      fallbackText.toLowerCase().includes("be in touch"),
      `customer fallback text should contain "be in touch"; got: "${fallbackText}"`
    );
    const passThreadCalls = calls.filter((c) => c.url?.includes("pass_thread_control"));
    assert.strictEqual(passThreadCalls.length, 0, "pass_thread_control must NOT be called when ADMIN_PSID is absent");
  } finally {
    axios.post = originalPost;
    if (savedPsid === undefined) {
      delete process.env.ADMIN_PSID;
    } else {
      process.env.ADMIN_PSID = savedPsid;
    }
  }
});
