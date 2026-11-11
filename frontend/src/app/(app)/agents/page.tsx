"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import Link from "next/link";
import { Plus, Copy, Trash2, ChevronRight } from "lucide-react";
import { Page, Card, PageHeader, Button, Field, Pill, EmptyState } from "@/components/ui";
import { SceneOrbit } from "@/components/brand";

export default function AgentsPage() {
  const [agents, setAgents] = useState<any[]>([]);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({ name: "", description: "", system_prompt: "" });

  const load = () => api.getAgents().then((d) => setAgents(d.agents || [])).catch(() => {});
  useEffect(() => { load(); }, []);

  const create = async () => {
    if (!form.name.trim()) return;
    await api.createAgent(form);
    setForm({ name: "", description: "", system_prompt: "" });
    setCreating(false);
    load();
  };

  const remove = async (id: string) => {
    if (!confirm("Delete this agent?")) return;
    await api.deleteAgent(id);
    load();
  };

  return (
    <Page>
      <PageHeader
        title="Agents"
        subtitle="Personalities and instruction sets Kaia can run as"
        action={
          <Button variant="primary" onClick={() => setCreating(true)}>
            <Plus size={14} /> New agent
          </Button>
        }
      />

      {creating && (
        <Card className="mb-4 rise">
          <h3 className="text-sm font-medium text-text mb-4">New agent</h3>
          <div className="space-y-3">
            <Field value={form.name} onChange={(v) => setForm({ ...form, name: v })} placeholder="Name" />
            <Field value={form.description} onChange={(v) => setForm({ ...form, description: v })} placeholder="Short description" />
            <Field value={form.system_prompt} onChange={(v) => setForm({ ...form, system_prompt: v })} placeholder="System prompt — how should this agent behave?" rows={5} />
            <div className="flex gap-2 pt-1">
              <Button variant="primary" onClick={create}>Create</Button>
              <Button onClick={() => setCreating(false)}>Cancel</Button>
            </div>
          </div>
        </Card>
      )}

      {agents.length === 0 && !creating ? (
        <EmptyState
          scene={<SceneOrbit />}
          title="No agents yet"
          body="Agents let you give Kaia a different voice, model, or set of instructions for specific jobs."
          action={<Button variant="primary" onClick={() => setCreating(true)}><Plus size={14} /> Create your first agent</Button>}
        />
      ) : (
        <div className="space-y-3">
          {agents.map((a, i) => (
            <Card key={a.id} className="rise hover:border-[var(--border-hover)] transition-colors" >
              <div className="flex items-start justify-between gap-4" style={{ animationDelay: `${i * 40}ms` }}>
                <div className="min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <h3 className="text-sm font-medium text-text">{a.name}</h3>
                    {a.is_default && <Pill tone="accent">default</Pill>}
                  </div>
                  {a.description && <p className="text-[13px] text-text-3">{a.description}</p>}
                  <div className="flex flex-wrap gap-4 mt-3 text-[11px] font-mono text-text-4">
                    <span>voice · {a.voice_id}</span>
                    <span>model · {a.model_fast}</span>
                  </div>
                </div>
                <div className="flex items-center gap-1 flex-shrink-0">
                  <Button size="sm" onClick={() => api.cloneAgent(a.id).then(load)} title="Duplicate"><Copy size={14} /></Button>
                  <Button size="sm" variant="danger" onClick={() => remove(a.id)} title="Delete"><Trash2 size={14} /></Button>
                  <Link href={`/agents/${a.id}`} className="p-2 rounded-lg text-text-3 hover:text-text hover:bg-surface-hover transition-colors">
                    <ChevronRight size={16} />
                  </Link>
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}
    </Page>
  );
}
