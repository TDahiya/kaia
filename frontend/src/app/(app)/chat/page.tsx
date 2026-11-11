"use client";

import { useState, useRef, useEffect, useCallback, useMemo } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import {
  Mic, Square, Wrench, Phone, Plus, PanelLeft, ArrowUp, Trash2, Check, X,
} from "lucide-react";
import { KaiaMark, SceneSignal } from "@/components/brand";
import { Pill } from "@/components/ui";

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
            className="text-accent underline underline-offset-2 decoration-[var(--accent-ring)] hover:decoration-accent">
            {p.text}
          </a>
        ) : (
          <span key={i}>{p.text}</span>
        )
      )}
    </>
  );
}

interface Message {
  role: "user" | "assistant" | "system";
  content: string;
  model?: string;
  tokens_in?: number;
  tokens_out?: number;
  toolCalls?: string[];
  timestamp?: string;
}

const PROMPTS = [
  "What's on my calendar today?",
  "Draft a reply to my latest email",
  "Remember that I prefer morning meetings",
  "How much have I spent this month?",
];

export default function ChatPage() {
  const { user } = useAuth();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [mode, setMode] = useState<"text" | "voice">("text");
  const [listening, setListening] = useState(false);
  const [voiceStatus, setVoiceStatus] = useState("");
  const [conversations, setConversations] = useState<any[]>([]);
  const [showHistory, setShowHistory] = useState(false);
  const [calling, setCalling] = useState(false);
  const [callStatus, setCallStatus] = useState("");
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);

  const endRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const queueRef = useRef<string[]>([]);
  const playingRef = useRef(false);

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

  const loadList = useCallback(() => {
    api.getConversations(30).then((d) => setConversations(d.conversations || [])).catch(() => {});
  }, []);
  useEffect(() => { loadList(); }, [loadList]);

  const openConversation = async (id: string) => {
    const data = await api.getMessages(id);
    setMessages((data.messages || []).map((m: any) => ({
      role: m.role, content: m.content, model: m.model_used,
      tokens_in: m.tokens_in, tokens_out: m.tokens_out, timestamp: m.created_at,
    })));
    setConversationId(id);
    setShowHistory(false);
  };

  const deleteConversation = async (id: string) => {
    try {
      await api.deleteConversation(id);
      setConversations((prev) => prev.filter((c) => c.id !== id));
      if (conversationId === id) { setMessages([]); setConversationId(null); }
    } catch {}
    setConfirmDelete(null);
  };

  const send = async () => {
    if (!input.trim() || loading) return;
    const text = input.trim();
    setInput("");
    setMessages((p) => [...p, { role: "user", content: text, timestamp: new Date().toISOString() }]);
    setLoading(true);
    try {
      const r = await api.sendMessage(text, conversationId || undefined);
      setConversationId(r.conversation_id);
      setMessages((p) => [...p, {
        role: "assistant", content: r.reply, model: r.model,
        tokens_in: r.tokens_in, tokens_out: r.tokens_out,
        toolCalls: r.tool_calls_made, timestamp: new Date().toISOString(),
      }]);
      loadList();
    } catch (e: any) {
      setMessages((p) => [...p, { role: "system", content: e.message }]);
    } finally {
      setLoading(false);
    }
  };

  const ring = async () => {
    setCalling(true);
    setCallStatus("Ringing…");
    try {
      const r = await api.callMe();
      setCallStatus(r.error || "Kaia is calling you");
    } catch (e: any) {
      setCallStatus(`Failed: ${e.message}`);
    }
    setTimeout(() => { setCalling(false); setCallStatus(""); }, 7000);
  };

  const playNext = useCallback(() => {
    if (queueRef.current.length === 0) { playingRef.current = false; return; }
    playingRef.current = true;
    const b64 = queueRef.current.shift()!;
    const bin = atob(b64);
    const arr = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) arr[i] = bin.charCodeAt(i);
    const url = URL.createObjectURL(new Blob([arr], { type: "audio/mp3" }));
    const a = new Audio(url);
    audioRef.current = a;
    a.onended = () => { URL.revokeObjectURL(url); playNext(); };
    a.play();
  }, []);

  const enqueue = useCallback((b64: string) => {
    queueRef.current.push(b64);
    if (!playingRef.current) playNext();
  }, [playNext]);

  const startMic = async (ws: WebSocket) => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, sampleRate: 16000 } });
      const rec = new MediaRecorder(stream, { mimeType: "audio/webm;codecs=opus" });
      rec.ondataavailable = (e) => {
        if (e.data.size > 0 && ws.readyState === WebSocket.OPEN) ws.send(e.data);
      };
      rec.start(250);
    } catch { setVoiceStatus("Microphone blocked"); }
  };

  const startVoice = useCallback(() => {
    const base = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";
    const ws = new WebSocket(base.replace(/^http/, "ws") + "/ws/voice");
    wsRef.current = ws;
    ws.onopen = () => {
      ws.send(JSON.stringify({ token: "", user_id: user?.id, org_id: "", conversation_id: conversationId }));
      setVoiceStatus("Connecting…");
    };
    ws.onmessage = (ev) => {
      const d = JSON.parse(ev.data);
      switch (d.type) {
        case "ready": setConversationId(d.conversation_id); setVoiceStatus("Listening"); startMic(ws); break;
        case "transcript_interim": setVoiceStatus(d.text); break;
        case "transcript_final":
          setMessages((p) => [...p, { role: "user", content: d.text, timestamp: new Date().toISOString() }]);
          setVoiceStatus("Thinking…");
          break;
        case "thinking": setVoiceStatus("Thinking…"); break;
        case "response_text":
          setMessages((p) => [...p, { role: "assistant", content: d.text, model: d.model }]);
          setVoiceStatus("Speaking…");
          break;
        case "audio": enqueue(d.data); break;
        case "audio_done": setVoiceStatus("Listening"); break;
        case "error": setVoiceStatus(d.message); break;
      }
    };
    ws.onclose = () => { setListening(false); setVoiceStatus(""); };
    setListening(true);
  }, [user, conversationId, enqueue]);

  const stopVoice = () => {
    wsRef.current?.close();
    wsRef.current = null;
    queueRef.current = [];
    playingRef.current = false;
    audioRef.current?.pause();
    audioRef.current = null;
    setListening(false);
    setVoiceStatus("");
  };

  const newThread = () => { setMessages([]); setConversationId(null); setShowHistory(false); };

  const time = (ts?: string) =>
    ts ? new Date(ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "";

  return (
    <div className="flex h-full bg-bg">
      {/* History rail */}
      {showHistory && (
        <div className="fixed inset-0 z-30 lg:hidden" style={{ background: "var(--scrim)" }} onClick={() => setShowHistory(false)} />
      )}
      <div className={`${showHistory ? "fixed inset-y-0 left-0 z-30 w-[260px]" : "hidden"} lg:relative lg:flex lg:w-[248px] flex-col bg-bg border-r border-border`}>
        <div className="flex items-center justify-between px-4 h-16 flex-shrink-0">
          <span className="text-[10px] font-medium uppercase tracking-[0.14em] text-text-4">History</span>
          <button onClick={newThread} title="New thread"
            className="p-1.5 rounded-lg text-text-3 hover:text-accent hover:bg-surface-hover transition-colors">
            <Plus size={15} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-2 pb-4 space-y-0.5">
          {conversations.length === 0 && (
            <p className="text-xs text-text-4 text-center py-12">No threads yet</p>
          )}
          {conversations.map((c) => {
            const active = conversationId === c.id;
            const pending = confirmDelete === c.id;
            return (
              <div key={c.id}
                className={`group relative flex items-center rounded-lg transition-colors ${
                  active ? "bg-[var(--accent-soft)]" : "hover:bg-surface-hover"
                }`}>
                {pending ? (
                  <div className="flex items-center justify-between w-full px-3 py-2">
                    <span className="text-[11px] text-bad">Delete?</span>
                    <div className="flex gap-1">
                      <button onClick={() => deleteConversation(c.id)} aria-label="Confirm delete"
                        className="p-1 rounded text-bad hover:bg-[var(--bad-soft)]">
                        <Check size={13} />
                      </button>
                      <button onClick={() => setConfirmDelete(null)} aria-label="Cancel"
                        className="p-1 rounded text-text-3 hover:text-text">
                        <X size={13} />
                      </button>
                    </div>
                  </div>
                ) : (
                  <>
                    <button onClick={() => openConversation(c.id)}
                      className={`flex-1 text-left px-3 py-2 text-[12.5px] truncate pr-8 ${
                        active ? "text-text font-medium" : "text-text-3"
                      }`}>
                      {c.title || "Untitled"}
                    </button>
                    <button onClick={() => setConfirmDelete(c.id)} aria-label="Delete thread"
                      className="absolute right-1.5 p-1.5 rounded text-text-4 opacity-0 group-hover:opacity-100 hover:text-bad transition-all">
                      <Trash2 size={13} />
                    </button>
                  </>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Conversation column */}
      <div className="flex-1 flex flex-col min-w-0">
        <header className="h-16 flex-shrink-0 flex items-center justify-between px-4 md:px-6 border-b border-border">
          <div className="flex items-center gap-3 pl-12 md:pl-0">
            <button onClick={() => setShowHistory(!showHistory)} aria-label="Toggle history"
              className="lg:hidden p-1.5 rounded-lg text-text-3 hover:text-text hover:bg-surface-hover">
              <PanelLeft size={16} />
            </button>
            <div className="flex p-0.5 rounded-lg bg-surface border border-border">
              {(["text", "voice"] as const).map((m) => (
                <button key={m}
                  onClick={() => { setMode(m); if (m === "text") stopVoice(); }}
                  className={`px-3 py-1 rounded-md text-[11px] font-medium capitalize transition-colors ${
                    mode === m ? "bg-surface-raised text-text" : "text-text-4 hover:text-text-2"
                  }`}>
                  {m}
                </button>
              ))}
            </div>
          </div>

          <div className="flex items-center gap-3">
            {voiceStatus && <span className="hidden sm:inline text-[11px] font-mono text-text-3 truncate max-w-[180px]">{voiceStatus}</span>}
            {callStatus && <span className="text-[11px] font-mono text-accent" style={{ animation: "breathe 2s infinite" }}>{callStatus}</span>}
            <button onClick={ring} disabled={calling}
              className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs text-text-3 border border-border hover:border-[var(--border-hover)] hover:text-accent transition-colors press disabled:opacity-40">
              <Phone size={13} />
              <span className="hidden sm:inline">{calling ? "Ringing…" : "Call me"}</span>
            </button>
          </div>
        </header>

        <div className="flex-1 overflow-y-auto">
          <div className="max-w-[720px] mx-auto px-6 py-8">
            {messages.length === 0 && (
              <div className="flex flex-col items-center pt-[8vh] rise">
                <SceneSignal size={180} />
                <h1 className="text-[28px] font-semibold tracking-[-0.03em] text-text mt-6">
                  What do you need?
                </h1>
                <p className="text-sm text-text-3 mt-2">Calendar, email, memory, or just talk.</p>
                <div className="grid sm:grid-cols-2 gap-2 mt-8 w-full max-w-[520px]">
                  {PROMPTS.map((p) => (
                    <button key={p} onClick={() => setInput(p)}
                      className="text-left px-4 py-3 rounded-xl text-[13px] bg-surface border border-border text-text-3 hover:border-[var(--border-hover)] hover:text-text transition-colors press">
                      {p}
                    </button>
                  ))}
                </div>
              </div>
            )}

            <div className="space-y-6">
              {messages.map((m, i) => (
                <div key={i} className="rise" style={{ animationDelay: `${Math.min(i * 24, 120)}ms` }}>
                  {m.role === "user" ? (
                    <div className="flex justify-end">
                      <div className="max-w-[80%] rounded-2xl rounded-br-md px-4 py-3 bg-surface-raised border border-border">
                        <div className="text-[14px] leading-[1.65] text-text whitespace-pre-wrap">
                          <RichText text={m.content} />
                        </div>
                      </div>
                    </div>
                  ) : m.role === "system" ? (
                    <div className="text-[12px] text-bad px-4 py-3 rounded-xl bg-[var(--bad-soft)] border border-[var(--bad-soft)]">
                      {m.content}
                    </div>
                  ) : (
                    <div className="group flex gap-3">
                      <div className="flex-shrink-0 mt-0.5"><KaiaMark size={22} orbit={false} /></div>
                      <div className="min-w-0 flex-1">
                        <div className="text-[14px] leading-[1.75] text-text-2 whitespace-pre-wrap">
                          <RichText text={m.content} />
                        </div>
                        <div className="flex items-center gap-3 mt-2 opacity-0 group-hover:opacity-100 transition-opacity">
                          {m.toolCalls && m.toolCalls.length > 0 && (
                            <span className="flex items-center gap-1 text-[10px] text-text-4">
                              <Wrench size={9} /> {m.toolCalls.join(", ")}
                            </span>
                          )}
                          {m.model && <span className="text-[10px] font-mono text-text-4">{m.model}</span>}
                          {m.timestamp && <span className="text-[10px] font-mono text-text-4">{time(m.timestamp)}</span>}
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              ))}

              {loading && (
                <div className="flex gap-3 rise">
                  <div className="flex-shrink-0 mt-0.5"><KaiaMark size={22} orbit={false} /></div>
                  <div className="flex items-center gap-1.5 pt-2">
                    {[0, 0.2, 0.4].map((d) => (
                      <span key={d} className="w-1.5 h-1.5 rounded-full bg-accent"
                        style={{ animation: `breathe 1.2s ${d}s infinite` }} />
                    ))}
                  </div>
                </div>
              )}
            </div>
            <div ref={endRef} />
          </div>
        </div>

        {/* Composer */}
        <div className="flex-shrink-0 px-6 pb-6 pt-2">
          <div className="max-w-[720px] mx-auto">
            {mode === "text" ? (
              <div className="flex items-end gap-2 rounded-2xl bg-surface border border-border px-4 py-2 focus-within:border-[var(--accent-ring)] transition-colors">
                <input
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && send()}
                  placeholder="Message Kaia…"
                  disabled={loading}
                  className="flex-1 bg-transparent py-2.5 text-[14px] text-text focus:outline-none"
                />
                <button onClick={send} disabled={!input.trim() || loading} aria-label="Send"
                  className="mb-1 p-2 rounded-lg transition-all press disabled:opacity-30"
                  style={{
                    background: input.trim() ? "var(--accent)" : "transparent",
                    color: input.trim() ? "var(--on-accent)" : "var(--text-4)",
                  }}>
                  <ArrowUp size={15} strokeWidth={2.5} />
                </button>
              </div>
            ) : (
              <div className="flex flex-col items-center gap-3 py-6">
                <button onClick={listening ? stopVoice : startVoice}
                  className="relative p-5 rounded-full transition-all press"
                  style={{
                    background: listening ? "var(--bad-soft)" : "var(--surface)",
                    color: listening ? "var(--bad)" : "var(--accent)",
                    boxShadow: `0 0 0 1px ${listening ? "var(--bad)" : "var(--border)"}`,
                  }}>
                  {listening && (
                    <span className="absolute inset-0 rounded-full"
                      style={{ background: "var(--bad)", opacity: 0.15, animation: "breathe 1.6s infinite" }} />
                  )}
                  {listening ? <Square size={22} fill="currentColor" /> : <Mic size={22} />}
                </button>
                <span className="text-[11px] text-text-4">{listening ? "Tap to stop" : "Tap to speak"}</span>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
