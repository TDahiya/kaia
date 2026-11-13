"use client";

import { useEffect, useState, useRef } from "react";
import { api } from "@/lib/api";
import { Plus, Copy, Check, Ban, RotateCcw, Trash2, ExternalLink, FileText, Upload, AlertTriangle } from "lucide-react";
import { Page, Card, CardTitle, PageHeader, Button, Field, Pill, EmptyState, Spinner } from "@/components/ui";
import { SceneNodes } from "@/components/brand";

const SITE = "https://kaia-ai.duckdns.org";

function timeLeft(iso: string): { text: string; dead: boolean } {
  const ms = new Date(iso).getTime() - Date.now();
  if (ms <= 0) return { text: "expired", dead: true };
  const h = Math.floor(ms / 3_600_000);
  if (h < 1) return { text: `${Math.max(1, Math.floor(ms / 60_000))}m left`, dead: false };
  if (h < 48) return { text: `${h}h left`, dead: false };
  return { text: `${Math.floor(h / 24)}d left`, dead: false };
}

export default function PassesPage() {
  const [passes, setPasses] = useState<any[] | null>(null);
  const [limits, setLimits] = useState<any>(null);
  const [creating, setCreating] = useState(false);
  const [copied, setCopied] = useState("");
  const [form, setForm] = useState({ label: "", note: "", days: 1, max_messages: 20, max_calls: 1 });
  const [cv, setCv] = useState<any>(null);
  const [cvBusy, setCvBusy] = useState(false);
  const [cvError, setCvError] = useState("");
  const cvRef = useRef<HTMLInputElement>(null);

  const load = () =>
    api.getPasses()
      .then((d) => { setPasses(d.passes || []); setLimits(d.limits); })
      .catch(() => setPasses([]));

  const loadCv = () => api.getGuestCv().then(setCv).catch(() => setCv({ uploaded: false }));

  useEffect(() => { load(); loadCv(); }, []);

  const uploadCv = async (file: File) => {
    setCvBusy(true);
    setCvError("");
    try {
      await api.uploadGuestCv(file);
      loadCv();
    } catch (e: any) {
      setCvError(e.message);
    } finally {
      setCvBusy(false);
      if (cvRef.current) cvRef.current.value = "";
    }
  };

  const create = async () => {
    if (!form.label.trim()) return;
    await api.createPass(form);
    setForm({ label: "", note: "", days: 1, max_messages: 20, max_calls: 1 });
    setCreating(false);
    load();
  };

  /* The message has to describe the pass you actually issued. It used to
     say "24 hours" whatever the expiry was, so a 7-day code went out
     telling people it died tomorrow. */
  const validFor = (iso: string) => {
    const ms = new Date(iso).getTime() - Date.now();
    if (ms <= 0) return "expired";
    const hours = Math.round(ms / 3_600_000);
    if (hours < 36) return `good for ${hours} hour${hours === 1 ? "" : "s"}`;
    return `good for ${Math.round(hours / 24)} days`;
  };

  const copyInvite = (p: any) => {
    const calls = p.max_calls > 0
      ? ` and ${p.max_calls} phone call${p.max_calls === 1 ? "" : "s"}.`
      : ".";
    const text = [
      `Here's your access code for Kaia — ${p.code}`,
      "",
      SITE,
      "",
      `It's ${validFor(p.expires_at)} and covers ${p.max_messages} messages${calls}`,
      "",
      "She can email you my CV, read a job spec and tell you honestly where I fit, book time with me directly, or walk you through how any of it was built.",
    ].join("\n");
    navigator.clipboard.writeText(text);
    setCopied(p.code);
    setTimeout(() => setCopied(""), 2000);
  };

  const active = (passes || []).filter((p) => !p.revoked && !timeLeft(p.expires_at).dead);
  const callsUsedToday = (passes || []).reduce((n, p) => n + (p.used_calls || 0), 0);

  return (
    <Page>
      <PageHeader
        title="Guest passes"
        subtitle="Codes you hand out individually, so you know who used what"
        action={
          <Button variant="primary" onClick={() => setCreating(true)}>
            <Plus size={14} /> New pass
          </Button>
        }
      />

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <Card>
          <div className="text-[11px] font-medium uppercase tracking-[0.12em] text-text-3 mb-3">Active</div>
          <div className="text-[28px] leading-none font-semibold text-text tnum">{active.length}</div>
        </Card>
        <Card>
          <div className="text-[11px] font-medium uppercase tracking-[0.12em] text-text-3 mb-3">Calls used</div>
          <div className="text-[28px] leading-none font-semibold text-text tnum">{callsUsedToday}</div>
          {limits && <div className="text-xs text-text-4 mt-2">of {limits.daily_calls}/day</div>}
        </Card>
        <Card className="col-span-2">
          <div className="text-[11px] font-medium uppercase tracking-[0.12em] text-text-3 mb-3">Portal</div>
          <a href={`${SITE}/try`} target="_blank" rel="noopener noreferrer"
            className="text-[14px] font-mono text-accent hover:underline inline-flex items-center gap-1.5">
            {SITE.replace("https://", "")}/try <ExternalLink size={12} />
          </a>
          <div className="text-xs text-text-4 mt-2">Needs a code — nothing is public</div>
        </Card>
      </div>

      <Card className="mb-6">
        <CardTitle
          action={cv?.uploaded ? <Pill tone="ok">loaded</Pill> : <Pill tone="warn">not uploaded</Pill>}
        >
          <span className="flex items-center gap-2"><FileText size={13} /> CV</span>
        </CardTitle>

        <p className="text-[13px] text-text-3 mb-4 leading-relaxed">
          One upload does two jobs — the PDF is what gets emailed, and the text
          is what Kaia answers from. No chunking or retrieval: a CV fits in
          context whole, so she sees all of it rather than a retrieved fragment.
        </p>

        <input ref={cvRef} type="file" hidden accept=".pdf"
          onChange={(e) => { const f = e.target.files?.[0]; if (f) uploadCv(f); }} />

        <div className="flex flex-wrap items-center gap-3">
          <Button variant={cv?.uploaded ? "outline" : "primary"} onClick={() => cvRef.current?.click()} disabled={cvBusy}>
            <Upload size={14} /> {cvBusy ? "Reading…" : cv?.uploaded ? "Replace" : "Upload CV"}
          </Button>
          {cv?.uploaded && (
            <span className="text-[12px] text-text-4 tnum">
              {cv.filename} · {Math.round(cv.size_bytes / 1024)}KB · {cv.extracted_chars.toLocaleString()} chars extracted
            </span>
          )}
        </div>

        {cvError && (
          <div className="flex items-start gap-2 mt-3 text-[12px] text-bad">
            <AlertTriangle size={12} className="mt-0.5 flex-shrink-0" /> {cvError}
          </div>
        )}
      </Card>

      {creating && (
        <Card className="mb-4 rise">
          <h3 className="text-sm font-medium text-text mb-4">New pass</h3>
          <div className="space-y-3">
            <Field value={form.label} onChange={(v) => setForm({ ...form, label: v })}
              placeholder="Who is it for? e.g. Amazon — Sarah" />
            <Field value={form.note} onChange={(v) => setForm({ ...form, note: v })}
              placeholder="Note to yourself (optional)" />
            <div className="grid grid-cols-3 gap-3">
              {([
                ["Days", "days", 1, 30],
                ["Messages", "max_messages", 1, 200],
                ["Calls", "max_calls", 0, 5],
              ] as const).map(([label, key, min, max]) => (
                <label key={key} className="block">
                  <span className="block text-[11px] uppercase tracking-[0.1em] text-text-4 mb-2">{label}</span>
                  <input
                    type="number" min={min} max={max}
                    value={(form as any)[key]}
                    onChange={(e) => setForm({ ...form, [key]: parseInt(e.target.value) || min })}
                    className="w-full bg-control border border-[var(--control-border)] rounded-lg px-3 py-2 text-sm text-text tnum"
                  />
                </label>
              ))}
            </div>
            <div className="flex gap-2 pt-1">
              <Button variant="primary" onClick={create}>Create</Button>
              <Button onClick={() => setCreating(false)}>Cancel</Button>
            </div>
          </div>
        </Card>
      )}

      {passes === null ? (
        <div className="flex justify-center py-16"><Spinner size={20} /></div>
      ) : passes.length === 0 && !creating ? (
        <EmptyState
          scene={<SceneNodes />}
          title="No passes yet"
          body="Create one per person. You'll see exactly who used theirs, how much, and you can revoke a single code without touching the rest."
          action={<Button variant="primary" onClick={() => setCreating(true)}><Plus size={14} /> Create a pass</Button>}
        />
      ) : (
        <div className="space-y-2">
          {passes.map((p) => {
            const left = timeLeft(p.expires_at);
            const dead = p.revoked || left.dead;
            return (
              <Card key={p.id} className={dead ? "opacity-50" : ""}>
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2.5 flex-wrap">
                      <span className="font-mono text-[15px] font-medium text-accent tracking-wide">{p.code}</span>
                      {p.revoked
                        ? <Pill tone="bad">revoked</Pill>
                        : <Pill tone={left.dead ? "bad" : "ok"}>{left.text}</Pill>}
                      {!p.first_used_at && !dead && <Pill>unused</Pill>}
                    </div>
                    <div className="text-[13px] text-text-2 mt-2 flex items-center gap-2">
                      {p.label?.startsWith("signup:") ? (
                        <>
                          <span>{p.label.slice(7)}</span>
                          <Pill>signed up</Pill>
                        </>
                      ) : p.label}
                    </div>
                    {p.note && <div className="text-[12px] text-text-4 mt-1">{p.note}</div>}
                    <div className="flex flex-wrap gap-4 mt-3 text-[11px] text-text-4 tnum">
                      <span>{p.used_messages}/{p.max_messages} messages</span>
                      <span>{p.used_calls}/{p.max_calls} calls</span>
                      {p.last_used_at && <span>last used {new Date(p.last_used_at).toLocaleString()}</span>}
                    </div>
                  </div>

                  <div className="flex items-center gap-1 flex-shrink-0">
                    {!dead && (
                      <Button size="sm" onClick={() => copyInvite(p)}
                        title="Copy the invite message">
                        {copied === p.code ? <Check size={14} /> : <Copy size={14} />}
                      </Button>
                    )}
                    {p.revoked ? (
                      <Button size="sm" title="Put back into service"
                        onClick={async () => {
                          await api.setPassRevoked(p.id, false);
                          load();
                        }}>
                        <RotateCcw size={14} />
                      </Button>
                    ) : (
                      <Button size="sm" variant="danger" title="Revoke"
                        onClick={async () => {
                          if (!confirm(`Revoke ${p.code}? It stops working immediately, but you can resume it later.`)) return;
                          await api.setPassRevoked(p.id, true);
                          load();
                        }}>
                        <Ban size={14} />
                      </Button>
                    )}
                    <Button size="sm" variant="danger" title="Delete permanently"
                      onClick={async () => {
                        if (!confirm(`Delete ${p.code} permanently? This removes it and its usage history from the database and cannot be undone.`)) return;
                        await api.deletePass(p.id);
                        load();
                      }}>
                      <Trash2 size={14} />
                    </Button>
                  </div>
                </div>
              </Card>
            );
          })}
        </div>
      )}
    </Page>
  );
}
