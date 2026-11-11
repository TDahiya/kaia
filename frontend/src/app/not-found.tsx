"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { KaiaMark } from "@/components/brand";

/* Any unknown URL lands back on home rather than showing a dead end. */
export default function NotFound() {
  const router = useRouter();

  useEffect(() => {
    const t = setTimeout(() => router.replace("/"), 1400);
    return () => clearTimeout(t);
  }, [router]);

  return (
    <div className="flex flex-col items-center justify-center h-screen bg-bg px-6 text-center">
      <div className="bloom" />
      <div className="grid-field" />
      <div className="relative z-10 flex flex-col items-center">
        <KaiaMark size={40} />
        <h1 className="text-xl font-semibold text-text mt-6">That page doesn&apos;t exist</h1>
        <p className="text-sm text-text-3 mt-2">Taking you home…</p>
      </div>
    </div>
  );
}
