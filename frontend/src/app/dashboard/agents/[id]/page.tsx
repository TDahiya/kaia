"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { Save, ArrowLeft } from "lucide-react";

export default function AgentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [agent, setAgent] = useState<any>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    api.getAgent(id).then((d) => setAgent(d.agent)).catch(() => router.push("/dashboard/agents"));
  }, [id, router]);

  const save = async () => {
    if (!agent) return;
    setSaving(true);
    try {
      await api.updateAgent(id, agent);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } finally {
      setSaving(false);
    }
  };

  if (!agent) return <div className="text-muted">Loading...</div>;

  const field = (label: string, key: string, type: "text" | "textarea" | "select" = "text", options?: string[]) => (
    <div>
      <label className="block text-sm text-muted mb-1">{label}</label>
      {type === "textarea" ? (
        <textarea
          value={agent[key] || ""}
          onChange={(e) => setAgent({ ...agent, [key]: e.target.value })}
          rows={6}
          className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-accent/50 resize-none"
        />
      ) : type === "select" ? (
        <select
          value={agent[key] || ""}
          onChange={(e) => setAgent({ ...agent, [key]: e.target.value })}
          className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-accent/50"
        >
          {options?.map((o) => <option key={o} value={o}>{o}</option>)}
        </select>
      ) : (
        <input
          value={agent[key] || ""}
          onChange={(e) => setAgent({ ...agent, [key]: e.target.value })}
          className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-accent/50"
        />
      )}
    </div>
  );

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <button onClick={() => router.push("/dashboard/agents")} className="p-2 rounded-lg hover:bg-surface-hover text-muted">
            <ArrowLeft size={18} />
          </button>
          <h2 className="text-2xl font-semibold">{agent.name}</h2>
        </div>
        <button
          onClick={save}
          disabled={saving}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-accent/20 text-accent hover:bg-accent/30 text-sm disabled:opacity-50"
        >
          <Save size={16} /> {saved ? "Saved!" : saving ? "Saving..." : "Save"}
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="space-y-4 bg-surface border border-border rounded-xl p-5">
          <h3 className="font-medium">General</h3>
          {field("Name", "name")}
          {field("Description", "description")}
          {field("Language", "language", "select", ["en", "es", "fr", "de", "it", "pt", "ja", "zh"])}
        </div>

        <div className="space-y-4 bg-surface border border-border rounded-xl p-5">
          <h3 className="font-medium">Model Configuration</h3>
          {field("Fast Model (routine tasks)", "model_fast")}
          {field("Standard Model (complex tasks)", "model_standard")}
          {field("Premium Model (exceptional tasks)", "model_premium")}
          <div>
            <label className="block text-sm text-muted mb-1">Max Tool Calls Per Turn</label>
            <input
              type="number"
              value={agent.max_tool_calls_per_turn || 15}
              onChange={(e) => setAgent({ ...agent, max_tool_calls_per_turn: parseInt(e.target.value) || 15 })}
              className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-accent/50"
            />
          </div>
        </div>

        <div className="space-y-4 bg-surface border border-border rounded-xl p-5 lg:col-span-2">
          <h3 className="font-medium">Instructions & Personality</h3>
          {field("System Prompt", "system_prompt", "textarea")}
          {field("Personality", "personality", "textarea")}
        </div>

        <div className="space-y-4 bg-surface border border-border rounded-xl p-5">
          <h3 className="font-medium">Voice</h3>
          {field("Voice ID", "voice_id", "select", [
            "aura-2-theia-en", "aura-2-helios-en", "aura-2-luna-en",
            "aura-2-stella-en", "aura-2-zeus-en", "aura-2-orion-en",
          ])}
        </div>

        <div className="space-y-4 bg-surface border border-border rounded-xl p-5">
          <h3 className="font-medium">Settings</h3>
          <label className="flex items-center gap-3 cursor-pointer">
            <input
              type="checkbox"
              checked={agent.is_default || false}
              onChange={(e) => setAgent({ ...agent, is_default: e.target.checked })}
              className="w-4 h-4 rounded accent-accent"
            />
            <span className="text-sm">Set as default agent</span>
          </label>
        </div>
      </div>
    </div>
  );
}
