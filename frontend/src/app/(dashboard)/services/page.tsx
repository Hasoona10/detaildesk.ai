"use client";

import { useEffect, useState } from "react";
import { fetchBusiness, type BusinessProfile } from "@/lib/api";

export default function ServicesPage() {
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
        <h1 className="text-2xl font-semibold tracking-tight">Services</h1>
        <p className="text-sm text-slate-500">
          The services the AI quotes from. Edit these in Business Settings.
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
        <div className="grid gap-4 md:grid-cols-2">
          {(biz.services || []).map((svc) => (
            <article
              key={svc.name}
              className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm"
            >
              <div className="flex items-start justify-between gap-2">
                <div>
                  <h2 className="text-lg font-semibold">{svc.name}</h2>
                  {svc.category && (
                    <div className="text-xs uppercase tracking-wider text-slate-400">
                      {svc.category}
                    </div>
                  )}
                </div>
                {svc.price_min != null && svc.price_max != null && (
                  <div className="rounded-full bg-blue-50 px-3 py-1 text-sm font-semibold text-blue-800">
                    ${svc.price_min}–${svc.price_max}
                  </div>
                )}
              </div>
              {svc.description && (
                <p className="mt-2 text-sm text-slate-600">{svc.description}</p>
              )}
              {svc.notes && (
                <p className="mt-2 text-xs italic text-slate-500">
                  Note: {svc.notes}
                </p>
              )}
              {svc.duration_hours_min != null && svc.duration_hours_max != null && (
                <p className="mt-2 text-xs text-slate-500">
                  Typical duration: {svc.duration_hours_min}–{svc.duration_hours_max} hours
                </p>
              )}
            </article>
          ))}
        </div>
      )}
    </div>
  );
}
