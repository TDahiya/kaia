"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { AlertTriangle } from "lucide-react";
import { Page, Card, CardTitle, PageHeader, EmptyState } from "@/components/ui";
import { SceneLedger } from "@/components/brand";

export default function UsagePage() {
  const [usage, setUsage] = useState<any>(null);
  const [history, setHistory] = useState<any[]>([]);

  useEffect(() => {
    api.getUsage().then(setUsage).catch(() => {});
    api.getUsageHistory(30).then((d) => setHistory(d.events || [])).catch(() => {});
  }, []);

  const pct = usage ? (usage.total_usd / usage.limit_usd) * 100 : 0;
  const low = (usage?.remaining_usd ?? 99) < 5;
  const barColor = pct > 80 ? "var(--bad)" : pct > 50 ? "var(--warn)" : "var(--accent)";

  return (
    <Page>
      <PageHeader title="Usage" subtitle="What Kaia costs to run, by provider and event" />

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6 rise">
        <Card className="md:col-span-2">
          <div className="text-[11px] font-medium uppercase tracking-[0.12em] text-text-3 mb-3">This month</div>
          <div className="flex items-baseline gap-3">
            <span className="text-[40px] leading-none font-semibold tracking-[-0.03em] text-text tnum">
              ${usage?.total_usd?.toFixed(2) ?? "0.00"}
            </span>
            <span className="text-sm text-text-4 tnum">of ${usage?.limit_usd?.toFixed(2) ?? "—"}</span>
          </div>
          <div className="mt-6">
            <div className="h-2 rounded-full overflow-hidden bg-surface-raised">
              <div className="h-full rounded-full transition-all duration-500"
                style={{ width: `${Math.min(pct, 100)}%`, background: barColor }} />
            </div>
            <div className="flex justify-between mt-2 text-[11px] text-text-4 tnum">
              <span>{pct.toFixed(1)}% used</span>
              <span>${usage?.remaining_usd?.toFixed(2) ?? "—"} left</span>
            </div>
          </div>
        </Card>

        <Card>
          <div className="text-[11px] font-medium uppercase tracking-[0.12em] text-text-3 mb-3">Events</div>
          <div className="text-[32px] leading-none font-semibold tracking-[-0.03em] text-text tnum">{history.length}</div>
          <div className="text-xs text-text-4 mt-2">last 30 days</div>
          {low && (
            <div className="flex items-center gap-2 mt-4 px-3 py-2 rounded-lg text-[11px] text-bad"
              style={{ background: "var(--bad-soft)" }}>
              <AlertTriangle size={12} /> Budget running low
            </div>
          )}
        </Card>
      </div>

      {usage?.by_provider && Object.keys(usage.by_provider).length > 0 && (
        <Card className="mb-6 rise" >
          <CardTitle>By provider</CardTitle>
          <div className="space-y-4">
            {Object.entries(usage.by_provider)
              .sort(([, a], [, b]) => (b as number) - (a as number))
              .map(([p, cost]) => {
                const share = usage.total_usd > 0 ? ((cost as number) / usage.total_usd) * 100 : 0;
                return (
                  <div key={p}>
                    <div className="flex justify-between text-[13px] mb-2">
                      <span className="capitalize text-text-2">{p.replace(/_/g, " ")}</span>
                      <span className="font-mono text-text tnum">${(cost as number).toFixed(4)}</span>
                    </div>
                    <div className="h-1.5 rounded-full overflow-hidden bg-surface-raised">
                      <div className="h-full rounded-full bg-accent" style={{ width: `${share}%`, opacity: 0.8 }} />
                    </div>
                  </div>
                );
              })}
          </div>
        </Card>
      )}

      <Card padded={false} className="rise overflow-hidden">
        <div className="px-6 pt-6"><CardTitle>Recent events</CardTitle></div>
        {history.length === 0 ? (
          <EmptyState scene={<SceneLedger />} title="No usage recorded" body="Costs appear here as soon as Kaia starts working." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-[13px]">
              <thead>
                <tr className="text-left text-[10px] uppercase tracking-[0.1em] text-text-4 border-b border-border">
                  <th className="font-medium py-2 px-6">Provider</th>
                  <th className="font-medium py-2 pr-6">Type</th>
                  <th className="font-medium py-2 pr-6">Qty</th>
                  <th className="font-medium py-2 pr-6">Cost</th>
                  <th className="font-medium py-2 pr-6">Model</th>
                  <th className="font-medium py-2 pr-6">When</th>
                </tr>
              </thead>
              <tbody>
                {history.slice(0, 50).map((e, i) => (
                  <tr key={i} className="border-b border-border last:border-0 hover:bg-surface-hover transition-colors">
                    <td className="py-2.5 px-6 capitalize text-text-2">{e.provider.replace(/_/g, " ")}</td>
                    <td className="py-2.5 pr-6 text-text-3">{e.event_type}</td>
                    <td className="py-2.5 pr-6 font-mono text-xs text-text-3 tnum">{e.quantity} {e.unit}</td>
                    <td className="py-2.5 pr-6 font-mono text-xs text-text tnum">${parseFloat(e.estimated_cost_usd).toFixed(4)}</td>
                    <td className="py-2.5 pr-6 font-mono text-[11px] text-text-4">{e.model || "—"}</td>
                    <td className="py-2.5 pr-6 text-[11px] text-text-4">{new Date(e.created_at).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </Page>
  );
}
