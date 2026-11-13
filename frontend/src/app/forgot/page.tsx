"use client";

import { useState } from "react";
import Link from "next/link";
import { supabase } from "@/lib/supabase";
import { useTheme } from "@/lib/theme-context";
import { KaiaMark } from "@/components/brand";
import { Sun, Moon, ArrowLeft, MailCheck } from "lucide-react";

export default function ForgotPassword() {
  const { theme, toggle } = useTheme();
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const { error } = await supabase.auth.resetPasswordForEmail(email.trim(), {
        redirectTo: `${window.location.origin}/reset`,
      });
      if (error) throw error;
      // Always report success. Saying "no such account" would let anyone
      // test which addresses are registered here.
      setSent(true);
    } catch (err: any) {
      setError(err.message || "Could not send the email. Try again.");
    } finally {
      setBusy(false);
    }
  };

  const inputCls =
    "w-full bg-control border border-[var(--control-border)] rounded-xl px-4 py-3 text-sm text-text transition-colors";

  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-6">
      <div className="bloom" />
      <div className="grid-field" />

      <button onClick={toggle} aria-label="Toggle theme"
        className="fixed top-6 right-6 z-10 p-2 rounded-lg text-text-3 hover:text-text transition-colors">
        {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
      </button>

      <div className="relative z-10 w-full max-w-[360px] rise">
        <div className="flex flex-col items-center mb-8">
          <KaiaMark size={40} />
        </div>

        {sent ? (
          <div className="text-center">
            <div className="flex justify-center mb-4">
              <span className="w-11 h-11 rounded-full flex items-center justify-center"
                style={{ background: "var(--accent-soft)", color: "var(--accent)" }}>
                <MailCheck size={20} />
              </span>
            </div>
            <h1 className="text-[20px] font-semibold text-text">Check your email</h1>
            <p className="text-[13.5px] text-text-3 mt-2 leading-relaxed">
              If <span className="text-text-2">{email}</span> has an account, a
              reset link is on its way. It expires in an hour — check spam if it
              doesn&apos;t arrive.
            </p>
            <Link href="/login"
              className="inline-flex items-center gap-1.5 text-[13px] text-text-4 hover:text-accent transition-colors mt-8">
              <ArrowLeft size={13} /> Back to sign in
            </Link>
          </div>
        ) : (
          <>
            <h1 className="text-[22px] font-semibold tracking-[-0.02em] text-text text-center">
              Reset your password
            </h1>
            <p className="text-[13.5px] text-text-3 mt-2 mb-8 text-center leading-relaxed">
              Enter the address you sign in with and we&apos;ll send a link.
            </p>

            <form onSubmit={submit} className="space-y-3">
              {error && (
                <div className="text-[12px] px-4 py-3 rounded-xl text-bad"
                  style={{ background: "var(--bad-soft)" }}>
                  {error}
                </div>
              )}

              <input type="email" value={email} required autoFocus
                autoComplete="email" placeholder="you@example.com"
                onChange={(e) => { setEmail(e.target.value); setError(""); }}
                className={inputCls} />

              <button type="submit" disabled={busy || !email.trim()}
                className="w-full py-3 rounded-xl text-sm font-medium press disabled:opacity-40 transition-opacity"
                style={{ background: "var(--accent)", color: "var(--on-accent)" }}>
                {busy ? "Sending…" : "Send reset link"}
              </button>
            </form>

            <div className="mt-8 text-center">
              <Link href="/login"
                className="inline-flex items-center gap-1.5 text-[13px] text-text-4 hover:text-accent transition-colors">
                <ArrowLeft size={13} /> Back to sign in
              </Link>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
