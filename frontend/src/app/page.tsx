"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { KaiaMark } from "@/components/brand";

export default function Root() {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading) router.replace(user ? "/overview" : "/login");
  }, [user, loading, router]);

  return (
    <div className="flex items-center justify-center h-screen bg-bg">
      <div style={{ animation: "breathe 1.6s ease-in-out infinite" }}>
        <KaiaMark size={36} />
      </div>
    </div>
  );
}
