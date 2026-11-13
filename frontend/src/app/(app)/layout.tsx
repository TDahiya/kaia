"use client";

import { useAuth } from "@/lib/auth-context";
import { api } from "@/lib/api";
import { Sidebar } from "@/components/sidebar";
import { KaiaMark } from "@/components/brand";
import { useRouter } from "next/navigation";
import { useEffect, useState, ReactNode } from "react";
import { Menu, X } from "lucide-react";

export default function AppLayout({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [navOpen, setNavOpen] = useState(false);
  const [allowed, setAllowed] = useState<boolean | null>(null);

  useEffect(() => {
    if (loading) return;
    if (!user) {
      router.replace("/login");
      return;
    }

    // Being signed in is not the same as owning this. Supabase sign-up is
    // public, so the backend decides — anyone else is handed a guest pass
    // and sent to the portal rather than into the dashboard.
    let cancelled = false;
    api.whoAmI().then(async (isOwner) => {
      if (cancelled) return;
      if (isOwner) {
        setAllowed(true);
        return;
      }
      setAllowed(false);
      try {
        const pass = await api.signupPass();
        localStorage.setItem("kaia-guest-token", pass.token);
      } catch {
        // No pass to be had — the front door explains what to do.
      }
      router.replace("/try");
    });
    return () => { cancelled = true; };
  }, [user, loading, router]);

  if (loading || (user && allowed === null) || allowed === false) {
    return (
      <div className="flex items-center justify-center h-screen bg-bg">
        <div style={{ animation: "breathe 1.6s ease-in-out infinite" }}>
          <KaiaMark size={36} />
        </div>
      </div>
    );
  }

  if (!user) return null;

  return (
    <div className="flex h-screen bg-bg">
      {/* Sits behind every page. Pages must not paint an opaque background
          over it — use transparent surfaces and let this show through. */}
      <div className="bloom" />
      <div className="grid-field" />

      <button
        onClick={() => setNavOpen(true)}
        aria-label="Open navigation"
        className="fixed top-4 left-4 z-50 p-2 rounded-lg md:hidden bg-surface border border-border text-text-2 backdrop-blur"
      >
        <Menu size={16} />
      </button>

      {navOpen && (
        <div className="fixed inset-0 z-50 md:hidden" onClick={() => setNavOpen(false)}>
          <div className="absolute inset-0" style={{ background: "var(--scrim)" }} />
          <div className="relative w-[232px] h-full" onClick={(e) => e.stopPropagation()}>
            <button
              onClick={() => setNavOpen(false)}
              aria-label="Close navigation"
              className="absolute top-5 right-3 z-10 p-1.5 rounded-lg text-text-3 hover:text-text"
            >
              <X size={16} />
            </button>
            <Sidebar onNavigate={() => setNavOpen(false)} />
          </div>
        </div>
      )}

      <div className="hidden md:block relative z-10">
        <Sidebar />
      </div>

      <main className="flex-1 overflow-y-auto relative z-10">{children}</main>
    </div>
  );
}
