"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { fetchLeads, type Lead } from "@/lib/api";

function formatVehicle(lead: Lead) {
  const parts = [lead.vehicle_year, lead.vehicle_make, lead.vehicle_model].filter(Boolean);
  return parts.length ? parts.join(" ") : "Vehicle TBD";
}

export default function AppointmentsPage() {
  const [leads, setLeads] = useState<Lead[]>([]);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchLeads();
      setLeads(data);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 15_000);
    return () => clearInterval(id);
  }, [refresh]);

  const appointments = useMemo(() => {
    return leads
      .filter(
        (l) => l.status === "booked" || l.preferred_date || l.preferred_time
      )
      .sort((a, b) => {
        const at = `${a.preferred_date || ""} ${a.preferred_time || ""}`.trim();
        const bt = `${b.preferred_date || ""} ${b.preferred_time || ""}`.trim();
        return at.localeCompare(bt);
      });
  }, [leads]);

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Appointments</h1>
        <p className="text-sm text-slate-500">
          Booked detailing appointments and any leads with a requested date/time.
        </p>
      </header>

      {loading && appointments.length === 0 ? (
        <div className="rounded-lg border border-slate-200 bg-white p-10 text-center text-sm text-slate-500">
          Loading…
        </div>
      ) : appointments.length === 0 ? (
        <div className="rounded-lg border border-dashed border-slate-300 bg-white p-10 text-center text-sm text-slate-500">
          No appointments yet. They'll show up here as the AI books them.
        </div>
      ) : (
        <div className="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50 text-xs uppercase tracking-wider text-slate-500">
              <tr>
                <th className="px-4 py-3">When</th>
                <th className="px-4 py-3">Customer</th>
                <th className="px-4 py-3">Vehicle</th>
                <th className="px-4 py-3">Service</th>
                <th className="px-4 py-3">Mobile/Shop</th>
                <th className="px-4 py-3">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {appointments.map((lead) => (
                <tr key={lead.id}>
                  <td className="whitespace-nowrap px-4 py-3">
                    {lead.preferred_date || "—"}{" "}
                    {lead.preferred_time && (
                      <span className="text-slate-500">{lead.preferred_time}</span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <div className="font-medium">{lead.customer_name || "Unknown"}</div>
                    <div className="text-xs text-slate-500">{lead.customer_phone || "—"}</div>
                  </td>
                  <td className="px-4 py-3">{formatVehicle(lead)}</td>
                  <td className="px-4 py-3">{lead.service_requested || "—"}</td>
                  <td className="px-4 py-3">{lead.mobile_or_shop_preference || "—"}</td>
                  <td className="px-4 py-3">
                    <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-700">
                      {lead.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
