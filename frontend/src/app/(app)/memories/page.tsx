"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Plus, Trash2, RefreshCw } from "lucide-react";
import { Page, Card, CardTitle, PageHeader, Button, Field, Pill, EmptyState } from "@/components/ui";
import { SceneStack } from "@/components/brand";

const CATEGORIES = ["preference", "fact", "project", "contact", "general"];

export default function MemoriesPage() {
  const [memories, setMemories] = useState<any[]>([]);
  const [summaries, setSummaries] = useState<any[]>([]);
  const [filter, setFilter] = useState("");
  const [adding, setAdding] = useState(false);
  const [form, setForm] = useState({ content: "", category: "general", importance: 5 });
  const [summarizing, setSummarizing] = useState(false);

  const load = () => {
    api.getMemories(filter).then((d) => setMemories(d.memories || [])).catch(() => {});
    api.getSummaries().then((d) => setSummaries(d.summaries || [])).catch(() => {});
  };
  useEffect(() => { load(); }, [filter]);

  const add = async () => {
    if (!form.content.trim()) return;
    await api.createMemory(form);
    setForm({ content: "", category: "general", importance: 5 });
    setAdding(false);
    load();
  };

  const summarize = async () => {
    setSummarizing(true);
    try { await api.triggerSummarize(); load(); } finally { setSummarizing(false); }
  };

  return (
    <Page>
      <PageHeader
        title="Memories"
        subtitle="What Kaia knows about you and carries between conversations"
        action={
          <div className="flex gap-2">
            <Button onClick={summarize} disabled={summarizing}>
              <RefreshCw size={14} className={summarizing ? "animate-spin" : ""} />
              <span className="hidden sm:inline">{summarizing ? "Running…" : "Summarise"}</span>
            </Button>
            <Button variant="primary" onClick={() => setAdding(true)}>
              <Plus size={14} /> Add
            </Button>
          </div>
        }
      />

      <div className="flex flex-wrap gap-2 mb-6">
        {["", ...CATEGORIES].map((c) => (
          <button key={c || "all"} onClick={() => setFilter(c)}
            className={`px-3 py-1.5 rounded-lg text-xs capitalize transition-colors ${
              filter === c
                ? "bg-[var(--accent-soft)] text-accent font-medium"
                : "text-text-3 hover:text-text-2 hover:bg-surface-hover"
            }`}>
            {c || "All"}
          </button>
        ))}
      </div>

      {adding && (
        <Card className="mb-4 rise">
          <Field value={form.content} onChange={(v) => setForm({ ...form, content: v })}
            placeholder="What should Kaia remember?" rows={3} />
          <div className="flex flex-wrap items-center gap-4 mt-4">
            <select value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}
              className="bg-control border border-[var(--control-border)] rounded-lg px-3 py-2 text-xs text-text capitalize">
              {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
            <label className="flex items-center gap-2 text-xs text-text-3">
              Importance
              <input type="range" min={1} max={10} value={form.importance}
                onChange={(e) => setForm({ ...form, importance: +e.target.value })}
                className="w-24" style={{ accentColor: "var(--accent)" }} />
              <span className="tnum text-text w-4">{form.importance}</span>
            </label>
            <div className="flex gap-2 ml-auto">
              <Button variant="primary" onClick={add}>Save</Button>
              <Button onClick={() => setAdding(false)}>Cancel</Button>
            </div>
          </div>
        </Card>
      )}

      {memories.length === 0 && !adding ? (
        <EmptyState
          scene={<SceneStack />}
          title="Nothing stored yet"
          body="Memories persist across every conversation and call. Add one, or just tell Kaia to remember something."
          action={<Button variant="primary" onClick={() => setAdding(true)}><Plus size={14} /> Add a memory</Button>}
        />
      ) : (
        <div className="space-y-2 mb-10">
          {memories.map((m, i) => (
            <div key={m.id}
              className="group flex items-start justify-between gap-4 bg-surface border border-border rounded-xl px-5 py-4 hover:border-[var(--border-hover)] transition-colors rise"
              style={{ animationDelay: `${Math.min(i * 30, 150)}ms` }}>
              <div className="min-w-0">
                <p className="text-sm text-text-2 leading-relaxed">{m.content}</p>
                <div className="flex flex-wrap items-center gap-3 mt-3">
                  <Pill>{m.category}</Pill>
                  <span className="text-[11px] text-text-4 tnum">weight {m.importance}/10</span>
                  <span className="text-[11px] text-text-4">
                    {new Date(m.updated_at).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" })}
                  </span>
                </div>
              </div>
              <button onClick={() => api.deleteMemory(m.id).then(load)} aria-label="Delete memory"
                className="p-2 rounded-lg text-text-4 opacity-0 group-hover:opacity-100 hover:text-bad hover:bg-[var(--bad-soft)] transition-all flex-shrink-0">
                <Trash2 size={14} />
              </button>
            </div>
          ))}
        </div>
      )}

      {summaries.length > 0 && (
        <Card>
          <CardTitle>Weekly summaries</CardTitle>
          <div className="space-y-5">
            {summaries.map((s) => (
              <div key={s.id} className="pb-5 border-b border-border last:border-0 last:pb-0">
                <div className="flex flex-wrap gap-3 mb-2 text-[11px] text-text-4 font-mono">
                  <span>{s.week_start} → {s.week_end}</span>
                  <span className="tnum">{s.conversations_processed} threads</span>
                  <span className="tnum">{s.memories_updated} updated</span>
                </div>
                <p className="text-[13px] text-text-2 leading-relaxed">{s.summary}</p>
              </div>
            ))}
          </div>
        </Card>
      )}
    </Page>
  );
}
