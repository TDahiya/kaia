"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Plus, Trash2, Brain, RefreshCw, Filter } from "lucide-react";

const CATEGORIES = ["", "preference", "fact", "project", "contact", "general"];

export default function MemoriesPage() {
  const [memories, setMemories] = useState<any[]>([]);
  const [summaries, setSummaries] = useState<any[]>([]);
  const [category, setCategory] = useState("");
  const [showAdd, setShowAdd] = useState(false);
  const [form, setForm] = useState({ content: "", category: "general", importance: 5 });
  const [summarizing, setSummarizing] = useState(false);

  const load = () => {
    api.getMemories(category).then((d) => setMemories(d.memories || [])).catch(() => {});
    api.getSummaries().then((d) => setSummaries(d.summaries || [])).catch(() => {});
  };
  useEffect(() => { load(); }, [category]);

  const add = async () => {
    if (!form.content) return;
    await api.createMemory(form);
    setForm({ content: "", category: "general", importance: 5 });
    setShowAdd(false);
    load();
  };

  const remove = async (id: string) => {
    await api.deleteMemory(id);
    load();
  };

  const summarize = async () => {
    setSummarizing(true);
    try {
      await api.triggerSummarize();
      load();
    } finally {
      setSummarizing(false);
    }
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-semibold">Memories</h2>
        <div className="flex gap-2">
          <button
            onClick={summarize}
            disabled={summarizing}
            className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-muted hover:bg-surface-hover"
          >
            <RefreshCw size={16} className={summarizing ? "animate-spin" : ""} />
            {summarizing ? "Summarizing..." : "Run Summary"}
          </button>
          <button
            onClick={() => setShowAdd(true)}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-accent/20 text-accent hover:bg-accent/30 text-sm"
          >
            <Plus size={16} /> Add Memory
          </button>
        </div>
      </div>

      {/* Category filter */}
      <div className="flex gap-2 mb-4">
        {CATEGORIES.map((c) => (
          <button
            key={c || "all"}
            onClick={() => setCategory(c)}
            className={`px-3 py-1 rounded-lg text-sm ${
              category === c ? "bg-accent/20 text-accent" : "text-muted hover:bg-surface-hover"
            }`}
          >
            {c || "All"}
          </button>
        ))}
      </div>

      {showAdd && (
        <div className="bg-surface border border-border rounded-xl p-5 mb-4">
          <textarea
            placeholder="What should I remember?"
            value={form.content}
            onChange={(e) => setForm({ ...form, content: e.target.value })}
            rows={3}
            className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-accent/50 resize-none mb-3"
          />
          <div className="flex gap-3 items-center">
            <select
              value={form.category}
              onChange={(e) => setForm({ ...form, category: e.target.value })}
              className="bg-background border border-border rounded-lg px-3 py-2 text-sm"
            >
              {CATEGORIES.slice(1).map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
            <label className="text-sm text-muted">
              Importance:
              <input
                type="range" min={1} max={10}
                value={form.importance}
                onChange={(e) => setForm({ ...form, importance: parseInt(e.target.value) })}
                className="ml-2 w-24 accent-accent"
              />
              <span className="ml-1">{form.importance}</span>
            </label>
            <button onClick={add} className="px-4 py-2 rounded-lg bg-accent text-black text-sm font-medium">Save</button>
            <button onClick={() => setShowAdd(false)} className="px-3 py-2 text-sm text-muted">Cancel</button>
          </div>
        </div>
      )}

      {/* Memory list */}
      <div className="space-y-2 mb-8">
        {memories.length === 0 ? (
          <div className="text-center py-12 text-muted">
            <Brain size={40} className="mx-auto mb-3 opacity-30" />
            <p>No memories stored yet.</p>
          </div>
        ) : memories.map((m) => (
          <div key={m.id} className="bg-surface border border-border rounded-xl p-4 flex items-start justify-between">
            <div className="flex-1">
              <p className="text-sm">{m.content}</p>
              <div className="flex gap-3 mt-2 text-xs text-muted">
                <span className="px-2 py-0.5 rounded bg-surface-hover">{m.category}</span>
                <span>Importance: {m.importance}/10</span>
                <span>{new Date(m.updated_at).toLocaleDateString()}</span>
              </div>
            </div>
            <button onClick={() => remove(m.id)} className="p-2 text-muted hover:text-red-400">
              <Trash2 size={14} />
            </button>
          </div>
        ))}
      </div>

      {/* Weekly summaries */}
      {summaries.length > 0 && (
        <div>
          <h3 className="font-medium mb-3">Weekly Summaries</h3>
          <div className="space-y-3">
            {summaries.map((s) => (
              <div key={s.id} className="bg-surface border border-border rounded-xl p-4">
                <div className="flex items-center gap-3 mb-2 text-xs text-muted">
                  <span>{s.week_start} — {s.week_end}</span>
                  <span>{s.conversations_processed} conversations</span>
                  <span>{s.memories_updated} memories updated</span>
                </div>
                <p className="text-sm">{s.summary}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
