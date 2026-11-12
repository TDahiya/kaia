"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutGrid, MessageSquare, Bot, Brain, Wrench, BarChart3, Settings,
  LogOut, Sun, Moon, KeyRound,
} from "lucide-react";
import { useAuth } from "@/lib/auth-context";
import { useTheme } from "@/lib/theme-context";
import { KaiaMark, Wordmark } from "./brand";

/* Two groups: what you do, and what you configure. */
const primary = [
  { href: "/overview", label: "Overview", icon: LayoutGrid },
  { href: "/chat", label: "Chat", icon: MessageSquare },
];

const secondary = [
  { href: "/agents", label: "Agents", icon: Bot },
  { href: "/memories", label: "Memories", icon: Brain },
  { href: "/tools", label: "Tools", icon: Wrench },
  { href: "/passes", label: "Guest passes", icon: KeyRound },
  { href: "/usage", label: "Usage", icon: BarChart3 },
  { href: "/settings", label: "Settings", icon: Settings },
];

function NavItem({
  href, label, icon: Icon, active, onNavigate,
}: { href: string; label: string; icon: any; active: boolean; onNavigate?: () => void }) {
  return (
    <Link
      href={href}
      onClick={onNavigate}
      className={`relative flex items-center gap-3 px-3 py-2 rounded-lg text-[13px] transition-colors ${
        active
          ? "text-text bg-[var(--accent-soft)] font-medium"
          : "text-text-3 hover:text-text-2 hover:bg-surface-hover"
      }`}
    >
      {active && (
        <span className="absolute left-0 top-1/2 -translate-y-1/2 h-4 w-[3px] rounded-r-full bg-accent" />
      )}
      <Icon size={16} strokeWidth={active ? 2.2 : 1.75} className={active ? "text-accent" : ""} />
      {label}
    </Link>
  );
}

export function Sidebar({ onNavigate }: { onNavigate?: () => void } = {}) {
  const pathname = usePathname();
  const { signOut, user } = useAuth();
  const { theme, toggle } = useTheme();

  const isActive = (href: string) => pathname === href || pathname.startsWith(href + "/");

  return (
    <aside className="w-[232px] h-screen sticky top-0 flex flex-col bg-bg border-r border-border">
      <div className="px-5 pt-6 pb-6">
        <Link href="/overview" onClick={onNavigate} className="flex items-center gap-2.5">
          <KaiaMark size={24} />
          <Wordmark />
        </Link>
      </div>

      <nav className="flex-1 px-3 overflow-y-auto">
        <div className="space-y-1">
          {primary.map((item) => (
            <NavItem key={item.href} {...item} active={isActive(item.href)} onNavigate={onNavigate} />
          ))}
        </div>

        <div className="mt-8 mb-2 px-3">
          <span className="text-[10px] font-medium uppercase tracking-[0.14em] text-text-4">Workspace</span>
        </div>
        <div className="space-y-1">
          {secondary.map((item) => (
            <NavItem key={item.href} {...item} active={isActive(item.href)} onNavigate={onNavigate} />
          ))}
        </div>
      </nav>

      <div className="border-t border-border p-3 space-y-1">
        <button
          onClick={toggle}
          className="flex items-center gap-3 w-full px-3 py-2 rounded-lg text-[13px] text-text-3 hover:text-text-2 hover:bg-surface-hover transition-colors"
        >
          {theme === "dark" ? <Sun size={15} /> : <Moon size={15} />}
          {theme === "dark" ? "Light mode" : "Dark mode"}
        </button>

        <div className="px-3 pt-2 pb-1">
          <div className="text-[11px] font-mono text-text-4 truncate">{user?.email}</div>
        </div>

        <button
          onClick={() => signOut()}
          className="flex items-center gap-3 w-full px-3 py-2 rounded-lg text-[13px] text-text-3 hover:text-bad hover:bg-[var(--bad-soft)] transition-colors"
        >
          <LogOut size={15} />
          Sign out
        </button>
      </div>
    </aside>
  );
}
