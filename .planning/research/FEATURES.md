# Features Research

**Domain:** Rule-based Facebook Messenger customer support bot (e-commerce/retail)
**Project:** Govi AI
**Researched:** 2026-05-14
**Confidence:** HIGH (Messenger platform constraints are well-documented; e-commerce support patterns are stable)

---

## Table Stakes

These are the features that, if missing, cause the bot to feel broken or unresponsive. Users who hit a dead end will abandon the conversation and not return.

---

### Greeting / Welcome Message

- **Description:** When a user first messages the Messenger page (or sends a "Get Started" event), the bot responds with a welcome message that sets expectations — what the bot can do and how to navigate it. Facebook sends a `messaging_postbacks` event with payload `GET_STARTED` when the user taps the Get Started button in a fresh conversation.
- **Complexity:** Low
- **Dependencies:** Webhook event handling, postback routing
- **Expected user behavior:** User opens the page and taps "Get Started" or sends a first message. If there is no welcome message, the conversation starts with silence — users immediately assume the bot is broken.
- **Platform note:** The Get Started button must be registered via the Messenger Profile API before it appears. This is a one-time setup step, not a per-message handler.

---

### Persistent Menu (Main Menu)

- **Description:** A hamburger-style menu anchored to the bottom of the Messenger chat window, always visible, containing top-level navigation items (e.g., "Product Questions", "Contact Support"). Configured via the Messenger Profile API. Users can return to a known state at any time without typing anything.
- **Complexity:** Low (setup) / Medium (keeping in sync with content changes)
- **Dependencies:** Messenger Profile API access (Page access token), postback routing
- **Expected user behavior:** Users who get lost mid-conversation tap the persistent menu rather than typing. Without it, users who reach a dead end have no recovery path — they either retype from scratch or leave.
- **Platform note:** Limited to 3 top-level items, each supporting nested menus (up to 5 items per level). Items are postbacks or URLs — not free text. Changes require a Profile API call (not automatic).

---

### Quick Reply Buttons (Menu Navigation)

- **Description:** After each bot message, present a set of quick-reply chips that represent the valid next steps. Users tap rather than type. This is the primary navigation mechanism for rule-based bots — it removes the need for NLP entirely.
- **Complexity:** Low
- **Dependencies:** Menu state machine, message send API
- **Expected user behavior:** Users expect tappable options. If the bot sends a plain text question ("What do you need help with?") with no buttons, most users will not know what to type and will either try random words or abandon.
- **Platform note:** Messenger quick replies disappear after the user taps one. Maximum 13 quick replies per message, max 20 characters per label. Plan menu structure around this constraint.

---

### Product Q&A Flow (Content-Driven Answers)

- **Description:** A structured navigation tree that leads users to product-specific answers sourced from the Obsidian vault. Flow: user selects a product category → selects a specific question → receives the answer from the vault markdown file. The Node.js bot calls the FastAPI backend to retrieve the answer for a given question key; FastAPI reads the markdown file and returns the content.
- **Complexity:** Medium
- **Dependencies:** Persistent menu, quick reply buttons, Obsidian vault reader (FastAPI), menu state machine
- **Expected user behavior:** Users arrive with a specific question ("Does this product contain X?"). If the answer isn't findable within 3 taps, they escalate to a human or leave. Keep the tree shallow: category → question → answer, maximum 3 levels.
- **Content dependency:** The FastAPI backend must be able to map a question key (e.g., `skincare/ingredients`) to a vault file and return the answer text. This coupling between menu structure and vault file layout must be designed deliberately upfront.

---

### Human Escalation Flow

- **Description:** When a user selects "Talk to a person" (or the bot cannot resolve their issue), the bot notifies the admin via the Messenger page inbox and informs the user that a human will respond. The admin receives a Messenger notification in the Page inbox (not a separate tool — the admin is already managing the Page).
- **Complexity:** Medium
- **Dependencies:** Quick reply buttons, Facebook Page messaging permissions, admin Page inbox setup
- **Expected user behavior:** Users who are frustrated or have a question not covered by the menu expect a clear path to a human. If the escalation entry point is buried or absent, they leave negative reviews or contact via other channels.
- **Implementation note:** Messenger's "human takeover" protocol (`pass_thread_control`) is the correct mechanism when using the Handover Protocol — the bot passes thread control to the Page inbox app so the admin can reply directly. This requires the Page inbox to be configured as the secondary receiver. Without this, the bot and the admin can conflict (both trying to respond to the same thread).
- **Admin experience:** The admin sees the escalated conversation in the standard Facebook Page inbox and replies there. No extra tooling needed.

---

### "I Don't Understand" / Fallback Handler

- **Description:** When the bot receives a free-text message it cannot parse (which is most free-text in a rule-based system), it responds with a helpful fallback: "I didn't get that. Here's what I can help with:" followed by the main menu options. It does not silently fail or return nothing.
- **Complexity:** Low
- **Dependencies:** Quick reply buttons, main menu
- **Expected user behavior:** Some users will always type instead of tapping. Without a fallback handler, free-text input produces silence — users think the bot is down. The fallback re-anchors them to the menu.
- **Important:** The fallback must NOT say "I don't understand" and leave the user stranded. It must immediately offer a recovery path.

---

### Graceful Session Restart

- **Description:** If a user returns to a conversation after a long gap (hours/days), the bot does not continue from mid-flow state that is now stale. It detects a fresh message on a stale session and re-presents the main menu rather than trying to continue a broken flow.
- **Complexity:** Low (if session state is stored with a TTL) / Medium (if state is stateless and rebuilt from context)
- **Dependencies:** Session state management, main menu
- **Expected user behavior:** Users who return after days expect to start fresh. If the bot responds with a continuation of a previous menu step ("Please select from the options above" — with no options visible), the experience is confusing.

---

## Differentiators

These features add value over a basic bot but are not expected by default. They provide measurable improvement to support quality without being required for the bot to function.

---

### Typing Indicator Between Messages

- **Description:** Send a typing indicator (`sender_actions: typing_on`) before each bot response, especially before longer answers. Adds 0.5–1 second of perceived "thinking time" before the message appears.
- **Complexity:** Low (one extra API call per message)
- **Dependencies:** Message send API
- **User impact:** Makes the bot feel less robotic. Users accustomed to chat expect a brief typing indicator before a response. Without it, messages can feel like instant form-letter output.

---

### "Was this helpful?" Confirmation After Answers

- **Description:** After delivering a product Q&A answer, present two quick replies: "Yes, thanks" and "No, I need more help." If the user selects "No," route them to the escalation flow or back to the menu.
- **Complexity:** Low
- **Dependencies:** Quick reply buttons, escalation flow
- **User impact:** Captures a lightweight satisfaction signal. More importantly, it provides a graceful exit from an answer — without it, users who got an answer don't know what to do next and the conversation dies awkwardly.

---

### Answer Length Truncation with "Read More"

- **Description:** If a product Q&A answer from the vault is longer than ~600 characters, truncate it in the Messenger message and append a "Read more" quick reply that sends the full answer in a follow-up message (or links to an external page).
- **Complexity:** Low
- **Dependencies:** Product Q&A flow, FastAPI answer endpoint
- **User impact:** Messenger messages over ~600 characters render poorly on mobile — the message card becomes very tall and users scroll past it. Truncation with continuation keeps the conversation readable.
- **Note:** This is a content formatting concern, not a UX flow concern. The FastAPI layer should handle truncation logic so the bot layer stays simple.

---

### Escalation Context Forwarding

- **Description:** When a user escalates to a human, include a summary of what the user was asking about in the escalation notification (e.g., "User was asking about: Skincare / Ingredients"). The admin sees context without having to scroll back through the conversation.
- **Complexity:** Low (if session state tracks the navigation path)
- **Dependencies:** Session state, escalation flow
- **User impact:** Reduces admin response time. Without context, the admin has to read back through the conversation to understand the issue before responding.

---

### Obsidian Vault Hot-Reload (No Restart Required)

- **Description:** The FastAPI backend reads vault files on each request rather than caching them at startup. Content updates in Obsidian are reflected immediately without restarting the service.
- **Complexity:** Low (read file per request rather than at startup)
- **Dependencies:** Obsidian vault reader
- **User impact:** Enables the Govi team to update product Q&A content in Obsidian and have it live instantly. If the vault is cached at startup, a service restart is required for every content change — which defeats the purpose of Obsidian as the CMS.
- **Trade-off:** Slightly higher I/O per request. For the expected request volume of a single-brand support bot, this is negligible.

---

## Anti-Features (Don't Build in v1)

These are features that seem useful but would add disproportionate complexity, scope risk, or maintenance burden at this stage. Each has a "instead" note for how to handle the underlying need without building the feature.

---

- **Free-text NLP / intent detection:** Parsing user-typed messages to detect intent requires an ML model or LLM, which is explicitly out of scope. The fallback handler covers this: unrecognized input → re-present the menu. Do not add any keyword matching or regex-based intent logic — it creates maintenance burden and fails unpredictably. Instead: tight menu design eliminates the need for NLP.

- **Order tracking / order status lookup:** No store backend is connected. Even a stub would mislead users into expecting functionality that does not exist. Instead: include "Order questions" as an escalation path to a human.

- **Multi-language support:** Requires either duplicate vault content in each language or a translation layer. English-only for v1. Instead: single vault in English, escalate non-English users to a human.

- **Custom admin web UI:** Obsidian is the content management interface. Building a separate web UI duplicates the CMS problem Obsidian already solves. Instead: document the Obsidian vault file format clearly so content authors can work without developer help.

- **Proactive / outbound messaging:** Sending messages to users without them initiating contact requires the `pages_messaging` permission with approved use case, 24-hour messaging window enforcement, and message tag compliance. Complex regulatory overhead. Instead: respond-only (user initiates all conversations).

- **Conversation history persistence across sessions for users:** Storing per-user conversation history in a database to provide continuity across sessions adds a DB dependency, PII concerns (Messenger PSID is a user identifier), and session management complexity. The bot's stateless menu model does not require history. Instead: always greet returning users with the main menu — it is the correct starting state for a rule-based bot.

- **Rich media cards / carousels for product browsing:** Messenger generic templates (carousels) look good in demos but require structured product data (images, prices, URLs) that does not exist in the Obsidian vault. Instead: text-based answers from the vault, with an optional URL link if the vault content includes one.

- **Sentiment detection / escalation triggers:** Detecting frustration in free text and auto-escalating requires NLP. Out of scope. Instead: explicit "Talk to a person" option always visible in the persistent menu.

- **Analytics dashboard:** A dashboard for tracking conversation metrics (most asked questions, escalation rate) requires a separate data pipeline and storage. Instead: Facebook Page Insights provides basic conversation volume data for free. Add analytics in v2 once content patterns are stable.

---

## Feature Dependencies (Build Order)

The table stakes features have a natural dependency chain that determines implementation order:

```
1. Webhook event handling + postback routing
        |
        v
2. Messenger Profile API setup (Get Started button + Persistent Menu)
        |
        v
3. Quick reply button sender (message send wrapper)
        |
        v
4. Menu state machine (tracks where user is in the flow)
        |
        v
5. Obsidian vault reader in FastAPI (reads markdown, returns answer by key)
        |
        v
6. Product Q&A flow (wires menu state to vault reader)
        |
        v
7. Escalation flow + Handover Protocol setup
        |
        v
8. Fallback handler + session restart logic
```

Differentiators can be layered on after step 6 (typing indicator, "Was this helpful?") and step 7 (escalation context forwarding).

---

## Messenger Platform Constraints (Affects Feature Design)

These are hard platform limits that affect how features must be built. They are not design choices — they are constraints imposed by Facebook.

| Constraint | Limit | Impact |
|------------|-------|--------|
| Quick replies per message | 13 max | Menu branches cannot have more than 13 options |
| Quick reply label length | 20 characters | Menu item names must be short |
| Persistent menu top-level items | 3 max | Only 3 top-level categories |
| Persistent menu items per level | 5 max | Categories can have at most 5 sub-items |
| Message text length | 2000 characters | Long answers need truncation logic |
| 24-hour messaging window | Cannot message after 24h of user inactivity without a tag | Bot can only respond, not initiate |
| Handover Protocol | Required for bot-to-human handoff | Must configure Page inbox as secondary receiver |

---

## MVP Feature Set

Build in this order for a working v1:

1. Get Started + welcome message
2. Persistent menu with 2-3 top-level items
3. Quick reply navigation
4. Product Q&A flow (one product category as proof of concept)
5. Fallback handler
6. Human escalation with Handover Protocol

Add after MVP is stable:

- "Was this helpful?" confirmation
- Typing indicator
- Escalation context forwarding
- Full product category coverage in the vault
