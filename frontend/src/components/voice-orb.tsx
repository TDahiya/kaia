"use client";

import { useEffect, useRef } from "react";

/* An orb that actually tracks the audio rather than looping an animation.
   `analyser` is live while Kaia speaks; `listening` drives the idle pulse
   so the thing never looks frozen while it waits for you. */
export function VoiceOrb({
  analyser,
  listening,
  size = 180,
}: {
  analyser: AnalyserNode | null;
  listening: boolean;
  size?: number;
}) {
  const ref = useRef<SVGSVGElement>(null);
  const raf = useRef<number>(0);
  const level = useRef(0);

  useEffect(() => {
    const bins = analyser ? new Uint8Array(analyser.frequencyBinCount) : null;
    let t = 0;

    const frame = () => {
      t += 0.016;

      let target = 0;
      if (analyser && bins) {
        analyser.getByteFrequencyData(bins as any);
        // Speech energy sits low in the spectrum; averaging the whole range
        // washes it out, so weight the bottom third.
        const span = Math.max(1, Math.floor(bins.length / 3));
        let sum = 0;
        for (let i = 0; i < span; i++) sum += bins[i];
        target = sum / span / 255;
      }
      // Fall back to the idle pulse only when nothing is actually audible.
      // Keying this off a status string meant the orb froze mid-sentence,
      // because the server reports "done" while audio is still queued.
      if (target < 0.02) {
        target = listening ? 0.12 + Math.sin(t * 1.8) * 0.05 : 0.06;
      }

      // Asymmetric smoothing: jump to a transient, ease back down.
      const k = target > level.current ? 0.35 : 0.08;
      level.current += (target - level.current) * k;

      const svg = ref.current;
      if (svg) {
        const L = level.current;
        const core = svg.querySelector<SVGCircleElement>("[data-core]");
        const ring1 = svg.querySelector<SVGCircleElement>("[data-ring1]");
        const ring2 = svg.querySelector<SVGCircleElement>("[data-ring2]");
        const glow = svg.querySelector<SVGCircleElement>("[data-glow]");

        if (core) core.setAttribute("r", String(30 + L * 16));
        if (ring1) {
          ring1.setAttribute("r", String(46 + L * 30));
          ring1.setAttribute("opacity", String(0.5 - L * 0.18));
        }
        if (ring2) {
          ring2.setAttribute("r", String(62 + L * 46));
          ring2.setAttribute("opacity", String(0.26 - L * 0.1));
        }
        if (glow) {
          glow.setAttribute("r", String(38 + L * 40));
          glow.setAttribute("opacity", String(0.18 + L * 0.4));
        }
      }
      raf.current = requestAnimationFrame(frame);
    };

    raf.current = requestAnimationFrame(frame);
    return () => cancelAnimationFrame(raf.current);
  }, [analyser, listening]);

  return (
    <svg ref={ref} width={size} height={size} viewBox="0 0 200 200" aria-hidden="true">
      <defs>
        <radialGradient id="orb-core" cx="38%" cy="32%">
          <stop offset="0%" stopColor="#FFCDBC" />
          <stop offset="45%" stopColor="#FF9654" />
          <stop offset="100%" stopColor="#D9541F" />
        </radialGradient>
        <radialGradient id="orb-glow">
          <stop offset="0%" stopColor="var(--accent)" stopOpacity="0.55" />
          <stop offset="100%" stopColor="var(--accent)" stopOpacity="0" />
        </radialGradient>
      </defs>

      <circle data-glow cx="100" cy="100" r="40" fill="url(#orb-glow)" />
      <circle data-ring2 cx="100" cy="100" r="62" fill="none"
        stroke="var(--chestnut)" strokeWidth="1" opacity="0.26" />
      <circle data-ring1 cx="100" cy="100" r="46" fill="none"
        stroke="var(--accent)" strokeWidth="1.25" opacity="0.5" />
      <circle data-core cx="100" cy="100" r="30" fill="url(#orb-core)" />
      <ellipse cx="88" cy="86" rx="11" ry="7" fill="#fff" opacity="0.28"
        transform="rotate(-28 88 86)" />
    </svg>
  );
}
