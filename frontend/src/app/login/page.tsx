"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { KaiaMark } from "@/components/brand";
import { useTheme } from "@/lib/theme-context";
import { Sun, Moon } from "lucide-react";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isSignUp, setIsSignUp] = useState(false);
  const [note, setNote] = useState("");
  const [ok, setOk] = useState(false);
  const [loading, setLoading] = useState(false);
  const { signIn, signUp } = useAuth();
  const { theme, toggle } = useTheme();
  const router = useRouter();

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setNote("");
    setLoading(true);
    try {
      if (isSignUp) {
        await signUp(email, password);
        setOk(true);
        setNote("Check your email for a confirmation link.");
      } else {
        await signIn(email, password);
        router.push("/overview");
      }
    } catch (err: any) {
      setOk(false);
      setNote(err.message || "Authentication failed");
    } finally {
      setLoading(false);
    }
  };

  const inputCls =
    "w-full bg-control border border-[var(--control-border)] rounded-xl px-4 py-3 text-sm text-text transition-colors";

  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-6 bg-bg">
      <div className="bloom" />
      <div className="grid-field" />

      <button onClick={toggle} aria-label="Toggle theme"
        className="fixed top-6 right-6 z-10 p-2 rounded-lg text-text-3 hover:text-text hover:bg-surface-hover transition-colors">
        {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
      </button>

      <div className="w-full max-w-[360px] relative z-10">
        <div className="flex flex-col items-center mb-10 rise">
          <KaiaMark size={44} />
          <h1 className="text-[22px] font-medium tracking-[0.08em] lowercase text-text mt-5">kaia</h1>
          <p className="text-[13px] text-text-3 mt-1.5">your personal AI</p>
        </div>

        <form onSubmit={submit} className="space-y-3 rise" style={{ animationDelay: "80ms" }}>
          {note && (
            <div className="text-[12px] px-4 py-3 rounded-xl border"
              style={{
                color: ok ? "var(--ok)" : "var(--bad)",
                background: ok ? "var(--ok-soft)" : "var(--bad-soft)",
                borderColor: ok ? "var(--ok-soft)" : "var(--bad-soft)",
              }}>
              {note}
            </div>
          )}

          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)}
            placeholder="Email" required autoComplete="email" className={inputCls} />
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)}
            placeholder="Password" required minLength={6}
            autoComplete={isSignUp ? "new-password" : "current-password"} className={inputCls} />

          <button type="submit" disabled={loading}
            className="w-full py-3 rounded-xl text-sm font-medium transition-colors press disabled:opacity-50"
            style={{ background: "var(--accent)", color: "var(--on-accent)" }}>
            {loading ? "…" : isSignUp ? "Create account" : "Sign in"}
          </button>

          <button type="button" onClick={() => { setIsSignUp(!isSignUp); setNote(""); }}
            className="w-full text-[12px] text-text-4 hover:text-text-2 transition-colors pt-2">
            {isSignUp ? "Already have an account? Sign in" : "Create an account"}
          </button>
        </form>

        {/* Guests land here by mistake — their code works at /try, not as a password. */}
        <div className="mt-10 pt-6 border-t border-border text-center rise" style={{ animationDelay: "120ms" }}>
          <p className="text-[12px] text-text-4">
            Been given an access code?{" "}
            <a href="/try" className="text-accent hover:underline underline-offset-2">Use it here</a>
          </p>
        </div>
      </div>
    </div>
  );
}
