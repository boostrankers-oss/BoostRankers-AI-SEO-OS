import { useState } from "react";
import { useStore } from "@/lib/store";
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
import { Badge } from "@/components/ui/badge";
import { KeyRound, CheckCircle2, AlertCircle } from "lucide-react";

export function Settings() {
  const { apiKey, setApiKey } = useStore();
  const [input, setInput] = useState(apiKey);
  const [saved, setSaved] = useState(false);

  const handleSave = () => {
    setApiKey(input);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="font-serif text-3xl font-bold text-slate-900">Settings</h1>
        <p className="mt-1 text-sm text-slate-500">Configure your AI SEO OS</p>
      </div>

      <Card className="border-slate-200 shadow-sm">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 font-serif text-xl">
            <KeyRound className="h-5 w-5 text-emerald-600" />
            API Configuration
          </CardTitle>
          <CardDescription>Connect your AI API key to enable live Claude analysis</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="apiKey">Anthropic API Key</Label>
            <Input
              id="apiKey"
              type="password"
              placeholder="sk-ant-..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
            />
            <p className="text-xs text-slate-500">
              Your API key is stored locally in your browser and never sent to any server other than Anthropic.
            </p>
          </div>
          <Button onClick={handleSave} className="bg-emerald-600 hover:bg-emerald-700">
            {saved ? <CheckCircle2 className="mr-2 h-4 w-4" /> : null}
            {saved ? "Saved!" : "Save API Key"}
          </Button>
          <div className="flex items-center gap-2 pt-2">
            {apiKey ? (
              <Badge className="bg-emerald-50 text-emerald-700">
                <CheckCircle2 className="mr-1 h-3 w-3" /> API Key Connected
              </Badge>
            ) : (
              <Badge variant="outline" className="text-amber-700">
                <AlertCircle className="mr-1 h-3 w-3" /> Simulator Mode (No API Key)
              </Badge>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}