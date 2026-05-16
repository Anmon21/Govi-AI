// Covers: SEC-02 — Graph API error detection inside HTTP 200
//         SEC-03 — Token-safe error logging (no PAGE_ACCESS_TOKEN in catch logs)
// Plan 02 will export sendMessage from ../index and make these tests green.

import { test } from "node:test";
import assert from "node:assert/strict";
// Type-only side-effect import — Plan 02 will add sendMessage export here
import type {} from "../index";

// Wave-0: sendMessage is not yet exported from ../index.
// Tests skip gracefully until Plan 02 lands.
// Set PORT=0 so index.ts binds to an OS-assigned port rather than conflicting with port 3000.
process.env.FACEBOOK_VERIFY_TOKEN = "test-token";
process.env.PORT = "0";

type SendFn = (recipientId: string, text: string, quickReplies?: unknown[]) => Promise<void>;
let sendMessage: SendFn | undefined;
try {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const mod = require("../index");
  sendMessage = typeof mod.sendMessage === "function" ? mod.sendMessage as SendFn : undefined;
} catch {
  sendMessage = undefined;
}

test("sendMessage logs Graph API error when response.data.error present", async (t) => {
  if (!sendMessage) {
    t.skip("pending Plan 02 implementation");
    return;
  }

  // Mock axios to return a 200 response with an error body (SEC-02 scenario)
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const axios = require("axios");
  const originalPost = axios.post;
  axios.post = async () => ({
    data: { error: { message: "send failed", code: 10 } },
  });

  const errorMessages: string[] = [];
  const originalError = console.error;
  console.error = (...args: unknown[]) => { errorMessages.push(args.join(" ")); };

  try {
    await sendMessage("USER_1", "hello");
    const combined = errorMessages.join(" ");
    assert.ok(
      combined.includes("Graph API error"),
      `console.error should include "Graph API error"; got: ${combined}`
    );
  } finally {
    console.error = originalError;
    axios.post = originalPost;
  }
});

test("sendMessage catch block does not log full axios error object (no PAGE_ACCESS_TOKEN leak)", async (t) => {
  if (!sendMessage) {
    t.skip("pending Plan 02 implementation");
    return;
  }

  const SECRET_TOKEN = "secret123";
  const originalToken = process.env.FACEBOOK_PAGE_ACCESS_TOKEN;
  process.env.FACEBOOK_PAGE_ACCESS_TOKEN = SECRET_TOKEN;

  // Mock axios to reject with an AxiosError whose config.url contains the token
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const axios = require("axios");
  const originalPost = axios.post;
  const fakeError: any = new Error("Request failed with status code 403");
  fakeError.isAxiosError = true;
  fakeError.config = { url: `https://graph.facebook.com/v21.0/me/messages?access_token=${SECRET_TOKEN}` };
  fakeError.response = { data: { error: "Forbidden" } };
  axios.post = async () => { throw fakeError; };

  const errorMessages: string[] = [];
  const originalError = console.error;
  console.error = (...args: unknown[]) => { errorMessages.push(args.map(String).join(" ")); };

  try {
    await sendMessage("USER_1", "hello");
    const combined = errorMessages.join(" ");
    assert.ok(
      !combined.includes(SECRET_TOKEN),
      `Logs must NOT contain PAGE_ACCESS_TOKEN "${SECRET_TOKEN}"; got: ${combined}`
    );
    assert.ok(
      combined.includes(fakeError.message),
      `Logs should include err.message; got: ${combined}`
    );
  } finally {
    console.error = originalError;
    axios.post = originalPost;
    if (originalToken === undefined) {
      delete process.env.FACEBOOK_PAGE_ACCESS_TOKEN;
    } else {
      process.env.FACEBOOK_PAGE_ACCESS_TOKEN = originalToken;
    }
  }
});
