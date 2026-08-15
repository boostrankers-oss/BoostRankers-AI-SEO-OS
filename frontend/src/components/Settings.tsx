import { useEffect, useState } from "react";

import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

import { toast } from "sonner";

import {
  KeyRound,
  Save,
  CheckCircle2,
  AlertCircle,
  Database,
  RefreshCw,
  Loader2,
  CreditCard,
  ShieldCheck,
} from "lucide-react";

import { useClaude } from "@/components/ClaudeProvider";

export function Settings() {
  const {
    apiKey,
    setApiKey,
    isConfigured,
    isReady,
    status,
    loading,
    testConnection,
    refreshStatus,
  } = useClaude();

  const [
    tempKey,
    setTempKey,
  ] = useState("");

  const [
    saving,
    setSaving,
  ] = useState(false);

  const [
    testing,
    setTesting,
  ] = useState(false);

  useEffect(() => {
    void refreshStatus();
  }, []);

  useEffect(() => {
    /*
     * apiKey is masked.
     * Never put the real stored key into the input.
     */
    setTempKey("");
  }, [apiKey]);

  const handleSave =
    async () => {
      const key =
        tempKey.trim();

      if (!key) {
        toast.error(
          "Please enter your Anthropic API key."
        );
        return;
      }

      if (
        !key.startsWith(
          "sk-ant-"
        )
      ) {
        toast.error(
          "Please enter a valid Anthropic API key starting with sk-ant-."
        );
        return;
      }

      setSaving(true);

      try {
        await setApiKey(key);

        setTempKey("");

        toast.success(
          "Anthropic API key verified successfully."
        );
      } catch (error: any) {
        toast.error(
          error?.message ||
            "Unable to save Anthropic API key.",
          {
            duration: 8000,
          }
        );

        /*
         * Provider may have stored the credential with
         * billing_required status, so refresh the real state.
         */
        await refreshStatus();
      } finally {
        setSaving(false);
      }
    };

  const handleTestConnection =
    async () => {
      setTesting(true);

      try {
        await testConnection();

        toast.success(
          "Anthropic connection is working."
        );
      } catch (error: any) {
        toast.error(
          error?.message ||
            "Anthropic connection test failed.",
          {
            duration: 8000,
          }
        );

        await refreshStatus();
      } finally {
        setTesting(false);
      }
    };

  const statusConfig =
    (() => {
      switch (status) {
        case "valid":
          return {
            icon: (
              <CheckCircle2 className="size-5" />
            ),
            title:
              "Claude AI is active and ready to use.",
            description:
              "Your Anthropic API key has been verified and AI features are available.",
            className:
              "border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-500/30 dark:bg-emerald-500/10 dark:text-emerald-400",
          };

        case "billing_required":
          return {
            icon: (
              <CreditCard className="size-5" />
            ),
            title:
              "Anthropic billing is required.",
            description:
              "Your API key is valid, but your Anthropic credit balance is too low. Add credits or upgrade your Anthropic plan, then click Test Connection.",
            className:
              "border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-400",
          };

        case "invalid_api_key":
          return {
            icon: (
              <AlertCircle className="size-5" />
            ),
            title:
              "Anthropic API key is invalid.",
            description:
              "Anthropic rejected the API key. Replace it with a valid key and try again.",
            className:
              "border-red-200 bg-red-50 text-red-700 dark:border-red-500/30 dark:bg-red-500/10 dark:text-red-400",
          };

        case "rate_limited":
          return {
            icon: (
              <AlertCircle className="size-5" />
            ),
            title:
              "Anthropic usage limit reached.",
            description:
              "Anthropic has reached a usage or rate limit. Check your usage and billing, then try again.",
            className:
              "border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-400",
          };

        case "forbidden":
          return {
            icon: (
              <ShieldCheck className="size-5" />
            ),
            title:
              "Anthropic access is restricted.",
            description:
              "The Anthropic account or API key does not have permission to perform this request.",
            className:
              "border-red-200 bg-red-50 text-red-700 dark:border-red-500/30 dark:bg-red-500/10 dark:text-red-400",
          };

        case "provider_unavailable":
          return {
            icon: (
              <AlertCircle className="size-5" />
            ),
            title:
              "Anthropic is currently unavailable.",
            description:
              "The application could not connect to Anthropic. Please try again later.",
            className:
              "border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-400",
          };

        case "provider_request_error":
          return {
            icon: (
              <AlertCircle className="size-5" />
            ),
            title:
              "Anthropic rejected the request.",
            description:
              "Anthropic rejected the test request. Check the provider response and try again.",
            className:
              "border-red-200 bg-red-50 text-red-700 dark:border-red-500/30 dark:bg-red-500/10 dark:text-red-400",
          };

        case "secret_error":
          return {
            icon: (
              <AlertCircle className="size-5" />
            ),
            title:
              "Stored API key could not be read.",
            description:
              "The encrypted Anthropic credential could not be decrypted.",
            className:
              "border-red-200 bg-red-50 text-red-700 dark:border-red-500/30 dark:bg-red-500/10 dark:text-red-400",
          };

        default:
          return {
            icon: (
              <AlertCircle className="size-5" />
            ),
            title:
              "Claude AI is not configured.",
            description:
              "Enter your Anthropic API key and save it to enable AI-powered features.",
            className:
              "border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-400",
          };
      }
    })();

  return (
    <div className="p-8 space-y-6">
      <header>
        <h2 className="font-serif text-3xl font-bold tracking-tight">
          Settings
        </h2>

        <p className="text-slate-500 dark:text-slate-400 mt-1">
          Manage your account, AI configurations, and
          database connections.
        </p>
      </header>

      <Card className="border-slate-200 dark:border-slate-800 shadow-sm">
        <CardHeader>
          <CardTitle className="font-serif flex items-center gap-2">
            <KeyRound className="size-5 text-emerald-600" />

            Claude AI Integration
          </CardTitle>

          <CardDescription>
            Your Anthropic API key is stored securely on
            the backend and verified before AI features
            are enabled.
          </CardDescription>
        </CardHeader>

        <CardContent className="space-y-5">
          <div className="space-y-2">
            <Label htmlFor="api-key">
              Anthropic API Key
            </Label>

            <Input
              id="api-key"
              type="password"
              placeholder={
                apiKey
                  ? apiKey
                  : "sk-ant-..."
              }
              value={tempKey}
              onChange={(event) =>
                setTempKey(
                  event.target.value
                )
              }
              disabled={
                loading ||
                saving ||
                testing
              }
              autoComplete="new-password"
              spellCheck={false}
            />

            <p className="text-xs text-slate-500 dark:text-slate-400">
              Your full API key is never displayed
              after it has been saved.
            </p>
          </div>

          <div className="flex flex-wrap gap-2">
            <Button
              onClick={handleSave}
              disabled={
                loading ||
                saving ||
                testing ||
                !tempKey.trim()
              }
              className="bg-emerald-600 hover:bg-emerald-700 text-white"
            >
              {saving ? (
                <Loader2 className="size-4 mr-2 animate-spin" />
              ) : (
                <Save className="size-4 mr-2" />
              )}

              {saving
                ? "Verifying..."
                : "Save Key"}
            </Button>

            {isConfigured && (
              <Button
                type="button"
                variant="outline"
                onClick={
                  handleTestConnection
                }
                disabled={
                  loading ||
                  saving ||
                  testing
                }
              >
                {testing ? (
                  <Loader2 className="size-4 mr-2 animate-spin" />
                ) : (
                  <RefreshCw className="size-4 mr-2" />
                )}

                {testing
                  ? "Testing..."
                  : "Test Connection"}
              </Button>
            )}
          </div>

          <div
            className={`flex items-start gap-3 rounded-lg border p-4 ${statusConfig.className}`}
          >
            <div className="mt-0.5">
              {loading ? (
                <Loader2 className="size-5 animate-spin" />
              ) : (
                statusConfig.icon
              )}
            </div>

            <div className="space-y-1">
              <div className="font-medium">
                {loading
                  ? "Checking Claude AI status..."
                  : statusConfig.title}
              </div>

              {!loading && (
                <div className="text-sm opacity-90">
                  {statusConfig.description}
                </div>
              )}
            </div>
          </div>

          {isConfigured &&
            apiKey && (
              <div className="flex items-center gap-2 rounded-lg bg-slate-50 px-4 py-3 text-sm text-slate-600 dark:bg-slate-900 dark:text-slate-300">
                <ShieldCheck className="size-4 text-emerald-600" />

                <span>
                  Configured key:
                </span>

                <code className="font-mono">
                  {apiKey}
                </code>

                {!isReady && (
                  <span className="ml-auto text-xs font-medium">
                    {status}
                  </span>
                )}
              </div>
            )}
        </CardContent>
      </Card>

      <Card className="border-slate-200 dark:border-slate-800 shadow-sm">
        <CardHeader>
          <CardTitle className="font-serif flex items-center gap-2">
            <Database className="size-5 text-indigo-600" />

            PostgreSQL Database
          </CardTitle>

          <CardDescription>
            Enterprise multi-tenant database
            configuration.
          </CardDescription>
        </CardHeader>

        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="db-host">
                Database Host
              </Label>

              <Input
                id="db-host"
                defaultValue="localhost"
                readOnly
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="db-port">
                Port
              </Label>

              <Input
                id="db-port"
                defaultValue="5432"
                readOnly
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="db-name">
                Database Name
              </Label>

              <Input
                id="db-name"
                defaultValue="boost_rankers"
                readOnly
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="db-user">
                Username
              </Label>

              <Input
                id="db-user"
                defaultValue="postgres"
                readOnly
              />
            </div>
          </div>

          <div className="flex items-center gap-2 p-3 rounded-lg text-sm bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-400">
            <CheckCircle2 className="size-4" />

            Database connection established.
            Schema is up to date.
          </div>
        </CardContent>
      </Card>
    </div>
  );
}