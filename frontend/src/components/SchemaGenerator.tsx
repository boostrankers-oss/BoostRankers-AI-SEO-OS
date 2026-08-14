import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Code, Copy, Check, Sparkles, Loader2, AlertCircle } from "lucide-react";
import { useClaude } from "@/components/ClaudeProvider";
import { toast } from "sonner";

export function SchemaGenerator() {
  const { isConfigured, generateContent } = useClaude();
  const [type, setType] = useState("Article");
  const [headline, setHeadline] = useState("Boost Rankers AI SEO OS Launches");
  const [author, setAuthor] = useState("Agency Admin");
  const [date, setDate] = useState("2024-10-15");
  const [copied, setCopied] = useState(false);
  const [loading, setLoading] = useState(false);
  const [schema, setSchema] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  const generateSchema = async () => {
    setLoading(true);
    setError(null);
    setSchema(null);

    const prompt = `Generate a valid JSON-LD schema object for Schema.org type: "${type}".
    Headline: "${headline}"
    Author: "${author}"
    Date Published: "${date}"
    
    Return ONLY the raw JSON object, no markdown, no backticks, no explanation.`;

    try {
      const response = await generateContent(prompt);
      const cleanedResponse = response.replace(/```json/g, '').replace(/```/g, '').trim();
      const parsed = JSON.parse(cleanedResponse);
      setSchema(parsed);
      toast.success("Schema generated successfully");
    } catch (err: any) {
      setError(err.message || "Failed to generate schema.");
      toast.error("Schema generation failed");
    } finally {
      setLoading(false);
    }
  };

  const copyCode = () => {
    if (schema) {
      navigator.clipboard.writeText(JSON.stringify(schema, null, 2));
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div className="p-8 space-y-6">
      <header>
        <h2 className="font-serif text-3xl font-bold tracking-tight">Schema Generator</h2>
        <p className="text-slate-500 dark:text-slate-400 mt-1">
          Generate structured data markup for rich snippets and AI search.
        </p>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card className="border-slate-200 dark:border-slate-800 shadow-sm">
          <CardHeader>
            <CardTitle className="font-serif">Configuration</CardTitle>
            <CardDescription>Select schema type and enter details</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label>Schema Type</Label>
              <Select value={type} onValueChange={setType}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="Article">Article</SelectItem>
                  <SelectItem value="Product">Product</SelectItem>
                  <SelectItem value="FAQPage">FAQ Page</SelectItem>
                  <SelectItem value="LocalBusiness">Local Business</SelectItem>
                  <SelectItem value="Organization">Organization</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2"><Label htmlFor="headline">Headline</Label><Input id="headline" value={headline} onChange={(e) => setHeadline(e.target.value)} /></div>
            <div className="space-y-2"><Label htmlFor="author">Author</Label><Input id="author" value={author} onChange={(e) => setAuthor(e.target.value)} /></div>
            <div className="space-y-2"><Label htmlFor="date">Date Published</Label><Input id="date" type="date" value={date} onChange={(e) => setDate(e.target.value)} /></div>
            <Button onClick={generateSchema} disabled={loading || !isConfigured} className="w-full bg-emerald-600 hover:bg-emerald-700 text-white">
              {loading ? <Loader2 className="size-4 animate-spin" /> : <Sparkles className="size-4" />}
              {loading ? "Generating..." : "Generate Schema"}
            </Button>
            {!isConfigured && (
              <div className="flex items-center gap-2 p-3 rounded-lg text-xs text-amber-700 dark:text-amber-400 bg-amber-50 dark:bg-amber-500/10">
                <AlertCircle className="size-4" /> Configure Claude API key in Settings to use AI features.
              </div>
            )}
          </CardContent>
        </Card>

        <Card className="border-slate-200 dark:border-slate-800 shadow-sm">
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="font-serif flex items-center gap-2"><Code className="size-5 text-emerald-600" /> JSON-LD Output</CardTitle>
                <CardDescription>Copy and paste into your HTML head</CardDescription>
              </div>
              <Button variant="outline" size="sm" onClick={copyCode} disabled={!schema}>
                {copied ? <Check className="size-4 text-emerald-500" /> : <Copy className="size-4" />}
                {copied ? "Copied" : "Copy"}
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            <pre className="bg-slate-950 dark:bg-black text-slate-300 p-4 rounded-xl text-xs font-mono overflow-x-auto border border-slate-800 h-[320px]">
              {schema ? JSON.stringify(schema, null, 2) : "// Generated schema will appear here"}
            </pre>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}