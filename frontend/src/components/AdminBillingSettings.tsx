import { FormEvent, useEffect, useState } from "react";
import { api } from "@/lib/api";

type Settings = {
  single_workspace_price: string | number;
  agency_price: string | number;
  currency: string;
  billing_cycle: string;
  trial_days: number;
  upi_id: string;
  account_holder_name: string;
  account_number: string;
  ifsc_code: string;
  micr_code: string | null;
  swift_code: string | null;
  bank_name: string | null;
};

const empty: Settings = {
  single_workspace_price: 5000,
  agency_price: 15000,
  currency: "INR",
  billing_cycle: "monthly",
  trial_days: 1,
  upi_id: "mdarif921@ybl",
  account_holder_name: "MD ARIF ALAM",
  account_number: "50100497971201",
  ifsc_code: "HDFC0000609",
  micr_code: "110240098",
  swift_code: "HDFCINBBDEL",
  bank_name: "",
};

export default function AdminBillingSettings() {
  const [settings, setSettings] = useState<Settings>(empty);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");

  async function load() {
    setLoading(true);
    try {
      setSettings(await api.get<Settings>("/api/admin/billing/settings"));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void load(); }, []);

  async function save(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    setMessage("");
    try {
      await api.put("/api/admin/billing/settings", {
        ...settings,
        single_workspace_price: Number(settings.single_workspace_price),
        agency_price: Number(settings.agency_price),
        trial_days: Number(settings.trial_days),
      });
      setMessage("Billing settings saved. New QR codes now use the updated prices automatically.");
      await load();
    } catch (err: any) {
      console.error("Billing settings save failed:", err);
      const detail =
        err?.response?.data?.detail ??
        err?.response?.data?.message ??
        err?.message ??
        "Unknown validation error";
      setMessage(`Could not save billing settings: ${typeof detail === "string" ? detail : JSON.stringify(detail)}`);
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <div className="p-6">Loading billing settings...</div>;

  const field = (label: string, key: keyof Settings, type = "text") => (
    <label className="block">
      <span className="text-sm font-medium text-slate-700">{label}</span>
      <input type={type} value={String(settings[key] ?? "")} onChange={(e) => setSettings((current) => ({ ...current, [key]: e.target.value }))} className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-slate-900 placeholder:text-slate-400 focus:border-slate-500 focus:outline-none focus:ring-2 focus:ring-slate-200 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100 dark:placeholder:text-slate-500 dark:focus:ring-slate-700" />
    </label>
  );

  return (
    <form onSubmit={save} className="space-y-6 rounded-xl border bg-white p-6 shadow-sm">
      <div>
        <h2 className="text-xl font-semibold">Billing Settings</h2>
        <p className="mt-1 text-sm text-slate-500">Prices are stored centrally. The payment QR is regenerated from the current price each time.</p>
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        {field("Single Workspace price (â‚¹)", "single_workspace_price", "number")}
        {field("Agency price (â‚¹)", "agency_price", "number")}
        {field("Trial days", "trial_days", "number")}
        {field("UPI ID", "upi_id")}
        {field("Account holder", "account_holder_name")}
        {field("Bank name", "bank_name")}
        {field("Account number", "account_number")}
        {field("IFSC", "ifsc_code")}
        {field("MICR", "micr_code")}
        {field("SWIFT", "swift_code")}
      </div>
      <button disabled={saving} className="rounded-lg bg-slate-900 px-5 py-2 text-white disabled:opacity-50">{saving ? "Saving..." : "Save Billing Settings"}</button>
      {message && <p className="text-sm text-slate-600">{message}</p>}
    </form>
  );
}


