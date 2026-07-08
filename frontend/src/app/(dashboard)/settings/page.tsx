"use client";

import { useState } from "react";
import { API_BASE } from "@/lib/api";

const AI_NUMBER_DISPLAY = "(714) 278-3407";
const AI_NUMBER_DIAL = "17142783407";

const CARRIERS: {
  id: string;
  name: string;
  steps: string[];
}[] = [
  {
    id: "att",
    name: "AT&T",
    steps: [
      `From your business phone, dial **004*1${AI_NUMBER_DIAL.slice(1)}# and press call.`,
      "This forwards calls only when you're busy, don't answer, or are unreachable.",
      "To turn it off later, dial ##004# and press call.",
    ],
  },
  {
    id: "verizon",
    name: "Verizon",
    steps: [
      `From your business phone, dial *71${AI_NUMBER_DIAL} and press call.`,
      "This forwards only unanswered and busy calls — you still ring first.",
      "To turn it off later, dial *73 and press call.",
    ],
  },
  {
    id: "tmobile",
    name: "T-Mobile",
    steps: [
      `From your business phone, dial **004*1${AI_NUMBER_DIAL.slice(1)}# and press call.`,
      "This forwards calls when unanswered, busy, or unreachable.",
      "To turn it off later, dial ##004# and press call.",
    ],
  },
  {
    id: "google-voice",
    name: "Google Voice",
    steps: [
      "Open Google Voice → Settings → Calls.",
      `Under "Unanswered calls", choose to forward to ${AI_NUMBER_DISPLAY}.`,
      "Save — Google Voice rings you first, then hands off to your AI.",
    ],
  },
  {
    id: "ringcentral",
    name: "RingCentral",
    steps: [
      "Admin Portal → Phone System → your number → Call Handling.",
      `Set "If no one answers" to forward to ${AI_NUMBER_DISPLAY} after 15–20 seconds.`,
      "Save the rule — overflow and after-hours calls now go to your AI.",
    ],
  },
];

export default function SettingsPage() {
  const [carrier, setCarrier] = useState<string>("att");
  const [copied, setCopied] = useState(false);

  const active = CARRIERS.find((c) => c.id === carrier)!;

  const copyNumber = () => {
    navigator.clipboard.writeText(AI_NUMBER_DISPLAY).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  };

  return (
    <div className="mx-auto max-w-4xl space-y-8 px-8 py-8">
      <header>
        <h1 className="text-2xl font-bold tracking-tight">Settings</h1>
        <p className="mt-1 text-sm text-slate-500">
          Set up call forwarding, connections, and app config.
        </p>
      </header>

      {/* ----- Call forwarding setup (the magic screen) ----- */}
      <section className="overflow-hidden rounded-2xl bg-white shadow-[0_1px_3px_rgba(15,23,42,0.06),0_8px_24px_rgba(15,23,42,0.04)]">
        <div className="border-b border-slate-100 px-7 py-6">
          <h2 className="text-[15px] font-bold text-slate-900">
            Forward missed calls to your AI
          </h2>
          <p className="mt-1 text-[13px] leading-relaxed text-slate-500">
            Keep your normal business number. When you don&apos;t answer within
            15–20 seconds, the call forwards to your AI number — it only catches
            calls you would have missed anyway.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-4 border-b border-slate-100 bg-blue-50/50 px-7 py-5">
          <div>
            <div className="text-[11px] font-semibold uppercase tracking-wider text-blue-500">
              Your AI number
            </div>
            <div className="text-[26px] font-bold tracking-tight text-slate-900">
              {AI_NUMBER_DISPLAY}
            </div>
          </div>
          <button
            onClick={copyNumber}
            className="rounded-lg bg-blue-600 px-4 py-2 text-[12.5px] font-semibold text-white shadow-sm hover:bg-blue-500"
          >
            {copied ? "✓ Copied" : "Copy number"}
          </button>
          <a
            href={`tel:${AI_NUMBER_DIAL}`}
            className="rounded-lg bg-white px-4 py-2 text-[12.5px] font-semibold text-slate-700 ring-1 ring-slate-200 hover:bg-slate-50"
          >
            Place a test call
          </a>
        </div>

        <div className="px-7 py-6">
          <div className="mb-4 text-[12px] font-semibold uppercase tracking-wider text-slate-400">
            Carrier instructions
          </div>
          <div className="mb-5 flex flex-wrap gap-2">
            {CARRIERS.map((c) => (
              <button
                key={c.id}
                onClick={() => setCarrier(c.id)}
                className={`rounded-full px-4 py-1.5 text-[12.5px] font-semibold transition-colors ${
                  carrier === c.id
                    ? "bg-slate-900 text-white"
                    : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                }`}
              >
                {c.name}
              </button>
            ))}
          </div>
          <ol className="space-y-3">
            {active.steps.map((step, i) => (
              <li key={i} className="flex gap-3 text-[13.5px] leading-relaxed text-slate-700">
                <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-blue-100 text-[12px] font-bold text-blue-700">
                  {i + 1}
                </span>
                <span className="pt-0.5">{step}</span>
              </li>
            ))}
          </ol>
          <p className="mt-5 rounded-xl bg-slate-50 px-4 py-3 text-[12.5px] leading-relaxed text-slate-500">
            After setting it up, call your business number from another phone and
            let it ring. Your AI should pick up, and a test lead should appear in
            the Lead Inbox within a minute.
          </p>
        </div>
      </section>

      {/* ----- API connection ----- */}
      <section className="rounded-2xl bg-white px-7 py-6 shadow-[0_1px_3px_rgba(15,23,42,0.06),0_8px_24px_rgba(15,23,42,0.04)]">
        <h2 className="text-[15px] font-bold text-slate-900">API connection</h2>
        <div className="mt-3 text-[13.5px] text-slate-700">
          <span className="font-medium">Backend URL:</span>{" "}
          <code className="rounded bg-slate-100 px-1.5 py-0.5 text-xs">{API_BASE}</code>
        </div>
        <p className="mt-2 text-[12.5px] text-slate-500">
          Set{" "}
          <code className="rounded bg-slate-100 px-1 py-0.5">NEXT_PUBLIC_API_BASE</code>{" "}
          in <code>.env.local</code> to point this dashboard at a different backend.
        </p>
      </section>

      {/* ----- Twilio ----- */}
      <section className="rounded-2xl bg-white px-7 py-6 shadow-[0_1px_3px_rgba(15,23,42,0.06),0_8px_24px_rgba(15,23,42,0.04)]">
        <h2 className="text-[15px] font-bold text-slate-900">Twilio credentials</h2>
        <p className="mt-2 text-[13.5px] text-slate-600">
          The backend reads Twilio credentials from environment variables:
        </p>
        <ul className="mt-3 list-disc space-y-1.5 pl-5 text-[12.5px] text-slate-500">
          <li>
            <code>TWILIO_ACCOUNT_SID</code>
          </li>
          <li>
            <code>TWILIO_API_KEY_SID</code> + <code>TWILIO_API_KEY_SECRET</code>{" "}
            (preferred) or <code>TWILIO_AUTH_TOKEN</code>
          </li>
          <li>
            <code>TWILIO_PHONE_NUMBER</code> (your AI number, also the SMS sender)
          </li>
          <li>
            <code>OWNER_SMS_NUMBER</code> (where lead summaries are texted)
          </li>
        </ul>
      </section>

      {/* ----- About ----- */}
      <section className="rounded-2xl bg-white px-7 py-6 shadow-[0_1px_3px_rgba(15,23,42,0.06),0_8px_24px_rgba(15,23,42,0.04)]">
        <h2 className="text-[15px] font-bold text-slate-900">About</h2>
        <p className="mt-2 text-[13.5px] leading-relaxed text-slate-600">
          DetailDesk AI — your backup employee for missed calls. The AI answers
          calls you would have missed, captures the customer&apos;s vehicle and
          service info, and texts you the lead instantly.
        </p>
      </section>
    </div>
  );
}
