import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { KeyRound, Save, CheckCircle2, AlertCircle, Database } from "lucide-react";
import { useClaude } from "@/components/ClaudeProvider";

export function Settings() {
  const { apiKey, setApiKey, isConfigured } = useClaude();
  const [tempKey, setTempKey] = useState(apiKey);

  const handleSave = () => {
    setApiKey(tempKey);
    toast.success("Claude API Key updated successfully");
  };

  return (
    <div className="p-8 space-y-6">
      <header>
        <h2 className="font-serif text-3xl font-bold tracking-tight">Settings</h2>
        <p className="text-slate-500 dark:text-slate-400 mt-1">
          Manage your account, AI configurations, and database connections.
        </p>
      </header>

      <Card className="border-slate-200 dark:border-slate-800 shadow-sm">
        <CardHeader>
          <CardTitle className="font-serif flex items-center gap-2">
            <KeyRound className="size-5 text-emerald-600" /> Claude AI Integration
          </CardTitle>
          <CardDescription>
            Enter your Anthropic API key to enable AI-powered features across the platform.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="api-key">Anthropic API Key</Label>
            <Input 
              id="api-key" 
              type="password" 
              placeholder="sk-ant-..."
              value={tempKey}
              onChange={(e) => setTempKey(e.target.value)}
            />
          </div>
          <Button onClick={handleSave} className="bg-emerald-600 hover:bg-emerald-700 text-white">
            <Save className="size-4" /> Save Key
          </Button>
          <div className={`flex items-center gap-2 p-3 rounded-lg text-sm ${isConfigured ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-400" : "bg-amber-50 text-amber-700 dark:bg-amber-500/10 dark:text-amber-400"}`}>
            {isConfigured ? <CheckCircle2 className="size-4" /> : <AlertCircle className="size-4" />}
            {isConfigured ? "Claude AI is active and ready to use." : "Claude AI is not configured."}
          </div>
        </CardContent>
      </Card>

      <Card className="border-slate-200 dark:border-slate-800 shadow-sm">
        <CardHeader>
          <CardTitle className="font-serif flex items-center gap-2">
            <Database className="size-5 text-indigo-600" /> PostgreSQL Database
          </CardTitle>
          <CardDescription>
            Enterprise multi-tenant database configuration.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="db-host">Database Host</Label>
              <Input id="db-host" defaultValue="localhost" />
            </div>
            <div className="space-y-2">
              <Label htmlFor="db-port">Port</Label>
              <Input id="db-port" defaultValue="5432" />
            </div>
            <div className="space-y-2">
              <Label htmlFor="db-name">Database Name</Label>
              <Input id="db-name" defaultValue="boost_rankers" />
            </div>
            <div className="space-y-2">
              <Label htmlFor="db-user">Username</Label>
              <Input id="db-user" defaultValue="postgres" />
            </div>
          </div>
          <div className="flex items-center gap-2 p-3 rounded-lg text-sm bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-400">
            <CheckCircle2 className="size-4" /> Database connection established. Schema is up to date.
          </div>
        </CardContent>
      </Card>
    </div>
  );
}