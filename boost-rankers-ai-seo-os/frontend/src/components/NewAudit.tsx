import { useState } from "react";
import { useStore } from "@/lib/store";
import {
  Card, CardContent, CardHeader, CardTitle, CardDescription,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { motion } from "framer-motion";
import { Search, Loader2, AlertCircle, CheckCircle2, XCircle } from "lucide-react";

export function NewAudit() {
  const { addAudit, config } = useStore();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  
  const [formData, setFormData] = useState({
    url: "",
    primary_keyword: "",
    location: "",
    competitors: "",
  });

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setSuccess(false);

    if (!config?.is_configured) {
      setError("Please configure your Anthropic API key in Settings before running an audit.");
      setLoading(false);
      return;
    }

    try {
      await addAudit(formData);
      setSuccess(true);
      setFormData({ url: "", primary_keyword: "", location: "", competitors: "" });
    } catch (err: any) {
      setError(err.message || "Failed to run audit. Check console for details.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="font-serif text-3xl font-bold text-slate-900">New SEO Audit</h1>
        <p className="mt-1 text-sm text-slate-500">Run a comprehensive AI-powered SEO analysis on a website.</p>
      </div>

      <Card className="border-slate-200 shadow-sm">
        <CardHeader>
          <CardTitle className="font-serif text-xl">Audit Configuration</CardTitle>
          <CardDescription>Enter the details below to start the AI SEO engine.</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="url">Website URL</Label>
                <Input id="url" name="url" placeholder="https://example.com" value={formData.url} onChange={handleChange} required />
              </div>
              <div className="space-y-2">
                <Label htmlFor="primary_keyword">Primary Keyword</Label>
                <Input id="primary_keyword" name="primary_keyword" placeholder="e.g. SEO services" value={formData.primary_keyword} onChange={handleChange} required />
              </div>
              <div className="space-y-2">
                <Label htmlFor="location">Business Location</Label>
                <Input id="location" name="location" placeholder="e.g. New York, USA" value={formData.location} onChange={handleChange} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="competitors">Competitor URLs (comma separated)</Label>
                <Input id="competitors" name="competitors" placeholder="https://comp1.com, https://comp2.com" value={formData.competitors} onChange={handleChange} />
              </div>
            </div>

            {error && (
              <Alert variant="destructive">
                <AlertCircle className="h-4 w-4" />
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}

            {success && (
              <Alert>
                <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                <AlertDescription>Audit completed successfully! View results on the Dashboard.</AlertDescription>
              </Alert>
            )}

            <Button type="submit" disabled={loading} className="bg-emerald-600 hover:bg-emerald-700">
              {loading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Running AI Agents...
                </>
              ) : (
                <>
                  <Search className="mr-2 h-4 w-4" />
                  Start Audit
                </>
              )}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}