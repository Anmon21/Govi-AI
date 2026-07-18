---
slug: landing-page-chatbot-options
created: 2026-05-28
status: in_progress
---

# Quick Task: Chatbot Options Landing Page

## Goal
Add a static landing page served from FastAPI that presents 2 chatbot product options to potential clients:
1. **Classic Chatbot** — rule-based, recommended for low-budget clients
2. **AI Chatbot (Mongolian)** — AI-powered in Mongolian, recommended for higher-budget clients

## Steps

1. Create `static/landing.html` — full landing page HTML with both options, budget selector, and recommendation logic
2. Update `app/main.py` — mount `StaticFiles` at `/static` and add a redirect route so `/` or `/landing` serves the page
3. Verify FastAPI serves it correctly with `uvicorn`

## Files Changed
- `static/landing.html` (new)
- `app/main.py` (add StaticFiles mount + route)
- `requirements.txt` (add `aiofiles` if not present — required by FastAPI StaticFiles)
