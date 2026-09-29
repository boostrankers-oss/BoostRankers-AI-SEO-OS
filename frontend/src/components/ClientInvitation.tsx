import { useEffect, useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { ShieldCheck, Building2, Globe, AlertCircle } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";

interface InvitationInfo {
  invitation_id: string;
  client_id: string;
  business_name: string;
  website: string;
  email: string;
  agency_name: string;
  expires_at: string;
}

function getInvitationToken(): string {
  const match = window.location.pathname.match(/^\/invite\/([^/]+)\/?$/);
  return match ? decodeURIComponent(match[1]) : "";
}

export function ClientInvitation() {
  const token = getInvitationToken();

  const [info, setInfo] = useState<InvitationInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!token) {
      setError("Invalid invitation link.");
      setLoading(false);
      return;
    }

    const loadInvitation = async () => {
      try {
        const data = await api.get<InvitationInfo>(
          `/api/clients/invitations/${encodeURIComponent(token)}`
        );
        setInfo(data);
      } catch (err: any) {
        setError(
          err?.message ||
            "This invitation is unavailable, expired, or has already been used."
        );
      } finally {
        setLoading(false);
      }
    };

    void loadInvitation();
  }, [token]);

  const handleAccept = async () => {
    if (!token || !info) return;

    if (password.length < 12) {
      toast.error("Password must contain at least 12 characters.");
      return;
    }

    if (password !== confirmPassword) {
      toast.error("Passwords do not match.");
      return;
    }

    setSubmitting(true);

    try {
      const result = await api.post<{
        access_token?: string;
        refresh_token?: string;
        message?: string;
      }>(
        `/api/clients/invitations/${encodeURIComponent(token)}/accept`,
        {
          password,
          confirm_password: confirmPassword,
        }
      );

      if (result.access_token) {
        localStorage.setItem("access_token", result.access_token);
      }

      if (result.refresh_token) {
        localStorage.setItem("refresh_token", result.refresh_token);
      }

      toast.success(
        result.message || "Invitation accepted. Welcome to Boost Rankers!"
      );

      window.location.href = "/";
    } catch (err: any) {
      toast.error(
        err?.message ||
          "Unable to accept this invitation. Please try again."
      );
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50 dark:bg-slate-950 p-6">
        <Card className="w-full max-w-md">
          <CardContent className="p-8 text-center">
            <div className="mx-auto mb-4 size-8 animate-spin rounded-full border-2 border-slate-300 border-t-emerald-600" />
            <p className="text-sm text-slate-500">
              Loading your invitation...
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (error || !info) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50 dark:bg-slate-950 p-6">
        <Card className="w-full max-w-md">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <AlertCircle className="size-5 text-rose-500" />
              Invitation unavailable
            </CardTitle>
            <CardDescription>
              {error || "Invitation could not be loaded."}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button
              className="w-full"
              onClick={() => {
                window.location.href = "/";
              }}
            >
              Go to Boost Rankers
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950 px-4 py-10">
      <div className="mx-auto w-full max-w-lg">
        <Card className="shadow-xl border-slate-200 dark:border-slate-800">
          <CardHeader className="space-y-4">
            <div className="flex items-center gap-3">
              <div className="flex size-11 items-center justify-center rounded-xl bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300">
                <ShieldCheck className="size-6" />
              </div>
              <div>
                <CardTitle>Join Boost Rankers</CardTitle>
                <CardDescription>
                  You have been invited to access a client workspace.
                </CardDescription>
              </div>
            </div>
          </CardHeader>

          <CardContent className="space-y-6">
            <div className="rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
              <div className="flex items-start gap-3">
                <Building2 className="mt-0.5 size-5 text-slate-500" />
                <div className="min-w-0">
                  <p className="font-semibold">{info.business_name}</p>
                  <p className="text-sm text-slate-500">{info.agency_name}</p>
                </div>
              </div>

              {info.website && (
                <div className="mt-3 flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300">
                  <Globe className="size-4" />
                  <span className="truncate">{info.website}</span>
                </div>
              )}

              <p className="mt-3 text-xs text-slate-500">
                Invitation email: {info.email}
              </p>
            </div>

            <div className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="invitation-password">
                  Create Password
                </Label>
                <Input
                  id="invitation-password"
                  type="password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  placeholder="At least 12 characters"
                  autoComplete="new-password"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="invitation-confirm-password">
                  Confirm Password
                </Label>
                <Input
                  id="invitation-confirm-password"
                  type="password"
                  value={confirmPassword}
                  onChange={(event) =>
                    setConfirmPassword(event.target.value)
                  }
                  placeholder="Re-enter your password"
                  autoComplete="new-password"
                />
              </div>
            </div>

            <Button
              className="w-full bg-emerald-600 text-white hover:bg-emerald-700"
              onClick={handleAccept}
              disabled={submitting}
            >
              {submitting ? "Accepting Invitation..." : "Accept Invitation"}
            </Button>

            <p className="text-center text-xs text-slate-500">
              By accepting this invitation, you will receive access to your
              client workspace while the agency retains its authorized access.
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
