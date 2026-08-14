import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { ShieldCheck, Mail, Lock, User as UserIcon, Building2, ArrowRight, AlertCircle } from "lucide-react";
import { useAuth, UserRole } from "@/components/AuthProvider";
import { toast } from "sonner";

export function AuthScreen() {
  const { login, signup, loading } = useAuth();
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [error, setError] = useState("");

  const [loginEmail, setLoginEmail] = useState("");
  const [loginPassword, setLoginPassword] = useState("");

  const [signupFirstName, setSignupFirstName] = useState("");
  const [signupLastName, setSignupLastName] = useState("");
  const [signupEmail, setSignupEmail] = useState("");
  const [signupPassword, setSignupPassword] = useState("");
  const [signupConfirmPassword, setSignupConfirmPassword] = useState("");
  const [signupCompany, setSignupCompany] = useState("");
  const [signupRole, setSignupRole] = useState<UserRole>("client"); // default to client

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    try {
      await login(loginEmail, loginPassword);
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
    // Validation
    if (!signupFirstName || !signupLastName || !signupEmail || !signupPassword || !signupConfirmPassword) {
      setError("Please fill in all fields.");
      return;
    }
    if (signupPassword.length < 12) {
	  setError("Password must be at least 12 characters.");
	  return;
	}

	const passwordByteLength = new TextEncoder().encode(signupPassword).length;

	if (passwordByteLength > 72) {
	  setError(
		"Password is too long. Please use a password of 72 bytes or fewer."
	  );
	  return;
	}
	
	const confirmPasswordByteLength =
	  new TextEncoder().encode(signupConfirmPassword).length;

	if (confirmPasswordByteLength > 72) {
	  setError(
		"Confirmation password is too long. Please use a password of 72 bytes or fewer."
	  );
	  return;
	}
    if (signupPassword !== signupConfirmPassword) {
      setError("Passwords do not match.");
      return;
    }
    try {
      await signup({
        email: signupEmail,
        password: signupPassword,
        confirm_password: signupConfirmPassword,
        first_name: signupFirstName,
        last_name: signupLastName,
        company_name: signupCompany || undefined,
      });
      toast.success("Account created successfully!");
    } catch (err: any) {
      const msg = err?.data?.detail || "Signup failed. Please try again.";
      setError(msg);
      toast.error("Signup failed");
    }
  };

  return (
    <div className="min-h-screen grid grid-cols-1 lg:grid-cols-2 bg-slate-50 dark:bg-slate-950">
      <div className="hidden lg:flex flex-col justify-between p-12 bg-gradient-to-br from-emerald-600 to-teal-700 text-white relative overflow-hidden">
        <div className="absolute inset-0 opacity-10" style={{ backgroundImage: "radial-gradient(circle at 20% 20%, white 1px, transparent 1px)", backgroundSize: "32px 32px" }}></div>
        <div className="relative z-10">
          <div className="flex items-center gap-2">
            <div className="size-10 rounded-xl bg-white/20 backdrop-blur-sm flex items-center justify-center">
              <ShieldCheck className="size-6 text-white" />
            </div>
            <div>
              <h1 className="font-serif text-xl font-bold leading-none">Boost Rankers</h1>
              <p className="text-sm text-emerald-100 mt-1">AI SEO Operating System</p>
            </div>
          </div>
        </div>
        <div className="relative z-10 space-y-6">
          <h2 className="font-serif text-4xl font-bold leading-tight">
            Enterprise AI SEO<br />Operating System
          </h2>
          <p className="text-emerald-100 text-lg max-w-md">
            Multi-agent autonomous audits, AI-powered content planning, and comprehensive backlink intelligence for agencies.
          </p>
          <div className="flex gap-8 pt-4">
            <div>
              <p className="font-serif text-3xl font-bold">10+</p>
              <p className="text-sm text-emerald-200">AI Agents</p>
            </div>
            <div>
              <p className="font-serif text-3xl font-bold">15+</p>
              <p className="text-sm text-emerald-200">SEO Modules</p>
            </div>
            <div>
              <p className="font-serif text-3xl font-bold">99.9%</p>
              <p className="text-sm text-emerald-200">Uptime</p>
            </div>
          </div>
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

          <Tabs value={mode} onValueChange={(v) => { setMode(v as "login" | "signup"); setError(""); }}>
            <TabsList className="grid grid-cols-2 w-full mb-6">
              <TabsTrigger value="login">Login</TabsTrigger>
              <TabsTrigger value="signup">Sign Up</TabsTrigger>
            </TabsList>

            <TabsContent value="login">
              <Card className="border-slate-200 dark:border-slate-800 shadow-lg">
                <CardHeader>
                  <CardTitle className="font-serif text-2xl">Welcome back</CardTitle>
                  <CardDescription>Enter your credentials to access your dashboard</CardDescription>
                </CardHeader>
                <CardContent>
                  <form onSubmit={handleLogin} className="space-y-4">
                    <div className="space-y-2">
                      <Label htmlFor="email">Email</Label>
                      <div className="relative">
                        <Mail className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-slate-400" />
                        <Input type="email" id="email" placeholder="you@company.com" className="pl-9" value={loginEmail} onChange={(e) => setLoginEmail(e.target.value)} required />
                      </div>
                    </div>
                    <div className="space-y-2">
                      <div className="flex items-center justify-between">
                        <Label htmlFor="password">Password</Label>
                        <button type="button" className="text-xs text-emerald-600 hover:underline">Forgot password?</button>
                      </div>
                      <div className="relative">
                        <Lock className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-slate-400" />
                        <Input type="password" id="password" placeholder="••••••••" className="pl-9" value={loginPassword} onChange={(e) => setLoginPassword(e.target.value)} required />
                      </div>
                    </div>

                    {error && (
                      <div className="flex items-center gap-2 p-3 rounded-lg text-sm text-rose-700 bg-rose-50 dark:bg-rose-500/10 dark:text-rose-400">
                        <AlertCircle className="size-4" /> {error}
                      </div>
                    )}

                    <Button type="submit" className="w-full bg-emerald-600 hover:bg-emerald-700 text-white shadow-md shadow-emerald-600/20" disabled={loading}>
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
                  <CardDescription>Start your enterprise SEO journey today</CardDescription>
                </CardHeader>
                <CardContent>
                  <form onSubmit={handleSignup} className="space-y-4">
                    <div className="grid grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label htmlFor="first-name">First Name</Label>
                        <Input id="first-name" placeholder="John" value={signupFirstName} onChange={(e) => setSignupFirstName(e.target.value)} required />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="last-name">Last Name</Label>
                        <Input id="last-name" placeholder="Doe" value={signupLastName} onChange={(e) => setSignupLastName(e.target.value)} required />
                      </div>
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="signup-email">Email</Label>
                      <div className="relative">
                        <Mail className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-slate-400" />
                        <Input type="email" id="signup-email" placeholder="you@company.com" className="pl-9" value={signupEmail} onChange={(e) => setSignupEmail(e.target.value)} required />
                      </div>
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="company">Company Name</Label>
                      <div className="relative">
                        <Building2 className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-slate-400" />
                        <Input id="company" placeholder="Acme Corp" className="pl-9" value={signupCompany} onChange={(e) => setSignupCompany(e.target.value)} />
                      </div>
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="signup-password">Password</Label>
                      <div className="relative">
                        <Lock className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-slate-400" />
                        <Input type="password" maxLength={72} id="signup-password" placeholder="Min 12 characters" className="pl-9" value={signupPassword} onChange={(e) => setSignupPassword(e.target.value)} required />
                      </div>
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="signup-confirm-password">Confirm Password</Label>
                      <div className="relative">
                        <Lock className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-slate-400" />
                        <Input type="password" id="signup-confirm-password" maxLength={72} placeholder="••••••••" className="pl-9" value={signupConfirmPassword} onChange={(e) => setSignupConfirmPassword(e.target.value)} required />
                      </div>
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="role">Account Type</Label>
                      <Select value={signupRole} onValueChange={(v) => setSignupRole(v as UserRole)}>
                        <SelectTrigger id="role"><SelectValue /></SelectTrigger>
                        <SelectContent>
                          <SelectItem value="super_admin">Super Admin</SelectItem>
                          <SelectItem value="agency_admin">Agency Admin</SelectItem>
                          <SelectItem value="manager">Manager</SelectItem>
                          <SelectItem value="seo_specialist">SEO Specialist</SelectItem>
                          <SelectItem value="client">Client</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>

                    {error && (
                      <div className="flex items-center gap-2 p-3 rounded-lg text-sm text-rose-700 bg-rose-50 dark:bg-rose-500/10 dark:text-rose-400">
                        <AlertCircle className="size-4" /> {error}
                      </div>
                    )}

                    <Button type="submit" className="w-full bg-emerald-600 hover:bg-emerald-700 text-white shadow-md shadow-emerald-600/20" disabled={loading}>
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