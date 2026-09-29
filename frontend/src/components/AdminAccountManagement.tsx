import { useEffect, useState } from "react";
import { ArrowRightLeft, Building2, RefreshCw, ShieldAlert, Power } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import { toast } from "sonner";

type Account = {
  company_id: string;
  company_name: string;
  account_type: "client" | "agency";
  is_active: boolean;
  client_count: number;
  users: Array<{
    id: string;
    email: string;
    first_name: string;
    last_name: string;
    role: string;
    is_active: boolean;
  }>;
};

export function AdminAccountManagement() {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    try {
      const data = await api.get<Account[]>("/api/admin/accounts");
      setAccounts(data);
    } catch (error) {
      console.error("Failed to load account management:", error);
      toast.error("Could not load account management.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const setStatus = async (account: Account) => {
    setBusy(account.company_id);
    try {
      await api.patch(`/api/admin/accounts/${account.company_id}/status`, {
        is_active: !account.is_active,
      });
      toast.success(account.is_active ? "Account deactivated." : "Account activated.");
      await load();
    } catch (error) {
      console.error(error);
      toast.error("Account status could not be changed.");
    } finally {
      setBusy(null);
    }
  };

  const convert = async (account: Account) => {
    const target = account.account_type === "client" ? "agency" : "client";
    const confirmed = window.confirm(
      `Convert "${account.company_name}" from ${account.account_type} to ${target}?`
    );
    if (!confirmed) return;

    setBusy(account.company_id);
    try {
      await api.post(`/api/admin/accounts/${account.company_id}/convert`, {
        account_type: target,
      });
      toast.success(`Account converted to ${target}.`);
      await load();
    } catch (error: any) {
      const detail = error?.data?.detail || "Account conversion could not be completed.";
      toast.error(Array.isArray(detail) ? detail.map((x: any) => x.msg).join(", ") : detail);
    } finally {
      setBusy(null);
    }
  };

  if (loading) {
    return <div className="p-6 text-sm text-slate-500">Loading account management...</div>;
  }

  return (
    <Card className="border-slate-200 dark:border-slate-800">
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle className="flex items-center gap-2">
          <ShieldAlert className="size-5" />
          Account & Tenant Management
        </CardTitle>
        <Button variant="outline" size="sm" onClick={() => void load()}>
          <RefreshCw className="size-4 mr-2" /> Refresh
        </Button>
      </CardHeader>
      <CardContent className="space-y-3">
        {accounts.map((account) => (
          <div
            key={account.company_id}
            className="rounded-xl border border-slate-200 dark:border-slate-800 p-4"
          >
            <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <Building2 className="size-4 shrink-0" />
                  <p className="font-medium truncate">{account.company_name}</p>
                  <Badge variant={account.account_type === "agency" ? "default" : "secondary"}>
                    {account.account_type}
                  </Badge>
                  <Badge variant={account.is_active ? "outline" : "destructive"}>
                    {account.is_active ? "Active" : "Disabled"}
                  </Badge>
                </div>
                <p className="text-xs text-slate-500 mt-1">
                  {account.client_count} client record{account.client_count === 1 ? "" : "s"} ·{" "}
                  {account.users.length} user{account.users.length === 1 ? "" : "s"}
                </p>
              </div>

              <div className="flex gap-2 shrink-0">
                <Button
                  size="sm"
                  variant="outline"
                  disabled={busy === account.company_id}
                  onClick={() => void convert(account)}
                >
                  <ArrowRightLeft className="size-4 mr-2" />
                  Convert
                </Button>
                <Button
                  size="sm"
                  variant={account.is_active ? "destructive" : "outline"}
                  disabled={busy === account.company_id}
                  onClick={() => void setStatus(account)}
                >
                  <Power className="size-4 mr-2" />
                  {account.is_active ? "Disable" : "Activate"}
                </Button>
              </div>
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
