import { useEffect, useState } from "react";
import { api } from "@/lib/api";

type Payment = {
  id: string;
  company_id: string;
  plan_code: string;
  amount: string | number;
  currency: string;
  payment_method: string;
  status: string;
  transaction_reference: string | null;
  bank_reference: string | null;
  paid_at: string | null;
  verified_at: string | null;
};

export default function AdminPaymentRecords() {
  const [payments, setPayments] = useState<Payment[]>([]);
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    try { setPayments(await api.get<Payment[]>("/api/admin/billing/payments")); }
    finally { setLoading(false); }
  }

  useEffect(() => { void load(); }, []);

  async function verify(id: string) {
    await api.post(`/api/admin/billing/payments/${id}/verify`, {});
    await load();
  }

  if (loading) return <div className="p-6">Loading payments...</div>;

  return (
    <div className="rounded-xl border bg-white p-6 shadow-sm">
      <div className="mb-4 flex items-center justify-between"><h2 className="text-xl font-semibold">Payment Records</h2><button onClick={() => void load()} className="rounded-lg border px-3 py-2 text-sm">Refresh</button></div>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead><tr className="border-b text-slate-500"><th className="p-3">Company</th><th className="p-3">Plan</th><th className="p-3">Amount</th><th className="p-3">Reference</th><th className="p-3">Status</th><th className="p-3">Action</th></tr></thead>
          <tbody>{payments.map((payment) => <tr key={payment.id} className="border-b"><td className="p-3">{payment.company_id}</td><td className="p-3">{payment.plan_code}</td><td className="p-3">₹{Number(payment.amount).toLocaleString("en-IN")}</td><td className="p-3">{payment.transaction_reference || payment.bank_reference || "—"}</td><td className="p-3 uppercase">{payment.status}</td><td className="p-3">{payment.status === "pending" ? <button onClick={() => void verify(payment.id)} className="rounded-lg bg-emerald-600 px-3 py-1.5 text-white">Verify & Activate</button> : "—"}</td></tr>)}</tbody>
        </table>
        {!payments.length && <p className="p-5 text-center text-slate-500">No payment records.</p>}
      </div>
    </div>
  );
}
