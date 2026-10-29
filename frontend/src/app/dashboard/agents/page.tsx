"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Plus, Copy, Trash2, Bot, ChevronRight } from "lucide-react";
import Link from "next/link";

export default function AgentsPage() {
  const [agents, setAgents] = useState<any[]>([]);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ name: "", description: "", system_prompt: "" });

  const load = () => api.getAgents().then((d) => setAgents(d.agents || [])).catch(() => {});
  useEffect(() => { load(); }, []);

  const create = async () => {
    if (!form.name) return;
    await api.createAgent(form);
    setForm({ name: "", description: "", system_prompt: "" });
    setShowCreate(false);
    load();
  };

  const clone = async (id: string) => {
    await api.cloneAgent(id);
    load();
  };

  const remove = async (id: string) => {
    if (!confirm("Delete this agent?")) return;
    await api.deleteAgent(id);
    load();
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-semibold">Agents</h2>
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-accent/20 text-accent hover:bg-accent/30 text-sm"
        >
          <Plus size={16} /> Create Agent
        </button>
      </div>

      {showCreate && (
        <div className="bg-surface border border-border rounded-xl p-5 mb-6">
          <h3 className="font-medium mb-4">New Agent</h3>
          <div className="space-y-3">
            <input
              placeholder="Agent name"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-accent/50"
            />
            <input
              placeholder="Description"
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-accent/50"
            />
            <textarea
              placeholder="System prompt / instructions"
              value={form.system_prompt}
              onChange={(e) => setForm({ ...form, system_prompt: e.target.value })}
              rows={4}
              className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-accent/50 resize-none"
            />
            <div className="flex gap-2">
              <button onClick={create} className="px-4 py-2 rounded-lg bg-accent text-black text-sm font-medium hover:bg-accent/90">
                Create
              </button>
              <button onClick={() => setShowCreate(false)} className="px-4 py-2 rounded-lg text-sm text-muted hover:bg-surface-hover">
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {agents.length === 0 ? (
        <div className="text-center py-16 text-muted">
          <Bot size={48} className="mx-auto mb-4 opacity-30" />
          <p>No agents yet. Create one to get started.</p>
        </div>
      ) : (
        <div className="grid gap-4">
          {agents.map((a) => (
            <div key={a.id} className="bg-surface border border-border rounded-xl p-5 flex items-center justify-between">
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <h3 className="font-medium">{a.name}</h3>
                  {a.is_default && (
                    <span className="text-xs px-2 py-0.5 rounded bg-accent/20 text-accent">Default</span>
                  )}
                </div>
                {a.description && <p className="text-sm text-muted mt-1">{a.description}</p>}
                <div className="flex gap-4 mt-2 text-xs text-muted">
                  <span>Voice: {a.voice_id}</span>
                  <span>Fast: {a.model_fast}</span>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <button onClick={() => clone(a.id)} className="p-2 rounded-lg hover:bg-surface-hover text-muted" title="Clone">
                  <Copy size={16} />
                </button>
                <button onClick={() => remove(a.id)} className="p-2 rounded-lg hover:bg-surface-hover text-red-400" title="Delete">
                  <Trash2 size={16} />
                </button>
                <Link href={`/dashboard/agents/${a.id}`} className="p-2 rounded-lg hover:bg-surface-hover text-muted">
                  <ChevronRight size={16} />
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
