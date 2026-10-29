"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { Send, Mic, MicOff, Square, Loader2, Wrench, ChevronDown } from "lucide-react";

interface Message {
  id?: string;
  role: "user" | "assistant" | "system";
  content: string;
  model?: string;
  tokens_in?: number;
  tokens_out?: number;
  cost?: number;
  toolCalls?: string[];
  timestamp?: string;
}

export default function ChatPage() {
  const { user } = useAuth();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [mode, setMode] = useState<"text" | "voice">("text");
  const [isListening, setIsListening] = useState(false);
  const [voiceStatus, setVoiceStatus] = useState("");
  const [conversations, setConversations] = useState<any[]>([]);
  const [showHistory, setShowHistory] = useState(false);
  const messagesEnd = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  useEffect(() => {
    messagesEnd.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    api.getConversations(20).then((d) => setConversations(d.conversations || [])).catch(() => {});
  }, []);

  const loadConversation = async (id: string) => {
    const data = await api.getMessages(id);
    setMessages(
      (data.messages || []).map((m: any) => ({
        id: m.id,
        role: m.role,
        content: m.content,
        model: m.model_used,
        tokens_in: m.tokens_in,
        tokens_out: m.tokens_out,
        timestamp: m.created_at,
      }))
    );
    setConversationId(id);
    setShowHistory(false);
  };

  const sendText = async () => {
    if (!input.trim() || loading) return;
    const text = input.trim();
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: text, timestamp: new Date().toISOString() }]);
    setLoading(true);

    try {
      const resp = await api.sendMessage(text, conversationId || undefined);
      setConversationId(resp.conversation_id);
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: resp.reply,
          model: resp.model,
          tokens_in: resp.tokens_in,
          tokens_out: resp.tokens_out,
          cost: resp.estimated_cost_usd,
          toolCalls: resp.tool_calls_made,
          timestamp: new Date().toISOString(),
        },
      ]);
    } catch (err: any) {
      setMessages((prev) => [...prev, { role: "system", content: `Error: ${err.message}` }]);
    } finally {
      setLoading(false);
    }
  };

  const startVoice = useCallback(() => {
    const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";
    const wsUrl = backendUrl.replace(/^http/, "ws") + "/ws/voice";
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      ws.send(JSON.stringify({
        token: "",
        user_id: user?.id,
        org_id: "", // will be resolved backend-side
        conversation_id: conversationId,
      }));
      setVoiceStatus("Connecting...");
    };

    ws.onmessage = async (event) => {
      const data = JSON.parse(event.data);

      switch (data.type) {
        case "ready":
          setConversationId(data.conversation_id);
          setVoiceStatus("Listening...");
          startMic(ws);
          break;
        case "transcript_interim":
          setVoiceStatus(`Hearing: "${data.text}"`);
          break;
        case "transcript_final":
          setMessages((prev) => [...prev, { role: "user", content: data.text, timestamp: new Date().toISOString() }]);
          setVoiceStatus("Thinking...");
          break;
        case "thinking":
          setVoiceStatus("Thinking...");
          break;
        case "response_text":
          setMessages((prev) => [
            ...prev,
            {
              role: "assistant",
              content: data.text,
              model: data.model,
              tokens_in: data.tokens_in,
              tokens_out: data.tokens_out,
              cost: data.cost,
            },
          ]);
          setVoiceStatus("Speaking...");
          break;
        case "audio":
          playAudio(data.data);
          break;
        case "audio_done":
          setVoiceStatus("Listening...");
          break;
        case "tts_cancelled":
          if (audioRef.current) {
            audioRef.current.pause();
            audioRef.current = null;
          }
          setVoiceStatus("Listening...");
          break;
        case "error":
          setVoiceStatus(`Error: ${data.message}`);
          break;
      }
    };

    ws.onclose = () => {
      setIsListening(false);
      setVoiceStatus("");
    };

    setIsListening(true);
  }, [user, conversationId]);

  const stopVoice = () => {
    wsRef.current?.close();
    wsRef.current = null;
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current = null;
    }
    setIsListening(false);
    setVoiceStatus("");
  };

  const startMic = async (ws: WebSocket) => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { channelCount: 1, sampleRate: 16000 },
      });
      const recorder = new MediaRecorder(stream, { mimeType: "audio/webm;codecs=opus" });
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0 && ws.readyState === WebSocket.OPEN) {
          ws.send(e.data);
        }
      };
      recorder.start(250); // send audio chunks every 250ms
    } catch {
      setVoiceStatus("Microphone access denied");
    }
  };

  const playAudio = (base64: string) => {
    const bytes = atob(base64);
    const arr = new Uint8Array(bytes.length);
    for (let i = 0; i < bytes.length; i++) arr[i] = bytes.charCodeAt(i);
    const blob = new Blob([arr], { type: "audio/mp3" });
    const url = URL.createObjectURL(blob);
    if (audioRef.current) {
      audioRef.current.pause();
    }
    const audio = new Audio(url);
    audioRef.current = audio;
    audio.play();
    audio.onended = () => URL.revokeObjectURL(url);
  };

  const newConversation = () => {
    setMessages([]);
    setConversationId(null);
  };

  return (
    <div className="flex h-[calc(100vh-3rem)] -m-6">
      {/* Conversation sidebar */}
      <div className={`w-64 border-r border-border bg-surface flex-col ${showHistory ? "flex" : "hidden lg:flex"}`}>
        <div className="p-3 border-b border-border">
          <button
            onClick={newConversation}
            className="w-full px-3 py-2 rounded-lg bg-accent/10 text-accent text-sm hover:bg-accent/20"
          >
            New Conversation
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-2 space-y-0.5">
          {conversations.map((c) => (
            <button
              key={c.id}
              onClick={() => loadConversation(c.id)}
              className={`w-full text-left px-3 py-2 rounded-lg text-sm truncate ${
                conversationId === c.id ? "bg-accent/10 text-accent" : "text-muted hover:bg-surface-hover"
              }`}
            >
              {c.title || "Untitled"}
            </button>
          ))}
        </div>
      </div>

      {/* Main chat area */}
      <div className="flex-1 flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-border">
          <div className="flex items-center gap-3">
            <button onClick={() => setShowHistory(!showHistory)} className="lg:hidden text-muted">
              <ChevronDown size={18} />
            </button>
            <div className="flex bg-surface-hover rounded-lg p-0.5">
              <button
                onClick={() => { setMode("text"); stopVoice(); }}
                className={`px-3 py-1 rounded text-sm ${mode === "text" ? "bg-accent/20 text-accent" : "text-muted"}`}
              >
                Text
              </button>
              <button
                onClick={() => setMode("voice")}
                className={`px-3 py-1 rounded text-sm ${mode === "voice" ? "bg-accent/20 text-accent" : "text-muted"}`}
              >
                Voice
              </button>
            </div>
          </div>
          {voiceStatus && (
            <span className="text-xs text-muted animate-pulse">{voiceStatus}</span>
          )}
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {messages.length === 0 && (
            <div className="flex flex-col items-center justify-center h-full text-muted">
              <div className="text-4xl mb-4">👋</div>
              <p className="text-lg">Hi! I'm Kaia, your AI assistant.</p>
              <p className="text-sm mt-1">Type a message or switch to voice mode.</p>
            </div>
          )}
          {messages.map((msg, i) => (
            <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
              <div
                className={`max-w-[75%] rounded-2xl px-4 py-3 ${
                  msg.role === "user"
                    ? "bg-accent/20 text-foreground"
                    : msg.role === "system"
                    ? "bg-red-900/20 text-red-400"
                    : "bg-surface border border-border"
                }`}
              >
                <div className="text-sm whitespace-pre-wrap">{msg.content}</div>
                {msg.role === "assistant" && (
                  <div className="flex items-center gap-3 mt-2 text-xs text-muted">
                    {msg.model && <span>{msg.model}</span>}
                    {msg.tokens_in != null && <span>{msg.tokens_in + (msg.tokens_out || 0)} tok</span>}
                    {msg.cost != null && <span>${msg.cost.toFixed(4)}</span>}
                    {msg.toolCalls && msg.toolCalls.length > 0 && (
                      <span className="flex items-center gap-1">
                        <Wrench size={12} /> {msg.toolCalls.join(", ")}
                      </span>
                    )}
                  </div>
                )}
              </div>
            </div>
          ))}
          {loading && (
            <div className="flex justify-start">
              <div className="bg-surface border border-border rounded-2xl px-4 py-3">
                <Loader2 size={18} className="animate-spin text-muted" />
              </div>
            </div>
          )}
          <div ref={messagesEnd} />
        </div>

        {/* Input area */}
        <div className="border-t border-border p-4">
          {mode === "text" ? (
            <div className="flex gap-2">
              <input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && sendText()}
                placeholder="Type a message..."
                className="flex-1 bg-surface border border-border rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-accent/50 placeholder:text-muted"
                disabled={loading}
              />
              <button
                onClick={sendText}
                disabled={!input.trim() || loading}
                className="p-3 rounded-xl bg-accent/20 text-accent hover:bg-accent/30 disabled:opacity-30"
              >
                <Send size={18} />
              </button>
            </div>
          ) : (
            <div className="flex items-center justify-center gap-4">
              <button
                onClick={isListening ? stopVoice : startVoice}
                className={`p-6 rounded-full ${
                  isListening
                    ? "bg-red-500/20 text-red-400 animate-pulse"
                    : "bg-accent/20 text-accent hover:bg-accent/30"
                }`}
              >
                {isListening ? <MicOff size={28} /> : <Mic size={28} />}
              </button>
              <span className="text-sm text-muted">
                {isListening ? "Tap to stop" : "Tap to start listening"}
              </span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
