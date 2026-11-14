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

/* Read-only because it is read-only: these come from the server's own
   configuration, so showing them in an input box would promise an edit that
   never lands. */
function LiveValue({ value }: { value?: string | number }) {
  return (
    <div className="w-full bg-control/60 border border-[var(--control-border)] rounded-lg px-3 py-2 font-mono text-xs text-text-2">
      {value ?? "—"}
    </div>
  );
}

export default function AgentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [agent, setAgent] = useState<any>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  // Model choice is server configuration, not per-agent data. This card used
  // to edit columns on the agent row that nothing ever read, so it could sit
  // showing gpt-4o while every request went somewhere else entirely.
  const [live, setLive] = useState<any>(null);

  useEffect(() => {
    api.getAgent(id).then((d) => setAgent(d.agent)).catch(() => router.push("/agents"));
    api.getSystemStatus().then(setLive).catch(() => {});
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
      <div className="flex items-center justify-between gap-3 mb-8 pt-10 md:pt-0">
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
          <div className="flex items-baseline justify-between gap-3">
            <h3 className="text-sm font-medium text-text">Models</h3>
            <span className="text-[11px] text-text-4">live on the server</span>
          </div>
          <Row label="Fast — routine tasks">
            <LiveValue value={live?.models?.fast} />
          </Row>
          <Row label="Standard — complex tasks">
            <LiveValue value={live?.models?.standard} />
          </Row>
          <Row label="Premium — hard reasoning">
            <LiveValue value={live?.models?.premium} />
          </Row>
          <Row label="Max tool calls per turn">
            <LiveValue value={live?.limits?.max_tool_calls_per_turn} />
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
