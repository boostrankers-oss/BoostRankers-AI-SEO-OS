import { useState } from "react";
import { useStore } from "@/lib/store";
import {
  Card, CardContent, CardHeader, CardTitle, CardDescription,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { KeyRound, CheckCircle2, Loader2 } from "lucide-react";

export function Settings() {
  const { config, saveConfig } = useStore();
  const [apiKey, setApiKey] = useState("");
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setSuccess(false);
    try {
      await saveConfig(apiKey);
      setSuccess(true);
      setApiKey("");
    } catch (err) {
      console.error("Failed to save config", err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="font-serif text-3xl font-bold text-slate-900">Settings</h1>
        <p className="mt-1 text-sm text-slate-500">Configure your AI API keys and system settings.</p>
      </div>

      <Card className="border-slate-200 shadow-sm">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 font-serif text-xl">
            <KeyRound className="h-5 w-5 text-emerald-600" />
            Anthropic API Key
          </CardTitle>
          <CardDescription>
            Enter your Anthropic API key to enable live AI-powered SEO audits.
            {config?.is_configured && <span className="ml-2 font-medium text-emerald-600">(Configured)</span>}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="api_key">API Key</Label>
              <Input id="api_key" type="password" placeholder="sk-ant-..." value={apiKey} onChange={(e) => setApiKey(e.target.value)} required />
            </div>
            
            {success && (
              <Alert>
                <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                <AlertDescription>API Key saved successfully!</AlertDescription>
              </Alert>
            )}

            <Button type="submit" disabled={loading} className="bg-emerald-600 hover:bg-emerald-700">
              {loading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Saving...
                </>
              ) : (
                "Save Key"
              )}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}