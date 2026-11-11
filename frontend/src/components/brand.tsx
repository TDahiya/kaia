"use client";

/* ── The mark ──────────────────────────────────────────────
   A four-point spark inside an open orbit. The spark is the
   answer; the orbit is Kaia staying in range. Reads at 16px.  */
export function KaiaMark({ size = 24, orbit = true }: { size?: number; orbit?: boolean }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" fill="none" aria-hidden="true">
      <defs>
        <linearGradient id="km-g" x1="6" y1="4" x2="26" y2="28" gradientUnits="userSpaceOnUse">
          <stop stopColor="var(--accent-hover)" />
          <stop offset="1" stopColor="var(--accent)" />
        </linearGradient>
      </defs>
      {orbit && (
        <path
          d="M26.5 9.5a13 13 0 1 1-8-5.2"
          stroke="var(--chestnut)"
          strokeWidth="1.75"
          strokeLinecap="round"
          fill="none"
          opacity="0.85"
        />
      )}
      <path
        d="M16 5c0 6.1 -4.9 11 -11 11 6.1 0 11 4.9 11 11 0-6.1 4.9-11 11-11-6.1 0-11-4.9-11-11Z"
        fill="url(#km-g)"
      />
    </svg>
  );
}

export function Wordmark({ size = 15 }: { size?: number }) {
  return (
    <span
      style={{
        fontSize: size,
        fontWeight: 500,
        letterSpacing: "0.08em",
        color: "var(--text)",
        textTransform: "lowercase",
      }}
    >
      kaia
    </span>
  );
}

/* ── Empty-state scenes ────────────────────────────────────
   Flat vector, warm palette, one accent focal point each.    */

export function SceneSignal({ size = 168 }: { size?: number }) {
  return (
    <svg width={size} height={size * 0.72} viewBox="0 0 240 172" fill="none" aria-hidden="true">
      <ellipse cx="120" cy="150" rx="86" ry="10" fill="var(--accent-soft)" />
      {[46, 64, 82].map((r, i) => (
        <circle
          key={r}
          cx="120"
          cy="104"
          r={r}
          stroke="var(--chestnut)"
          strokeWidth="1"
          fill="none"
          opacity={0.5 - i * 0.14}
          strokeDasharray="3 6"
        />
      ))}
      <path d="M120 60a18 18 0 0 1-18 18 18 18 0 0 1 18 18 18 18 0 0 1 18-18 18 18 0 0 1-18-18Z" fill="var(--accent)" />
      <circle cx="54" cy="56" r="3" fill="var(--chestnut)" />
      <circle cx="196" cy="74" r="2.5" fill="var(--chestnut)" />
      <circle cx="178" cy="36" r="2" fill="var(--accent)" opacity="0.7" />
      <circle cx="70" cy="128" r="2" fill="var(--accent)" opacity="0.5" />
      <path d="M38 96h16M186 112h18" stroke="var(--chestnut)" strokeWidth="1.5" strokeLinecap="round" opacity="0.6" />
    </svg>
  );
}

export function SceneStack({ size = 160 }: { size?: number }) {
  return (
    <svg width={size} height={size * 0.75} viewBox="0 0 220 165" fill="none" aria-hidden="true">
      <ellipse cx="110" cy="146" rx="74" ry="9" fill="var(--accent-soft)" />
      <rect x="46" y="96" width="128" height="30" rx="8" fill="var(--surface-raised)" stroke="var(--border)" />
      <rect x="54" y="66" width="112" height="30" rx="8" fill="var(--surface-raised)" stroke="var(--border-hover)" />
      <rect x="62" y="34" width="96" height="32" rx="9" fill="var(--surface)" stroke="var(--accent)" strokeWidth="1.5" />
      <circle cx="80" cy="50" r="5" fill="var(--accent)" />
      <rect x="94" y="47" width="48" height="5" rx="2.5" fill="var(--text-4)" />
      <rect x="72" y="78" width="60" height="5" rx="2.5" fill="var(--text-4)" opacity="0.6" />
      <rect x="66" y="108" width="72" height="5" rx="2.5" fill="var(--text-4)" opacity="0.4" />
    </svg>
  );
}

export function SceneNodes({ size = 168 }: { size?: number }) {
  return (
    <svg width={size} height={size * 0.7} viewBox="0 0 240 168" fill="none" aria-hidden="true">
      <ellipse cx="120" cy="150" rx="80" ry="9" fill="var(--accent-soft)" />
      <path
        d="M70 58 L120 86 L170 58 M120 86 L120 128"
        stroke="var(--chestnut)"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        fill="none"
        strokeDasharray="4 4"
      />
      <rect x="50" y="40" width="40" height="36" rx="9" fill="var(--surface-raised)" stroke="var(--border-hover)" />
      <rect x="150" y="40" width="40" height="36" rx="9" fill="var(--surface-raised)" stroke="var(--border-hover)" />
      <rect x="96" y="112" width="48" height="34" rx="9" fill="var(--surface-raised)" stroke="var(--border-hover)" />
      <circle cx="120" cy="86" r="16" fill="var(--accent)" />
      <path d="M120 78v16M112 86h16" stroke="var(--on-accent)" strokeWidth="2" strokeLinecap="round" />
      <circle cx="70" cy="58" r="3.5" fill="var(--text-4)" />
      <circle cx="170" cy="58" r="3.5" fill="var(--text-4)" />
      <circle cx="120" cy="129" r="3.5" fill="var(--text-4)" />
    </svg>
  );
}

export function SceneOrbit({ size = 160 }: { size?: number }) {
  return (
    <svg width={size} height={size * 0.78} viewBox="0 0 220 172" fill="none" aria-hidden="true">
      <ellipse cx="110" cy="152" rx="70" ry="8" fill="var(--accent-soft)" />
      <ellipse cx="110" cy="84" rx="82" ry="30" stroke="var(--chestnut)" strokeWidth="1" fill="none" opacity="0.6" />
      <ellipse
        cx="110"
        cy="84"
        rx="82"
        ry="30"
        stroke="var(--chestnut)"
        strokeWidth="1"
        fill="none"
        opacity="0.4"
        transform="rotate(62 110 84)"
      />
      <circle cx="110" cy="84" r="24" fill="var(--surface-raised)" stroke="var(--accent)" strokeWidth="1.5" />
      <path d="M110 73a11 11 0 0 1-11 11 11 11 0 0 1 11 11 11 11 0 0 1 11-11 11 11 0 0 1-11-11Z" fill="var(--accent)" />
      <circle cx="192" cy="84" r="5" fill="var(--chestnut)" />
      <circle cx="28" cy="84" r="4" fill="var(--chestnut)" />
      <circle cx="148" cy="30" r="3.5" fill="var(--accent)" opacity="0.8" />
    </svg>
  );
}

export function SceneLedger({ size = 168 }: { size?: number }) {
  const bars = [26, 44, 34, 58, 48, 72];
  return (
    <svg width={size} height={size * 0.68} viewBox="0 0 240 164" fill="none" aria-hidden="true">
      <ellipse cx="120" cy="148" rx="82" ry="9" fill="var(--accent-soft)" />
      <line x1="44" y1="130" x2="200" y2="130" stroke="var(--border-hover)" strokeWidth="1.5" />
      {bars.map((h, i) => (
        <rect
          key={i}
          x={54 + i * 26}
          y={130 - h}
          width="16"
          height={h}
          rx="4"
          fill={i === bars.length - 1 ? "var(--accent)" : "var(--surface-raised)"}
          stroke={i === bars.length - 1 ? "none" : "var(--border-hover)"}
        />
      ))}
      <path d="M58 56 L110 40 L162 50 L206 24" stroke="var(--chestnut)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" fill="none" strokeDasharray="4 4" />
      <circle cx="206" cy="24" r="4" fill="var(--accent)" />
    </svg>
  );
}
