import "dotenv/config";
import express, { Request, Response, NextFunction } from "express";
import axios from "axios";
import crypto from "crypto";

if (!process.env.FACEBOOK_VERIFY_TOKEN) {
  console.error("FACEBOOK_VERIFY_TOKEN is not set — refusing to start. Configure it in messenger-bot/.env and restart.");
  process.exit(1);
}

const app = express();

const VERIFY_TOKEN = process.env.FACEBOOK_VERIFY_TOKEN!;
const PAGE_ACCESS_TOKEN = process.env.FACEBOOK_PAGE_ACCESS_TOKEN!;
const GOVI_AI_URL = process.env.GOVI_AI_URL ?? "http://localhost:8000";

if (!process.env.FACEBOOK_APP_SECRET) {
  console.warn("FACEBOOK_APP_SECRET not set — skipping webhook signature verification");
}

export interface QuickReply {
  content_type: "text";
  title: string;   // ≤20 chars
  payload: string; // ≤1000 chars
}

export function verifySignature(req: Request, res: Response, next: NextFunction): void {
  const appSecret = process.env.FACEBOOK_APP_SECRET;
  if (!appSecret) {
    console.warn("FACEBOOK_APP_SECRET not set — skipping webhook signature verification");
    let parsed: unknown;
    try {
      parsed = JSON.parse((req.body as Buffer).toString("utf8"));
    } catch {
      res.sendStatus(400);
      return;
    }
    (req as any).parsedBody = parsed;
    next();
    return;
  }

  const signature = req.headers["x-hub-signature-256"] as string | undefined;
  if (!signature) {
    console.warn("Webhook signature mismatch — check FACEBOOK_APP_SECRET");
    res.sendStatus(403);
    return;
  }

  const rawBody = req.body as Buffer;
  const expected = `sha256=${crypto.createHmac("sha256", appSecret).update(rawBody).digest("hex")}`;
  const expectedBuf = Buffer.from(expected, "utf8");
  const signatureBuf = Buffer.from(signature, "utf8");

  if (
    expectedBuf.length !== signatureBuf.length ||
    !crypto.timingSafeEqual(expectedBuf, signatureBuf)
  ) {
    console.warn("Webhook signature mismatch — check FACEBOOK_APP_SECRET");
    res.sendStatus(403);
    return;
  }

  let parsedBody: unknown;
  try {
    parsedBody = JSON.parse(rawBody.toString("utf8"));
  } catch {
    res.sendStatus(400);
    return;
  }
  (req as any).parsedBody = parsedBody;
  next();
}

// Webhook verification — Facebook calls this once when you register the webhook
app.get("/webhook", (req: Request, res: Response) => {
  const mode = req.query["hub.mode"];
  const token = req.query["hub.verify_token"];
  const challenge = req.query["hub.challenge"];

  if (mode === "subscribe" && token === VERIFY_TOKEN) {
    console.log("Webhook verified");
    res.status(200).send(challenge);
  } else {
    res.sendStatus(403);
  }
});

// Incoming messages from Facebook Messenger
app.post(
  "/webhook",
  express.raw({ type: "*/*" }),
  verifySignature,
  async (req: Request, res: Response) => {
    const body = (req as any).parsedBody;

    if (body.object !== "page") {
      res.sendStatus(404);
      return;
    }

    // Acknowledge receipt immediately — Facebook requires this within 20s
    res.sendStatus(200);

    for (const entry of body.entry ?? []) {
      for (const event of entry.messaging ?? []) {
        try {
          await handleWebhookEvent(event);
        } catch (err: unknown) {
          console.error("handleWebhookEvent failed (unexpected):", err instanceof Error ? err.message : String(err));
        }
      }
    }
  }
);

export const GRAPH_API_VERSION = "v21.0";
export const PAGE_INBOX_APP_ID = "263902037430900";
export const lastMessageCache = new Map<string, string>();

export async function sendMessage(recipientId: string, text: string, quickReplies?: QuickReply[]): Promise<void> {
  const messagePayload: Record<string, unknown> = { text };
  if (quickReplies && quickReplies.length > 0) {
    messagePayload.quick_replies = quickReplies;
  }

  try {
    const response = await axios.post(
      `https://graph.facebook.com/${GRAPH_API_VERSION}/me/messages`,
      {
        recipient: { id: recipientId },
        message: messagePayload,
      },
      {
        params: { access_token: PAGE_ACCESS_TOKEN },
      }
    );

    // SEC-02: Facebook returns errors inside HTTP 200
    if (response.data?.error) {
      console.error("Graph API error:", response.data.error.message, response.data.error);
    }
  } catch (err: unknown) {
    // SEC-03: Never log the full axios error object (contains PAGE_ACCESS_TOKEN in config.url)
    if (axios.isAxiosError(err)) {
      console.error("sendMessage failed:", err.message, err.response?.data);
    } else {
      console.error("sendMessage failed (unexpected error):", err instanceof Error ? err.message : String(err));
    }
  }
}

export async function passThreadControl(recipientId: string): Promise<void> {
  try {
    const response = await axios.post(
      `https://graph.facebook.com/${GRAPH_API_VERSION}/me/pass_thread_control`,
      {
        recipient: { id: recipientId },
        target_app_id: PAGE_INBOX_APP_ID,
      },
      { params: { access_token: PAGE_ACCESS_TOKEN } }
    );
    if (response.data?.error) {
      console.error("pass_thread_control Graph API error:", response.data.error.message, response.data.error);
    }
  } catch (err: unknown) {
    // SEC-03: never log the full axios error (config.url contains PAGE_ACCESS_TOKEN)
    if (axios.isAxiosError(err)) {
      console.error("passThreadControl failed:", err.message, err.response?.data);
    } else {
      console.error("passThreadControl failed (unexpected):", err instanceof Error ? err.message : String(err));
    }
  }
}

export async function sendTypingIndicator(
  recipientId: string,
  action: "typing_on" | "typing_off"
): Promise<void> {
  try {
    await axios.post(
      `https://graph.facebook.com/${GRAPH_API_VERSION}/me/messages`,
      {
        recipient: { id: recipientId },
        sender_action: action,
      },
      { params: { access_token: PAGE_ACCESS_TOKEN } }
    );
  } catch (err: unknown) {
    // SEC-03: Never log the full axios error (config.url contains PAGE_ACCESS_TOKEN)
    if (axios.isAxiosError(err)) {
      console.error("sendTypingIndicator failed:", err.message, err.response?.data);
    } else {
      console.error("sendTypingIndicator failed (unexpected error):", err instanceof Error ? err.message : String(err));
    }
  }
}

export async function handleEscalation(senderId: string): Promise<void> {
  const lastMessage = lastMessageCache.get(senderId);
  const adminPsid = process.env.ADMIN_PSID;

  if (!adminPsid) {
    console.warn("ADMIN_PSID not configured — escalation degraded");
    await sendMessage(senderId, "Thanks for reaching out! We'll be in touch as soon as possible.", MAIN_MENU_QUICK_REPLIES);
    return;
  }

  const contextLine = lastMessage ? `\nLast message: "${lastMessage}"` : "";
  await sendMessage(adminPsid, `A customer (${senderId}) requested human support.${contextLine}\nPlease reply from the Page Inbox.`);
  // Send customer confirmation BEFORE passThreadControl — bot must own the thread at send time (Pitfall 1)
  await sendMessage(senderId, "Connecting you with a human — we'll be with you shortly!");
  await passThreadControl(senderId);
}

export const MAIN_MENU_QUICK_REPLIES: QuickReply[] = [
  { content_type: "text", title: "Product Help", payload: "MENU_PRODUCT_HELP" },
  { content_type: "text", title: "Contact Human", payload: "MENU_CONTACT_HUMAN" },
];

export const FEEDBACK_QUICK_REPLIES: QuickReply[] = [
  { content_type: "text", title: "Was it helpful? Yes", payload: "HELPFUL_YES" },
  { content_type: "text", title: "Was it helpful? No",  payload: "HELPFUL_NO" },
];

export const PAYLOAD_HELPFUL_YES = "HELPFUL_YES";
export const PAYLOAD_HELPFUL_NO  = "HELPFUL_NO";

export const PAYLOAD_PREFIX_CATEGORY = "CATEGORY:";
export const PAYLOAD_PREFIX_QUESTION = "QUESTION:";
export const ANSWER_THRESHOLD = 200;
export const PAYLOAD_PREFIX_READ_MORE = "READ_MORE:";

async function sendApologyWithMenu(recipientId: string): Promise<void> {
  await sendMessage(
    recipientId,
    "Something went wrong fetching that — back to the main menu:",
    MAIN_MENU_QUICK_REPLIES
  );
}

export async function sendCategoryMenu(recipientId: string): Promise<void> {
  try {
    const response = await axios.get(`${GOVI_AI_URL}/content?type=category`);
    const items: Array<{ id: string; title: string }> = response.data?.items ?? [];
    if (items.length === 0) {
      await sendMessage(
        recipientId,
        "No product topics available yet — back to the main menu:",
        MAIN_MENU_QUICK_REPLIES
      );
      return;
    }
    const quickReplies: QuickReply[] = items.slice(0, 13).map((item) => ({
      content_type: "text",
      title: item.title,
      payload: `${PAYLOAD_PREFIX_CATEGORY}${item.id}`,
    }));
    await sendMessage(recipientId, "Pick a topic:", quickReplies);
  } catch (err: unknown) {
    if (axios.isAxiosError(err)) {
      console.error("sendCategoryMenu failed:", err.message, err.response?.data);
    } else {
      console.error("sendCategoryMenu failed (unexpected error):", err instanceof Error ? err.message : String(err));
    }
    await sendApologyWithMenu(recipientId);
  }
}

export async function sendQuestionMenu(recipientId: string, categoryId: string): Promise<void> {
  try {
    const url = `${GOVI_AI_URL}/content?type=question&category=${encodeURIComponent(categoryId)}`;
    const response = await axios.get(url);
    const items: Array<{ id: string; title: string }> = response.data?.items ?? [];
    if (items.length === 0) {
      await sendMessage(
        recipientId,
        "No questions in that topic yet — back to the main menu:",
        MAIN_MENU_QUICK_REPLIES
      );
      return;
    }
    const truncated = items.slice(0, 12);
    const quickReplies: QuickReply[] = truncated.map((item) => ({
      content_type: "text",
      title: item.title,
      payload: `${PAYLOAD_PREFIX_QUESTION}${item.id}`,
    }));
    // If we truncated, give the user an escape hatch
    if (items.length > 12) {
      quickReplies.push({ content_type: "text", title: "Main menu", payload: "MENU_MAIN" });
    }
    await sendMessage(recipientId, "Pick a question:", quickReplies);
  } catch (err: unknown) {
    if (axios.isAxiosError(err)) {
      console.error("sendQuestionMenu failed:", err.message, err.response?.data);
    } else {
      console.error("sendQuestionMenu failed (unexpected error):", err instanceof Error ? err.message : String(err));
    }
    await sendApologyWithMenu(recipientId);
  }
}

export async function sendAnswer(recipientId: string, questionId: string): Promise<void> {
  await sendTypingIndicator(recipientId, "typing_on");
  try {
    const response = await axios.get(`${GOVI_AI_URL}/content/${encodeURIComponent(questionId)}`);
    const body: string | undefined = response.data?.body;
    if (typeof body !== "string" || body.length === 0) {
      await sendApologyWithMenu(recipientId);
      return;
    }
    if (body.length > ANSWER_THRESHOLD) {
      const cutIndex = body.lastIndexOf(" ", ANSWER_THRESHOLD);
      const preview = cutIndex > 0 ? body.slice(0, cutIndex) + "..." : body.slice(0, ANSWER_THRESHOLD) + "...";
      const readMoreReply: QuickReply = {
        content_type: "text",
        title: "Read more",
        payload: `${PAYLOAD_PREFIX_READ_MORE}${questionId}`,
      };
      await sendMessage(recipientId, preview, [readMoreReply]);
    } else {
      await sendMessage(recipientId, body, FEEDBACK_QUICK_REPLIES);
    }
  } catch (err: unknown) {
    if (axios.isAxiosError(err)) {
      console.error("sendAnswer failed:", err.message, err.response?.data);
    } else {
      console.error("sendAnswer failed (unexpected error):", err instanceof Error ? err.message : String(err));
    }
    await sendApologyWithMenu(recipientId);
  } finally {
    await sendTypingIndicator(recipientId, "typing_off");
  }
}

export async function sendReadMoreAnswer(recipientId: string, questionId: string): Promise<void> {
  await sendTypingIndicator(recipientId, "typing_on");
  try {
    const response = await axios.get(`${GOVI_AI_URL}/content/${encodeURIComponent(questionId)}`);
    const body: string | undefined = response.data?.body;
    if (typeof body !== "string" || body.length === 0) {
      await sendApologyWithMenu(recipientId);
      return;
    }
    await sendMessage(recipientId, body, FEEDBACK_QUICK_REPLIES);
  } catch (err: unknown) {
    if (axios.isAxiosError(err)) {
      console.error("sendReadMoreAnswer failed:", err.message, err.response?.data);
    } else {
      console.error("sendReadMoreAnswer failed (unexpected error):", err instanceof Error ? err.message : String(err));
    }
    await sendApologyWithMenu(recipientId);
  } finally {
    await sendTypingIndicator(recipientId, "typing_off");
  }
}

export async function sendWelcomeMessage(recipientId: string): Promise<void> {
  await sendMessage(
    recipientId,
    "Welcome to Govi! I can help with product questions or connect you with a human.",
    MAIN_MENU_QUICK_REPLIES
  );
}

export async function sendFallbackMessage(recipientId: string): Promise<void> {
  await sendMessage(
    recipientId,
    "I work best with the buttons below — here's what I can help with:",
    MAIN_MENU_QUICK_REPLIES
  );
}

export async function handleWebhookEvent(event: any): Promise<void> {
  const senderId: string = event.sender?.id;
  if (!senderId) return;

  if (event.postback?.payload === "GET_STARTED") {
    await sendWelcomeMessage(senderId);
    return;
  }

  if (event.postback?.payload === "MENU_CONTACT_HUMAN") {
    await handleEscalation(senderId);
    return;
  }

  if (event.postback?.payload === "MENU_PRODUCT_HELP") {
    await sendCategoryMenu(senderId);
    return;
  }

  if (event.postback?.payload === "MENU_MAIN") {
    await sendWelcomeMessage(senderId);
    return;
  }

  if (event.postback) {
    // Additional postback payloads handled in Phase 2+
    console.log("Postback received:", event.postback.payload);
    return;
  }

  if (event.message?.quick_reply) {
    // Quick reply tap — PITFALL 6: must check before message.text (quick_reply also sets text)
    const payload: string = event.message.quick_reply.payload ?? "";
    console.log("Quick reply received:", payload);
    if (payload === "MENU_PRODUCT_HELP") {
      await sendCategoryMenu(senderId);
      return;
    }
    if (payload === "MENU_MAIN") {
      await sendWelcomeMessage(senderId);
      return;
    }
    if (payload === "MENU_CONTACT_HUMAN") {
      await handleEscalation(senderId);
      return;
    }
    if (payload.startsWith(PAYLOAD_PREFIX_CATEGORY)) {
      const categoryId = payload.slice(PAYLOAD_PREFIX_CATEGORY.length);
      if (categoryId) {
        await sendQuestionMenu(senderId, categoryId);
        return;
      }
    }
    if (payload.startsWith(PAYLOAD_PREFIX_QUESTION)) {
      const questionId = payload.slice(PAYLOAD_PREFIX_QUESTION.length);
      if (questionId) {
        await sendAnswer(senderId, questionId);
        return;
      }
    }
    if (payload.startsWith(PAYLOAD_PREFIX_READ_MORE)) {
      const questionId = payload.slice(PAYLOAD_PREFIX_READ_MORE.length);
      if (questionId) {
        await sendReadMoreAnswer(senderId, questionId);
        return;
      }
    }
    if (payload === "HELPFUL_YES") {
      await sendMessage(
        senderId,
        "Glad that helped! Let me know if you need anything else.",
        MAIN_MENU_QUICK_REPLIES
      );
      return;
    }
    if (payload === "HELPFUL_NO") {
      await handleEscalation(senderId);
      return;
    }
    // Unknown / malformed payload — re-anchor instead of going silent
    await sendFallbackMessage(senderId);
    return;
  }

  if (event.message?.text) {
    console.log(`[${senderId}] ${event.message.text}`);
    lastMessageCache.set(senderId, event.message.text);
    // CORE-04: Free text fallback — never a silent dead end
    await sendFallbackMessage(senderId);
    return;
  }
}

// Greeting + persistent-menu copy are placeholders per D-05 — user may adjust before go-live
export async function setupMessengerProfile(): Promise<void> {
  try {
    await axios.post(
      `https://graph.facebook.com/${GRAPH_API_VERSION}/me/messenger_profile`,
      {
        get_started: { payload: "GET_STARTED" },
        greeting: [
          {
            locale: "default",
            text: "Hi! I'm the Govi support bot. Ask me about products or talk to a human.",
          },
        ],
        persistent_menu: [
          {
            locale: "default",
            composer_input_disabled: false,
            call_to_actions: [
              { type: "postback", title: "Product Help", payload: "MENU_PRODUCT_HELP" },
              { type: "postback", title: "Contact Human", payload: "MENU_CONTACT_HUMAN" },
              { type: "postback", title: "Main Menu", payload: "MENU_MAIN" },
            ],
          },
        ],
      },
      { params: { access_token: PAGE_ACCESS_TOKEN } }
    );
    console.log("Messenger profile configured");
  } catch (err: unknown) {
    if (axios.isAxiosError(err)) {
      console.error("Messenger profile setup failed:", err.message, err.response?.data);
    } else {
      console.error("Messenger profile setup failed (unexpected error):", err instanceof Error ? err.message : String(err));
    }
  }
}

const port = process.env.PORT ?? 3000;
app.listen(port, () => {
  console.log(`Messenger bot listening on port ${port}`);
  setupMessengerProfile();
});
