# DetailDesk AI — Development Roadmap

DetailDesk AI is an AI receptionist and missed-call recovery SaaS for auto detailers, tint shops, wrap shops, ceramic coating shops, PPF shops, and—later—other high-ticket local service businesses.

This document describes the future development goals for the product. It is the north star for what we build next and what we deliberately defer.

---

## Current MVP Goal

A shop owner keeps their normal business number and forwards missed or unanswered calls to a DetailDesk AI number. The AI answers, qualifies the caller, captures lead details, saves the lead, and notifies the owner with a clean summary.

---

## Future Product Vision

DetailDesk should become a **controllable AI front desk system** where the business owner feels fully in control of their AI receptionist's voice, personality, behavior, rules, transfer logic, notifications, and lead workflow.

### Important Philosophy

**Do not make owners feel like AI is taking over their business.**  
Make them feel like they are configuring their own digital receptionist.

The owner should think:

> *"This is my AI receptionist. I control how it sounds, when it answers, what it says, what it collects, and when it alerts me."*

---

## Product Principle

Every future feature should support one of these outcomes:

- Capture more missed leads
- Help owners respond faster
- Make the AI safer and more controllable
- Increase trust
- Show ROI
- Reduce owner workload
- Improve customer experience

### Avoid

- Random AI features
- Multi-agent complexity too early
- Unnecessary enterprise integrations
- Native mobile app before demand
- Overbuilding before customer feedback

### Final Product Vision

DetailDesk AI is not just an AI receptionist. It is a **controllable AI front desk** for busy service business owners.

The owner controls:

- When it answers
- How it sounds
- How it talks
- What it knows
- What it collects
- When it transfers
- When it texts them
- What it never says
- How it follows up

The product should feel **powerful, but simple**.

---

## 1. Production Readiness

**Priority:** Before onboarding real busy shops, the app needs to feel reliable, secure, and safe.

### Goals

- Move from JSON file storage to Supabase/Postgres
- Add real multi-tenant database structure
- Add dashboard authentication
- Add Twilio webhook signature validation
- Add better error handling and fallback responses
- Add uptime/error monitoring
- Add logging for every call, turn, lead, notification, and failure
- Add safe fallback if OpenAI/Twilio/AI logic fails
- Add notification fallback if SMS fails
- Make partial leads save even when calls fail midway

### Suggested Tables

| Table | Purpose |
|---|---|
| `businesses` | Core tenant record |
| `users` | Dashboard users |
| `services` | Per-business service catalog |
| `business_settings` | Hours, radius, contact info |
| `ai_receptionist_settings` | Voice, tone, answering mode |
| `calls` | Inbound call sessions |
| `call_messages` | Per-turn conversation log |
| `leads` | Qualified and partial leads |
| `appointments` | Booking requests |
| `notifications` | SMS, email, dashboard alerts |
| `transfer_rules` | When to transfer or escalate |
| `guardrails` | Safety and behavior constraints |
| `audit_logs` | Compliance and debugging trail |

---

## 2. AI Receptionist Control Center

Build a main dashboard page where the owner controls how the AI behaves.

**Page name:** AI Receptionist Control Center

### Core Settings

- **AI status:** On / Paused / Off
- **Answering mode:**
  - Missed calls only
  - After-hours only
  - Always answer
  - High-value leads only
  - Off
- Business hours
- Owner notification phone
- Transfer phone number
- AI backup number
- Call forwarding instructions
- Test call button

### Goal

The owner should be able to understand and change the AI's behavior without touching code or prompts.

---

## 3. AI Receptionist Builder

Build a more advanced configuration page that feels like creating a digital front desk employee.

**Page name:** AI Receptionist Builder

### Sections

- Voice & Personality
- Greeting
- Services & Pricing
- Lead Capture Rules
- Transfer Rules
- Guardrails
- Notifications
- Test Your AI

This page should **not** expose raw prompts. It should use simple controls and generate the system prompt/config behind the scenes.

---

## 4. Voice & Personality Controls

Allow owners to customize the AI receptionist's voice and personality.

### Settings

| Category | Options |
|---|---|
| **Voice style** | Female, Male, Neutral |
| **Tone** | Professional, Friendly, Luxury, Calm, Energetic, Short and direct |
| **Personality presets** | Professional Receptionist, Friendly Local Assistant, Luxury Service Advisor, Fast Intake Mode, Bilingual Front Desk |
| **Speaking speed** | Slow, Normal, Fast |
| **Response length** | Short, Balanced, Detailed |
| **Language** | English, Spanish, English + Spanish |

### Goal

Owners should feel like they are choosing the exact front desk experience their customers hear.

---

## 5. Conversation Behavior Controls

Let owners control how the AI talks to customers.

### Settings

- Ask one question at a time
- Ask multiple intake questions quickly
- Give price ranges
- Avoid pricing and collect lead only
- Recommend related services
- No upselling
- Light upselling
- Premium upsell mode
- Always explain that final pricing depends on vehicle size/condition
- Always collect phone before ending call
- Always offer callback if uncertain

---

## 6. Service-Specific Intake Rules

Make lead capture configurable per service. DetailDesk should feel smarter than a generic AI receptionist because it knows what details matter for each auto service.

### Ceramic Coating

**Required fields:**

- Name
- Phone
- Vehicle year/make/model
- Vehicle color
- Paint condition
- Swirls/scratches/water spots
- Preferred date/time
- Timeline

### Paint Correction

**Required fields:**

- Vehicle color
- Swirls/scratches/oxidation
- Desired result
- Inspection preference
- Photos requested

### Mobile Detail

**Required fields:**

- City/location
- Water access
- Power access
- Apartment/house/business
- Vehicle condition
- Preferred date/time

### Tint / PPF / Wrap

**Required fields:**

- Vehicle
- Desired coverage
- Film/tint type if known
- Timeline
- Budget signal
- Preferred appointment

---

## 7. Guardrails

Create owner-controlled safety settings.

### Examples

- Do not guarantee exact prices
- Do not promise scratch removal
- Do not say ceramic coating is scratch-proof
- Do not book outside business hours
- Do not accept jobs outside service radius
- Do not discuss discounts unless enabled
- Do not handle refund complaints without owner callback
- Do not mention competitors
- Do not make promises about availability unless calendar confirms
- Always escalate angry customers
- Always escalate high-value leads if enabled

### Goal

Owners should trust the AI because they can define what it is **not** allowed to say.

---

## 8. Transfer Rules

Allow owners to decide when the AI should transfer or alert them.

### Transfer Triggers

- Caller asks for human
- Angry customer
- Complaint/refund issue
- Same-day urgent request
- Ceramic coating inquiry
- PPF inquiry
- High estimated lead value
- Existing customer
- Unknown question
- Caller calls multiple times

### Transfer Modes

- Transfer immediately
- Ask caller permission first
- Take message only
- Text owner instantly
- Create urgent dashboard lead

### Goal

Owners should feel safe knowing important calls are not trapped inside the AI.

---

## 9. Notification System

Improve what happens after a call.

### Options

- Owner SMS
- Owner email
- Dashboard notification
- Customer confirmation text
- Follow-up reminder
- Hot lead alert
- Missed revenue report
- Notification retry system

### Owner Channel Preferences

- SMS only
- Email only
- Dashboard only
- SMS + dashboard
- SMS + email + dashboard

### Goal

A lead should never disappear because one notification channel fails.

---

## 10. Test Your AI / Preview Mode

Build a demo/test page inside the dashboard.

### Features

- Preview greeting
- Place test call
- Simulate caller asking about ceramic coating
- Simulate caller asking for exact price
- Simulate angry customer
- Simulate Spanish caller
- Simulate high-value PPF lead
- Preview owner SMS summary
- Preview suggested follow-up text

### Goal

Before activating the AI, owners should be able to test and approve how it behaves. This will be a **major adoption feature**.

---

## 11. Onboarding Flow

Make onboarding extremely easy.

### Steps

1. Add business name
2. Add owner phone number
3. Add services and price ranges
4. Add business hours
5. Add service radius
6. Choose AI voice/personality preset
7. Choose answering mode
8. Get AI forwarding number
9. Run test call
10. Activate

### Setup Checklist

- [ ] Business info added
- [ ] Services added
- [ ] AI number assigned
- [ ] Test call completed
- [ ] Forwarding enabled
- [ ] Notifications enabled

### Goal

A non-technical detail owner should be able to set up the AI without confusion.

---

## 12. Call Forwarding Experience

Create a clear setup page for missed-call forwarding.

### Show

- Owner's normal business number
- DetailDesk AI backup number
- Current AI mode
- Setup instructions by carrier

### Supported Carriers / Providers

- AT&T
- Verizon
- T-Mobile
- Google Voice
- RingCentral
- OpenPhone
- Grasshopper

### Actions

- Copy AI number
- Test AI number
- Show forwarding instructions
- Pause AI

### Important

Explain clearly that the **phone provider** controls when calls forward, and **DetailDesk** controls what happens once the call reaches the AI.

---

## 13. Calendar and Booking

### Future Booking Goals

- Google Calendar integration
- Calendly integration
- Booking link by text
- Appointment request workflow
- Prevent booking outside business hours
- Prevent booking outside service radius
- Service-duration logic
- Longer blocks for ceramic coating/PPF/wraps
- Shorter blocks for maintenance washes

### Goal

Start with appointment requests and booking links. Do not overcomplicate full calendar automation until the core lead flow is stable.

---

## 14. Revenue and Retention Features

Add features that help owners see ROI.

### Weekly Report

- Calls answered
- Leads captured
- Hot leads
- Appointments booked
- Estimated recovered value
- Top requested services
- Missed calls recovered
- Follow-ups pending

### Dashboard Metric

**"Estimated recovered revenue this week"**

### Goal

Owners should not think they are paying for software. They should feel DetailDesk **recovered money they would have lost**.

---

## 15. Follow-Up Automation

### Future Follow-Up Features

- Suggested replies
- One-tap SMS
- Follow-up reminders
- Auto-follow-up if owner does not respond
- Review request after completed job
- Maintenance wash reminders
- Ceramic coating maintenance reminders
- Rebooking campaigns

### Goal

DetailDesk should eventually move from missed-call recovery into **customer retention and repeat revenue**.

---

## 16. Compliance and Trust

Add compliance and trust features:

- California all-party consent call recording disclosure
- SMS STOP/HELP handling
- TCPA-conscious customer texting
- Call recording setting
- Data deletion tools
- Privacy policy page
- Terms page
- Audit logs
- Customer data export

### Goal

Make the software feel trustworthy enough for real businesses.

---

## 17. Multi-Tenant SaaS

Eventually support multiple businesses properly.

### Goals

- Each business has isolated settings, leads, calls, services, notifications, and AI config
- Users can belong to one or more businesses
- Admin role vs staff role
- Subscription status controls access
- Stripe billing integration
- Usage limits by plan
- Per-business Twilio number assignment

---

## 18. Pricing and Billing

### Plans

| Plan | Price |
|---|---|
| Starter | $149/mo |
| Growth | $299/mo |
| Pro | $499/mo |

LA/OC beta pricing applies during early rollout.

### Stripe Goals

- Stripe checkout
- Subscription status webhook
- Trial period
- Failed payment handling
- Plan limits

### Plan Limits Could Include

- Number of calls/month
- SMS summaries
- Call transcripts
- Custom workflows
- Bilingual support
- Website chat widget
- Transfer rules

---

## 19. Mobile-First Experience / PWA

**Do not build native iOS/Android first.**

Instead:

- Make dashboard mobile responsive
- Make Lead Inbox feel great on iPhone
- Add PWA support later
- Allow owners to add DetailDesk to home screen
- Owner's main daily experience should be **SMS + mobile lead inbox**

---

## 20. Expansion Roadmap

### Start Narrow

- Auto detailers
- Ceramic coating shops
- Tint shops
- Wrap shops
- PPF shops
- Mobile auto services

### Then Expand

- Mobile mechanics
- Auto body shops
- Towing
- HVAC
- Plumbing
- Electricians
- Garage door companies
- Med spas
- Dentists
- Law firms

### Long-Term Company

AI missed-call recovery and controllable AI receptionist platform for **high-ticket local service businesses**.

**Do not expand too early.** Win the auto-service niche first.

---

## Roadmap Priority Summary

| Phase | Focus | Key Deliverables |
|---|---|---|
| **Phase 1** | Production Readiness | Postgres, auth, webhooks, monitoring, partial lead saves |
| **Phase 2** | Owner Control | Control Center, Builder, guardrails, transfer rules |
| **Phase 3** | Adoption | Onboarding, call forwarding UX, Test Your AI |
| **Phase 4** | ROI & Retention | Weekly reports, follow-up automation, booking links |
| **Phase 5** | SaaS Scale | Multi-tenant, Stripe, plan limits, compliance |
| **Phase 6** | Expansion | Adjacent verticals after auto-service niche is won |

---

*Last updated: July 2026*
