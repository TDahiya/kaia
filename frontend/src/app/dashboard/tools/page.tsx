"use client";

import { Wrench, Calendar, Mail, FileSpreadsheet, Cloud, Brain, Phone } from "lucide-react";

const tools = [
  { name: "list_calendar_events", desc: "List upcoming calendar events", icon: Calendar, cat: "Google Calendar" },
  { name: "check_calendar_availability", desc: "Check if a date is free or busy", icon: Calendar, cat: "Google Calendar" },
  { name: "create_calendar_event", desc: "Create a new event with attendees", icon: Calendar, cat: "Google Calendar" },
  { name: "cancel_calendar_event", desc: "Cancel an existing event", icon: Calendar, cat: "Google Calendar" },
  { name: "search_emails", desc: "Search Gmail messages", icon: Mail, cat: "Gmail" },
  { name: "read_email", desc: "Read full email content", icon: Mail, cat: "Gmail" },
  { name: "create_email_draft", desc: "Create a draft (doesn't send)", icon: Mail, cat: "Gmail" },
  { name: "send_email", desc: "Send an email (requires confirmation)", icon: Mail, cat: "Gmail" },
  { name: "crm_add_or_update_contact", desc: "Add/update CRM contact", icon: FileSpreadsheet, cat: "Sheets CRM" },
  { name: "crm_search_contacts", desc: "Search CRM contacts", icon: FileSpreadsheet, cat: "Sheets CRM" },
  { name: "get_weather", desc: "Get current weather for a city", icon: Cloud, cat: "Weather" },
  { name: "search_memories", desc: "Search stored memories", icon: Brain, cat: "Memory" },
  { name: "add_memory", desc: "Store new information", icon: Brain, cat: "Memory" },
  { name: "update_memory", desc: "Update existing memory", icon: Brain, cat: "Memory" },
  { name: "delete_memory", desc: "Remove a memory", icon: Brain, cat: "Memory" },
  { name: "call_owner", desc: "Call the owner's phone (restricted)", icon: Phone, cat: "Phone" },
];

export default function ToolsPage() {
  const categories = [...new Set(tools.map((t) => t.cat))];

  return (
    <div>
      <h2 className="text-2xl font-semibold mb-6">Tools & Integrations</h2>
      <p className="text-sm text-muted mb-6">
        These tools are available to the AI assistant during conversations. They execute real actions
        through connected services.
      </p>

      {categories.map((cat) => (
        <div key={cat} className="mb-8">
          <h3 className="font-medium mb-3 text-accent">{cat}</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {tools.filter((t) => t.cat === cat).map((t) => (
              <div key={t.name} className="bg-surface border border-border rounded-xl p-4 flex items-start gap-3">
                <t.icon size={18} className="text-muted mt-0.5 flex-shrink-0" />
                <div>
                  <div className="text-sm font-mono">{t.name}</div>
                  <div className="text-xs text-muted mt-0.5">{t.desc}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
