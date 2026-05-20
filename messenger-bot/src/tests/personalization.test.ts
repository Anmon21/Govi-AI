// Covers: UX-06 — in-memory name cache populated from Graph API on first contact per PSID
//         UX-07 — personalized greeting "Welcome back, {name}!" vs generic fallback

import { test } from "node:test";
import assert from "node:assert/strict";
import type {} from "../index";

process.env.FACEBOOK_VERIFY_TOKEN = "test-token";
process.env.PORT = "0";

type EventFn = (event: any) => Promise<void>;
type FetchUserNameFn = (psid: string) => Promise<void>;
type SendWelcomeMessageFn = (recipientId: string) => Promise<void>;

let handleWebhookEvent: EventFn | undefined;
let fetchUserName: FetchUserNameFn | undefined;
let userNameCache: Map<string, string> | undefined;
let sendWelcomeMessage: SendWelcomeMessageFn | undefined;

try {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const mod = require("../index");
  handleWebhookEvent = typeof mod.handleWebhookEvent === "function" ? mod.handleWebhookEvent as EventFn : undefined;
  fetchUserName = typeof mod.fetchUserName === "function" ? mod.fetchUserName as FetchUserNameFn : undefined;
  userNameCache = mod.userNameCache instanceof Map ? mod.userNameCache as Map<string, string> : undefined;
  sendWelcomeMessage = typeof mod.sendWelcomeMessage === "function" ? mod.sendWelcomeMessage as SendWelcomeMessageFn : undefined;
} catch {
  handleWebhookEvent = undefined;
  fetchUserName = undefined;
  userNameCache = undefined;
  sendWelcomeMessage = undefined;
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

test("UX-06: fetchUserName with valid first_name stores it in userNameCache", async (t) => {
  if (!fetchUserName || !userNameCache) { t.skip("pending Phase 9 implementation"); return; }
  userNameCache!.clear();
  const stubs = withAxiosStubs({
    onGet: (url) => {
      if (url.includes("graph.facebook.com")) return { data: { first_name: "Alice" } };
      return { data: {} };
    },
  });
  try {
    await fetchUserName!("PSID_A");
    assert.strictEqual(userNameCache!.get("PSID_A"), "Alice",
      "fetchUserName must store first_name in userNameCache");
  } finally { stubs.restore(); }
});

test("UX-06: fetchUserName with empty object response stores empty-string sentinel", async (t) => {
  if (!fetchUserName || !userNameCache) { t.skip("pending Phase 9 implementation"); return; }
  userNameCache!.clear();
  const stubs = withAxiosStubs({
    onGet: (url) => {
      if (url.includes("graph.facebook.com")) return { data: {} };
      return { data: {} };
    },
  });
  try {
    await fetchUserName!("PSID_B");
    assert.strictEqual(userNameCache!.get("PSID_B"), "",
      "fetchUserName must store empty-string sentinel when first_name absent");
  } finally { stubs.restore(); }
});

test("UX-06: fetchUserName with network error stores empty-string sentinel", async (t) => {
  if (!fetchUserName || !userNameCache) { t.skip("pending Phase 9 implementation"); return; }
  userNameCache!.clear();
  const stubs = withAxiosStubs({
    onGet: async () => { throw new Error("ECONNREFUSED"); },
  });
  const originalError = console.error;
  console.error = () => {};
  try {
    await fetchUserName!("PSID_C");
    assert.strictEqual(userNameCache!.get("PSID_C"), "",
      "fetchUserName must store empty-string sentinel on network error");
  } finally {
    stubs.restore();
    console.error = originalError;
  }
});

test("UX-06: handleWebhookEvent for unknown PSID triggers Graph API GET", async (t) => {
  if (!handleWebhookEvent || !userNameCache) { t.skip("pending Phase 9 implementation"); return; }
  userNameCache!.clear();
  const stubs = withAxiosStubs({
    onGet: (url) => {
      if (url.includes("graph.facebook.com")) return { data: {} };
      return { data: {} };
    },
  });
  try {
    await handleWebhookEvent!({ sender: { id: "PSID_D" }, postback: { payload: "GET_STARTED" } });
    assert.ok(
      stubs.getCalls.some((c) => c.url.includes("graph.facebook.com")),
      "handleWebhookEvent must call Graph API GET for unknown PSID"
    );
  } finally { stubs.restore(); }
});

test("UX-06: handleWebhookEvent fired twice for same PSID calls Graph API GET exactly once", async (t) => {
  if (!handleWebhookEvent || !userNameCache) { t.skip("pending Phase 9 implementation"); return; }
  userNameCache!.clear();
  const stubs = withAxiosStubs({
    onGet: (url) => {
      if (url.includes("graph.facebook.com")) return { data: { first_name: "Eve" } };
      return { data: {} };
    },
  });
  try {
    await handleWebhookEvent!({ sender: { id: "PSID_E" }, postback: { payload: "GET_STARTED" } });
    await handleWebhookEvent!({ sender: { id: "PSID_E" }, postback: { payload: "GET_STARTED" } });
    const graphCalls = stubs.getCalls.filter((c) => c.url.includes("graph.facebook.com"));
    assert.strictEqual(graphCalls.length, 1,
      "sentinel must prevent second Graph API call for same PSID");
  } finally { stubs.restore(); }
});

test("UX-07: sendWelcomeMessage sends personalized greeting when cache has non-empty name", async (t) => {
  if (!sendWelcomeMessage || !userNameCache) { t.skip("pending Phase 9 implementation"); return; }
  userNameCache!.set("PSID_F", "Bob");
  const stubs = withAxiosStubs({});
  try {
    await sendWelcomeMessage!("PSID_F");
    assert.strictEqual(
      stubs.postCalls[0].body.message.text,
      "Welcome back, Bob! How can I help you today?",
      "sendWelcomeMessage must use personalized text when cache has a non-empty name"
    );
  } finally { stubs.restore(); }
});

test("UX-07: sendWelcomeMessage sends generic greeting when cache has empty-string sentinel", async (t) => {
  if (!sendWelcomeMessage || !userNameCache) { t.skip("pending Phase 9 implementation"); return; }
  userNameCache!.set("PSID_G", "");
  const stubs = withAxiosStubs({});
  try {
    await sendWelcomeMessage!("PSID_G");
    assert.strictEqual(
      stubs.postCalls[0].body.message.text,
      "Welcome to Govi! I can help with product questions or connect you with a human.",
      "sendWelcomeMessage must use generic text when cache has empty-string sentinel"
    );
  } finally { stubs.restore(); }
});

test("UX-07: sendWelcomeMessage sends generic greeting when PSID absent from cache", async (t) => {
  if (!sendWelcomeMessage || !userNameCache) { t.skip("pending Phase 9 implementation"); return; }
  userNameCache!.clear();
  const stubs = withAxiosStubs({});
  try {
    await sendWelcomeMessage!("PSID_H");
    assert.strictEqual(
      stubs.postCalls[0].body.message.text,
      "Welcome to Govi! I can help with product questions or connect you with a human.",
      "sendWelcomeMessage must use generic text when PSID not in cache"
    );
  } finally { stubs.restore(); }
});

test("UX-06+UX-07 end-to-end: GET_STARTED for unknown PSID with name fetched sends personalized greeting", async (t) => {
  if (!handleWebhookEvent || !userNameCache) { t.skip("pending Phase 9 implementation"); return; }
  userNameCache!.clear();
  const stubs = withAxiosStubs({
    onGet: (url) => {
      if (url.includes("graph.facebook.com")) return { data: { first_name: "Alice" } };
      return { data: {} };
    },
  });
  try {
    await handleWebhookEvent!({ sender: { id: "PSID_I" }, postback: { payload: "GET_STARTED" } });
    assert.ok(
      stubs.postCalls.some((c) => c.body?.message?.text === "Welcome back, Alice! How can I help you today?"),
      "end-to-end: GET_STARTED must send personalized greeting after Graph API fetch"
    );
  } finally { stubs.restore(); }
});
