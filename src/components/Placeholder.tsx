import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Construction } from "lucide-react";

export function Placeholder({ title, description }: { title: string; description: string }) {
  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="font-serif text-3xl font-bold text-slate-900">{title}</h1>
        <p className="mt-1 text-sm text-slate-500">{description}</p>
      </div>
      <Card className="border-slate-200 shadow-sm">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 font-serif text-xl">
            <Construction className="h-5 w-5 text-amber-500" />
            Module Under Construction
          </CardTitle>
          <CardDescription>
            This module is part of the Boost Rankers AI SEO OS roadmap.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-slate-600">
            The backend logic for this module requires the Python FastAPI server and a connected Anthropic API key to run live AI analysis. The frontend interface is ready to be wired up to the backend endpoints.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}