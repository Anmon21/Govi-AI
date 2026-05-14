import "dotenv/config";
import express, { Request, Response, NextFunction } from "express";
import axios from "axios";
import crypto from "crypto";

const app = express();

const VERIFY_TOKEN = process.env.FACEBOOK_VERIFY_TOKEN!;
const PAGE_ACCESS_TOKEN = process.env.FACEBOOK_PAGE_ACCESS_TOKEN!;
const GOVI_AI_URL = process.env.GOVI_AI_URL ?? "http://localhost:8000";
const APP_SECRET = process.env.FACEBOOK_APP_SECRET; // optional — skip verification if absent

if (!APP_SECRET) {
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
        await handleWebhookEvent(event);
      }
    }
  }
);

export const GRAPH_API_VERSION = "v21.0";

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
    const axiosErr = err as import("axios").AxiosError;
    // SEC-03: Never log the full axios error object (contains PAGE_ACCESS_TOKEN in config.url)
    console.error("sendMessage failed:", axiosErr.message, axiosErr.response?.data);
  }
}

export const MAIN_MENU_QUICK_REPLIES: QuickReply[] = [
  { content_type: "text", title: "Product Help", payload: "MENU_PRODUCT_HELP" },
  { content_type: "text", title: "Contact Human", payload: "MENU_CONTACT_HUMAN" },
];

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

  if (event.postback) {
    // Additional postback payloads handled in Phase 2+
    console.log("Postback received:", event.postback.payload);
    return;
  }

  if (event.message?.quick_reply) {
    // Quick reply tap — PITFALL 6: must check before message.text (quick_reply also sets text)
    console.log("Quick reply received:", event.message.quick_reply.payload);
    return;
  }

  if (event.message?.text) {
    console.log(`[${senderId}] ${event.message.text}`);
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
    const axiosErr = err as import("axios").AxiosError;
    console.error("Messenger profile setup failed:", axiosErr.message, axiosErr.response?.data);
  }
}

const port = process.env.PORT ?? 3000;
app.listen(port, () => {
  console.log(`Messenger bot listening on port ${port}`);
  setupMessengerProfile();
});
