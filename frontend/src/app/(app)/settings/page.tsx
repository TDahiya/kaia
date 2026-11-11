"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useTheme } from "@/lib/theme-context";
import { Link2, Phone, Check, Sun, Moon, AlertTriangle } from "lucide-react";
import { Page, Card, CardTitle, PageHeader, Button, Pill, Spinner } from "@/components/ui";

/* E.164: + then 8–15 digits, first digit non-zero. */
const E164 = /^\+[1-9]\d{7,14}$/;

export default function SettingsPage() {
  const { theme, toggle } = useTheme();
  const [google, setGoogle] = useState<any>(null);
  const [system, setSystem] = useState<any>(null);
  const [phone, setPhone] = useState<any>(null);
  const [draft, setDraft] = useState("");
  const [err, setErr] = useState("");
  const [savedPhone, setSavedPhone] = useState(false);
  const [saving, setSaving] = useState(false);

  const loadPhone = () =>
    api.getOwnerPhone()
      .then((d) => { setPhone(d); setDraft(d.owner_phone || ""); })
      .catch(() => setPhone({ owner_phone: null, twilio_configured: false }));

  useEffect(() => {
    api.getGoogleStatus().then(setGoogle).catch(() => {});
    api.getSystemStatus().then(setSystem).catch(() => {});
    loadPhone();
  }, []);

  const savePhone = async () => {
    const v = draft.replace(/[\s()-]/g, "");
    if (!E164.test(v)) {
      setErr("Use international format — e.g. +353871234567");
      return;
    }
    setErr("");
    setSaving(true);
    try {
      await api.setOwnerPhone(v);
      setDraft(v);
      setSavedPhone(true);
      setTimeout(() => setSavedPhone(false), 2000);
      loadPhone();
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setSaving(false);
    }
  };

  const services = system
    ? Object.entries(system).filter(([k]) => k !== "models" && k !== "limits")
    : [];

  const inputCls = "w-full bg-control border border-[var(--control-border)] rounded-lg px-4 py-2.5 text-sm text-text font-mono";

  return (
    <Page>
      <PageHeader title="Settings" subtitle="Connections, phone, and appearance" />

      <div className="space-y-4">
        {/* ── Phone ─────────────────────────────── */}
        <Card className="rise">
          <CardTitle
            action={
              <Pill tone={phone?.twilio_configured ? "ok" : "warn"}>
                {phone?.twilio_configured ? "twilio ready" : "twilio missing"}
              </Pill>
            }
          >
            <span className="flex items-center gap-2"><Phone size={13} /> Your number</span>
          </CardTitle>

          <p className="text-[13px] text-text-3 mb-4 leading-relaxed">
            The only number Kaia is ever allowed to ring. Enforced in the backend — a prompt can&apos;t
            talk her into calling anyone else.
          </p>

          {phone === null ? (
            <Spinner />
          ) : (
            <>
              <div className="flex flex-col sm:flex-row gap-2">
                <input
                  value={draft}
                  onChange={(e) => { setDraft(e.target.value); setErr(""); }}
                  onKeyDown={(e) => e.key === "Enter" && savePhone()}
                  placeholder="+353871234567"
                  className={inputCls}
                />
                <Button variant="primary" onClick={savePhone} disabled={saving || draft === phone?.owner_phone}>
                  {savedPhone ? <Check size={14} /> : null}
                  {savedPhone ? "Saved" : saving ? "Saving…" : "Save"}
                </Button>
              </div>

              {err && (
                <div className="flex items-center gap-2 mt-3 text-[12px] text-bad">
                  <AlertTriangle size={12} /> {err}
                </div>
              )}

              {phone.from_number && (
                <div className="flex items-center justify-between mt-4 pt-4 border-t border-border">
                  <span className="text-[12px] text-text-3">Calls arrive from</span>
                  <span className="text-[12px] font-mono text-text-2">{phone.from_number}</span>
                </div>
              )}
            </>
          )}
        </Card>

        {/* ── Google ────────────────────────────── */}
        <Card className="rise" >
          <CardTitle
            action={
              <Pill tone={google?.connected ? "ok" : "warn"}>
                {google?.connected ? "connected" : "not connected"}
              </Pill>
            }
          >
            <span className="flex items-center gap-2"><Link2 size={13} /> Google</span>
          </CardTitle>

          <p className="text-[13px] text-text-3 mb-4 leading-relaxed">
            Calendar, Gmail, Sheets and Docs. Tokens are encrypted at rest.
          </p>

          {google?.scopes && (
            <div className="flex flex-wrap gap-1.5 mb-4">
              {google.scopes.map((s: string) => (
                <Pill key={s}>{s.split("/").pop()}</Pill>
              ))}
            </div>
          )}

          {google?.connected ? (
            <Button variant="danger" onClick={async () => {
              if (!confirm("Disconnect Google? Calendar, Gmail, Sheets and Docs will stop working.")) return;
              await api.revokeGoogle();
              setGoogle({ connected: false });
            }}>
              Disconnect
            </Button>
          ) : (
            <Button variant="primary" onClick={async () => {
              try {
                const { auth_url } = await api.getGoogleAuthUrl();
                window.location.href = auth_url;
              } catch (e: any) { alert(e.message); }
            }}>
              Connect Google
            </Button>
          )}
        </Card>

        {/* ── Appearance ────────────────────────── */}
        <Card className="rise">
          <CardTitle>Appearance</CardTitle>
          <div className="flex items-center justify-between">
            <div>
              <div className="text-sm text-text">Theme</div>
              <div className="text-[12px] text-text-3 mt-0.5">
                {theme === "dark" ? "Coffee bean — low light" : "Almond silk — daylight"}
              </div>
            </div>
            <button onClick={toggle}
              className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm border border-border text-text-2 hover:border-[var(--border-hover)] hover:text-text transition-colors press">
              {theme === "dark" ? <Sun size={14} /> : <Moon size={14} />}
              {theme === "dark" ? "Switch to light" : "Switch to dark"}
            </button>
          </div>
        </Card>

        {/* ── System ────────────────────────────── */}
        <Card className="rise">
          <CardTitle>System</CardTitle>
          {!system ? (
            <Spinner />
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
              <div>
                <div className="text-[10px] uppercase tracking-[0.12em] text-text-4 mb-3">Services</div>
                <div className="space-y-2.5">
                  {services.map(([k, v]) => (
                    <div key={k} className="flex items-center justify-between">
                      <span className="text-[13px] text-text-2 capitalize">{k.replace(/_/g, " ")}</span>
                      <Pill tone={v === "configured" ? "ok" : "warn"}>{v === "configured" ? "ready" : "not set"}</Pill>
                    </div>
                  ))}
                </div>
              </div>

              <div className="space-y-6">
                {system.models && (
                  <div>
                    <div className="text-[10px] uppercase tracking-[0.12em] text-text-4 mb-3">Models</div>
                    <div className="space-y-2.5">
                      {Object.entries(system.models).map(([tier, m]) => (
                        <div key={tier} className="flex items-center justify-between gap-3">
                          <span className="text-[13px] text-text-2 capitalize">{tier}</span>
                          <span className="text-[11px] font-mono text-text-4 truncate">{m as string}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                {system.limits && (
                  <div>
                    <div className="text-[10px] uppercase tracking-[0.12em] text-text-4 mb-3">Limits</div>
                    <div className="space-y-2.5">
                      {Object.entries(system.limits).map(([k, v]) => (
                        <div key={k} className="flex items-center justify-between gap-3">
                          <span className="text-[13px] text-text-2 capitalize">{k.replace(/_/g, " ")}</span>
                          <span className="text-[11px] font-mono text-text-4 tnum">{v as string}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </Card>
      </div>
    </Page>
  );
}
