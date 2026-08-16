import { useEffect, useState } from "react";
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
import {
  Building2,
  Users,
  Plus,
  UserCheck,
  UserX,
  ShieldCheck,
  CalendarDays,
  RefreshCw,
} from "lucide-react";

/* ============================================================
   Types
   ============================================================ */

interface Company {
  id: string;
  name: string;
  email: string;
  subscription_plan: string;
  is_active: boolean;
  created_at: string;
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

/* ============================================================
   Helpers
   ============================================================ */

function formatDate(value?: string | null): string {
  if (!value) return "—";

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "—";
  }

  return date.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

function getUserDisplayName(user: User): string {
  const name = `${user.first_name || ""} ${user.last_name || ""}`.trim();

  return name || user.email;
}

/* ============================================================
   Component
   ============================================================ */

export default function AdminDashboard() {
  const [companies, setCompanies] = useState<Company[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [stats, setStats] = useState<PlatformStats | null>(null);

  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const [isAddCompanyOpen, setIsAddCompanyOpen] = useState(false);
  const [newCompany, setNewCompany] = useState({
    name: "",
    email: "",
  });

  const [isSubmitting, setIsSubmitting] = useState(false);

  /* ==========================================================
     Fetch Admin Data
     ========================================================== */

  const fetchData = async (showRefreshState = false) => {
    if (showRefreshState) {
      setRefreshing(true);
    } else {
      setLoading(true);
    }

    try {
      const [companiesRes, usersRes, statsRes] = await Promise.all([
        api.get<Company[]>("/api/companies"),
        api.get<User[]>("/api/users"),
        api.get<PlatformStats>("/api/users/stats"),
      ]);

      setCompanies(companiesRes);
      setUsers(usersRes);
      setStats(statsRes);
    } catch (error) {
      console.error("Failed to fetch admin data:", error);

      toast.error(
        "Could not load admin data. Make sure you are logged in as Super Admin."
      );
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    void fetchData();
  }, []);

  /* ==========================================================
     Add Company
     ========================================================== */

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

      setNewCompany({
        name: "",
        email: "",
      });

      await fetchData(true);
    } catch (error) {
      console.error("Failed to add company:", error);
      toast.error("Could not add company");
    } finally {
      setIsSubmitting(false);
    }
  };

  /* ==========================================================
     Loading
     ========================================================== */

  if (loading) {
    return (
      <div className="p-8 flex min-h-[300px] items-center justify-center">
        <div className="flex items-center gap-2 text-slate-500">
          <RefreshCw className="size-4 animate-spin" />
          Loading admin dashboard...
        </div>
      </div>
    );
  }

  /* ==========================================================
     Render
     ========================================================== */

  return (
    <div className="p-8 space-y-8">
      {/* ======================================================
          Header
         ====================================================== */}

      <header className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h2 className="font-serif text-3xl font-bold tracking-tight">
            Super Admin Dashboard
          </h2>

          <p className="text-slate-500 dark:text-slate-400 mt-1">
            Manage companies, users, and platform activity across Boost
            Rankers AI SEO OS.
          </p>
        </div>

        <Button
          variant="outline"
          onClick={() => void fetchData(true)}
          disabled={refreshing}
        >
          <RefreshCw
            className={`size-4 ${refreshing ? "animate-spin" : ""}`}
          />
          {refreshing ? "Refreshing..." : "Refresh"}
        </Button>
      </header>

      {/* ======================================================
          Primary Platform Statistics
         ====================================================== */}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Card className="border-slate-200 dark:border-slate-800">
          <CardHeader className="pb-2">
            <CardDescription>Total Users</CardDescription>

            <CardTitle className="flex items-center justify-between text-3xl">
              <span>{stats?.total_users ?? 0}</span>

              <Users className="size-7 text-indigo-600" />
            </CardTitle>
          </CardHeader>

          <CardContent>
            <p className="text-xs text-slate-500">
              All registered platform users
            </p>
          </CardContent>
        </Card>

        <Card className="border-slate-200 dark:border-slate-800">
          <CardHeader className="pb-2">
            <CardDescription>Active Users</CardDescription>

            <CardTitle className="flex items-center justify-between text-3xl">
              <span>{stats?.active_users ?? 0}</span>

              <UserCheck className="size-7 text-emerald-600" />
            </CardTitle>
          </CardHeader>

          <CardContent>
            <p className="text-xs text-slate-500">
              Currently active accounts
            </p>
          </CardContent>
        </Card>

        <Card className="border-slate-200 dark:border-slate-800">
          <CardHeader className="pb-2">
            <CardDescription>Total Companies</CardDescription>

            <CardTitle className="flex items-center justify-between text-3xl">
              <span>{stats?.total_companies ?? 0}</span>

              <Building2 className="size-7 text-emerald-600" />
            </CardTitle>
          </CardHeader>

          <CardContent>
            <p className="text-xs text-slate-500">
              Registered customer companies
            </p>
          </CardContent>
        </Card>

        <Card className="border-slate-200 dark:border-slate-800">
          <CardHeader className="pb-2">
            <CardDescription>New This Month</CardDescription>

            <CardTitle className="flex items-center justify-between text-3xl">
              <span>{stats?.new_users_this_month ?? 0}</span>

              <CalendarDays className="size-7 text-blue-600" />
            </CardTitle>
          </CardHeader>

          <CardContent>
            <p className="text-xs text-slate-500">
              Users registered this month
            </p>
          </CardContent>
        </Card>
      </div>

      {/* ======================================================
          Secondary Platform Statistics
         ====================================================== */}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Card className="border-slate-200 dark:border-slate-800">
          <CardHeader className="pb-2">
            <CardDescription>Verified Users</CardDescription>

            <CardTitle className="flex items-center justify-between text-2xl">
              <span>{stats?.verified_users ?? 0}</span>

              <ShieldCheck className="size-6 text-green-600" />
            </CardTitle>
          </CardHeader>
        </Card>

        <Card className="border-slate-200 dark:border-slate-800">
          <CardHeader className="pb-2">
            <CardDescription>Inactive Users</CardDescription>

            <CardTitle className="flex items-center justify-between text-2xl">
              <span>{stats?.inactive_users ?? 0}</span>

              <UserX className="size-6 text-rose-600" />
            </CardTitle>
          </CardHeader>
        </Card>

        <Card className="border-slate-200 dark:border-slate-800">
          <CardHeader className="pb-2">
            <CardDescription>Active Companies</CardDescription>

            <CardTitle className="flex items-center justify-between text-2xl">
              <span>{stats?.active_companies ?? 0}</span>

              <Building2 className="size-6 text-emerald-600" />
            </CardTitle>
          </CardHeader>
        </Card>

        <Card className="border-slate-200 dark:border-slate-800">
          <CardHeader className="pb-2">
            <CardDescription>New Users Today</CardDescription>

            <CardTitle className="flex items-center justify-between text-2xl">
              <span>{stats?.new_users_today ?? 0}</span>

              <CalendarDays className="size-6 text-indigo-600" />
            </CardTitle>
          </CardHeader>
        </Card>
      </div>

      {/* ======================================================
          Companies + Users
         ====================================================== */}

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        {/* ====================================================
            Companies
           ==================================================== */}

        <Card className="border-slate-200 dark:border-slate-800 shadow-sm">
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="font-serif flex items-center gap-2">
                  <Building2 className="size-5 text-emerald-600" />
                  Companies
                </CardTitle>

                <CardDescription>
                  All registered companies
                </CardDescription>
              </div>

              <Button
                size="sm"
                onClick={() => setIsAddCompanyOpen(true)}
                className="bg-emerald-600 hover:bg-emerald-700 text-white"
              >
                <Plus className="size-4" />
                Add
              </Button>
            </div>
          </CardHeader>

          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Email</TableHead>
                  <TableHead>Plan</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>

              <TableBody>
                {companies.map((company) => (
                  <TableRow key={company.id}>
                    <TableCell className="font-medium">
                      {company.name}
                    </TableCell>

                    <TableCell>
                      {company.email || "—"}
                    </TableCell>

                    <TableCell>
                      {company.subscription_plan || "—"}
                    </TableCell>

                    <TableCell>
                      <span
                        className={`px-2 py-1 rounded-md text-xs font-medium ${
                          company.is_active
                            ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-400"
                            : "bg-rose-50 text-rose-700 dark:bg-rose-500/10 dark:text-rose-400"
                        }`}
                      >
                        {company.is_active ? "Active" : "Inactive"}
                      </span>
                    </TableCell>
                  </TableRow>
                ))}

                {companies.length === 0 && (
                  <TableRow>
                    <TableCell
                      colSpan={4}
                      className="text-center text-slate-500"
                    >
                      No companies found
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </CardContent>
        </Card>

        {/* ====================================================
            Users
           ==================================================== */}

        <Card className="border-slate-200 dark:border-slate-800 shadow-sm">
          <CardHeader>
            <CardTitle className="font-serif flex items-center gap-2">
              <Users className="size-5 text-indigo-600" />
              Users
            </CardTitle>

            <CardDescription>
              All platform users
            </CardDescription>
          </CardHeader>

          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Email</TableHead>
                  <TableHead>Role</TableHead>
                  <TableHead>Company</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>

              <TableBody>
                {users.map((user) => (
                  <TableRow key={user.id}>
                    <TableCell className="font-medium">
                      {getUserDisplayName(user)}
                    </TableCell>

                    <TableCell>
                      {user.email}
                    </TableCell>

                    <TableCell>
                      <span className="px-2 py-1 rounded-md text-xs font-medium bg-slate-100 dark:bg-slate-800">
                        {user.role}
                      </span>
                    </TableCell>

                    <TableCell>
                      {user.company_id || "—"}
                    </TableCell>

                    <TableCell>
                      <span
                        className={`px-2 py-1 rounded-md text-xs font-medium ${
                          user.is_active
                            ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-400"
                            : "bg-rose-50 text-rose-700 dark:bg-rose-500/10 dark:text-rose-400"
                        }`}
                      >
                        {user.is_active ? "Active" : "Inactive"}
                      </span>
                    </TableCell>
                  </TableRow>
                ))}

                {users.length === 0 && (
                  <TableRow>
                    <TableCell
                      colSpan={5}
                      className="text-center text-slate-500"
                    >
                      No users found
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      </div>

      {/* ======================================================
          Add Company Dialog
         ====================================================== */}

      <Dialog
        open={isAddCompanyOpen}
        onOpenChange={setIsAddCompanyOpen}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              Add New Company
            </DialogTitle>

            <DialogDescription>
              Create a new company tenant.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="company-name">
                Company Name *
              </Label>

              <Input
                id="company-name"
                value={newCompany.name}
                onChange={(event) =>
                  setNewCompany((previous) => ({
                    ...previous,
                    name: event.target.value,
                  }))
                }
                placeholder="Acme Corp"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="company-email">
                Email
              </Label>

              <Input
                id="company-email"
                type="email"
                value={newCompany.email}
                onChange={(event) =>
                  setNewCompany((previous) => ({
                    ...previous,
                    email: event.target.value,
                  }))
                }
                placeholder="admin@acme.com"
              />
            </div>
          </div>

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setIsAddCompanyOpen(false)}
              disabled={isSubmitting}
            >
              Cancel
            </Button>

            <Button
              onClick={() => void handleAddCompany()}
              disabled={isSubmitting}
              className="bg-emerald-600 hover:bg-emerald-700 text-white"
            >
              {isSubmitting ? "Adding..." : "Add Company"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}