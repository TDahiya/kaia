"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import Link from "next/link";
import { ArrowUpRight, MessageSquare, Phone } from "lucide-react";
import { Page, Card, CardTitle, PageHeader, Pill, Spinner, Button } from "@/components/ui";
import { SceneSignal } from "@/components/brand";

function Metric({ label, value, foot, tone }: { label: string; value: string; foot?: string; tone?: "accent" }) {
  return (
    <Card className="hover:border-[var(--border-hover)] transition-colors">
      <div className="text-[11px] font-medium uppercase tracking-[0.12em] text-text-3 mb-3">{label}</div>
      <div className={`text-[32px] leading-none font-semibold tracking-[-0.03em] tnum ${tone === "accent" ? "text-accent" : "text-text"}`}>
        {value}
      </div>
      {foot && <div className="text-xs text-text-4 mt-2">{foot}</div>}
    </Card>
  );
}

export default function OverviewPage() {
  const [usage, setUsage] = useState<any>(null);
  const [status, setStatus] = useState<any>(null);
  const [convos, setConvos] = useState<any[]>([]);
  const [calling, setCalling] = useState(false);

  useEffect(() => {
    api.getUsage().then(setUsage).catch(() => {});
    api.getSystemStatus().then(setStatus).catch(() => {});
    api.getConversations(5).then((d) => setConvos(d.conversations || [])).catch(() => {});
  }, []);

  const services = status
    ? Object.entries(status).filter(([k]) => k !== "models" && k !== "limits")
    : [];
  const up = services.filter(([, v]) => v === "configured").length;

  const ring = async () => {
    setCalling(true);
    try { await api.callMe(); } catch {}
    setTimeout(() => setCalling(false), 6000);
  };

  return (
    <Page>
      <PageHeader
        title="Overview"
        subtitle="Everything Kaia is running right now"
        action={
          <Button variant="outline" onClick={ring} disabled={calling}>
            <Phone size={14} />
            {calling ? "Ringing…" : "Call me"}
          </Button>
        }
      />

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6 rise" style={{ animationDelay: "40ms" }}>
        <Metric
          label="Spend"
          value={usage ? `$${usage.total_usd.toFixed(2)}` : "—"}
          foot={usage ? `$${usage.remaining_usd.toFixed(2)} remaining` : undefined}
        />
        <Metric label="Services" value={status ? `${up}/${services.length}` : "—"} foot="configured" />
        <Metric label="Threads" value={String(convos.length)} foot="recent" />
        <Metric
          label="Budget"
          value={usage ? `${Math.round((usage.total_usd / usage.limit_usd) * 100)}%` : "—"}
          foot={usage ? `of $${usage.limit_usd.toFixed(0)} cap` : undefined}
          tone="accent"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 rise" style={{ animationDelay: "80ms" }}>
        <Card>
          <CardTitle
            action={
              <Link href="/chat" className="text-[11px] text-text-4 hover:text-accent flex items-center gap-1 transition-colors">
                Open chat <ArrowUpRight size={11} />
              </Link>
            }
          >
            Recent threads
          </CardTitle>

          {convos.length === 0 ? (
            <div className="flex flex-col items-center py-8">
              <SceneSignal size={132} />
              <p className="text-sm text-text-3 mt-4">Nothing yet — start a conversation.</p>
            </div>
          ) : (
            <div className="-mx-2">
              {convos.map((c) => (
                <Link
                  key={c.id}
                  href="/chat"
                  className="group flex items-center justify-between gap-3 px-2 py-2.5 rounded-lg hover:bg-surface-hover transition-colors"
                >
                  <div className="min-w-0 flex items-center gap-3">
                    <MessageSquare size={14} className="text-text-4 flex-shrink-0" />
                    <div className="min-w-0">
                      <div className="text-sm text-text-2 truncate group-hover:text-text transition-colors">
                        {c.title || "Untitled"}
                      </div>
                      <div className="text-[11px] text-text-4 mt-0.5">
                        {new Date(c.started_at).toLocaleDateString(undefined, { month: "short", day: "numeric" })}
                      </div>
                    </div>
                  </div>
                  <Pill>{c.mode}</Pill>
                </Link>
              ))}
            </div>
          )}
        </Card>

        <Card>
          <CardTitle>System</CardTitle>
          {!status ? (
            <div className="flex justify-center py-10"><Spinner /></div>
          ) : (
            <div className="-mx-2">
              {services.map(([key, val]) => (
                <div key={key} className="flex items-center justify-between px-2 py-2.5">
                  <span className="text-sm text-text-2 capitalize">{key.replace(/_/g, " ")}</span>
                  <Pill tone={val === "configured" ? "ok" : "warn"}>
                    {val === "configured" ? "ready" : "not set"}
                  </Pill>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>
    </Page>
  );
}
