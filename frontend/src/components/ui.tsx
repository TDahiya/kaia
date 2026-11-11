"use client";

import { ReactNode } from "react";

/* Spacing is 8px-based throughout: p-2=8 p-4=16 p-6=24 p-8=32 */

export function Card({
  children,
  className = "",
  padded = true,
}: { children: ReactNode; className?: string; padded?: boolean }) {
  return (
    <div
      className={`bg-surface border border-border rounded-2xl ${padded ? "p-6" : ""} ${className}`}
    >
      {children}
    </div>
  );
}

export function CardTitle({ children, action }: { children: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex items-center justify-between mb-4">
      <h3 className="text-[11px] font-medium uppercase tracking-[0.12em] text-text-3">{children}</h3>
      {action}
    </div>
  );
}

export function PageHeader({
  title,
  subtitle,
  action,
}: { title: string; subtitle?: string; action?: ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-4 mb-8 pl-12 md:pl-0 rise">
      <div>
        <h1 className="text-2xl font-semibold tracking-[-0.02em] text-text">{title}</h1>
        {subtitle && <p className="text-sm text-text-3 mt-1">{subtitle}</p>}
      </div>
      {action && <div className="flex-shrink-0">{action}</div>}
    </div>
  );
}

export function Button({
  children,
  onClick,
  variant = "ghost",
  size = "md",
  disabled,
  type = "button",
  title,
  className = "",
}: {
  children: ReactNode;
  onClick?: () => void;
  variant?: "primary" | "ghost" | "outline" | "danger";
  size?: "sm" | "md";
  disabled?: boolean;
  type?: "button" | "submit";
  title?: string;
  className?: string;
}) {
  const base =
    "inline-flex items-center justify-center gap-2 rounded-lg font-medium transition-colors press ring disabled:opacity-40 disabled:pointer-events-none";
  const sizes = { sm: "px-3 py-1.5 text-xs", md: "px-4 py-2 text-sm" };
  const variants = {
    primary: "bg-accent text-[var(--on-accent)] hover:bg-[var(--accent-hover)]",
    outline: "border border-border text-text-2 hover:border-[var(--border-hover)] hover:text-text",
    ghost: "text-text-3 hover:text-text hover:bg-surface-hover",
    danger: "text-bad hover:bg-[var(--bad-soft)]",
  };
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      title={title}
      className={`${base} ${sizes[size]} ${variants[variant]} ${className}`}
    >
      {children}
    </button>
  );
}

export function Field({
  value,
  onChange,
  placeholder,
  type = "text",
  rows,
  mono,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  type?: string;
  rows?: number;
  mono?: boolean;
}) {
  const cls = `w-full bg-control border border-[var(--control-border)] rounded-lg px-4 py-2.5 text-sm text-text transition-colors ${
    mono ? "font-mono" : ""
  }`;
  return rows ? (
    <textarea value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} rows={rows} className={`${cls} resize-none`} />
  ) : (
    <input type={type} value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} className={cls} />
  );
}

export function Pill({ tone = "neutral", children }: { tone?: "neutral" | "ok" | "warn" | "bad" | "accent"; children: ReactNode }) {
  const tones = {
    neutral: "bg-surface-raised text-text-3 border-border",
    ok: "bg-[var(--ok-soft)] text-ok border-[var(--ok-soft)]",
    warn: "bg-[var(--warn-soft)] text-warn border-[var(--warn-soft)]",
    bad: "bg-[var(--bad-soft)] text-bad border-[var(--bad-soft)]",
    accent: "bg-[var(--accent-soft)] text-accent border-[var(--accent-soft)]",
  };
  return (
    <span className={`inline-flex items-center text-[10px] font-medium px-2 py-0.5 rounded-md border ${tones[tone]}`}>
      {children}
    </span>
  );
}

export function EmptyState({
  scene,
  title,
  body,
  action,
}: { scene: ReactNode; title: string; body?: string; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center text-center py-16 rise">
      <div className="mb-6 opacity-90">{scene}</div>
      <h3 className="text-base font-medium text-text">{title}</h3>
      {body && <p className="text-sm text-text-3 mt-2 max-w-[340px]">{body}</p>}
      {action && <div className="mt-6">{action}</div>}
    </div>
  );
}

export function Spinner({ size = 16 }: { size?: number }) {
  return (
    <div
      className="rounded-full border-2 border-border"
      style={{
        width: size,
        height: size,
        borderTopColor: "var(--accent)",
        animation: "rotate 0.7s linear infinite",
      }}
    />
  );
}

/* Page shell — every page uses this so gutters and max-width never drift. */
export function Page({ children }: { children: ReactNode }) {
  return <div className="px-6 md:px-8 py-8 max-w-[1040px] mx-auto">{children}</div>;
}
