"use client";

import { useState, useRef, useEffect, useMemo } from "react";
import { useRouter } from "next/navigation";
import { ArrowUp, Wrench, Sun, Moon, Phone, X, Check, Paperclip, FileSpreadsheet, FileText, Loader2 } from "lucide-react";
import { KaiaMark, SceneSignal } from "@/components/brand";
import { useTheme } from "@/lib/theme-context";

const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";
const STORE = "kaia-guest-token";

interface Msg {
  role: "user" | "assistant" | "system";
  content: string;
  tools?: string[];
}

const SUGGESTIONS = [
  "How was this actually built?",
  "Send me his CV",
  "Here's a job spec — is he a fit?",
  "Why not use a vector database for spreadsheets?",
];

function RichText({ text }: { text: string }) {
  const parts = useMemo(() => {
    const out: { text: string; href?: string }[] = [];
    const re = /(\[([^\]]+)\]\((https?:\/\/[^\s)]+)\))|(https?:\/\/[^\s<>)\]]+)/g;
    let last = 0;
    let m: RegExpExecArray | null;
    while ((m = re.exec(text)) !== null) {
      if (m.index > last) out.push({ text: text.slice(last, m.index) });
      if (m[1]) out.push({ text: m[2], href: m[3] });
      else out.push({ text: m[4], href: m[4] });
      last = m.index + m[0].length;
    }
    if (last < text.length) out.push({ text: text.slice(last) });
    return out;
  }, [text]);
  return (
    <>
      {parts.map((p, i) =>
        p.href ? (
          <a key={i} href={p.href} target="_blank" rel="noopener noreferrer"
            className="text-accent underline underline-offset-2">{p.text}</a>
        ) : <span key={i}>{p.text}</span>
      )}
    </>
  );
}

export default function GuestPortal() {
  const { theme, toggle } = useTheme();
  const router = useRouter();
  const [token, setToken] = useState<string | null>(null);
  const [label, setLabel] = useState("");
  const [remaining, setRemaining] = useState<any>(null);


  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [tool, setTool] = useState("");
  const endRef = useRef<HTMLDivElement>(null);

  const [files, setFiles] = useState<any[]>([]);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  const attach = async (f: File) => {
    if (!token) return;
    setUploading(true);
    setUploadError("");
    try {
      const fd = new FormData();
      fd.append("file", f);
      const r = await fetch(`${BACKEND}/api/guest/upload`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: fd,
      });
      const d = await r.json();
      if (!r.ok) throw new Error(d.detail || "Upload failed.");
      setFiles((p) => [...p, d]);
    } catch (e: any) {
      setUploadError(e.message);
      setTimeout(() => setUploadError(""), 6000);
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const [callOpen, setCallOpen] = useState(false);
  const [phone, setPhone] = useState("");
  const [callState, setCallState] = useState<"idle" | "dialling" | "done">("idle");
  const [callError, setCallError] = useState("");

  const requestCall = async () => {
    if (!phone.trim() || !token) return;
    setCallState("dialling");
    setCallError("");
    try {
      const r = await fetch(`${BACKEND}/api/guest/callback`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ phone: phone.trim() }),
      });
      const d = await r.json();
      if (!r.ok) throw new Error(d.detail || "That didn't work.");
      setRemaining(d.remaining);
      setCallState("done");
      setTimeout(() => { setCallOpen(false); setCallState("idle"); }, 6000);
    } catch (e: any) {
      setCallError(e.message);
      setCallState("idle");
    }
  };

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages, tool]);

  // Resume an existing session so a refresh doesn't burn a message.
  useEffect(() => {
    const saved = localStorage.getItem(STORE);
    if (!saved) {
      router.replace("/");
      return;
    }
    fetch(`${BACKEND}/api/guest/me`, { headers: { Authorization: `Bearer ${saved}` } })
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((d) => { setToken(saved); setLabel(d.label); setRemaining(d.remaining); })
      .catch(() => {
        localStorage.removeItem(STORE);
        router.replace("/");
      });
  }, [router]);

  const send = async (text?: string) => {
    const body = (text ?? input).trim();
    if (!body || busy || !token) return;
    setInput("");
    setMessages((p) => [...p, { role: "user", content: body }]);
    setBusy(true);
    setTool("");

    const history = messages
      .filter((m) => m.role !== "system")
      .map((m) => ({ role: m.role, content: m.content }));

    let idx = -1;
    try {
      const res = await fetch(`${BACKEND}/api/guest/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ message: body, history, document_ids: files.map((f) => f.id) }),
      });

      if (!res.ok || !res.body) {
        const d = await res.json().catch(() => ({}));
        throw new Error(d.detail || "Something went wrong.");
      }

      const reader = res.body.getReader();
      const dec = new TextDecoder();
      let buf = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        const frames = buf.split("\n\n");
        buf = frames.pop() ?? "";
        for (const f of frames) {
          const line = f.split("\n").find((l) => l.startsWith("data: "));
          if (!line) continue;
          let e: any;
          try { e = JSON.parse(line.slice(6)); } catch { continue; }

          if (e.type === "tool") {
            setTool(e.name);
            setMessages((p) => {
              if (idx < 0) return p;
              const n = [...p];
              n[idx] = { ...n[idx], tools: [...(n[idx].tools || []), e.name] };
              return n;
            });
          } else if (e.type === "delta") {
            setTool("");
            setMessages((p) => {
              const n = [...p];
              if (idx < 0) {
                n.push({ role: "assistant", content: e.text });
                idx = n.length - 1;
              } else {
                n[idx] = { ...n[idx], content: n[idx].content + e.text };
              }
              return n;
            });
          } else if (e.type === "done") {
            setRemaining(e.remaining);
          } else if (e.type === "error") {
            setMessages((p) => [...p, { role: "system", content: e.message }]);
          }
        }
      }
    } catch (e: any) {
      setMessages((p) => [...p, { role: "system", content: e.message }]);
    } finally {
      setBusy(false);
      setTool("");
    }
  };

  const out = remaining && remaining.messages <= 0;

  /* No token? There is exactly one place to enter a code, and it is the
     front door. Keeping a second form here is how people ended up typing
     their code into the owner's password field. */
  if (!token) {
    return (
      <div className="flex items-center justify-center h-screen bg-bg">
        <div style={{ animation: "breathe 1.6s ease-in-out infinite" }}>
          <KaiaMark size={36} />
        </div>
      </div>
    );
  }

  /* ── Portal ──
     h-screen, not min-h-screen: the container must be exactly the viewport
     so only the transcript scrolls and the header and composer stay put. */
  return (
    <div className="h-screen flex flex-col overflow-hidden">
      <div className="bloom" />
      <div className="grid-field" />

      {callOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center px-6"
          style={{ background: "var(--scrim)" }}
          onClick={() => callState !== "dialling" && setCallOpen(false)}>
          <div className="w-full max-w-[380px] rounded-2xl bg-surface border border-border p-6 rise"
            onClick={(e) => e.stopPropagation()}>
            {callState === "done" ? (
              <div className="text-center py-4">
                <div className="flex justify-center mb-4">
                  <span className="w-10 h-10 rounded-full flex items-center justify-center"
                    style={{ background: "var(--accent-soft)", color: "var(--accent)" }}>
                    <Check size={18} />
                  </span>
                </div>
                <p className="text-[15px] text-text">Calling you now.</p>
                <p className="text-[13px] text-text-3 mt-1.5">
                  It should ring in a few seconds. The call ends automatically after about two minutes.
                </p>
              </div>
            ) : (
              <>
                <div className="flex items-start justify-between mb-1">
                  <h3 className="text-[16px] font-medium text-text">Have Kaia call you</h3>
                  <button onClick={() => setCallOpen(false)} aria-label="Close"
                    className="p-1 -mt-1 -mr-1 text-text-4 hover:text-text">
                    <X size={16} />
                  </button>
                </div>
                <p className="text-[13px] text-text-3 mb-5 leading-relaxed">
                  She&apos;ll ring you and answer questions about his work out loud.
                  Include your country code.
                </p>

                <input
                  value={phone}
                  onChange={(e) => { setPhone(e.target.value); setCallError(""); }}
                  onKeyDown={(e) => e.key === "Enter" && requestCall()}
                  placeholder="+353 87 123 4567"
                  autoFocus
                  className="w-full bg-control border border-[var(--control-border)] rounded-xl px-4 py-3 text-[15px] font-mono text-text"
                />

                {callError && <p className="text-[12px] text-bad mt-2.5">{callError}</p>}

                <button onClick={requestCall} disabled={!phone.trim() || callState === "dialling"}
                  className="w-full mt-4 py-3 rounded-xl text-sm font-medium press disabled:opacity-40"
                  style={{ background: "var(--accent)", color: "var(--on-accent)" }}>
                  {callState === "dialling" ? "Dialling…" : "Call me"}
                </button>

                <p className="text-[11px] text-text-4 mt-3 text-center">
                  Your number is used for this one call and isn&apos;t stored.
                </p>
              </>
            )}
          </div>
        </div>
      )}

      <header className="relative z-10 flex-shrink-0 flex items-center justify-between px-6 h-16 border-b border-border bg-bg/80 backdrop-blur">
        <div className="flex items-center gap-2.5">
          <KaiaMark size={22} />
          <span className="text-[15px] font-medium tracking-[0.08em] lowercase text-text">kaia</span>
          {label && <span className="hidden sm:inline text-[12px] text-text-4 ml-2">for {label}</span>}
        </div>
        <div className="flex items-center gap-4">
          {remaining && (
            remaining.calls > 0 && remaining.calls_today_left > 0 ? (
              <button onClick={() => setCallOpen(true)}
                className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs text-text-2 border border-border hover:border-[var(--border-hover)] hover:text-accent transition-colors press">
                <Phone size={13} /> <span className="hidden sm:inline">Call me</span>
              </button>
            ) : (
              /* Shown but inert: a visible locked capability says more about
                 what this can do than hiding it would. */
              <span
                title="Voice calls need an access code from Tanishq"
                className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs text-text-4 border border-border cursor-not-allowed">
                <Phone size={13} />
                <span className="hidden sm:inline">Call me - ask for a code</span>
              </span>
            )
          )}
          {remaining && (
            <span className="text-[12px] text-text-3 tnum">
              {remaining.messages} message{remaining.messages === 1 ? "" : "s"} left
            </span>
          )}
          <button onClick={toggle} aria-label="Toggle theme" className="p-1.5 text-text-3 hover:text-text">
            {theme === "dark" ? <Sun size={15} /> : <Moon size={15} />}
          </button>
        </div>
      </header>

      <div className="relative z-10 flex-1 overflow-y-auto">
        <div className="max-w-[720px] mx-auto px-6 py-10">
          {messages.length === 0 && (
            <div className="flex flex-col items-center text-center pt-[6vh] rise">
              <SceneSignal size={176} />
              <h2 className="text-[26px] font-semibold tracking-[-0.03em] text-text mt-6">
                Ask me about Tanishq
              </h2>
              <p className="text-[14px] text-text-3 mt-2 max-w-[420px]">
                Or ask how I work — I&apos;m the thing he built, so that&apos;s
                a fair question to put to me.
              </p>
              <div className="grid sm:grid-cols-2 gap-2 mt-8 w-full max-w-[540px]">
                {SUGGESTIONS.map((s) => (
                  <button key={s} onClick={() => send(s)}
                    className="text-left px-4 py-3 rounded-xl text-[13px] bg-surface border border-border text-text-3 hover:border-[var(--border-hover)] hover:text-text transition-colors press">
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}

          <div className="space-y-6">
            {messages.map((m, i) => (
              <div key={i} className="rise">
                {m.role === "user" ? (
                  <div className="flex justify-end">
                    <div className="max-w-[80%] rounded-2xl rounded-br-md px-4 py-3 bg-surface-raised border border-border">
                      <div className="text-[14px] leading-[1.65] text-text whitespace-pre-wrap">{m.content}</div>
                    </div>
                  </div>
                ) : m.role === "system" ? (
                  <div className="text-[13px] text-bad px-4 py-3 rounded-xl" style={{ background: "var(--bad-soft)" }}>
                    {m.content}
                  </div>
                ) : (
                  <div className="flex gap-3">
                    <div className="flex-shrink-0 mt-0.5"><KaiaMark size={22} orbit={false} /></div>
                    <div className="min-w-0 flex-1">
                      {m.tools && m.tools.length > 0 && (
                        <div className="flex flex-wrap gap-1.5 mb-2">
                          {m.tools.map((t, j) => (
                            <span key={j} className="inline-flex items-center gap-1 text-[10px] font-mono px-2 py-1 rounded-md"
                              style={{ background: "var(--accent-soft)", color: "var(--accent)" }}>
                              <Wrench size={9} /> {t}
                            </span>
                          ))}
                        </div>
                      )}
                      <div className="text-[14px] leading-[1.75] text-text-2 whitespace-pre-wrap">
                        <RichText text={m.content} />
                      </div>
                    </div>
                  </div>
                )}
              </div>
            ))}

            {busy && messages[messages.length - 1]?.role !== "assistant" && (
              <div className="flex gap-3 rise">
                <div className="flex-shrink-0 mt-0.5"><KaiaMark size={22} orbit={false} /></div>
                <div className="flex items-center gap-2 pt-2">
                  <div className="flex items-center gap-1.5">
                    {[0, 0.2, 0.4].map((d) => (
                      <span key={d} className="w-1.5 h-1.5 rounded-full bg-accent"
                        style={{ animation: `breathe 1.2s ${d}s infinite` }} />
                    ))}
                  </div>
                  {tool && <span className="text-[11px] font-mono text-text-4">{tool}</span>}
                </div>
              </div>
            )}
          </div>
          <div ref={endRef} />
        </div>
      </div>

      <div className="relative z-10 flex-shrink-0 px-6 pb-8 pt-2">
        <div className="max-w-[720px] mx-auto">
          {out ? (
            <div className="rounded-2xl border border-border bg-surface px-5 py-4 text-center">
              <p className="text-[14px] text-text">That&apos;s the pass used up.</p>
              <p className="text-[13px] text-text-3 mt-1">
                Email{" "}
                <a href="mailto:tanishq.dahiya2@mail.dcu.ie" className="text-accent underline underline-offset-2">
                  tanishq.dahiya2@mail.dcu.ie
                </a>{" "}
                and he&apos;ll reply himself.
              </p>
            </div>
          ) : (
            <div>
              {uploadError && (
                <div className="mb-2 text-[12px] px-3 py-2 rounded-lg text-bad" style={{ background: "var(--bad-soft)" }}>
                  {uploadError}
                </div>
              )}
              {files.length > 0 && (
                <div className="flex flex-wrap gap-2 mb-2">
                  {files.map((f) => (
                    <span key={f.id}
                      className="inline-flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-[12px] bg-surface border border-border text-text-2">
                      {f.kind === "table"
                        ? <FileSpreadsheet size={13} className="text-accent" />
                        : <FileText size={13} className="text-text-3" />}
                      <span className="max-w-[180px] truncate">{f.filename}</span>
                    </span>
                  ))}
                </div>
              )}
            <div className="flex items-end gap-2 rounded-2xl bg-surface border border-border px-2 py-2 focus-within:border-[var(--accent-ring)] transition-colors">
              <input ref={fileRef} type="file" hidden
                accept=".csv,.tsv,.xlsx,.xlsm,.xls,.json,.pdf,.txt,.md"
                onChange={(e) => { const f = e.target.files?.[0]; if (f) attach(f); }} />
              <button onClick={() => fileRef.current?.click()} disabled={uploading || busy}
                aria-label="Attach a file" title="Attach a spreadsheet, PDF or text file"
                className="mb-0.5 p-2 rounded-lg text-text-4 hover:text-accent hover:bg-surface-hover transition-colors disabled:opacity-40">
                {uploading ? <Loader2 size={16} className="animate-spin" /> : <Paperclip size={16} />}
              </button>
              <input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && send()}
                placeholder="Ask about his work, or paste a job spec…"
                disabled={busy}
                className="flex-1 bg-transparent py-2.5 text-[14px] text-text focus:outline-none"
              />
              <button onClick={() => send()} disabled={!input.trim() || busy} aria-label="Send"
                className="mb-0.5 p-2 rounded-lg press disabled:opacity-30"
                style={{
                  background: input.trim() ? "var(--accent)" : "transparent",
                  color: input.trim() ? "var(--on-accent)" : "var(--text-4)",
                }}>
                <ArrowUp size={15} strokeWidth={2.5} />
              </button>
            </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
