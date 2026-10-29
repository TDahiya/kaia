"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard, Bot, MessageSquare, Mic, Brain, Phone,
  Settings, BarChart3, BookOpen, Wrench, LogOut,
} from "lucide-react";
import { useAuth } from "@/lib/auth-context";

const nav = [
  { href: "/dashboard", label: "Overview", icon: LayoutDashboard },
  { href: "/dashboard/chat", label: "Chat", icon: MessageSquare },
  { href: "/dashboard/agents", label: "Agents", icon: Bot },
  { href: "/dashboard/voice", label: "Voice", icon: Mic },
  { href: "/dashboard/memories", label: "Memories", icon: Brain },
  { href: "/dashboard/phone", label: "Phone", icon: Phone },
  { href: "/dashboard/tools", label: "Tools", icon: Wrench },
  { href: "/dashboard/knowledge", label: "Knowledge", icon: BookOpen },
  { href: "/dashboard/usage", label: "Usage", icon: BarChart3 },
  { href: "/dashboard/settings", label: "Settings", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();
  const { signOut, user } = useAuth();

  return (
    <aside className="w-60 flex flex-col border-r border-border bg-surface h-screen sticky top-0">
      <div className="p-4 border-b border-border">
        <h1 className="text-lg font-semibold tracking-tight">
          <span className="text-accent">Kaia</span>
          <span className="text-muted text-xs ml-2 font-normal">AI Assistant</span>
        </h1>
      </div>

      <nav className="flex-1 p-2 space-y-0.5 overflow-y-auto">
        {nav.map(({ href, label, icon: Icon }) => {
          const active = pathname === href || (href !== "/dashboard" && pathname.startsWith(href));
          return (
            <Link
              key={href}
              href={href}
              className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm ${
                active
                  ? "bg-accent/10 text-accent font-medium"
                  : "text-muted hover:text-foreground hover:bg-surface-hover"
              }`}
            >
              <Icon size={18} />
              {label}
            </Link>
          );
        })}
      </nav>

      <div className="p-3 border-t border-border">
        <div className="text-xs text-muted truncate mb-2 px-1">{user?.email}</div>
        <button
          onClick={() => signOut()}
          className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm text-muted hover:text-foreground hover:bg-surface-hover w-full"
        >
          <LogOut size={16} />
          Sign out
        </button>
      </div>
    </aside>
  );
}
