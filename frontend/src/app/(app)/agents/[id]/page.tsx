"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { Save, ArrowLeft, Check } from "lucide-react";
import { Page, Card, Button, Spinner } from "@/components/ui";

const VOICES = [
  "aura-2-theia-en", "aura-2-helios-en", "aura-2-luna-en",
  "aura-2-stella-en", "aura-2-zeus-en", "aura-2-orion-en",
];
const LANGS = ["en", "es", "fr", "de", "it", "pt", "ja", "zh"];

export default function AgentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [agent, setAgent] = useState<any>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    api.getAgent(id).then((d) => setAgent(d.agent)).catch(() => router.push("/agents"));
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

  if (!agent) {
    return <Page><div className="flex justify-center py-20"><Spinner size={20} /></div></Page>;
  }

  const set = (k: string, v: any) => setAgent({ ...agent, [k]: v });

  const inputCls = "w-full bg-control border border-[var(--control-border)] rounded-lg px-3 py-2 text-sm text-text";

  const Row = ({ label, children }: { label: string; children: React.ReactNode }) => (
    <div>
      <label className="block text-[11px] font-medium uppercase tracking-[0.1em] text-text-4 mb-2">{label}</label>
      {children}
    </div>
  );

  return (
    <Page>
      <div className="flex items-center justify-between mb-8 pl-12 md:pl-0">
        <div className="flex items-center gap-3 min-w-0">
          <button onClick={() => router.push("/agents")} aria-label="Back"
            className="p-2 rounded-lg text-text-3 hover:text-text hover:bg-surface-hover transition-colors">
            <ArrowLeft size={18} />
          </button>
          <h1 className="text-2xl font-semibold tracking-[-0.02em] text-text truncate">{agent.name}</h1>
        </div>
        <Button variant="primary" onClick={save} disabled={saving}>
          {saved ? <Check size={14} /> : <Save size={14} />}
          {saved ? "Saved" : saving ? "Saving…" : "Save"}
        </Button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card className="space-y-4">
          <h3 className="text-sm font-medium text-text">General</h3>
          <Row label="Name">
            <input value={agent.name || ""} onChange={(e) => set("name", e.target.value)} className={inputCls} />
          </Row>
          <Row label="Description">
            <input value={agent.description || ""} onChange={(e) => set("description", e.target.value)} className={inputCls} />
          </Row>
          <Row label="Language">
            <select value={agent.language || "en"} onChange={(e) => set("language", e.target.value)} className={inputCls}>
              {LANGS.map((l) => <option key={l} value={l}>{l}</option>)}
            </select>
          </Row>
        </Card>

        <Card className="space-y-4">
          <h3 className="text-sm font-medium text-text">Models</h3>
          <Row label="Fast — routine tasks">
            <input value={agent.model_fast || ""} onChange={(e) => set("model_fast", e.target.value)} className={`${inputCls} font-mono text-xs`} />
          </Row>
          <Row label="Standard — complex tasks">
            <input value={agent.model_standard || ""} onChange={(e) => set("model_standard", e.target.value)} className={`${inputCls} font-mono text-xs`} />
          </Row>
          <Row label="Premium — hard reasoning">
            <input value={agent.model_premium || ""} onChange={(e) => set("model_premium", e.target.value)} className={`${inputCls} font-mono text-xs`} />
          </Row>
          <Row label="Max tool calls per turn">
            <input type="number" value={agent.max_tool_calls_per_turn ?? 15}
              onChange={(e) => set("max_tool_calls_per_turn", parseInt(e.target.value) || 15)}
              className={`${inputCls} tnum`} />
          </Row>
        </Card>

        <Card className="space-y-4 lg:col-span-2">
          <h3 className="text-sm font-medium text-text">Instructions</h3>
          <Row label="System prompt">
            <textarea value={agent.system_prompt || ""} onChange={(e) => set("system_prompt", e.target.value)}
              rows={8} className={`${inputCls} resize-none leading-relaxed`} />
          </Row>
          <Row label="Personality">
            <textarea value={agent.personality || ""} onChange={(e) => set("personality", e.target.value)}
              rows={4} className={`${inputCls} resize-none leading-relaxed`} />
          </Row>
        </Card>

        <Card className="space-y-4">
          <h3 className="text-sm font-medium text-text">Voice</h3>
          <Row label="Deepgram voice">
            <select value={agent.voice_id || VOICES[0]} onChange={(e) => set("voice_id", e.target.value)} className={`${inputCls} font-mono text-xs`}>
              {VOICES.map((v) => <option key={v} value={v}>{v}</option>)}
            </select>
          </Row>
        </Card>

        <Card className="space-y-4">
          <h3 className="text-sm font-medium text-text">Behaviour</h3>
          <label className="flex items-center gap-3 cursor-pointer select-none">
            <input type="checkbox" checked={!!agent.is_default}
              onChange={(e) => set("is_default", e.target.checked)}
              className="w-4 h-4 rounded" style={{ accentColor: "var(--accent)" }} />
            <span className="text-sm text-text-2">Use as the default agent</span>
          </label>
        </Card>
      </div>
    </Page>
  );
}
