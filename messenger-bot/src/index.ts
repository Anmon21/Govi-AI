import "dotenv/config";
import express, { Request, Response } from "express";
import axios from "axios";

const app = express();
app.use(express.json());

const VERIFY_TOKEN = process.env.FACEBOOK_VERIFY_TOKEN!;
const PAGE_ACCESS_TOKEN = process.env.FACEBOOK_PAGE_ACCESS_TOKEN!;
const GOVI_AI_URL = process.env.GOVI_AI_URL ?? "http://localhost:8000";

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
app.post("/webhook", async (req: Request, res: Response) => {
  const body = req.body;

  if (body.object !== "page") {
    res.sendStatus(404);
    return;
  }

  // Acknowledge receipt immediately — Facebook requires this within 20s
  res.sendStatus(200);

  for (const entry of body.entry ?? []) {
    for (const event of entry.messaging ?? []) {
      if (!event.message?.text) continue;

      const senderId: string = event.sender.id;
      const userText: string = event.message.text;

      console.log(`[${senderId}] ${userText}`);

      try {
        const { data } = await axios.post(`${GOVI_AI_URL}/ai/chat`, {
          message: userText,
        });

        await sendMessage(senderId, data.reply);
      } catch (err) {
        console.error("Error calling Govi AI:", err);
        await sendMessage(senderId, "Sorry, something went wrong. Please try again.");
      }
    }
  }
});

async function sendMessage(recipientId: string, text: string): Promise<void> {
  await axios.post(
    `https://graph.facebook.com/v19.0/me/messages`,
    {
      recipient: { id: recipientId },
      message: { text },
    },
    {
      params: { access_token: PAGE_ACCESS_TOKEN },
    }
  );
}

const port = process.env.PORT ?? 3000;
app.listen(port, () => {
  console.log(`Messenger bot listening on port ${port}`);
});
