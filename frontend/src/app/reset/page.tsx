"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { supabase } from "@/lib/supabase";
import { useTheme } from "@/lib/theme-context";
import { KaiaMark } from "@/components/brand";
import { Sun, Moon, Check, AlertTriangle } from "lucide-react";

/* Where the emailed link lands. Supabase puts a recovery token in the URL
   fragment and the client exchanges it for a short-lived session, which is
   what lets updateUser set a new password without the old one. */
export default function ResetPassword() {
  const { theme, toggle } = useTheme();
  const router = useRouter();

  const [ready, setReady] = useState<boolean | null>(null);
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    // The token arrives in the fragment, so this only resolves client-side.
    const check = async () => {
      const { data } = await supabase.auth.getSession();
      if (data.session) {
        setReady(true);
        return;
      }
      // Give the client a moment to process the fragment on a cold load.
      const { data: sub } = supabase.auth.onAuthStateChange((event) => {
        if (event === "PASSWORD_RECOVERY" || event === "SIGNED_IN") setReady(true);
      });
      setTimeout(async () => {
        const { data: again } = await supabase.auth.getSession();
        setReady((r) => (r === null ? !!again.session : r));
      }, 1500);
      return () => sub.subscription.unsubscribe();
    };
    check();
  }, []);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (password.length < 8) {
      setError("Use at least 8 characters.");
      return;
    }
    if (password !== confirm) {
      setError("Those don't match.");
      return;
    }
    setBusy(true);
    try {
      const { error } = await supabase.auth.updateUser({ password });
      if (error) throw error;
      setDone(true);
      setTimeout(() => router.replace("/login"), 2500);
    } catch (err: any) {
      setError(err.message || "Could not update the password.");
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

        {done ? (
          <div className="text-center">
            <div className="flex justify-center mb-4">
              <span className="w-11 h-11 rounded-full flex items-center justify-center"
                style={{ background: "var(--accent-soft)", color: "var(--accent)" }}>
                <Check size={20} />
              </span>
            </div>
            <h1 className="text-[20px] font-semibold text-text">Password updated</h1>
            <p className="text-[13.5px] text-text-3 mt-2">Taking you to sign in…</p>
          </div>
        ) : ready === false ? (
          <div className="text-center">
            <div className="flex justify-center mb-4">
              <span className="w-11 h-11 rounded-full flex items-center justify-center"
                style={{ background: "var(--bad-soft)", color: "var(--bad)" }}>
                <AlertTriangle size={20} />
              </span>
            </div>
            <h1 className="text-[20px] font-semibold text-text">This link has expired</h1>
            <p className="text-[13.5px] text-text-3 mt-2 leading-relaxed">
              Reset links are single-use and last an hour. Request a fresh one.
            </p>
            <Link href="/forgot"
              className="inline-block mt-6 px-5 py-2.5 rounded-xl text-sm font-medium press"
              style={{ background: "var(--accent)", color: "var(--on-accent)" }}>
              Send a new link
            </Link>
          </div>
        ) : ready === null ? (
          <div className="flex justify-center py-6">
            <div style={{ animation: "breathe 1.6s ease-in-out infinite" }}>
              <span className="text-[13px] text-text-3">Checking your link…</span>
            </div>
          </div>
        ) : (
          <>
            <h1 className="text-[22px] font-semibold tracking-[-0.02em] text-text text-center">
              Choose a new password
            </h1>
            <p className="text-[13.5px] text-text-3 mt-2 mb-8 text-center">
              At least 8 characters.
            </p>

            <form onSubmit={submit} className="space-y-3">
              {error && (
                <div className="text-[12px] px-4 py-3 rounded-xl text-bad"
                  style={{ background: "var(--bad-soft)" }}>
                  {error}
                </div>
              )}

              <input type="password" value={password} required autoFocus
                autoComplete="new-password" placeholder="New password"
                onChange={(e) => { setPassword(e.target.value); setError(""); }}
                className={inputCls} />

              <input type="password" value={confirm} required
                autoComplete="new-password" placeholder="Repeat it"
                onChange={(e) => { setConfirm(e.target.value); setError(""); }}
                className={inputCls} />

              <button type="submit" disabled={busy || !password || !confirm}
                className="w-full py-3 rounded-xl text-sm font-medium press disabled:opacity-40 transition-opacity"
                style={{ background: "var(--accent)", color: "var(--on-accent)" }}>
                {busy ? "Updating…" : "Update password"}
              </button>
            </form>
          </>
        )}
      </div>
    </div>
  );
}
