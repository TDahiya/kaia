"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Activity, Bot, MessageSquare, Brain, Phone, DollarSign } from "lucide-react";

function StatCard({ label, value, icon: Icon, sub }: { label: string; value: string; icon: any; sub?: string }) {
  return (
    <div className="bg-surface border border-border rounded-xl p-5">
      <div className="flex items-center justify-between mb-3">
        <span className="text-muted text-sm">{label}</span>
        <Icon size={18} className="text-muted" />
      </div>
      <div className="text-2xl font-semibold">{value}</div>
      {sub && <div className="text-xs text-muted mt-1">{sub}</div>}
    </div>
  );
}

export default function DashboardOverview() {
  const [usage, setUsage] = useState<any>(null);
  const [status, setStatus] = useState<any>(null);
  const [convos, setConvos] = useState<any[]>([]);

  useEffect(() => {
    api.getUsage().then(setUsage).catch(() => {});
    api.getSystemStatus().then(setStatus).catch(() => {});
    api.getConversations(5).then((d) => setConvos(d.conversations || [])).catch(() => {});
  }, []);

  const configured = status
    ? Object.values(status).filter((v) => v === "configured").length
    : 0;
  const total = status ? Object.keys(status).filter((k) => k !== "models" && k !== "limits").length : 0;

  return (
    <div>
      <h2 className="text-2xl font-semibold mb-6">Dashboard</h2>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatCard
          label="Month Spend"
          value={usage ? `$${usage.total_usd.toFixed(2)}` : "—"}
          icon={DollarSign}
          sub={usage ? `$${usage.remaining_usd.toFixed(2)} remaining` : undefined}
        />
        <StatCard
          label="Conversations"
          value={convos.length > 0 ? `${convos.length}+` : "0"}
          icon={MessageSquare}
        />
        <StatCard label="System Health" value={`${configured}/${total}`} icon={Activity} sub="services configured" />
        <StatCard label="Memories" value="—" icon={Brain} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent Conversations */}
        <div className="bg-surface border border-border rounded-xl p-5">
          <h3 className="font-medium mb-4">Recent Conversations</h3>
          {convos.length === 0 ? (
            <p className="text-sm text-muted">No conversations yet. Start chatting!</p>
          ) : (
            <div className="space-y-2">
              {convos.map((c) => (
                <div key={c.id} className="flex items-center justify-between py-2 border-b border-border last:border-0">
                  <div>
                    <div className="text-sm">{c.title || "Untitled"}</div>
                    <div className="text-xs text-muted">{new Date(c.started_at).toLocaleString()}</div>
                  </div>
                  <span className="text-xs px-2 py-0.5 rounded bg-surface-hover text-muted">{c.mode}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* System Status */}
        <div className="bg-surface border border-border rounded-xl p-5">
          <h3 className="font-medium mb-4">System Status</h3>
          {status ? (
            <div className="space-y-2">
              {Object.entries(status)
                .filter(([k]) => k !== "models" && k !== "limits")
                .map(([key, val]) => (
                  <div key={key} className="flex items-center justify-between py-1">
                    <span className="text-sm capitalize">{key.replace(/_/g, " ")}</span>
                    <span
                      className={`text-xs px-2 py-0.5 rounded ${
                        val === "configured" ? "bg-green-900/30 text-green-400" : "bg-yellow-900/30 text-yellow-400"
                      }`}
                    >
                      {val as string}
                    </span>
                  </div>
                ))}
            </div>
          ) : (
            <p className="text-sm text-muted">Loading...</p>
          )}
        </div>

        {/* Monthly Cost Breakdown */}
        {usage?.by_provider && Object.keys(usage.by_provider).length > 0 && (
          <div className="bg-surface border border-border rounded-xl p-5">
            <h3 className="font-medium mb-4">Cost Breakdown</h3>
            <div className="space-y-2">
              {Object.entries(usage.by_provider).map(([provider, cost]) => (
                <div key={provider} className="flex items-center justify-between py-1">
                  <span className="text-sm capitalize">{provider.replace(/_/g, " ")}</span>
                  <span className="text-sm font-mono">${(cost as number).toFixed(4)}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
