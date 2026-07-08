"use client";

import { useCallback, useEffect, useState } from "react";
import { fetchTurnLog, type TurnLog } from "@/lib/api";

const SOURCE_LABELS: Record<string, string> = {
  template_fast_path: "Template",
  llm_turn: "AI (LLM)",
};

export default function CallsPage() {
  const [turns, setTurns] = useState<TurnLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setLoading(true);
      const data = await fetchTurnLog();
      setTurns(data);
      setError(null);
    } catch {
      setError("Couldn't load conversation log. Is the backend running?");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 10_000);
    return () => clearInterval(id);
  }, [refresh]);

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Calls &amp; Chats</h1>
        <p className="text-sm text-slate-500">
          Every individual turn the AI handled — useful for QA and tuning.
        </p>
      </header>

      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </div>
      )}

      <div className="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
        <table className="w-full text-left text-sm">
          <thead className="bg-slate-50 text-xs uppercase tracking-wider text-slate-500">
            <tr>
              <th className="px-4 py-3">When</th>
              <th className="px-4 py-3">Intent</th>
              <th className="px-4 py-3">Customer said</th>
              <th className="px-4 py-3">AI reply</th>
              <th className="px-4 py-3">Source</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {loading && turns.length === 0 && (
              <tr>
                <td colSpan={5} className="px-4 py-10 text-center text-slate-500">
                  Loading…
                </td>
              </tr>
            )}
            {!loading && turns.length === 0 && (
              <tr>
                <td colSpan={5} className="px-4 py-10 text-center text-slate-500">
                  No calls or chats yet.
                </td>
              </tr>
            )}
            {turns.map((t, i) => (
              <tr key={i}>
                <td className="whitespace-nowrap px-4 py-3 text-slate-500">
                  {new Date(t.timestamp).toLocaleString()}
                </td>
                <td className="px-4 py-3">
                  <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-700">
                    {t.intent || "—"}
                  </span>
                </td>
                <td className="px-4 py-3 text-slate-900">{t.customer_said}</td>
                <td className="px-4 py-3 text-slate-700">{t.ai_response}</td>
                <td className="px-4 py-3 text-xs text-slate-500">
                  {SOURCE_LABELS[t.response_source || ""] || t.response_source || "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
