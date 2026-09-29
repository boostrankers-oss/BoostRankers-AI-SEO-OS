import { useEffect, useState } from "react";
import { api } from "@/lib/api";

type Plan = {
  code: "single_workspace" | "agency";
  name: string;
  amount: string | number;
  currency: string;
  billing_cycle: string;
  trial_days: number;
};

type QR = {
  plan_code: string;
  amount: string | number;
  currency: string;
  upi_id: string;
  upi_uri: string;
  qr_data_url: string;
};

type Subscription = {
  id: string | null;
  plan_code: string | null;
  amount: string | number | null;
  currency: string | null;
  status: string;
  trial_ends_at: string | null;
  expires_at: string | null;
};

export default function Billing() {
  const [plans, setPlans] = useState<Plan[]>([]);
  const [subscription, setSubscription] = useState<Subscription | null>(null);
  const [selectedPlan, setSelectedPlan] = useState<Plan | null>(null);
  const [qr, setQr] = useState<QR | null>(null);
  const [reference, setReference] = useState("");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const [plansResponse, subscriptionResponse] = await Promise.all([
        api.get<Plan[]>("/api/billing/plans"),
        api.get<Subscription>("/api/billing/me"),
      ]);
      setPlans(plansResponse);
      setSubscription(subscriptionResponse);
    } catch (err) {
      console.error(err);
      setError("Unable to load billing information.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  async function choosePlan(plan: Plan) {
    setSelectedPlan(plan);
    setError(null);
    try {
      const response = await api.get<QR>(`/api/billing/qr/${plan.code}`);
      setQr(response);
    } catch (err) {
      console.error(err);
      setError("Unable to generate the payment QR code.");
    }
  }

  async function submitPayment() {
    if (!selectedPlan) return;
    setSubmitting(true);
    setError(null);
    try {
      await api.post("/api/billing/payments", {
        plan_code: selectedPlan.code,
        payment_method: "upi",
        transaction_reference: reference.trim() || undefined,
      });
      setReference("");
      await load();
      setSelectedPlan(null);
      setQr(null);
    } catch (err) {
      console.error(err);
      setError("Payment record could not be submitted.");
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) return <div className="p-8">Loading billing...</div>;

  return (
    <div className="space-y-6 p-8">
      <div>
        <h1 className="text-3xl font-bold">Billing & Subscription</h1>
        <p className="mt-1 text-slate-500">Manage your workspace subscription and payment.</p>
      </div>

      {error && <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">{error}</div>}

      {subscription && (
        <div className="rounded-xl border bg-white p-5 shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-sm text-slate-500">Current subscription</p>
              <p className="text-xl font-semibold">{subscription.plan_code || "Existing account"}</p>
            </div>
            <span className="rounded-full bg-slate-100 px-3 py-1 text-sm font-medium uppercase">{subscription.status}</span>
          </div>
          {subscription.trial_ends_at && <p className="mt-3 text-sm text-slate-600">Trial ends: {new Date(subscription.trial_ends_at).toLocaleString()}</p>}
        </div>
      )}

      <div className="grid gap-5 md:grid-cols-2">
        {plans.map((plan) => (
          <div key={plan.code} className="rounded-xl border bg-white p-6 shadow-sm">
            <h2 className="text-xl font-semibold">{plan.name}</h2>
            <p className="mt-3 text-3xl font-bold">₹{Number(plan.amount).toLocaleString("en-IN")}</p>
            <p className="text-sm text-slate-500">per month · {plan.trial_days}-day free trial</p>
            <button className="mt-5 w-full rounded-lg bg-slate-900 px-4 py-2 text-white hover:bg-slate-800" onClick={() => void choosePlan(plan)}>
              Pay for this plan
            </button>
          </div>
        ))}
      </div>

      {qr && selectedPlan && (
        <div className="rounded-xl border bg-white p-6 shadow-sm">
          <div className="grid gap-6 md:grid-cols-[220px_1fr]">
            <div className="flex justify-center">
              <img src={qr.qr_data_url} alt={`UPI QR for ₹${qr.amount}`} className="h-[220px] w-[220px] rounded-lg border p-2" />
            </div>
            <div>
              <h2 className="text-xl font-semibold">Pay ₹{Number(qr.amount).toLocaleString("en-IN")}</h2>
              <p className="mt-2 text-sm text-slate-600">UPI ID: <strong>{qr.upi_id}</strong></p>
              <p className="mt-1 break-all text-xs text-slate-400">The QR is generated from the current admin price.</p>
              <label className="mt-5 block text-sm font-medium">UPI / bank transaction reference</label>
              <input value={reference} onChange={(e) => setReference(e.target.value)} className="mt-2 w-full rounded-lg border px-3 py-2" placeholder="Enter transaction reference" />
              <button disabled={submitting} onClick={() => void submitPayment()} className="mt-4 rounded-lg bg-emerald-600 px-5 py-2 text-white disabled:opacity-50">
                {submitting ? "Submitting..." : "Submit Payment"}
              </button>
              <p className="mt-3 text-xs text-slate-500">Payment remains pending until the Super Admin verifies the transfer. Workspace activation happens automatically when verified.</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
