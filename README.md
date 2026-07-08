# AI Detailing Receptionist

> AI missed-call assistant for auto detailers.
> Never lose another detailing lead from missed calls.

A small, opinionated MVP of an AI receptionist for auto detailing shops and mobile
detailers. When a customer calls or chats, the AI answers, captures the vehicle
details, service interest, preferred time and contact info, then texts the owner a
clean lead summary and shows it in a Lead Inbox dashboard.

The demo business is **OC Elite Detailing** in Orange County, CA. To re-skin this for
another shop, edit `backend/business_data.json`.

---

## What it does

| Channel | What happens |
|---|---|
| **Inbound phone (Twilio)** | AI picks up, greets the caller for the shop, has a structured conversation, captures the lead, and continues asking questions until they hang up. |
| **Inbound SMS (Twilio)** | Customer texts the shop's Twilio number; the AI replies via SMS using the same conversation engine. Multi-turn conversations resume per phone number. Customer's phone is captured automatically. |
| **Web chat widget** | Embeddable JS widget that hits the same backend over WebSocket (HTTP fallback). |
| **Owner SMS** | When a lead becomes "qualified" (contact info + service / vehicle / preferred date), Twilio texts a one-line summary to the owner's phone. |
| **Owner dashboard** | Next.js Lead Inbox with status workflow (`new → contacted → booked / lost / resolved`), suggested replies, transcripts, and service/business pages. |

It deliberately does *not* try to be a full CRM, scheduling system, or POS.
The goal is to make sure no inbound detailing lead is ever lost.

---

## Repo layout

```
backend/                        FastAPI app (Python)
  main.py                       Routes: Twilio, chat, widget, leads API
  call_flow.py                  Conversation logic + lead extraction (LLM JSON)
  lead_store.py                 Lead model + JSON-file store
  sms_notify.py                 Owner SMS via Twilio
  intents.py                    Detailing intents (ML → rule → LLM fallback)
  twilio_handler.py             Twilio voice webhooks
  websocket_handler.py          Real-time chat
  rag.py                        ChromaDB-backed Q&A from business_data.json
  business_data.json            Demo shop profile (OC Elite Detailing)
  ml_models/                    Sklearn intent classifier (optional)
  data/                         Training + eval data for the classifier
  tests/                        Pytest tests
frontend/                       Next.js owner dashboard
  src/app/(dashboard)/inbox/    Lead Inbox (main view)
  src/app/(dashboard)/calls/    Per-turn QA log
  src/app/(dashboard)/appointments/
  src/app/(dashboard)/services/
  src/app/(dashboard)/business-settings/
  src/app/(dashboard)/settings/
website/                        Marketing site (served by FastAPI at /)
widget/                         Embeddable chat widget (vanilla JS/CSS)
scripts/                        Seeding + training utilities
```

---

## Quickstart (demo mode)

```bash
# 1. Python deps
pip install -r backend/requirements.txt

# 2. Env vars (copy and fill in real values)
cp .env.example .env

# 3. (Optional but recommended) Seed demo leads so the dashboard isn't empty
python scripts/seed_demo_leads.py --replace

# 4. Start the backend (port 8000)
python run.py

# 5. In another shell, start the owner dashboard (port 3002)
cd frontend
npm install
npx next dev -p 3002
```

Then:

- Marketing site + chat widget: <http://localhost:8000>
- Owner Lead Inbox: <http://localhost:3002/inbox>
- Standalone widget smoke test: open `test_chat.html` in a browser

You'll see 5 seeded demo leads (Tesla Model 3 ceramic coating, BMW M4 paint
correction, Toyota Camry full detail, Ford F-150 mobile interior, Mercedes C-Class
mobile full detail) in the Lead Inbox.

---

## Key environment variables

| Var | Required for | Notes |
|---|---|---|
| `OPENAI_API_KEY` | LLM responses + lead extraction | Falls back to a deterministic reply if missing |
| `OPENAI_MODEL` | Choose model | Default `gpt-4o-mini` |
| `TWILIO_ACCOUNT_SID` / `TWILIO_AUTH_TOKEN` / `TWILIO_PHONE_NUMBER` | Phone calls + owner SMS | Owner SMS no-ops if Twilio creds are missing |
| `OWNER_SMS_NUMBER` | Owner SMS | If unset, lead is still captured; SMS is just skipped |
| `DEFAULT_BUSINESS_ID` | Backend bootstrap | Default `oc_elite_detailing` |
| `OWNER_DASHBOARD_URL` | Redirect from backend `/owner/orders` and `/inbox` | Default `http://localhost:3002/inbox` |
| `NEXT_PUBLIC_API_BASE` | Frontend → backend URL | Default `http://127.0.0.1:8000` |

---

## API surface

| Method | Path | Purpose |
|---|---|---|
| GET | `/` | Marketing site |
| GET | `/health` | Health check |
| POST | `/api/twilio/voice/incoming` | Twilio inbound call webhook |
| POST | `/api/twilio/voice/process` | Twilio speech-result webhook |
| POST | `/api/twilio/voice/status` | Twilio call status webhook |
| POST | `/api/twilio/sms/incoming` | Twilio inbound SMS webhook |
| POST | `/api/chat/message` | HTTP chat (widget fallback) |
| WS | `/api/chat/ws` | Real-time chat (widget) |
| GET | `/widget/widget.js` / `/widget/widget.css` | Widget assets |
| GET | `/api/leads` | List leads (Lead Inbox) |
| GET | `/api/leads/{id}` | Get one lead |
| POST | `/api/leads/{id}/status` | Update status (`new \| contacted \| booked \| lost \| resolved`) |
| GET | `/api/business` | Read-only business profile |
| GET | `/api/owner/orders` | Per-turn conversation log (Calls tab) |

---

## The Lead model

Captured progressively across the conversation:

```
id, business_id, call_sid, channel, status, ai_confidence,
customer_name, customer_phone,
vehicle_year, vehicle_make, vehicle_model, vehicle_color,
service_requested, condition_notes,
mobile_or_shop_preference, customer_location,
preferred_date, preferred_time, urgency, budget_signal,
lead_summary,
owner_notified, owner_notified_at,
transcript[], created_at, updated_at
```

A lead becomes "qualified" (and triggers the one-time owner SMS) when it has
a contact handle (phone or name) **and** at least one of `service_requested`,
`vehicle_make`, or `preferred_date`.

---

## How the AI decides what to say

For each customer turn `backend/call_flow.py`:

1. Classifies intent (`backend/intents.classify_intent`, `auto` mode):
   ML model → rule-based keywords → LLM fallback.
2. Runs a cheap regex pre-pass to extract obvious slots (phone numbers,
   vehicle make/color/year, urgency, mobile vs shop).
3. For cheap intents (hours, location, service area, mobile service, services
   list, greeting, goodbye) it returns a templated answer with **no LLM call**.
4. Otherwise, one LLM call generates **both** the customer-facing reply and the
   structured lead-slot updates as JSON.
5. Merges new slots into the lead, writes to `backend/leads_log.json`.
6. The first time the lead is qualified, `notify_owner` fires a Twilio SMS to
   `OWNER_SMS_NUMBER`.

---

## Phone demo (Twilio)

1. Buy a Twilio number.
2. Expose port 8000 via ngrok / Cloudflare Tunnel.
3. In the Twilio console for that number:
   - **Voice** → "A CALL COMES IN" → webhook → `POST https://<tunnel>/api/twilio/voice/incoming`
   - **Voice** → "CALL STATUS CHANGES" → webhook → `POST https://<tunnel>/api/twilio/voice/status`
   - **Messaging** → "A MESSAGE COMES IN" → webhook → `POST https://<tunnel>/api/twilio/sms/incoming`
4. Set `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER`, and
   `OWNER_SMS_NUMBER` in `.env`.
5. Call **or text** the number.

The voice greeting is `Thanks for calling {business_name}. How can we help with
your vehicle today?`. For SMS the AI's first reply uses the same conversational
greeting, and the customer's phone is captured automatically from Twilio's `From`
header — they don't need to give it again.

### SMS compliance keywords

`STOP / STOPALL / UNSUBSCRIBE / CANCEL / END / QUIT` always returns the
unsubscribe confirmation without touching the LLM.

`HELP / INFO` returns the business name plus how to reach a human, also without
touching the LLM.

### SMS multi-turn

The AI keeps a per-phone-number conversation alive indefinitely, so a customer
can text back and forth across hours or days and the AI still knows the
vehicle, service, and other slots they've already provided.

---

## Tests

```bash
pip install pytest pytest-asyncio
pytest backend/tests -v
```

---

## Re-skinning for another shop

Almost all customer-facing text is derived from `backend/business_data.json`:
business name, services + price ranges, hours, mobile service radius and cities,
FAQ, AI persona, and owner notification config. The widget greeting and the
marketing site (`website/index.html`) are the two places where the
"OC Elite Detailing" copy is hard-coded — replace those when re-skinning.

---

## Safety / quality rules the AI follows

(See `business_data.json -> ai_persona.safety_rules` and the system prompt in
`call_flow._SYSTEM_PROMPT_TEMPLATE`.)

- Never guarantees an exact price; always offers a range and says the team will
  confirm after seeing the vehicle.
- Never promises ceramic coating prevents all scratches.
- Never books outside business hours.
- Never books mobile service outside the ~25-mile radius without flagging it.
- Always tries to capture name + phone before ending a qualified lead.
- Always saves the transcript and lead summary.

---

## License

MIT.
