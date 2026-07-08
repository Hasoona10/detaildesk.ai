"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  fetchBusiness,
  fetchLeads,
  updateLeadStatus,
  type BusinessProfile,
  type Lead,
  type LeadStatus,
} from "@/lib/api";

/* ------------------------------------------------------------------ */
/* Helpers                                                             */
/* ------------------------------------------------------------------ */

const FALLBACK_VALUES: [RegExp, [number, number]][] = [
  [/ceramic|coating/i, [800, 1500]],
  [/paint\s*correction|polish/i, [400, 1200]],
  [/ppf|film|clear\s*bra/i, [1500, 3500]],
  [/wrap/i, [2000, 4000]],
  [/tint/i, [350, 600]],
  [/full\s*detail/i, [180, 350]],
  [/interior/i, [150, 220]],
  [/wash|exterior/i, [50, 150]],
];

function estValue(
  lead: Lead,
  business: BusinessProfile | null
): [number, number] | null {
  const svc = lead.service_requested;
  if (!svc) return null;
  const s = svc.toLowerCase();
  if (business?.services) {
    for (const bs of business.services) {
      if (!bs.name) continue;
      const n = bs.name.toLowerCase();
      if (
        (n.includes(s) || s.includes(n)) &&
        bs.price_min != null &&
        bs.price_max != null
      ) {
        return [bs.price_min, bs.price_max];
      }
    }
  }
  for (const [re, range] of FALLBACK_VALUES) {
    if (re.test(s)) return range;
  }
  return null;
}

function money(n: number) {
  return `$${n.toLocaleString()}`;
}

function valueLabel(range: [number, number] | null) {
  if (!range) return null;
  return `${money(range[0])}–${money(range[1])}`;
}

function relativeTime(iso?: string | null) {
  if (!iso) return "";
  const diff = Math.max(0, Date.now() - new Date(iso).getTime());
  const m = Math.floor(diff / 60_000);
  if (m < 1) return "just now";
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.floor(h / 24);
  return `${d}d ago`;
}

function clockTime(iso?: string | null) {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return "";
  }
}

function formatVehicle(lead: Lead) {
  const parts = [
    lead.vehicle_color,
    lead.vehicle_year,
    lead.vehicle_make,
    lead.vehicle_model,
  ].filter(Boolean);
  return parts.length ? parts.join(" ") : null;
}

function formatPreferred(lead: Lead) {
  if (lead.preferred_date && lead.preferred_time)
    return `${lead.preferred_date} ${lead.preferred_time}`;
  return lead.preferred_date || lead.preferred_time || null;
}

/** Honest "capture completeness" score. */
function captureScore(lead: Lead) {
  const slots = [
    lead.customer_name,
    lead.customer_phone,
    lead.vehicle_make,
    lead.vehicle_model || lead.vehicle_year || lead.vehicle_color,
    lead.service_requested,
    formatPreferred(lead),
    lead.customer_location || lead.mobile_or_shop_preference,
    lead.lead_summary || lead.condition_notes,
  ];
  const filled = slots.filter(Boolean).length;
  return Math.round((filled / slots.length) * 100);
}

function aiSummary(lead: Lead) {
  if (lead.lead_summary) return lead.lead_summary;
  const bits: string[] = [];
  const veh = formatVehicle(lead);
  if (lead.service_requested)
    bits.push(
      `${lead.customer_name || "Caller"} asked about ${lead.service_requested.toLowerCase()}${veh ? ` for a ${veh}` : ""}.`
    );
  else if (veh) bits.push(`${lead.customer_name || "Caller"} has a ${veh}.`);
  if (lead.condition_notes) bits.push(lead.condition_notes);
  const when = formatPreferred(lead);
  if (when) bits.push(`Preferred time: ${when}.`);
  if (lead.urgency) bits.push(`Urgency: ${lead.urgency}.`);
  return bits.length
    ? bits.join(" ")
    : "Conversation in progress — details still being captured.";
}

function ownerSmsPreview(lead: Lead) {
  const veh = formatVehicle(lead);
  const lines = [
    `New detailing lead: ${lead.customer_name || "Unknown caller"}${
      lead.service_requested
        ? ` wants ${lead.service_requested.toLowerCase()}`
        : ""
    }${veh ? ` for a ${veh}` : ""}.`,
  ];
  if (lead.condition_notes) lines.push(lead.condition_notes);
  const when = formatPreferred(lead);
  if (when) lines.push(`Wants ${when}.`);
  if (lead.customer_phone) lines.push(`Call back: ${lead.customer_phone}`);
  return lines.join(" ");
}

function suggestedReply(lead: Lead) {
  const name = lead.customer_name || "there";
  const service = lead.service_requested?.toLowerCase() || "your detail";
  const veh = formatVehicle(lead);
  const when = lead.preferred_date
    ? `${lead.preferred_date}${lead.preferred_time ? " " + lead.preferred_time : ""}`
    : null;
  let msg = `Hey ${name}, this is OC Elite Detailing. We got your request for ${service}${veh ? ` on your ${veh}` : ""}.`;
  if (lead.condition_notes?.match(/swirl|scratch|correction/i)) {
    msg += ` Since you mentioned the paint condition, we'd recommend a quick inspection first.`;
  }
  msg += when
    ? ` Are you available ${when} for us to take a look?`
    : ` What day works best for you?`;
  return msg;
}

/* ------------------------------------------------------------------ */
/* Status / tab config                                                 */
/* ------------------------------------------------------------------ */

const STATUS_META: Record<LeadStatus, { label: string; pill: string }> = {
  new: { label: "New Lead", pill: "bg-blue-100 text-blue-700" },
  contacted: { label: "Follow-up", pill: "bg-amber-100 text-amber-700" },
  booked: { label: "Booked", pill: "bg-emerald-100 text-emerald-700" },
  lost: { label: "Lost", pill: "bg-slate-100 text-slate-500" },
  resolved: { label: "Resolved", pill: "bg-violet-100 text-violet-700" },
};

type Tab = "new" | "contacted" | "booked" | "lost" | "all";

const TABS: { key: Tab; label: string }[] = [
  { key: "new", label: "New" },
  { key: "contacted", label: "Follow-up" },
  { key: "booked", label: "Booked" },
  { key: "lost", label: "Lost" },
  { key: "all", label: "All" },
];

/* ------------------------------------------------------------------ */
/* Page                                                                */
/* ------------------------------------------------------------------ */

export default function InboxPage() {
  const [leads, setLeads] = useState<Lead[]>([]);
  const [business, setBusiness] = useState<BusinessProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("all");
  const [search, setSearch] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [reply, setReply] = useState("");
  const [copied, setCopied] = useState(false);
  const [moreOpen, setMoreOpen] = useState(false);
  const replyRef = useRef<HTMLTextAreaElement>(null);

  const refresh = useCallback(async () => {
    try {
      const data = await fetchLeads();
      setLeads(data);
      setError(null);
    } catch {
      setError("Couldn't load leads. Is the backend running on :8000?");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    fetchBusiness().then(setBusiness).catch(() => {});
    const id = setInterval(refresh, 10_000);
    return () => clearInterval(id);
  }, [refresh]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return leads.filter((lead) => {
      if (tab !== "all" && lead.status !== tab) return false;
      if (!q) return true;
      return [
        lead.customer_name,
        lead.customer_phone,
        lead.service_requested,
        lead.vehicle_make,
        lead.vehicle_model,
        lead.customer_location,
        lead.lead_summary,
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase()
        .includes(q);
    });
  }, [leads, tab, search]);

  const counts = useMemo(() => {
    const out: Record<string, number> = {};
    for (const l of leads) out[l.status] = (out[l.status] || 0) + 1;
    return out;
  }, [leads]);

  const selected =
    filtered.find((l) => l.id === selectedId) || filtered[0] || null;

  useEffect(() => {
    if (selected) setReply(suggestedReply(selected));
    setMoreOpen(false);
  }, [selected?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const stats = useMemo(() => {
    const weekMs = 7 * 24 * 3600 * 1000;
    const now = Date.now();
    const inWeek = (l: Lead) => now - new Date(l.created_at).getTime() < weekMs;
    const thisWeek = leads.filter(inWeek);
    const weekEmpty = thisWeek.length === 0;
    const base = weekEmpty ? leads : thisWeek;
    const withPhone = base.filter((l) => l.customer_phone);
    const booked = leads.filter((l) => l.status === "booked");
    const openValue = leads
      .filter((l) => l.status === "new" || l.status === "contacted")
      .map((l) => estValue(l, business))
      .filter(Boolean)
      .reduce((sum, r) => sum + (r as [number, number])[1], 0);
    return {
      answered: base.length,
      recovered: withPhone.length,
      periodLabel: weekEmpty ? "All time" : "This week",
      pipeline: openValue,
      booked: booked.length,
    };
  }, [leads, business]);

  async function setStatus(id: string, status: LeadStatus) {
    setSaving(true);
    try {
      const updated = await updateLeadStatus(id, status);
      setLeads((prev) => prev.map((l) => (l.id === id ? updated : l)));
    } catch {
      setError("Failed to update lead status.");
    } finally {
      setSaving(false);
      setMoreOpen(false);
    }
  }

  async function copyReply() {
    try {
      await navigator.clipboard.writeText(reply);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {}
  }

  return (
    <div className="mx-auto flex min-h-full max-w-[1500px] flex-col gap-8 p-8">
      {/* ===== Top metrics ===== */}
      <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
        <StatCard
          icon="📞"
          tint="bg-blue-50 text-blue-600"
          value={String(stats.answered)}
          label="Calls answered"
          sub={stats.periodLabel}
        />
        <StatCard
          icon="📈"
          tint="bg-emerald-50 text-emerald-600"
          value={String(stats.recovered)}
          label="Leads recovered"
          sub={stats.periodLabel}
        />
        <StatCard
          icon="💲"
          tint="bg-violet-50 text-violet-600"
          value={
            stats.pipeline >= 1000
              ? `$${(stats.pipeline / 1000).toFixed(1)}k`
              : money(stats.pipeline)
          }
          label="Est. lead value"
          sub="Open leads"
        />
        <StatCard
          icon="📅"
          tint="bg-amber-50 text-amber-600"
          value={String(stats.booked)}
          label="Appointments booked"
          sub="All time"
        />
      </div>

      {error && (
        <div className="rounded-xl border border-red-100 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* ===== Inbox + workspace ===== */}
      <div className="grid flex-1 items-start gap-8 xl:grid-cols-[minmax(340px,400px)_1fr]">
        {/* ---------- Lead inbox ---------- */}
        <section className="overflow-hidden rounded-2xl bg-white shadow-[0_1px_3px_rgba(15,23,42,0.06),0_8px_24px_rgba(15,23,42,0.04)]">
          <div className="px-6 pb-4 pt-6">
            <h1 className="text-[17px] font-bold tracking-tight">Lead Inbox</h1>
            <p className="mt-0.5 text-[12.5px] text-slate-500">
              Every missed call becomes a qualified lead.
            </p>
            <div className="mt-4 flex gap-1 rounded-lg bg-slate-100 p-1">
              {TABS.map((t) => {
                const count = t.key === "all" ? leads.length : counts[t.key] || 0;
                const active = tab === t.key;
                return (
                  <button
                    key={t.key}
                    onClick={() => setTab(t.key)}
                    className={`flex-1 rounded-md px-2 py-1.5 text-[12px] font-semibold transition-all ${
                      active
                        ? "bg-white text-slate-900 shadow-sm"
                        : "text-slate-500 hover:text-slate-700"
                    }`}
                  >
                    {t.label}
                    {count > 0 && (
                      <span className={active ? "ml-1 text-blue-600" : "ml-1 text-slate-400"}>
                        {count}
                      </span>
                    )}
                  </button>
                );
              })}
            </div>
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search customers, vehicles, services…"
              className="mt-3 w-full rounded-lg bg-slate-50 px-3.5 py-2.5 text-[13px] ring-1 ring-transparent transition-shadow placeholder:text-slate-400 focus:bg-white focus:outline-none focus:ring-blue-400"
            />
          </div>

          <div className="max-h-[calc(100vh-350px)] overflow-y-auto">
            {loading && leads.length === 0 ? (
              <div className="p-10 text-center text-sm text-slate-500">
                Loading leads…
              </div>
            ) : filtered.length === 0 ? (
              <div className="p-10 text-center text-sm text-slate-500">
                No leads in this view yet.
              </div>
            ) : (
              filtered.map((lead) => {
                const meta = STATUS_META[lead.status];
                const range = estValue(lead, business);
                const active = selected?.id === lead.id;
                const veh = formatVehicle(lead);
                const line2 = [veh, lead.service_requested]
                  .filter(Boolean)
                  .join("  ·  ");
                return (
                  <button
                    key={lead.id}
                    onClick={() => setSelectedId(lead.id)}
                    className={`block w-full px-6 py-4 text-left transition-colors ${
                      active ? "bg-blue-50/70" : "hover:bg-slate-50"
                    }`}
                    style={{
                      boxShadow: active
                        ? "inset 3px 0 0 #2563eb"
                        : "inset 0 -1px 0 #f1f5f9",
                    }}
                  >
                    <div className="flex items-baseline justify-between gap-3">
                      <span className="truncate text-[14px] font-semibold text-slate-900">
                        {lead.customer_name || "Unknown caller"}
                      </span>
                      <span
                        className={`shrink-0 rounded-full px-2.5 py-0.5 text-[10.5px] font-semibold ${meta.pill}`}
                      >
                        {meta.label}
                      </span>
                    </div>
                    <div className="mt-1 text-[12px] text-slate-400">
                      {lead.customer_phone || "no number"} ·{" "}
                      {relativeTime(lead.created_at)}
                    </div>
                    {line2 && (
                      <div className="mt-1.5 truncate text-[12.5px] font-medium text-slate-600">
                        {line2}
                      </div>
                    )}
                    <div className="mt-1.5 flex items-end justify-between gap-3">
                      <p className="line-clamp-1 flex-1 text-[12.5px] text-slate-500">
                        {aiSummary(lead)}
                      </p>
                      {range && (
                        <span className="shrink-0 text-[12.5px] font-semibold text-emerald-600">
                          {valueLabel(range)}
                        </span>
                      )}
                    </div>
                  </button>
                );
              })
            )}
          </div>
        </section>

        {/* ---------- Selected lead workspace ---------- */}
        {selected ? (
          <Workspace
            lead={selected}
            business={business}
            saving={saving}
            reply={reply}
            copied={copied}
            moreOpen={moreOpen}
            replyRef={replyRef}
            onReplyChange={setReply}
            onCopy={copyReply}
            onStatus={(s) => setStatus(selected.id, s)}
            onToggleMore={() => setMoreOpen((v) => !v)}
          />
        ) : (
          <section className="flex min-h-[400px] items-center justify-center rounded-2xl border border-dashed border-slate-200 bg-white/60 text-sm text-slate-400">
            Select a lead to open the workspace.
          </section>
        )}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Components                                                          */
/* ------------------------------------------------------------------ */

function StatCard({
  icon,
  tint,
  value,
  label,
  sub,
}: {
  icon: string;
  tint: string;
  value: string;
  label: string;
  sub: string;
}) {
  return (
    <div className="flex items-center gap-3.5 rounded-2xl bg-white p-5 shadow-[0_1px_3px_rgba(15,23,42,0.06)]">
      <div
        className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl text-base ${tint}`}
      >
        {icon}
      </div>
      <div className="min-w-0">
        <div className="text-[20px] font-bold leading-tight tracking-tight">
          {value}
        </div>
        <div className="truncate text-[12px] text-slate-500">
          {label} <span className="text-slate-300">·</span>{" "}
          <span className="text-slate-400">{sub}</span>
        </div>
      </div>
    </div>
  );
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div className="mb-3 text-[11px] font-bold uppercase tracking-[0.08em] text-slate-400">
      {children}
    </div>
  );
}

function KV({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="text-[11px] text-slate-400">{label}</div>
      <div className="mt-0.5 text-[13.5px] font-medium text-slate-800">
        {children}
      </div>
    </div>
  );
}

function Workspace({
  lead,
  business,
  saving,
  reply,
  copied,
  moreOpen,
  replyRef,
  onReplyChange,
  onCopy,
  onStatus,
  onToggleMore,
}: {
  lead: Lead;
  business: BusinessProfile | null;
  saving: boolean;
  reply: string;
  copied: boolean;
  moreOpen: boolean;
  replyRef: React.RefObject<HTMLTextAreaElement | null>;
  onReplyChange: (v: string) => void;
  onCopy: () => void;
  onStatus: (s: LeadStatus) => void;
  onToggleMore: () => void;
}) {
  const range = estValue(lead, business);
  const score = captureScore(lead);
  const meta = STATUS_META[lead.status];
  const smsBody = encodeURIComponent(reply);

  return (
    <section className="overflow-hidden rounded-2xl bg-white shadow-[0_1px_3px_rgba(15,23,42,0.06),0_8px_24px_rgba(15,23,42,0.04)]">
      {/* ----- Header ----- */}
      <div className="flex flex-wrap items-center justify-between gap-4 px-8 pb-6 pt-7">
        <div>
          <div className="flex items-center gap-3">
            <h2 className="text-[22px] font-bold tracking-tight">
              {lead.customer_name || "Unknown caller"}
            </h2>
            <span
              className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ${meta.pill}`}
            >
              {meta.label}
            </span>
          </div>
          <div className="mt-1 text-[13.5px] text-slate-500">
            {lead.customer_phone || "No number captured"}
            <span className="mx-2 text-slate-300">·</span>
            Last contact {relativeTime(lead.updated_at)}
            {lead.channel && (
              <>
                <span className="mx-2 text-slate-300">·</span>
                via {lead.channel}
              </>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2">
          {lead.customer_phone && (
            <a
              href={`tel:${lead.customer_phone}`}
              className="rounded-lg bg-emerald-600 px-4 py-2.5 text-[13px] font-semibold text-white shadow-sm hover:bg-emerald-500"
            >
              Call back
            </a>
          )}
          {lead.customer_phone && (
            <a
              href={`sms:${lead.customer_phone}?body=${smsBody}`}
              className="rounded-lg bg-blue-600 px-4 py-2.5 text-[13px] font-semibold text-white shadow-sm hover:bg-blue-500"
            >
              Text customer
            </a>
          )}
          <button
            disabled={saving || lead.status === "booked"}
            onClick={() => onStatus("booked")}
            className="rounded-lg bg-white px-4 py-2.5 text-[13px] font-semibold text-slate-700 ring-1 ring-slate-200 hover:bg-slate-50 disabled:opacity-40"
          >
            Book appointment
          </button>
          <div className="relative">
            <button
              onClick={onToggleMore}
              className="rounded-lg bg-white px-3 py-2.5 text-[13px] font-semibold text-slate-500 ring-1 ring-slate-200 hover:bg-slate-50"
            >
              •••
            </button>
            {moreOpen && (
              <div className="absolute right-0 z-10 mt-1.5 w-44 rounded-xl bg-white py-1.5 shadow-lg ring-1 ring-slate-200">
                {(["new", "contacted", "lost", "resolved"] as LeadStatus[]).map(
                  (s) => (
                    <button
                      key={s}
                      disabled={saving || lead.status === s}
                      onClick={() => onStatus(s)}
                      className="block w-full px-4 py-2 text-left text-[13px] hover:bg-slate-50 disabled:opacity-40"
                    >
                      Mark {STATUS_META[s].label.toLowerCase()}
                    </button>
                  )
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ----- AI Summary (hero section) ----- */}
      <div className="border-t border-slate-100 px-8 py-6">
        <SectionLabel>AI Summary</SectionLabel>
        <p className="max-w-3xl text-[15.5px] leading-relaxed text-slate-800">
          {aiSummary(lead)}
        </p>
      </div>

      {/* ----- Lead details + SMS preview ----- */}
      <div className="grid gap-8 border-t border-slate-100 px-8 py-6 lg:grid-cols-[1fr_320px]">
        <div>
          <SectionLabel>Lead Details</SectionLabel>
          <div className="grid grid-cols-2 gap-x-10 gap-y-4">
            <KV label="Service">{lead.service_requested || "—"}</KV>
            <KV label="Vehicle">{formatVehicle(lead) || "—"}</KV>
            <KV label="Preferred time">{formatPreferred(lead) || "—"}</KV>
            <KV label="Location">
              {lead.customer_location
                ? `${lead.customer_location}${lead.mobile_or_shop_preference ? ` (${lead.mobile_or_shop_preference})` : ""}`
                : lead.mobile_or_shop_preference || "—"}
            </KV>
            <KV label="Est. value">
              {range ? (
                <span className="text-emerald-600">{valueLabel(range)}</span>
              ) : (
                "—"
              )}
            </KV>
            <KV label="Urgency">
              {lead.urgency ? (
                <span className="font-semibold uppercase text-red-500">
                  {lead.urgency}
                </span>
              ) : (
                "Normal"
              )}
            </KV>
            {lead.condition_notes && (
              <div className="col-span-2">
                <KV label="Condition notes">{lead.condition_notes}</KV>
              </div>
            )}
            <div className="col-span-2 flex items-center gap-3 pt-1">
              <span className="text-[11px] text-slate-400">
                Capture completeness
              </span>
              <div className="h-1.5 w-28 overflow-hidden rounded-full bg-slate-100">
                <div
                  className="h-full rounded-full bg-emerald-500"
                  style={{ width: `${score}%` }}
                />
              </div>
              <span className="text-[12px] font-semibold text-slate-600">
                {score}%
              </span>
            </div>
          </div>
        </div>

        <div>
          <div className="mb-3 flex items-center justify-between">
            <SectionLabel>
              <span className="mb-0">Owner SMS</span>
            </SectionLabel>
            <span
              className={`rounded-full px-2 py-0.5 text-[10.5px] font-semibold ${
                lead.owner_notified
                  ? "bg-emerald-100 text-emerald-700"
                  : "bg-slate-100 text-slate-500"
              }`}
            >
              {lead.owner_notified ? "Sent" : "Not sent"}
            </span>
          </div>
          <div className="rounded-2xl rounded-tl-md bg-slate-100 px-4 py-3 text-[12.5px] leading-relaxed text-slate-700">
            {ownerSmsPreview(lead)}
          </div>
          {!lead.owner_notified && lead.owner_notify_reason && (
            <p className="mt-2 text-[11px] text-slate-400">
              {lead.owner_notify_reason}
            </p>
          )}
        </div>
      </div>

      {/* ----- Suggested follow-up (next action) ----- */}
      <div className="border-t border-slate-100 px-8 py-6">
        <div className="rounded-2xl bg-blue-50/60 p-5">
          <div className="mb-3 flex items-center justify-between">
            <div className="text-[13px] font-bold text-blue-900">
              Recommended next action
            </div>
            <span className="text-[11px] font-medium text-blue-400">
              AI-drafted reply
            </span>
          </div>
          <textarea
            ref={replyRef}
            value={reply}
            onChange={(e) => onReplyChange(e.target.value)}
            rows={3}
            className="w-full resize-none rounded-xl bg-white p-4 text-[13.5px] leading-relaxed text-slate-800 shadow-sm ring-1 ring-transparent focus:outline-none focus:ring-blue-400"
          />
          <div className="mt-3 flex flex-wrap gap-2">
            {lead.customer_phone && (
              <a
                href={`sms:${lead.customer_phone}?body=${smsBody}`}
                className="rounded-lg bg-blue-600 px-4 py-2 text-[12.5px] font-semibold text-white shadow-sm hover:bg-blue-500"
              >
                Send SMS
              </a>
            )}
            <button
              onClick={onCopy}
              className="rounded-lg bg-white px-4 py-2 text-[12.5px] font-semibold text-slate-700 ring-1 ring-slate-200 hover:bg-slate-50"
            >
              {copied ? "✓ Copied" : "Copy reply"}
            </button>
            <button
              onClick={() => replyRef.current?.focus()}
              className="rounded-lg bg-white px-4 py-2 text-[12.5px] font-semibold text-slate-700 ring-1 ring-slate-200 hover:bg-slate-50"
            >
              Edit
            </button>
          </div>
        </div>
      </div>

      {/* ----- Transcript ----- */}
      <div className="border-t border-slate-100 px-8 pb-8 pt-6">
        <SectionLabel>Transcript</SectionLabel>
        <div className="flex max-h-72 flex-col gap-2.5 overflow-y-auto pr-2">
          {(lead.transcript || []).map((turn, i) => {
            const isCaller = turn.role === "user";
            return (
              <div
                key={i}
                className={`max-w-[85%] rounded-2xl px-4 py-2.5 text-[13px] leading-relaxed ${
                  isCaller
                    ? "self-start rounded-tl-md bg-slate-100 text-slate-800"
                    : "self-end rounded-tr-md bg-blue-600/90 text-white"
                }`}
              >
                <div
                  className={`mb-0.5 flex items-center gap-2 text-[10px] font-semibold uppercase tracking-wide ${
                    isCaller ? "text-slate-400" : "text-blue-100"
                  }`}
                >
                  {isCaller ? "Caller" : "AI"}
                  <span className="font-normal">{clockTime(turn.ts)}</span>
                </div>
                {turn.text}
              </div>
            );
          })}
          {(!lead.transcript || lead.transcript.length === 0) && (
            <div className="py-6 text-center text-[13px] text-slate-400">
              No transcript captured for this lead.
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
