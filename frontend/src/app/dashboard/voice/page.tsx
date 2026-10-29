"use client";

import Link from "next/link";
import { Mic } from "lucide-react";

export default function VoicePage() {
  return (
    <div>
      <h2 className="text-2xl font-semibold mb-6">Voice Playground</h2>
      <div className="bg-surface border border-border rounded-xl p-8 text-center">
        <Mic size={48} className="mx-auto mb-4 text-accent opacity-50" />
        <p className="text-lg mb-2">Real-time voice conversations</p>
        <p className="text-sm text-muted mb-6">
          Switch to voice mode in the Chat page for hands-free conversations with Kaia.
          The assistant uses Deepgram for speech recognition and text-to-speech.
        </p>
        <Link
          href="/dashboard/chat"
          className="inline-flex px-6 py-3 rounded-lg bg-accent/20 text-accent hover:bg-accent/30 text-sm"
        >
          Open Chat with Voice
        </Link>
        <div className="mt-8 text-left max-w-md mx-auto space-y-2 text-sm text-muted">
          <p>Features:</p>
          <ul className="list-disc list-inside space-y-1">
            <li>Streaming speech-to-text via Deepgram Nova-3</li>
            <li>Natural text-to-speech via Deepgram Aura 2</li>
            <li>Automatic turn detection</li>
            <li>Barge-in support (interrupt the assistant)</li>
            <li>Same tools and memory as text mode</li>
          </ul>
        </div>
      </div>
    </div>
  );
}
