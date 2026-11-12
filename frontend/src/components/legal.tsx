import Link from "next/link";
import { ReactNode } from "react";

/* Shared shell for the public legal pages. Deliberately outside the (app)
   route group so Google's reviewers and anyone else can read them without
   an account. */
export function LegalPage({
  title,
  updated,
  children,
}: { title: string; updated: string; children: ReactNode }) {
  return (
    <div className="min-h-screen">
      <div className="bloom" />
      <div className="grid-field" />

      <div className="relative z-10 max-w-[720px] mx-auto px-6 py-16">
        <Link href="/" className="inline-flex items-center gap-2.5 mb-12 group">
          <svg width="22" height="22" viewBox="0 0 32 32" fill="none" aria-hidden="true">
            <circle
              cx="16" cy="16" r="13" fill="none" stroke="var(--chestnut)"
              strokeWidth="1.75" strokeLinecap="round"
              strokeDasharray="65.3 16.3" transform="rotate(-40 16 16)" opacity="0.85"
            />
            <path
              d="M 16,5 c 0,6.1 -4.9,11 -11,11 c 6.1,0 11,4.9 11,11 c 0,-6.1 4.9,-11 11,-11 c -6.1,0 -11,-4.9 -11,-11 Z"
              fill="var(--accent)"
            />
          </svg>
          <span className="text-[15px] font-medium tracking-[0.08em] lowercase text-text group-hover:text-accent transition-colors">
            kaia
          </span>
        </Link>

        <h1 className="text-[32px] font-semibold tracking-[-0.03em] text-text">{title}</h1>
        <p className="text-[13px] text-text-4 mt-2 mb-10">Last updated {updated}</p>

        <div className="legal-body">{children}</div>

        <div className="mt-16 pt-8 border-t border-border flex gap-6 text-[13px]">
          <Link href="/privacy" className="text-text-3 hover:text-accent transition-colors">Privacy</Link>
          <Link href="/terms" className="text-text-3 hover:text-accent transition-colors">Terms</Link>
          <Link href="/" className="text-text-3 hover:text-accent transition-colors">Home</Link>
        </div>
      </div>
    </div>
  );
}

export function H2({ children }: { children: ReactNode }) {
  return <h2 className="text-[18px] font-semibold text-text mt-10 mb-3 tracking-[-0.015em]">{children}</h2>;
}

export function P({ children }: { children: ReactNode }) {
  return <p className="text-[14px] leading-[1.75] text-text-2 mb-4">{children}</p>;
}

export function UL({ children }: { children: ReactNode }) {
  return <ul className="mb-4 space-y-2">{children}</ul>;
}

export function LI({ children }: { children: ReactNode }) {
  return (
    <li className="text-[14px] leading-[1.7] text-text-2 pl-5 relative">
      <span className="absolute left-0 top-[9px] w-1.5 h-1.5 rounded-full bg-accent" />
      {children}
    </li>
  );
}
