import { useEffect, useMemo, useState } from "react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { AdminAccountManagement } from "@/components/AdminAccountManagement";
import AdminBillingSettings from "@/components/AdminBillingSettings";
import AdminPaymentRecords from "@/components/AdminPaymentRecords";
import {
  Building2,
  Users,
  Plus,
  UserCheck,
  UserX,
  ShieldCheck,
  CalendarDays,
  RefreshCw,
  CreditCard,
  LayoutDashboard,
  Settings2,
  AlertCircle,
} from "lucide-react";

interface Company {
  id: string;
  name: string;
  email?: string | null;
  subscription_plan?: string | null;
  subscription_status?: string | null;
  billing_cycle?: string | null;
  monthly_price?: number | string | null;
  is_active: boolean;
  is_verified?: boolean;
  status?: string | null;
  created_at?: string | null;
}

interface CompanyListResponse {
  items: Company[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

interface User {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  role: string;
  company_id: string | null;
  is_active: boolean;
  is_verified?: boolean;
  is_superuser?: boolean;
  last_login?: string | null;
  created_at?: string | null;
}

interface PlatformStats {
  total_users: number;
  active_users: number;
  inactive_users: number;
  verified_users: number;
  unverified_users: number;
  total_companies: number;
  active_companies: number;
  inactive_companies: number;
  new_users_today: number;
  new_users_this_month: number;
}

type DashboardSection = "overview" | "users" | "companies" | "accounts" | "billing";

function getUserDisplayName(user: User): string {
  const name = `${user.first_name || ""} ${user.last_name || ""}`.trim();
  return name || user.email;
}

function formatDate(value?: string | null): string {
  if (!value) return "â€”";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "â€”" : date.toLocaleDateString();
}

function formatMoney(value?: number | string | null): string {
  if (value === null || value === undefined || value === "") return "â€”";
  const amount = Number(value);
  if (!Number.isFinite(amount)) return "â€”";
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(amount);
}

export default function AdminDashboard() {
  const [section, setSection] = useState<DashboardSection>("overview");
  const [companies, setCompanies] = useState<Company[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [stats, setStats] = useState<PlatformStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [isAddCompanyOpen, setIsAddCompanyOpen] = useState(false);
  const [newCompany, setNewCompany] = useState({ name: "", email: "" });
  const [isSubmitting, setIsSubmitting] = useState(false);

  const companyById = useMemo(() => {
    return new Map(companies.map((company) => [company.id, company.name]));
  }, [companies]);

  const fetchData = async (showRefreshState = false) => {
    if (showRefreshState) setRefreshing(true);
    else setLoading(true);

    setLoadError(null);

    const errors: string[] = [];

    try {
      const companiesRes = await api.get<CompanyListResponse>(
        "/api/companies?page=1&page_size=100&sort_by=created_at&sort_order=desc"
      );
      setCompanies(companiesRes.items || []);
    } catch (error) {
      console.error("Super Admin companies endpoint failed:", error);
      errors.push("Companies could not be loaded.");
    }

    try {
      const usersRes = await api.get<User[]>("/api/users");
      setUsers(usersRes || []);
    } catch (error) {
      console.error("Super Admin users endpoint failed:", error);
      errors.push("Users could not be loaded.");
    }

    try {
      const statsRes = await api.get<PlatformStats>("/api/users/stats");
      setStats(statsRes);
    } catch (error) {
      console.error("Super Admin stats endpoint failed:", error);
      errors.push("Platform statistics could not be loaded.");
    }

    if (errors.length) {
      setLoadError(errors.join(" "));
      toast.error("Some Super Admin data could not be loaded. Check the error panel and retry.");
    }

    setLoading(false);
    setRefreshing(false);
  };

  useEffect(() => {
    void fetchData();
  }, []);

  const handleAddCompany = async () => {
    const companyName = newCompany.name.trim();
    if (!companyName) {
      toast.error("Company name is required");
      return;
    }

    setIsSubmitting(true);
    try {
      await api.post("/api/companies", {
        name: companyName,
        email: newCompany.email.trim() || undefined,
      });
      toast.success("Company added successfully");
      setIsAddCompanyOpen(false);
      setNewCompany({ name: "", email: "" });
      await fetchData(true);
    } catch (error) {
      console.error("Failed to add company:", error);
      toast.error("Could not add company");
    } finally {
      setIsSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="p-8 flex min-h-[420px] items-center justify-center">
        <div className="flex items-center gap-2 text-slate-500">
          <RefreshCw className="size-4 animate-spin" />
          Loading Super Admin dashboard...
        </div>
      </div>
    );
  }

  const navItems: Array<{ id: DashboardSection; label: string; icon: typeof LayoutDashboard }> = [
    { id: "overview", label: "Overview", icon: LayoutDashboard },
    { id: "users", label: "Users", icon: Users },
    { id: "companies", label: "Companies", icon: Building2 },
    { id: "accounts", label: "Account Management", icon: Settings2 },
    { id: "billing", label: "Billing", icon: CreditCard },
  ];

  return (
    <div className="p-6 lg:p-8 space-y-6">
      <header className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-indigo-600">
            <ShieldCheck className="size-4" /> Platform Administration
          </div>
          <h2 className="mt-1 font-serif text-3xl font-bold tracking-tight">Super Admin Dashboard</h2>
          <p className="mt-1 text-slate-500 dark:text-slate-400">
            Platform-wide visibility for users, workspaces, subscriptions, and account controls.
          </p>
        </div>
        <Button variant="outline" onClick={() => void fetchData(true)} disabled={refreshing}>
          <RefreshCw className={`size-4 mr-2 ${refreshing ? "animate-spin" : ""}`} />
          {refreshing ? "Refreshing..." : "Refresh"}
        </Button>
      </header>

      {loadError && (
        <Card className="border-rose-200 bg-rose-50/60 dark:border-rose-900 dark:bg-rose-950/20">
          <CardContent className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-start gap-3">
              <AlertCircle className="mt-0.5 size-5 text-rose-600 shrink-0" />
              <div>
                <p className="font-medium text-rose-800 dark:text-rose-300">Admin data loading issue</p>
                <p className="text-sm text-rose-700 dark:text-rose-400">{loadError}</p>
              </div>
            </div>
            <Button variant="outline" onClick={() => void fetchData(true)}>Retry</Button>
          </CardContent>
        </Card>
      )}

      <div className="flex flex-wrap gap-2 rounded-xl border border-slate-200 bg-white p-2 dark:border-slate-800 dark:bg-slate-950">
        {navItems.map(({ id, label, icon: Icon }) => (
          <Button
            key={id}
            variant={section === id ? "default" : "ghost"}
            onClick={() => setSection(id)}
            className="gap-2"
          >
            <Icon className="size-4" />
            {label}
          </Button>
        ))}
      </div>

      {section === "overview" && (
        <>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard label="Total Users" value={stats?.total_users} icon={Users} note="All registered platform users" />
            <StatCard label="Active Users" value={stats?.active_users} icon={UserCheck} note="Currently active users" />
            <StatCard label="Total Companies" value={stats?.total_companies} icon={Building2} note="Registered workspaces" />
            <StatCard label="New This Month" value={stats?.new_users_this_month} icon={CalendarDays} note="Users registered this month" />
            <StatCard label="Verified Users" value={stats?.verified_users} icon={ShieldCheck} note="Verified platform users" />
            <StatCard label="Inactive Users" value={stats?.inactive_users} icon={UserX} note="Inactive platform users" />
            <StatCard label="Active Companies" value={stats?.active_companies} icon={Building2} note="Active workspaces" />
            <StatCard label="New Users Today" value={stats?.new_users_today} icon={CalendarDays} note="Users registered today" />
          </div>

          <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
            <PlatformSnapshot stats={stats} companies={companies} />
            <SubscriptionSnapshot companies={companies} />
          </div>
        </>
      )}

      {section === "users" && (
        <UserManagement users={users} companyById={companyById} />
      )}

      {section === "companies" && (
        <CompanyManagement
          companies={companies}
          onAdd={() => setIsAddCompanyOpen(true)}
          onRefresh={() => void fetchData(true)}
        />
      )}

      {section === "accounts" && <AdminAccountManagement />}

      {section === "billing" && (
        <div className="space-y-6">
          <AdminBillingSettings />
          <AdminPaymentRecords />
        </div>
      )}

      <Dialog open={isAddCompanyOpen} onOpenChange={setIsAddCompanyOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add New Company</DialogTitle>
            <DialogDescription>Create a new platform workspace. Subscription/payment status is not fabricated here.</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="company-name">Company Name *</Label>
              <Input
                id="company-name"
                value={newCompany.name}
                onChange={(event) => setNewCompany((previous) => ({ ...previous, name: event.target.value }))}
                placeholder="Acme Corp"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="company-email">Email</Label>
              <Input
                id="company-email"
                type="email"
                value={newCompany.email}
                onChange={(event) => setNewCompany((previous) => ({ ...previous, email: event.target.value }))}
                placeholder="admin@acme.com"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsAddCompanyOpen(false)} disabled={isSubmitting}>Cancel</Button>
            <Button onClick={() => void handleAddCompany()} disabled={isSubmitting}>
              {isSubmitting ? "Adding..." : "Add Company"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function StatCard({
  label,
  value,
  icon: Icon,
  note,
}: {
  label: string;
  value?: number;
  icon: typeof Users;
  note: string;
}) {
  return (
    <Card className="border-slate-200 dark:border-slate-800 shadow-sm">
      <CardHeader className="pb-2">
        <CardDescription>{label}</CardDescription>
        <CardTitle className="flex items-center justify-between text-3xl">
          <span>{value === undefined ? "â€”" : value}</span>
          <Icon className="size-7 text-indigo-600" />
        </CardTitle>
      </CardHeader>
      <CardContent><p className="text-xs text-slate-500">{note}</p></CardContent>
    </Card>
  );
}

function PlatformSnapshot({ stats, companies }: { stats: PlatformStats | null; companies: Company[] }) {
  const verifiedRate = stats && stats.total_users > 0
    ? Math.round((stats.verified_users / stats.total_users) * 100)
    : 0;

  return (
    <Card className="border-slate-200 dark:border-slate-800">
      <CardHeader>
        <CardTitle>Platform Snapshot</CardTitle>
        <CardDescription>Current platform state from live API data.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <ProgressRow label="Active users" value={stats?.active_users ?? 0} total={stats?.total_users ?? 0} />
        <ProgressRow label="Verified users" value={stats?.verified_users ?? 0} total={stats?.total_users ?? 0} />
        <ProgressRow label="Active companies" value={stats?.active_companies ?? 0} total={stats?.total_companies ?? 0} />
        <div className="grid grid-cols-2 gap-3 pt-2">
          <MiniMetric label="Verification rate" value={`${verifiedRate}%`} />
          <MiniMetric label="Loaded companies" value={companies.length.toString()} />
        </div>
      </CardContent>
    </Card>
  );
}

function SubscriptionSnapshot({ companies }: { companies: Company[] }) {
  const active = companies.filter((company) => company.is_active);
  const paid = active.filter((company) => {
    const plan = String(company.subscription_plan || "").toLowerCase();
    return plan && !["free", "trial"].includes(plan);
  });
  const trial = active.filter((company) => String(company.subscription_status || "").toLowerCase() === "trial");

  return (
    <Card className="border-slate-200 dark:border-slate-800">
      <CardHeader>
        <CardTitle className="flex items-center gap-2"><CreditCard className="size-5" /> Subscription Visibility</CardTitle>
        <CardDescription>Account subscription fields only; no payment/revenue is invented.</CardDescription>
      </CardHeader>
      <CardContent className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <MiniMetric label="Active" value={active.length.toString()} />
        <MiniMetric label="Paid-plan records" value={paid.length.toString()} />
        <MiniMetric label="Trial" value={trial.length.toString()} />
      </CardContent>
    </Card>
  );
}

function ProgressRow({ label, value, total }: { label: string; value: number; total: number }) {
  const percent = total > 0 ? Math.min(100, Math.round((value / total) * 100)) : 0;
  return (
    <div>
      <div className="mb-1 flex justify-between text-sm">
        <span>{label}</span><span className="text-slate-500">{value} / {total}</span>
      </div>
      <div className="h-2 rounded-full bg-slate-100 dark:bg-slate-800">
        <div className="h-2 rounded-full bg-indigo-500" style={{ width: `${percent}%` }} />
      </div>
    </div>
  );
}

function MiniMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-slate-200 p-3 dark:border-slate-800">
      <p className="text-xs text-slate-500">{label}</p>
      <p className="mt-1 text-lg font-semibold">{value}</p>
    </div>
  );
}

function UserManagement({ users, companyById }: { users: User[]; companyById: Map<string, string> }) {
  return (
    <Card className="border-slate-200 dark:border-slate-800">
      <CardHeader>
        <CardTitle className="flex items-center gap-2"><Users className="size-5" /> Platform Users</CardTitle>
        <CardDescription>{users.length} users returned by the Super Admin API.</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead><TableHead>Email</TableHead><TableHead>Role</TableHead>
                <TableHead>Workspace</TableHead><TableHead>Verification</TableHead><TableHead>Status</TableHead>
                <TableHead>Created</TableHead><TableHead>Last Login</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {users.map((user) => (
                <TableRow key={user.id}>
                  <TableCell className="font-medium">{getUserDisplayName(user)}</TableCell>
                  <TableCell>{user.email}</TableCell>
                  <TableCell><span className="rounded-md bg-slate-100 px-2 py-1 text-xs dark:bg-slate-800">{user.role}</span></TableCell>
                  <TableCell>{user.company_id ? (companyById.get(user.company_id) || user.company_id) : "Platform"}</TableCell>
                  <TableCell>{user.is_verified ? "Verified" : "Unverified"}</TableCell>
                  <TableCell>{user.is_active ? "Active" : "Inactive"}</TableCell>
                  <TableCell>{formatDate(user.created_at)}</TableCell>
                  <TableCell>{formatDate(user.last_login)}</TableCell>
                </TableRow>
              ))}
              {!users.length && <TableRow><TableCell colSpan={8} className="py-8 text-center text-slate-500">No users exist in the returned platform dataset.</TableCell></TableRow>}
            </TableBody>
          </Table>
        </div>
      </CardContent>
    </Card>
  );
}

function CompanyManagement({ companies, onAdd, onRefresh }: { companies: Company[]; onAdd: () => void; onRefresh: () => void }) {
  return (
    <Card className="border-slate-200 dark:border-slate-800">
      <CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <CardTitle className="flex items-center gap-2"><Building2 className="size-5" /> Companies / Workspaces</CardTitle>
          <CardDescription>Platform workspaces with their stored subscription state.</CardDescription>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={onRefresh}><RefreshCw className="size-4 mr-2" />Refresh</Button>
          <Button size="sm" onClick={onAdd}><Plus className="size-4 mr-2" />Add Company</Button>
        </div>
      </CardHeader>
      <CardContent>
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Company</TableHead><TableHead>Email</TableHead><TableHead>Plan</TableHead>
                <TableHead>Subscription</TableHead><TableHead>Monthly Price</TableHead><TableHead>Status</TableHead><TableHead>Created</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {companies.map((company) => (
                <TableRow key={company.id}>
                  <TableCell className="font-medium">{company.name}</TableCell>
                  <TableCell>{company.email || "â€”"}</TableCell>
                  <TableCell>{company.subscription_plan || "â€”"}</TableCell>
                  <TableCell>{company.subscription_status || "â€”"}</TableCell>
                  <TableCell>{formatMoney(company.monthly_price)}</TableCell>
                  <TableCell>{company.is_active ? "Active" : "Inactive"}</TableCell>
                  <TableCell>{formatDate(company.created_at)}</TableCell>
                </TableRow>
              ))}
              {!companies.length && <TableRow><TableCell colSpan={7} className="py-8 text-center text-slate-500">No companies exist in the returned platform dataset.</TableCell></TableRow>}
            </TableBody>
          </Table>
        </div>
      </CardContent>
    </Card>
  );
}



