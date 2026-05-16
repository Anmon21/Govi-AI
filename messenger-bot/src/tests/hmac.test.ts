// Covers: SEC-01 — HMAC-SHA256 webhook signature verification
// Plan 02 will export verifySignature from ../index and make these tests green.

import { test } from "node:test";
import assert from "node:assert/strict";
import crypto from "crypto";
// Type-only side-effect import — Plan 02 will add verifySignature export here
import type {} from "../index";

// Wave-0: verifySignature is not yet exported from ../index.
// Tests skip gracefully until Plan 02 lands.
// Set PORT=0 so index.ts binds to an OS-assigned port rather than conflicting with port 3000.
process.env.FACEBOOK_VERIFY_TOKEN = "test-token";
process.env.PORT = "0";

type VerifyFn = (req: any, res: any, next: any) => void;
let verifySignature: VerifyFn | undefined;
try {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const mod = require("../index");
  verifySignature = typeof mod.verifySignature === "function" ? mod.verifySignature as VerifyFn : undefined;
} catch {
  verifySignature = undefined;
}

test("verifySignature: valid X-Hub-Signature-256 calls next()", (t) => {
  if (!verifySignature) {
    t.skip("pending Plan 02 implementation");
    return;
  }

  const APP_SECRET = "test-secret";
  const rawBody = Buffer.from('{"object":"page"}', "utf8");
  const sig = `sha256=${crypto.createHmac("sha256", APP_SECRET).update(rawBody).digest("hex")}`;

  const req: any = {
    headers: { "x-hub-signature-256": sig },
    body: rawBody,
  };
  const res: any = { sendStatus: (code: number) => { throw new Error(`sendStatus(${code}) called`); } };
  let nextCalled = false;
  const next = () => { nextCalled = true; };

  const originalSecret = process.env.FACEBOOK_APP_SECRET;
  process.env.FACEBOOK_APP_SECRET = APP_SECRET;
  try {
    verifySignature(req, res, next);
    assert.ok(nextCalled, "next() should be called for valid signature");
  } finally {
    if (originalSecret === undefined) {
      delete process.env.FACEBOOK_APP_SECRET;
    } else {
      process.env.FACEBOOK_APP_SECRET = originalSecret;
    }
  }
});

test("verifySignature: invalid signature returns 403", (t) => {
  if (!verifySignature) {
    t.skip("pending Plan 02 implementation");
    return;
  }

  const rawBody = Buffer.from('{"object":"page"}', "utf8");
  const req: any = {
    headers: { "x-hub-signature-256": "sha256=invalidsignature" },
    body: rawBody,
  };
  let statusSent: number | undefined;
  const res: any = { sendStatus: (code: number) => { statusSent = code; } };
  let nextCalled = false;
  const next = () => { nextCalled = true; };

  const originalSecret = process.env.FACEBOOK_APP_SECRET;
  process.env.FACEBOOK_APP_SECRET = "test-secret";
  try {
    verifySignature(req, res, next);
    assert.strictEqual(statusSent, 403, "res.sendStatus(403) should be called once");
    assert.ok(!nextCalled, "next() should not be called for invalid signature");
  } finally {
    if (originalSecret === undefined) {
      delete process.env.FACEBOOK_APP_SECRET;
    } else {
      process.env.FACEBOOK_APP_SECRET = originalSecret;
    }
  }
});

test("verifySignature: missing FACEBOOK_APP_SECRET logs warn and calls next()", (t) => {
  if (!verifySignature) {
    t.skip("pending Plan 02 implementation");
    return;
  }

  const rawBody = Buffer.from('{"object":"page"}', "utf8");
  const req: any = { headers: {}, body: rawBody };
  const res: any = { sendStatus: (code: number) => { throw new Error(`sendStatus(${code}) called`); } };
  let nextCalled = false;
  const next = () => { nextCalled = true; };

  const originalSecret = process.env.FACEBOOK_APP_SECRET;
  delete process.env.FACEBOOK_APP_SECRET;
  const warnMessages: string[] = [];
  const originalWarn = console.warn;
  console.warn = (...args: unknown[]) => { warnMessages.push(args.join(" ")); };
  try {
    verifySignature(req, res, next);
    assert.ok(nextCalled, "next() should be called when APP_SECRET is absent");
    const warnText = warnMessages.join(" ");
    assert.ok(
      warnText.includes("skipping webhook signature verification"),
      `console.warn should mention "skipping webhook signature verification"; got: ${warnText}`
    );
  } finally {
    console.warn = originalWarn;
    if (originalSecret === undefined) {
      delete process.env.FACEBOOK_APP_SECRET;
    } else {
      process.env.FACEBOOK_APP_SECRET = originalSecret;
    }
  }
});
