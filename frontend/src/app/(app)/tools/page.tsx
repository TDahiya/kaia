"use client";

import { Calendar, Mail, FileSpreadsheet, Cloud, Brain, Phone } from "lucide-react";
import { Page, PageHeader, Pill } from "@/components/ui";

const TOOLS = [
  { name: "list_calendar_events", desc: "List upcoming events", cat: "Calendar", icon: Calendar },
  { name: "check_calendar_availability", desc: "Check if a slot is free", cat: "Calendar", icon: Calendar },
  { name: "create_calendar_event", desc: "Create an event with attendees", cat: "Calendar", icon: Calendar },
  { name: "cancel_calendar_event", desc: "Cancel an existing event", cat: "Calendar", icon: Calendar },
  { name: "search_emails", desc: "Search Gmail messages", cat: "Gmail", icon: Mail },
  { name: "read_email", desc: "Read full message content", cat: "Gmail", icon: Mail },
  { name: "create_email_draft", desc: "Draft without sending", cat: "Gmail", icon: Mail },
  { name: "send_email", desc: "Send — asks first", cat: "Gmail", icon: Mail, guarded: true },
  { name: "crm_add_or_update_contact", desc: "Write a contact row", cat: "Sheets", icon: FileSpreadsheet },
  { name: "crm_search_contacts", desc: "Look up a contact", cat: "Sheets", icon: FileSpreadsheet },
  { name: "get_weather", desc: "Current conditions for a city", cat: "World", icon: Cloud },
  { name: "search_memories", desc: "Recall stored memories", cat: "Memory", icon: Brain },
  { name: "add_memory", desc: "Store something new", cat: "Memory", icon: Brain },
  { name: "update_memory", desc: "Revise a memory", cat: "Memory", icon: Brain },
  { name: "delete_memory", desc: "Forget a memory", cat: "Memory", icon: Brain },
  { name: "call_owner", desc: "Ring your phone — owner number only", cat: "Phone", icon: Phone, guarded: true },
];

export default function ToolsPage() {
  const cats = [...new Set(TOOLS.map((t) => t.cat))];

  return (
    <Page>
      <PageHeader
        title="Tools"
        subtitle={`${TOOLS.length} actions Kaia can take on your behalf during a conversation`}
      />

      <div className="space-y-10">
        {cats.map((cat, ci) => {
          const items = TOOLS.filter((t) => t.cat === cat);
          const Icon = items[0].icon;
          return (
            <section key={cat} className="rise" style={{ animationDelay: `${ci * 50}ms` }}>
              <div className="flex items-center gap-2.5 mb-4">
                <Icon size={15} className="text-accent" />
                <h2 className="text-sm font-medium text-text">{cat}</h2>
                <span className="text-[11px] text-text-4 tnum">{items.length}</span>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                {items.map((t) => (
                  <div key={t.name}
                    className="flex items-start justify-between gap-3 bg-surface border border-border rounded-xl px-4 py-3.5 hover:border-[var(--border-hover)] transition-colors">
                    <div className="min-w-0">
                      <div className="text-[12.5px] font-mono text-text truncate">{t.name}</div>
                      <div className="text-xs text-text-3 mt-1">{t.desc}</div>
                    </div>
                    {t.guarded && <Pill tone="warn">guarded</Pill>}
                  </div>
                ))}
              </div>
            </section>
          );
        })}
      </div>
    </Page>
  );
}
