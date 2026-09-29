import { useState } from "react";
import {
  ShieldCheck,
  Mail,
  Lock,
  Building2,
  Globe,
  ArrowRight,
  AlertCircle,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { useAuth } from "@/components/AuthProvider";
import { toast } from "sonner";

type AccountType = "client" | "agency";

export function AuthScreen() {
  const { login, signup, loading } = useAuth();
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [error, setError] = useState("");

  const [loginEmail, setLoginEmail] = useState("");
  const [loginPassword, setLoginPassword] = useState("");

  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [businessName, setBusinessName] = useState("");
  const [website, setWebsite] = useState("");
  const [industry, setIndustry] = useState("");
  const [accountType, setAccountType] = useState<AccountType>("client");

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    try {
      await login(loginEmail.trim(), loginPassword);
      toast.success("Welcome back!");
    } catch (err: any) {
      const msg = err?.data?.detail || "Invalid credentials. Please try again.";
      setError(msg);
      toast.error("Login failed");
    }
  };

  const handleSignup = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (
      !firstName.trim() ||
      !lastName.trim() ||
      !email.trim() ||
      !password ||
      !confirmPassword ||
      !businessName.trim()
    ) {
      setError(
        accountType === "client"
          ? "Please complete your name, email, business name, website and password."
          : "Please complete your name, email, agency name and password."
      );
      return;
    }

    if (accountType === "client" && !website.trim()) {
      setError("Website is required for a single client / business owner account.");
      return;
    }

    if (password.length < 12) {
      setError("Password must be at least 12 characters.");
      return;
    }

    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    try {
      await signup({
        email: email.trim(),
        password,
        confirm_password: confirmPassword,
        first_name: firstName.trim(),
        last_name: lastName.trim(),
        account_type: accountType,
        company_name: businessName.trim(),
        website: website.trim() || undefined,
        industry: industry.trim() || undefined,
      });
      toast.success("Account created successfully!");
    } catch (err: any) {
      const msg =
        err?.data?.detail ||
        err?.message ||
        "Signup failed. Please try again.";
      setError(Array.isArray(msg) ? msg.map((x: any) => x.msg).join(", ") : msg);
      toast.error("Signup failed");
    }
  };

  return (
    <div className="min-h-screen grid grid-cols-1 lg:grid-cols-2 bg-slate-50 dark:bg-slate-950">
      <div className="hidden lg:flex flex-col justify-between p-12 bg-gradient-to-br from-emerald-600 to-teal-700 text-white relative overflow-hidden">
        <div className="absolute inset-0 opacity-10" style={{ backgroundImage: "radial-gradient(circle at 20% 20%, white 1px, transparent 1px)", backgroundSize: "32px 32px" }} />
        <div className="relative z-10 flex items-center gap-2">
          <div className="size-10 rounded-xl bg-white/20 flex items-center justify-center">
            <ShieldCheck className="size-6" />
          </div>
          <div>
            <h1 className="font-serif text-xl font-bold leading-none">Boost Rankers</h1>
            <p className="text-sm text-emerald-100 mt-1">AI SEO Operating System</p>
          </div>
        </div>
        <div className="relative z-10 space-y-6">
          <h2 className="font-serif text-4xl font-bold leading-tight">
            Enterprise AI SEO<br />Operating System
          </h2>
          <p className="text-emerald-100 text-lg max-w-md">
            Secure multi-tenant SEO management for businesses and agencies.
          </p>
        </div>
        <div className="relative z-10 text-sm text-emerald-200">
          © 2024 Boost Rankers. All rights reserved.
        </div>
      </div>

      <div className="flex items-center justify-center p-8">
        <div className="w-full max-w-md">
          <div className="lg:hidden flex items-center gap-2 mb-8 justify-center">
            <div className="size-10 rounded-xl bg-emerald-600 flex items-center justify-center">
              <ShieldCheck className="size-6 text-white" />
            </div>
            <h1 className="font-serif text-xl font-bold">Boost Rankers</h1>
          </div>

          <Tabs
            value={mode}
            onValueChange={(v) => {
              setMode(v as "login" | "signup");
              setError("");
            }}
          >
            <TabsList className="grid grid-cols-2 w-full mb-6">
              <TabsTrigger value="login">Login</TabsTrigger>
              <TabsTrigger value="signup">Sign Up</TabsTrigger>
            </TabsList>

            <TabsContent value="login">
              <Card className="border-slate-200 dark:border-slate-800 shadow-lg">
                <CardHeader>
                  <CardTitle className="font-serif text-2xl">Welcome back</CardTitle>
                  <CardDescription>Enter your credentials to access your dashboard.</CardDescription>
                </CardHeader>
                <CardContent>
                  <form onSubmit={handleLogin} className="space-y-4">
                    <div className="space-y-2">
                      <Label htmlFor="login-email">Email</Label>
                      <div className="relative">
                        <Mail className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-slate-400" />
                        <Input id="login-email" type="email" className="pl-9" value={loginEmail} onChange={(e) => setLoginEmail(e.target.value)} required />
                      </div>
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="login-password">Password</Label>
                      <div className="relative">
                        <Lock className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-slate-400" />
                        <Input id="login-password" type="password" className="pl-9" value={loginPassword} onChange={(e) => setLoginPassword(e.target.value)} required />
                      </div>
                    </div>
                    {error && (
                      <div className="flex items-center gap-2 p-3 rounded-lg text-sm text-rose-700 bg-rose-50 dark:bg-rose-500/10 dark:text-rose-400">
                        <AlertCircle className="size-4" /> {error}
                      </div>
                    )}
                    <Button type="submit" className="w-full bg-emerald-600 hover:bg-emerald-700 text-white" disabled={loading}>
                      {loading ? "Signing in..." : "Sign In"} <ArrowRight className="size-4" />
                    </Button>
                  </form>
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="signup">
              <Card className="border-slate-200 dark:border-slate-800 shadow-lg">
                <CardHeader>
                  <CardTitle className="font-serif text-2xl">Create an account</CardTitle>
                  <CardDescription>
                    Choose a separate workspace type. Super Admin accounts are never created through public signup.
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <form onSubmit={handleSignup} className="space-y-4">
                    <div className="space-y-2">
                      <Label>Account Type</Label>
                      <Select value={accountType} onValueChange={(v) => { setAccountType(v as AccountType); setError(""); }}>
                        <SelectTrigger><SelectValue /></SelectTrigger>
                        <SelectContent>
                          <SelectItem value="client">Single Client / Business Owner</SelectItem>
                          <SelectItem value="agency">Agency</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label htmlFor="first-name">First Name</Label>
                        <Input id="first-name" value={firstName} onChange={(e) => setFirstName(e.target.value)} required />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="last-name">Last Name</Label>
                        <Input id="last-name" value={lastName} onChange={(e) => setLastName(e.target.value)} required />
                      </div>
                    </div>

                    <div className="space-y-2">
                      <Label htmlFor="signup-email">Email</Label>
                      <div className="relative">
                        <Mail className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-slate-400" />
                        <Input id="signup-email" type="email" className="pl-9" value={email} onChange={(e) => setEmail(e.target.value)} required />
                      </div>
                    </div>

                    <div className="space-y-2">
                      <Label htmlFor="business-name">{accountType === "client" ? "Business / Client Name" : "Agency Name"}</Label>
                      <div className="relative">
                        <Building2 className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-slate-400" />
                        <Input id="business-name" className="pl-9" value={businessName} onChange={(e) => setBusinessName(e.target.value)} required />
                      </div>
                    </div>

                    {accountType === "client" && (
                      <>
                        <div className="space-y-2">
                          <Label htmlFor="website">Website</Label>
                          <div className="relative">
                            <Globe className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-slate-400" />
                            <Input id="website" type="url" placeholder="https://example.com" className="pl-9" value={website} onChange={(e) => setWebsite(e.target.value)} required />
                          </div>
                        </div>
                        <div className="space-y-2">
                          <Label htmlFor="industry">Industry <span className="text-slate-400">(optional)</span></Label>
                          <Input id="industry" value={industry} onChange={(e) => setIndustry(e.target.value)} />
                        </div>
                      </>
                    )}

                    <div className="space-y-2">
                      <Label htmlFor="signup-password">Password</Label>
                      <div className="relative">
                        <Lock className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-slate-400" />
                        <Input id="signup-password" type="password" placeholder="Minimum 12 characters" className="pl-9" value={password} onChange={(e) => setPassword(e.target.value)} required />
                      </div>
                    </div>

                    <div className="space-y-2">
                      <Label htmlFor="signup-confirm-password">Confirm Password</Label>
                      <Input id="signup-confirm-password" type="password" className="pl-9" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} required />
                    </div>

                    {error && (
                      <div className="flex items-center gap-2 p-3 rounded-lg text-sm text-rose-700 bg-rose-50 dark:bg-rose-500/10 dark:text-rose-400">
                        <AlertCircle className="size-4 shrink-0" /> {error}
                      </div>
                    )}

                    <Button type="submit" className="w-full bg-emerald-600 hover:bg-emerald-700 text-white" disabled={loading}>
                      {loading ? "Creating..." : "Create Account"} <ArrowRight className="size-4" />
                    </Button>
                  </form>
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        </div>
      </div>
    </div>
  );
}
