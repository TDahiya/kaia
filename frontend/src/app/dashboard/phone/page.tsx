"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Phone, PhoneCall, PhoneOff, Shield } from "lucide-react";

export default function PhonePage() {
  const [phoneData, setPhoneData] = useState<any>(null);
  const [callLogs, setCallLogs] = useState<any[]>([]);

  useEffect(() => {
    api.getPhoneNumbers().then(setPhoneData).catch(() => {});
    api.getCallLogs().then((d) => setCallLogs(d.call_logs || [])).catch(() => {});
  }, []);

  return (
    <div>
      <h2 className="text-2xl font-semibold mb-6">Phone System</h2>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        {/* Configuration */}
        <div className="bg-surface border border-border rounded-xl p-5">
          <h3 className="font-medium mb-4 flex items-center gap-2">
            <Phone size={18} /> Phone Configuration
          </h3>
          {phoneData ? (
            <div className="space-y-3 text-sm">
              <div className="flex justify-between">
                <span className="text-muted">Telnyx Status</span>
                <span className={phoneData.telnyx_configured ? "text-green-400" : "text-yellow-400"}>
                  {phoneData.telnyx_configured ? "Connected" : "Not configured"}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted">Phone Number</span>
                <span className="font-mono">{phoneData.configured_number || "Not set"}</span>
              </div>
              {phoneData.phone_numbers?.map((p: any) => (
                <div key={p.id} className="flex justify-between border-t border-border pt-2">
                  <span className="text-muted">{p.phone_number}</span>
                  <span className={`text-xs px-2 py-0.5 rounded ${
                    p.status === "active" ? "bg-green-900/30 text-green-400" : "bg-yellow-900/30 text-yellow-400"
                  }`}>{p.status}</span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-muted">Loading...</p>
          )}
        </div>

        {/* Security notice */}
        <div className="bg-surface border border-border rounded-xl p-5">
          <h3 className="font-medium mb-4 flex items-center gap-2">
            <Shield size={18} className="text-accent" /> Outbound Call Security
          </h3>
          <div className="space-y-3 text-sm text-muted">
            <p>Outbound calls are restricted to the owner's phone number only.</p>
            <ul className="list-disc list-inside space-y-1">
              <li>Only OWNER_PHONE_E164 can be called</li>
              <li>Backend validates every outbound request</li>
              <li>Daily call limit enforced</li>
              <li>Monthly spend limit applied</li>
              <li>Call duration capped</li>
              <li>Requires explicit user instruction</li>
            </ul>
            <p className="text-xs mt-3">
              The assistant cannot call arbitrary numbers. This restriction is enforced
              in backend code and cannot be bypassed from the frontend or via prompts.
            </p>
          </div>
        </div>
      </div>

      {/* Call Logs */}
      <div className="bg-surface border border-border rounded-xl p-5">
        <h3 className="font-medium mb-4">Call History</h3>
        {callLogs.length === 0 ? (
          <p className="text-sm text-muted">No calls recorded yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-muted text-left border-b border-border">
                  <th className="pb-2 pr-4">Direction</th>
                  <th className="pb-2 pr-4">From</th>
                  <th className="pb-2 pr-4">To</th>
                  <th className="pb-2 pr-4">Status</th>
                  <th className="pb-2 pr-4">Duration</th>
                  <th className="pb-2">Time</th>
                </tr>
              </thead>
              <tbody>
                {callLogs.map((log) => (
                  <tr key={log.id} className="border-b border-border/50 last:border-0">
                    <td className="py-2 pr-4">
                      {log.direction === "inbound" ? (
                        <PhoneCall size={14} className="text-green-400" />
                      ) : (
                        <PhoneOff size={14} className="text-blue-400" />
                      )}
                    </td>
                    <td className="py-2 pr-4 font-mono text-xs">{log.caller_number}</td>
                    <td className="py-2 pr-4 font-mono text-xs">{log.callee_number}</td>
                    <td className="py-2 pr-4">
                      <span className={`text-xs px-2 py-0.5 rounded ${
                        log.status === "completed" ? "bg-green-900/30 text-green-400" :
                        log.status === "failed" ? "bg-red-900/30 text-red-400" :
                        "bg-yellow-900/30 text-yellow-400"
                      }`}>{log.status}</span>
                    </td>
                    <td className="py-2 pr-4 text-muted">{log.duration_seconds ? `${log.duration_seconds}s` : "—"}</td>
                    <td className="py-2 text-muted text-xs">{new Date(log.started_at).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
