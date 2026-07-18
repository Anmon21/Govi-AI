---
slug: landing-page-chatbot-options
status: complete
completed: 2026-05-28
---

# Summary

Added a Mongolian-language landing page at `/landing` serving two chatbot options for potential clients.

## What was done
- Created `static/landing.html` — full landing page with Classic Chatbot vs AI Chatbot (Mongolian) cards, budget selector (Бага / Дунд / Өндөр), and JS-driven recommendation logic
- Updated `app/main.py` — mounted `StaticFiles` at `/static`, added `GET /landing` route returning the HTML file
- Added `aiofiles>=23.0.0` to `requirements.txt` (required by FastAPI StaticFiles)

## Outcome
- `/landing` serves the page correctly (verified via app route inspection)
- Low budget → Classic Chatbot highlighted; High budget → AI Chatbot highlighted
