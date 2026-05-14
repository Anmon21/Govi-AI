---
status: partial
phase: 01-security-bot-foundation
source: [01-VERIFICATION.md]
started: 2026-05-14T08:30:00.000Z
updated: 2026-05-14T08:30:00.000Z
---

## Current Test

[awaiting human testing]

## Tests

### 1. Forged POST returns 403 at network level
expected: `curl -X POST https://<your-ngrok-url>/webhook` with a tampered X-Hub-Signature-256 header returns HTTP 403 and the bot does not process the event
result: [pending]

### 2. Get Started shows welcome + quick replies in live Messenger
expected: Clicking "Get Started" on the Facebook Page opens a Messenger conversation and the bot replies with a welcome message containing at least 2 quick reply buttons (Product Help, Contact Human)
result: [pending]

### 3. Hamburger menu visible in live Messenger
expected: After `setupMessengerProfile` runs at bot startup, the persistent hamburger menu appears in the Messenger thread with 3 options (Product Help, Contact Human, Main Menu)
result: [pending]

### 4. Free-text sends fallback re-anchor message
expected: Typing any free text in live Messenger (not a quick reply tap) delivers a "not sure" re-anchor message with menu options — bot never goes silent
result: [pending]

### 5. Graph API failure does not leak PAGE_ACCESS_TOKEN in logs
expected: Triggering a real Graph API send failure (e.g. invalid token) emits a console.error with error message and response data only — PAGE_ACCESS_TOKEN value is absent from all log lines
result: [pending]

## Summary

total: 5
passed: 0
issues: 0
pending: 5
skipped: 0
blocked: 0

## Gaps
