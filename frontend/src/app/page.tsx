"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import { useTheme } from "@/lib/theme-context";
import { KaiaMark } from "@/components/brand";
import { Sun, Moon, ArrowRight } from "lucide-react";

const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";
const GUEST_TOKEN = "kaia-guest-token";

/* The single front door. Owners are sent straight through; everyone else
   gets one field. Previously this was three separate pages and visitors
   landed on the owner's login and tried their code as a password. */
export default function FrontDoor() {
  const { user, loading } = useAuth();
  const { theme, toggle } = useTheme();
  const router = useRouter();

  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const [checking, setChecking] = useState(false);

  // Already signed in? You own this thing — skip the door.
  useEffect(() => {
    if (!loading && user) router.replace("/overview");
  }, [user, loading, router]);

  const enter = async () => {
    if (!code.trim()) return;
    setChecking(true);
    setError("");
    try {
      const r = await fetch(`${BACKEND}/api/guest/redeem`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code: code.trim() }),
      });
      const d = await r.json();
      if (!r.ok) throw new Error(d.detail || "That code didn't work.");
      localStorage.setItem(GUEST_TOKEN, d.token);
      router.push("/try");
    } catch (e: any) {
      setError(e.message);
      setChecking(false);
    }
  };

  if (loading || user) {
    return (
      <div className="flex items-center justify-center h-screen bg-bg">
        <div style={{ animation: "breathe 1.6s ease-in-out infinite" }}>
          <KaiaMark size={36} />
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-6">
      <div className="bloom" />
      <div className="grid-field" />

      <button onClick={toggle} aria-label="Toggle theme"
        className="fixed top-6 right-6 z-10 p-2 rounded-lg text-text-3 hover:text-text transition-colors">
        {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
      </button>

      <main className="relative z-10 w-full max-w-[400px] text-center rise">
        <div className="flex justify-center"><KaiaMark size={48} /></div>

        <h1 className="text-[26px] font-semibold tracking-[-0.02em] text-text mt-6">
          Kaia
        </h1>
        <p className="text-[14px] text-text-3 mt-2 leading-relaxed">
          A personal AI assistant that handles calendars, email and
          documents — and can ring your phone.
        </p>

        <div className="mt-10">
          <label htmlFor="code" className="block text-[13px] text-text-2 mb-3">
            Got an access code? Enter it here.
          </label>
          <div className="flex gap-2">
            <input
              id="code"
              value={code}
              onChange={(e) => { setCode(e.target.value.toUpperCase()); setError(""); }}
              onKeyDown={(e) => e.key === "Enter" && enter()}
              placeholder="AMZN-4K2P"
              autoComplete="off"
              /* min-w-0 is the whole fix for the button falling off a phone:
                 a flex item will not shrink below its content, and a mono
                 letter-spaced placeholder is wider than a 375px screen has
                 left over once the button has its share. */
              className="flex-1 min-w-0 bg-control border border-[var(--control-border)] rounded-xl px-4 py-3 text-[15px] font-mono tracking-widest text-center text-text uppercase"
            />
            <button onClick={enter} disabled={checking || !code.trim()}
              aria-label="Enter"
              className="flex-shrink-0 px-5 rounded-xl text-sm font-medium press disabled:opacity-40 transition-opacity flex items-center justify-center"
              style={{ background: "var(--accent)", color: "var(--on-accent)" }}>
              {checking ? "…" : <ArrowRight size={16} />}
            </button>
          </div>
          {error && <p className="text-[13px] text-bad mt-3">{error}</p>}
        </div>

        <div className="mt-10 pt-6 border-t border-border">
          <Link href="/login"
            className="text-[13px] text-text-4 hover:text-accent transition-colors">
            This is my assistant — sign in
          </Link>
        </div>

        <p className="text-[12px] text-text-4 mt-8">
          No code?{" "}
          <a href="mailto:tanishq.dahiya2@mail.dcu.ie"
            className="text-text-3 hover:text-accent underline underline-offset-2">
            Ask for one
          </a>
        </p>
      </main>
    </div>
  );
}
