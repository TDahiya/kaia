"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { BarChart3, TrendingUp, AlertTriangle } from "lucide-react";

export default function UsagePage() {
  const [usage, setUsage] = useState<any>(null);
  const [history, setHistory] = useState<any[]>([]);

  useEffect(() => {
    api.getUsage().then(setUsage).catch(() => {});
    api.getUsageHistory(30).then((d) => setHistory(d.events || [])).catch(() => {});
  }, []);

  const percentUsed = usage ? (usage.total_usd / usage.limit_usd) * 100 : 0;

  return (
    <div>
      <h2 className="text-2xl font-semibold mb-6">Usage & Costs</h2>

      {/* Summary cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
        <div className="bg-surface border border-border rounded-xl p-5">
          <div className="text-sm text-muted mb-1">Monthly Spend</div>
          <div className="text-3xl font-semibold">${usage?.total_usd?.toFixed(2) || "0.00"}</div>
          <div className="mt-3">
            <div className="flex justify-between text-xs text-muted mb-1">
              <span>Limit: ${usage?.limit_usd?.toFixed(2)}</span>
              <span>{percentUsed.toFixed(1)}%</span>
            </div>
            <div className="h-2 bg-surface-hover rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full ${percentUsed > 80 ? "bg-red-500" : percentUsed > 50 ? "bg-yellow-500" : "bg-accent"}`}
                style={{ width: `${Math.min(percentUsed, 100)}%` }}
              />
            </div>
          </div>
        </div>

        <div className="bg-surface border border-border rounded-xl p-5">
          <div className="text-sm text-muted mb-1">Remaining Budget</div>
          <div className={`text-3xl font-semibold ${(usage?.remaining_usd || 0) < 5 ? "text-red-400" : ""}`}>
            ${usage?.remaining_usd?.toFixed(2) || "0.00"}
          </div>
          {(usage?.remaining_usd || 0) < 5 && (
            <div className="flex items-center gap-1 mt-2 text-xs text-red-400">
              <AlertTriangle size={12} /> Budget running low
            </div>
          )}
        </div>

        <div className="bg-surface border border-border rounded-xl p-5">
          <div className="text-sm text-muted mb-1">API Events (30d)</div>
          <div className="text-3xl font-semibold">{history.length}</div>
        </div>
      </div>

      {/* Cost breakdown by provider */}
      {usage?.by_provider && Object.keys(usage.by_provider).length > 0 && (
        <div className="bg-surface border border-border rounded-xl p-5 mb-8">
          <h3 className="font-medium mb-4">Cost by Provider</h3>
          <div className="space-y-3">
            {Object.entries(usage.by_provider)
              .sort(([, a], [, b]) => (b as number) - (a as number))
              .map(([provider, cost]) => {
                const pct = usage.total_usd > 0 ? ((cost as number) / usage.total_usd) * 100 : 0;
                return (
                  <div key={provider}>
                    <div className="flex justify-between text-sm mb-1">
                      <span className="capitalize">{provider.replace(/_/g, " ")}</span>
                      <span className="font-mono">${(cost as number).toFixed(4)}</span>
                    </div>
                    <div className="h-1.5 bg-surface-hover rounded-full overflow-hidden">
                      <div className="h-full bg-accent/60 rounded-full" style={{ width: `${pct}%` }} />
                    </div>
                  </div>
                );
              })}
          </div>
        </div>
      )}

      {/* Recent events */}
      <div className="bg-surface border border-border rounded-xl p-5">
        <h3 className="font-medium mb-4">Recent Events</h3>
        {history.length === 0 ? (
          <p className="text-sm text-muted">No usage events recorded yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-muted text-left border-b border-border">
                  <th className="pb-2 pr-4">Provider</th>
                  <th className="pb-2 pr-4">Type</th>
                  <th className="pb-2 pr-4">Quantity</th>
                  <th className="pb-2 pr-4">Cost</th>
                  <th className="pb-2 pr-4">Model</th>
                  <th className="pb-2">Time</th>
                </tr>
              </thead>
              <tbody>
                {history.slice(0, 50).map((e, i) => (
                  <tr key={i} className="border-b border-border/50 last:border-0">
                    <td className="py-2 pr-4 capitalize">{e.provider.replace(/_/g, " ")}</td>
                    <td className="py-2 pr-4">{e.event_type}</td>
                    <td className="py-2 pr-4 font-mono">{e.quantity} {e.unit}</td>
                    <td className="py-2 pr-4 font-mono">${parseFloat(e.estimated_cost_usd).toFixed(4)}</td>
                    <td className="py-2 pr-4 text-xs text-muted">{e.model || "—"}</td>
                    <td className="py-2 text-xs text-muted">{new Date(e.created_at).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
