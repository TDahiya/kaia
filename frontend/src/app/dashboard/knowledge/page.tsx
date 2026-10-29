"use client";

import { BookOpen } from "lucide-react";

export default function KnowledgePage() {
  return (
    <div>
      <h2 className="text-2xl font-semibold mb-6">Knowledge & FAQ</h2>
      <div className="bg-surface border border-border rounded-xl p-8 text-center">
        <BookOpen size={48} className="mx-auto mb-4 text-muted opacity-30" />
        <p className="text-lg mb-2">Knowledge Base</p>
        <p className="text-sm text-muted max-w-md mx-auto">
          The assistant learns from conversations and stores durable memories automatically.
          Use the Memories page to view, add, or correct stored knowledge.
          The weekly summarization process extracts key information from conversations.
        </p>
        <div className="mt-6 bg-surface-hover rounded-xl p-4 max-w-lg mx-auto text-left">
          <h4 className="text-sm font-medium mb-2">How knowledge works:</h4>
          <ul className="text-sm text-muted space-y-1 list-disc list-inside">
            <li>Conversations are retained for 7 days</li>
            <li>Weekly summaries extract durable facts</li>
            <li>Personal memory profile is updated automatically</li>
            <li>Google Docs backup of memory summary</li>
            <li>You can manually add, edit, or delete memories</li>
          </ul>
        </div>
      </div>
    </div>
  );
}
