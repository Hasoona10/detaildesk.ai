"use client";

import { useEffect, useState } from "react";
import { fetchBusiness, type BusinessProfile } from "@/lib/api";

export default function BusinessSettingsPage() {
  const [biz, setBiz] = useState<BusinessProfile | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchBusiness()
      .then(setBiz)
      .catch(() => setBiz(null))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Business Settings</h1>
        <p className="text-sm text-slate-500">
          Read-only view of the business profile the AI uses. Edit
          <code className="mx-1 rounded bg-slate-100 px-1 py-0.5 text-xs">backend/business_data.json</code>
          to change these values for now (an editor UI is on the roadmap).
        </p>
      </header>

      {loading ? (
        <div className="rounded-lg border border-slate-200 bg-white p-10 text-center text-sm text-slate-500">
          Loading…
        </div>
      ) : !biz ? (
        <div className="rounded-lg border border-red-200 bg-red-50 p-6 text-sm text-red-700">
          Couldn't load business profile.
        </div>
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          <Card title="Business hours">
            <ul className="space-y-1 text-sm">
              {Object.entries(biz.hours || {}).map(([day, hours]) => (
                <li key={day} className="flex justify-between">
                  <span className="capitalize text-slate-600">{day}</span>
                  <span className="font-medium">{hours}</span>
                </li>
              ))}
            </ul>
          </Card>

          <Card title="Mobile service">
            {biz.mobile_service?.available ? (
              <div className="space-y-2 text-sm">
                <div>
                  Service radius:{" "}
                  <span className="font-medium">
                    {biz.mobile_service.service_radius_miles ?? 25} miles
                  </span>
                </div>
                <div>Cities served:</div>
                <div className="flex flex-wrap gap-1">
                  {(biz.mobile_service.service_area_examples || []).map((c) => (
                    <span
                      key={c}
                      className="rounded-full bg-slate-100 px-2 py-0.5 text-xs"
                    >
                      {c}
                    </span>
                  ))}
                </div>
                {biz.mobile_service.requirements && (
                  <p className="text-xs text-slate-500">
                    {biz.mobile_service.requirements}
                  </p>
                )}
              </div>
            ) : (
              <p className="text-sm text-slate-500">Mobile service not enabled.</p>
            )}
          </Card>

          <Card title="Owner SMS notifications">
            <div className="space-y-1 text-sm">
              <div>
                Enabled:{" "}
                <span className="font-medium">
                  {biz.owner_notification?.sms_enabled === false ? "No" : "Yes"}
                </span>
              </div>
              <div>
                Owner number:{" "}
                <span className="font-medium">
                  {biz.owner_notification?.owner_sms_number ||
                    "(set OWNER_SMS_NUMBER env var)"}
                </span>
              </div>
              <p className="text-xs text-slate-500">
                The AI texts this number every time a qualified lead is captured.
              </p>
            </div>
          </Card>

          <Card title="FAQs the AI knows">
            <ul className="space-y-3 text-sm">
              {(biz.faq || []).slice(0, 6).map((f, i) => (
                <li key={i}>
                  <div className="font-medium">{f.question}</div>
                  <div className="text-slate-600">{f.answer}</div>
                </li>
              ))}
            </ul>
          </Card>

          <Card title="Services &amp; price ranges" className="lg:col-span-2">
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {(biz.services || []).map((svc) => (
                <div
                  key={svc.name}
                  className="rounded-md border border-slate-200 p-3 text-sm"
                >
                  <div className="font-medium">{svc.name}</div>
                  {svc.price_min != null && svc.price_max != null && (
                    <div className="text-slate-600">
                      ${svc.price_min}–${svc.price_max}
                    </div>
                  )}
                  {svc.description && (
                    <div className="mt-1 text-xs text-slate-500">{svc.description}</div>
                  )}
                </div>
              ))}
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}

function Card({
  title,
  children,
  className = "",
}: {
  title: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section
      className={`rounded-lg border border-slate-200 bg-white p-5 shadow-sm ${className}`}
    >
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-slate-500">
        {title}
      </h2>
      {children}
    </section>
  );
}
