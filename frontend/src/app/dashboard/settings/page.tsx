"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Settings, Link2, CheckCircle, XCircle, ExternalLink } from "lucide-react";

export default function SettingsPage() {
  const [googleStatus, setGoogleStatus] = useState<any>(null);
  const [systemStatus, setSystemStatus] = useState<any>(null);

  useEffect(() => {
    api.getGoogleStatus().then(setGoogleStatus).catch(() => {});
    api.getSystemStatus().then(setSystemStatus).catch(() => {});
  }, []);

  const connectGoogle = async () => {
    try {
      const { auth_url } = await api.getGoogleAuthUrl();
      window.location.href = auth_url;
    } catch (e: any) {
      alert(`Failed to start Google auth: ${e.message}`);
    }
  };

  const disconnectGoogle = async () => {
    if (!confirm("Disconnect Google account? Calendar, Gmail, Sheets, and Docs integrations will stop working.")) return;
    await api.revokeGoogle();
    setGoogleStatus({ connected: false });
  };

  return (
    <div>
      <h2 className="text-2xl font-semibold mb-6">Settings</h2>

      <div className="space-y-6">
        {/* Google Integration */}
        <div className="bg-surface border border-border rounded-xl p-5">
          <h3 className="font-medium mb-4 flex items-center gap-2">
            <Link2 size={18} /> Google Integration
          </h3>
          <div className="flex items-center justify-between">
            <div>
              <div className="flex items-center gap-2 mb-1">
                {googleStatus?.connected ? (
                  <><CheckCircle size={16} className="text-green-400" /> <span className="text-sm text-green-400">Connected</span></>
                ) : (
                  <><XCircle size={16} className="text-yellow-400" /> <span className="text-sm text-yellow-400">Not connected</span></>
                )}
              </div>
              {googleStatus?.scopes && (
                <div className="text-xs text-muted mt-1">
                  Scopes: {googleStatus.scopes.map((s: string) => s.split("/").pop()).join(", ")}
                </div>
              )}
            </div>
            {googleStatus?.connected ? (
              <button onClick={disconnectGoogle} className="px-4 py-2 rounded-lg text-sm text-red-400 hover:bg-red-900/20">
                Disconnect
              </button>
            ) : (
              <button onClick={connectGoogle} className="px-4 py-2 rounded-lg bg-accent/20 text-accent hover:bg-accent/30 text-sm">
                Connect Google
              </button>
            )}
          </div>
          <div className="mt-4 text-xs text-muted space-y-1">
            <p>Grants access to: Calendar, Gmail, Sheets, Docs</p>
            <p>Tokens are encrypted at rest. Only your account has access.</p>
          </div>
        </div>

        {/* System Configuration */}
        <div className="bg-surface border border-border rounded-xl p-5">
          <h3 className="font-medium mb-4 flex items-center gap-2">
            <Settings size={18} /> System Configuration
          </h3>
          {systemStatus ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <h4 className="text-sm text-muted mb-2">Services</h4>
                <div className="space-y-2">
                  {Object.entries(systemStatus)
                    .filter(([k]) => k !== "models" && k !== "limits")
                    .map(([key, val]) => (
                      <div key={key} className="flex justify-between text-sm">
                        <span className="capitalize">{key.replace(/_/g, " ")}</span>
                        <span className={val === "configured" ? "text-green-400" : "text-yellow-400"}>
                          {val as string}
                        </span>
                      </div>
                    ))}
                </div>
              </div>
              <div>
                <h4 className="text-sm text-muted mb-2">Models</h4>
                <div className="space-y-2 text-sm">
                  {systemStatus.models && Object.entries(systemStatus.models).map(([tier, model]) => (
                    <div key={tier} className="flex justify-between">
                      <span className="capitalize">{tier}</span>
                      <span className="font-mono text-xs">{model as string}</span>
                    </div>
                  ))}
                </div>
                <h4 className="text-sm text-muted mb-2 mt-4">Limits</h4>
                <div className="space-y-2 text-sm">
                  {systemStatus.limits && Object.entries(systemStatus.limits).map(([key, val]) => (
                    <div key={key} className="flex justify-between">
                      <span className="capitalize">{key.replace(/_/g, " ")}</span>
                      <span className="font-mono text-xs">{val as string}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            <p className="text-sm text-muted">Loading...</p>
          )}
        </div>
      </div>
    </div>
  );
}
