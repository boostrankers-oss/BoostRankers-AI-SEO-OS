import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { ShieldCheck, Building2, Globe, CheckCircle2, AlertCircle } from "lucide-react";
import { api } from "@/lib/api";
import { toast } from "sonner";

interface InvitationInfo {
  valid: boolean;
  invitation_id: string;
  email: string;
  client_id: string;
  business_name: string;
  website: string;
  workspace_name: string;
  expires_at: string;
}

interface AcceptResponse {
  success: boolean;
  message: string;
  user: { id: string; email: string; role: string; company_id: string };
  tokens: { access_token: string; refresh_token: string };
}

export function ClientInvitation() {
  const { token = "" } = useParams<{ token: string }>();
  const navigate = useNavigate();
  const [info, setInfo] = useState<InvitationInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");

  useEffect(() => {
    if (!token) return;
    api.get<InvitationInfo>(`/api/clients/invitations/${encodeURIComponent(token)}`, { auth: false })
      .then(setInfo)
      .catch((err: any) => setError(err?.data?.detail || "This invitation is invalid or expired."))
      .finally(() => setLoading(false));
  }, [token]);

  const accept = async (event: React.FormEvent) => {
    event.preventDefault();
    if (submitting) return;
    setError("");
    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }
    setSubmitting(true);
    try {
      const response = await api.post<AcceptResponse>(
        `/api/clients/invitations/${encodeURIComponent(token)}/accept`,
        { first_name: firstName, last_name: lastName, password, confirm_password: confirmPassword },
        { auth: false },
      );
      localStorage.setItem("access_token", response.tokens.access_token);
      localStorage.setItem("refresh_token", response.tokens.refresh_token);
      localStorage.setItem("boost_user", JSON.stringify(response.user));
      toast.success("Invitation accepted. Welcome to Boost Rankers!");
      navigate("/", { replace: true });
      window.location.reload();
    } catch (err: any) {
      const message = err?.data?.detail || err?.message || "Could not accept invitation.";
      setError(message);
      toast.error(message);
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) return <div className="min-h-screen flex items-center justify-center p-6"><p>Validating invitation...</p></div>;

  if (error || !info) {
    return <div className="min-h-screen flex items-center justify-center bg-slate-50 dark:bg-slate-950 p-6"><Card className="w-full max-w-md"><CardHeader><CardTitle className="flex items-center gap-2"><AlertCircle className="size-5 text-rose-500" /> Invitation unavailable</CardTitle><CardDescription>{error || "Invitation could not be loaded."}</CardDescription></CardHeader><CardContent><Button className="w-full" onClick={() => navigate("/")}>Go to Boost Rankers</Button></CardContent></Card></div>;
  }

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950 flex items-center justify-center p-6">
      <Card className="w-full max-w-lg shadow-xl">
        <CardHeader>
          <div className="flex items-center gap-2 text-emerald-600"><ShieldCheck className="size-6" /><span className="font-semibold">Boost Rankers</span></div>
          <CardTitle className="text-2xl">You're invited to manage your SEO workspace</CardTitle>
          <CardDescription>The agency has invited you to access your business workspace. Create your client login to continue.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="rounded-xl border p-4 mb-6 space-y-2 bg-white dark:bg-slate-900">
            <div className="font-semibold flex items-center gap-2"><Building2 className="size-4" /> {info.business_name}</div>
            <div className="text-sm text-slate-500 flex items-center gap-2"><Globe className="size-4" /> {info.website}</div>
            <div className="text-sm text-slate-500">Invitation for: {info.email}</div>
          </div>
          <form onSubmit={accept} className="space-y-4">
            <div className="grid grid-cols-2 gap-3"><div><Label>First name</Label><Input value={firstName} onChange={e => setFirstName(e.target.value)} required /></div><div><Label>Last name</Label><Input value={lastName} onChange={e => setLastName(e.target.value)} required /></div></div>
            <div><Label>Password</Label><Input type="password" value={password} onChange={e => setPassword(e.target.value)} minLength={12} required /><p className="text-xs text-slate-500 mt-1">Use 12+ characters with upper/lowercase, a number, and a special character.</p></div>
            <div><Label>Confirm password</Label><Input type="password" value={confirmPassword} onChange={e => setConfirmPassword(e.target.value)} minLength={12} required /></div>
            {error && <p className="text-sm text-rose-600">{error}</p>}
            <Button className="w-full bg-emerald-600 hover:bg-emerald-700 text-white" disabled={submitting}>{submitting ? "Accepting invitation..." : "Accept Invitation & Create Account"}</Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
