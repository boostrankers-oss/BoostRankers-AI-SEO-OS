import {
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  AlertCircle,
  BarChart3,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Clock3,
  FileSearch,
  Globe,
  Lightbulb,
  Link2,
  Loader2,
  MapPin,
  Search,
  ShieldCheck,
  Sparkles,
  Target,
  Trash2,
  TrendingUp,
  Wrench,
} from "lucide-react";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

import {
  Button,
} from "@/components/ui/button";

import {
  Input,
} from "@/components/ui/input";

import {
  Label,
} from "@/components/ui/label";

import {
  Badge,
} from "@/components/ui/badge";

import {
  toast,
} from "sonner";

import {
  api,
} from "@/lib/api";

import {
  useClaude,
} from "@/components/ClaudeProvider";

import {
  cn,
} from "@/lib/utils";


interface ContentGap {
  topic?: string;
  reason?: string;
  priority?: string;
  recommended_asset?: string;
}

interface TechnicalOpportunity {
  issue?: string;
  impact?: string;
  recommendation?: string;
  priority?: string;
}

interface ActionPlan {
  days_0_30?: string[];
  days_31_60?: string[];
  days_61_90?: string[];
}

interface WebsiteMetrics {
  internal_links?: number;
  external_links?: number;
  unique_content_terms?: number;
  missing_title?: number;
  missing_meta_description?: number;
  missing_h1?: number;
  missing_canonical?: number;
  broken_links?: number;
}

interface WebsiteEvidence {
  site?: string;
  pages_crawled?: number;
  pages?: Array<{
    url?: string;
    status_code?: number;
    title?: string;
    meta_description?: string;
    canonical?: string;
    h1?: string[];
    h2?: string[];
    h3?: string[];
    internal_links?: number;
    external_links?: number;
    word_count?: number;
  }>;
  metrics?: WebsiteMetrics;
}

interface Strategy {
  executive_summary?: string;
  competitive_position?: string;
  strengths?: string[];
  weaknesses?: string[];
  content_gaps?: ContentGap[];
  keyword_strategy?: {
    target_terms?: string[];
    long_tail_opportunities?: string[];
    intent_clusters?: string[];
    gap_status?: string;
  };
  technical_strategy?: TechnicalOpportunity[];
  local_seo_strategy?: string[];
  serp_strategy?: string[];
  backlink_strategy?: string[];
  ai_search_strategy?: string[];
  conversion_strategy?: string[];
  quick_wins?: string[];
  action_plan?: ActionPlan;
  kpis?: string[];
}

interface CompetitorDetails {
  version?: number;
  competitor?: {
    domain?: string;
  };
  target?: {
    domain?: string | null;
  };
  verified_metrics?: {
    traffic?: string | number | null;
    ranking_keywords?: string | number | null;
    backlinks?: string | number | null;
    domain_authority?: string | number | null;
    keyword_gap?: string | number | null;
  };
  website_evidence?: WebsiteEvidence;
  strategy?: Strategy;
}

interface Competitor {
  id: string;
  domain: string;
  traffic: string;
  keywords: number;
  backlinks: number;
  da: number;
  gap: number;
  analysis: string;
  details?: CompetitorDetails;
  created_at?: string | null;
}


function unavailableMetric(
  value: number | string | null | undefined,
  fallback = "Not connected",
) {
  if (
    value === null ||
    value === undefined ||
    value === 0 ||
    value === "0"
  ) {
    return fallback;
  }

  return String(
    value
  );
}


export function Competitors() {
  const {
    isConfigured,
    isReady,
    status,
  } = useClaude();

  const [
    competitors,
    setCompetitors,
  ] = useState<Competitor[]>(
    []
  );

  const [
    loading,
    setLoading,
  ] = useState(true);

  const [
    analyzing,
    setAnalyzing,
  ] = useState(false);

  const [
    newDomain,
    setNewDomain,
  ] = useState("");

  const [
    targetDomain,
    setTargetDomain,
  ] = useState("");

  const [
    error,
    setError,
  ] = useState<string | null>(
    null
  );

  const [
    expanded,
    setExpanded,
  ] = useState<string | null>(
    null
  );


  useEffect(() => {
    void fetchCompetitors();
  }, []);


  const fetchCompetitors =
    async () => {
      try {
        const data =
          await api.get<Competitor[]>(
            "/api/competitors"
          );

        setCompetitors(
          Array.isArray(data)
            ? data
            : []
        );
      } catch (err) {
        console.error(
          "Failed to fetch competitors:",
          err
        );

        toast.error(
          "Could not load competitors."
        );
      } finally {
        setLoading(false);
      }
    };


  const handleAnalyze =
    async () => {
      const competitor =
        newDomain.trim();

      if (!competitor) {
        toast.error(
          "Please enter a competitor domain."
        );
        return;
      }

      if (!isConfigured) {
        const message =
          "Claude API key is not configured. Please add it in Settings.";

        setError(message);
        toast.error(message);
        return;
      }

      if (!isReady) {
        const message =
          status === "billing_required"
            ? "Anthropic billing is required. Please add credits or update your billing."
            : status === "invalid_api_key"
              ? "Anthropic API key is invalid. Please update it in Settings."
              : "Claude AI is currently unavailable. Please check Settings.";

        setError(message);
        toast.error(message);
        return;
      }

      setAnalyzing(true);
      setError(null);

      try {
        const params =
          new URLSearchParams();

        params.set(
          "domain",
          competitor
        );

        if (
          targetDomain.trim()
        ) {
          params.set(
            "target_domain",
            targetDomain.trim()
          );
        }

        const data =
          await api.post<Competitor>(
            `/api/competitors?${params.toString()}`,
            {}
          );

        setCompetitors(
          current => [
            data,
            ...current,
          ]
        );

        setNewDomain("");

        toast.success(
          "Competitor intelligence generated successfully."
        );

        setExpanded(
          data.id
        );

      } catch (
        err: any
      ) {
        console.error(
          "Failed to analyze competitor:",
          err
        );

        const message =
          err?.data?.detail ||
          "Failed to analyze competitor. Please try again.";

        setError(
          String(message)
        );

        toast.error(
          String(message)
        );
      } finally {
        setAnalyzing(false);
      }
    };


  const handleDelete =
    async (
      id: string
    ) => {
      try {
        await api.delete(
          `/api/competitors/${id}`
        );

        setCompetitors(
          current =>
            current.filter(
              competitor =>
                competitor.id !== id
            )
        );

        if (
          expanded === id
        ) {
          setExpanded(null);
        }

        toast.success(
          "Competitor deleted."
        );

      } catch (err) {
        console.error(
          "Failed to delete competitor:",
          err
        );

        toast.error(
          "Could not delete competitor."
        );
      }
    };


  const sortedCompetitors =
    useMemo(
      () =>
        [
          ...competitors,
        ].sort(
          (
            a,
            b
          ) =>
            String(
              b.created_at || ""
            ).localeCompare(
              String(
                a.created_at || ""
              )
            )
        ),
      [
        competitors,
      ]
    );


  if (loading) {
    return (
      <div className="p-8 flex justify-center items-center">
        <div className="flex items-center gap-2 text-slate-500">
          <Loader2 className="size-5 animate-spin" />
          Loading competitor intelligence...
        </div>
      </div>
    );
  }


  return (
    <div className="p-8 space-y-6">

      {/* ======================================================
          Header
      ====================================================== */}

      <header>
        <h2 className="font-serif text-3xl font-bold tracking-tight">
          Competitor Intelligence
        </h2>

        <p className="text-slate-500 dark:text-slate-400 mt-1">
          Analyze competitor websites, uncover content gaps,
          identify SEO opportunities, and build an actionable
          90-day competitive strategy.
        </p>
      </header>


      {/* ======================================================
          Provider status
      ====================================================== */}

      {!isConfigured ? (
        <Card className="border-amber-200 dark:border-amber-900/50 bg-amber-50 dark:bg-amber-900/10">
          <CardContent className="p-4 flex items-center gap-3">
            <AlertCircle className="size-5 text-amber-600" />
            <p className="text-sm text-amber-700 dark:text-amber-400">
              Configure your Anthropic API key in Settings
              before running competitor intelligence.
            </p>
          </CardContent>
        </Card>
      ) : !isReady ? (
        <Card className="border-amber-200 dark:border-amber-900/50 bg-amber-50 dark:bg-amber-900/10">
          <CardContent className="p-4 flex items-center gap-3">
            <AlertCircle className="size-5 text-amber-600" />
            <p className="text-sm text-amber-700 dark:text-amber-400">
              {status ===
              "billing_required"
                ? "Anthropic billing is required. Add credits or update your billing."
                : "Claude AI is currently unavailable. Please check Settings."}
            </p>
          </CardContent>
        </Card>
      ) : (
        <Card className="border-emerald-200 dark:border-emerald-900/50 bg-emerald-50 dark:bg-emerald-900/10">
          <CardContent className="p-4 flex items-center gap-3">
            <CheckCircle2 className="size-5 text-emerald-600" />
            <p className="text-sm text-emerald-700 dark:text-emerald-400">
              Anthropic AI is connected and ready for competitor analysis.
            </p>
          </CardContent>
        </Card>
      )}


      {/* ======================================================
          Add competitor
      ====================================================== */}

      <Card className="border-slate-200 dark:border-slate-800 shadow-sm">

        <CardHeader>
          <CardTitle className="font-serif">
            Add Competitor
          </CardTitle>

          <CardDescription>
            Analyze a competitor against your own website when
            you provide the target domain.
          </CardDescription>
        </CardHeader>


        <CardContent className="space-y-4">

          <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">

            <div className="space-y-2">
              <Label htmlFor="target-domain">
                Your Website
              </Label>

              <Input
                id="target-domain"
                placeholder="https://yourwebsite.com"
                value={targetDomain}
                onChange={
                  event =>
                    setTargetDomain(
                      event.target.value
                    )
                }
                disabled={
                  analyzing
                }
              />

              <p className="text-xs text-slate-500">
                Required for a true competitor keyword-gap comparison.
              </p>
            </div>


            <div className="space-y-2">
              <Label htmlFor="competitor-domain">
                Competitor Domain
              </Label>

              <div className="flex gap-2">

                <Input
                  id="competitor-domain"
                  placeholder="https://competitor.com"
                  value={newDomain}
                  onChange={
                    event =>
                      setNewDomain(
                        event.target.value
                      )
                  }
                  disabled={
                    analyzing
                  }
                />

                <Button
                  onClick={
                    handleAnalyze
                  }
                  disabled={
                    analyzing ||
                    !isReady
                  }
                  className="bg-emerald-600 hover:bg-emerald-700 text-white shrink-0"
                >
                  {analyzing ? (
                    <Loader2 className="size-4 animate-spin" />
                  ) : (
                    <Search className="size-4" />
                  )}

                  {
                    analyzing
                      ? "Analyzing..."
                      : "Analyze"
                  }
                </Button>

              </div>
            </div>

          </div>


          {error && (
            <div className="flex items-start gap-2 p-3 rounded-lg text-sm text-rose-700 bg-rose-50 dark:bg-rose-500/10 dark:text-rose-400">
              <AlertCircle className="size-4 shrink-0 mt-0.5" />
              <span>
                {error}
              </span>
            </div>
          )}

        </CardContent>
      </Card>


      {/* ======================================================
          Data availability notice
      ====================================================== */}

      <Card className="border-slate-200 dark:border-slate-800">
        <CardContent className="p-4">

          <div className="flex items-start gap-3">

            <ShieldCheck className="size-5 text-indigo-500 shrink-0" />

            <div>
              <p className="font-medium text-sm">
                Data accuracy
              </p>

              <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                Website and on-page metrics are collected from
                the competitor website. Organic traffic, ranking
                keywords, backlinks and Domain Authority require
                a connected SEO data provider and are therefore
                never fabricated by the AI.
              </p>
            </div>

          </div>

        </CardContent>
      </Card>


      {/* ======================================================
          Competitors
      ====================================================== */}

      {sortedCompetitors.length === 0 ? (
        <Card className="border-slate-200 dark:border-slate-800">
          <CardContent className="p-12 text-center">

            <Target className="size-12 text-slate-300 mx-auto mb-4" />

            <p className="font-medium">
              No competitors analyzed yet.
            </p>

            <p className="text-sm text-slate-500 mt-1">
              Enter a competitor domain above to start.
            </p>

          </CardContent>
        </Card>
      ) : (
        <div className="space-y-5">

          {sortedCompetitors.map(
            competitor => {

              const details =
                competitor.details || {};

              const evidence =
                details.website_evidence;

              const metrics =
                evidence?.metrics;

              const strategy =
                details.strategy || {};

              const isOpen =
                expanded ===
                competitor.id;

              const verified =
                details.verified_metrics ||
                {};

              return (
                <Card
                  key={
                    competitor.id
                  }
                  className="border-slate-200 dark:border-slate-800 shadow-sm"
                >

                  {/* ====================================================
                      Competitor header
                  ==================================================== */}

                  <CardHeader>

                    <div className="flex items-start justify-between gap-4">

                      <div className="flex items-center gap-4">

                        <div className="size-12 rounded-xl bg-gradient-to-br from-rose-400 to-orange-500 flex items-center justify-center text-white font-bold text-lg">
                          {
                            competitor.domain
                              .replace(
                                /^https?:\/\//,
                                ""
                              )
                              .charAt(0)
                              .toUpperCase()
                          }
                        </div>

                        <div>

                          <CardTitle className="font-serif text-xl">
                            {
                              competitor.domain
                            }
                          </CardTitle>

                          <CardDescription className="flex items-center gap-1 mt-1">
                            <Globe className="size-3" />
                            Competitor intelligence
                          </CardDescription>

                        </div>

                      </div>


                      <Button
                        variant="ghost"
                        size="icon"
                        className="text-slate-400 hover:text-rose-500"
                        onClick={() =>
                          void handleDelete(
                            competitor.id
                          )
                        }
                      >
                        <Trash2 className="size-4" />
                      </Button>

                    </div>

                  </CardHeader>


                  <CardContent className="space-y-6">

                    {/* ==================================================
                        Primary metrics
                    ================================================== */}

                    <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">

                      <Metric
                        icon={
                          TrendingUp
                        }
                        label="Organic Traffic"
                        value={
                          unavailableMetric(
                            verified.traffic ??
                            competitor.traffic
                          )
                        }
                        color="text-emerald-600"
                      />

                      <Metric
                        icon={
                          Search
                        }
                        label="Ranking Keywords"
                        value={
                          unavailableMetric(
                            verified.ranking_keywords ??
                            competitor.keywords
                          )
                        }
                        color="text-indigo-600"
                      />

                      <Metric
                        icon={
                          Link2
                        }
                        label="Backlinks"
                        value={
                          unavailableMetric(
                            verified.backlinks ??
                            competitor.backlinks
                          )
                        }
                        color="text-amber-600"
                      />

                      <Metric
                        icon={
                          BarChart3
                        }
                        label="Domain Authority"
                        value={
                          unavailableMetric(
                            verified.domain_authority ??
                            competitor.da
                          )
                        }
                        color="text-cyan-600"
                      />

                      <Metric
                        icon={
                          Target
                        }
                        label="Keyword Gap"
                        value={
                          targetDomain.trim()
                            ? unavailableMetric(
                                verified.keyword_gap ??
                                competitor.gap,
                                "Requires SEO data"
                              )
                            : "Requires target domain"
                        }
                        color="text-rose-600"
                      />

                    </div>


                    {/* ==================================================
                        Website evidence
                    ================================================== */}

                    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">

                      <EvidenceCard
                        icon={
                          FileSearch
                        }
                        label="Pages Crawled"
                        value={
                          String(
                            evidence?.pages_crawled ||
                            0
                          )
                        }
                      />

                      <EvidenceCard
                        icon={
                          Link2
                        }
                        label="Internal Links"
                        value={
                          String(
                            metrics?.internal_links ||
                            0
                          )
                        }
                      />

                      <EvidenceCard
                        icon={
                          Globe
                        }
                        label="External Links"
                        value={
                          String(
                            metrics?.external_links ||
                            0
                          )
                        }
                      />

                      <EvidenceCard
                        icon={
                          Search
                        }
                        label="Content Terms"
                        value={
                          String(
                            metrics?.unique_content_terms ||
                            0
                          )
                        }
                      />

                    </div>


                    {/* ==================================================
                        Summary
                    ================================================== */}

                    {strategy.executive_summary && (
                      <section className="rounded-xl border border-emerald-200 dark:border-emerald-900/50 bg-emerald-50/60 dark:bg-emerald-500/5 p-5">

                        <div className="flex items-center gap-2 mb-2">

                          <Sparkles className="size-4 text-emerald-600" />

                          <h3 className="font-semibold text-emerald-700 dark:text-emerald-400">
                            Executive Competitive Summary
                          </h3>

                        </div>

                        <p className="text-sm leading-7 text-slate-700 dark:text-slate-300">
                          {
                            strategy.executive_summary
                          }
                        </p>

                      </section>
                    )}


                    {/* ==================================================
                        Expand controls
                    ================================================== */}

                    <Button
                      variant="outline"
                      className="w-full"
                      onClick={() =>
                        setExpanded(
                          isOpen
                            ? null
                            : competitor.id
                        )
                      }
                    >
                      {isOpen ? (
                        <>
                          <ChevronUp className="size-4" />
                          Hide Detailed Strategy
                        </>
                      ) : (
                        <>
                          <ChevronDown className="size-4" />
                          View Full Competitive Strategy
                        </>
                      )}
                    </Button>


                    {/* ==================================================
                        Detailed intelligence
                    ================================================== */}

                    {isOpen && (
                      <div className="space-y-6">

                        {/* Competitive position */}

                        {strategy.competitive_position && (
                          <StrategySection
                            icon={
                              Target
                            }
                            title="Competitive Position"
                          >
                            <p className="text-sm leading-7 text-slate-600 dark:text-slate-300">
                              {
                                strategy.competitive_position
                              }
                            </p>
                          </StrategySection>
                        )}


                        {/* Strengths / weaknesses */}

                        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">

                          <ListSection
                            title="Competitive Strengths"
                            items={
                              strategy.strengths
                            }
                            icon={
                              CheckCircle2
                            }
                            tone="green"
                          />

                          <ListSection
                            title="Competitive Weaknesses"
                            items={
                              strategy.weaknesses
                            }
                            icon={
                              AlertCircle
                            }
                            tone="red"
                          />

                        </div>


                        {/* Content gaps */}

                        {strategy.content_gaps &&
                          strategy.content_gaps.length > 0 && (
                            <StrategySection
                              icon={
                                FileSearch
                              }
                              title="Content Gap Opportunities"
                            >

                              <div className="space-y-3">

                                {strategy.content_gaps.map(
                                  (
                                    item,
                                    index
                                  ) => (
                                    <div
                                      key={
                                        `${item.topic}-${index}`
                                      }
                                      className="rounded-lg border border-slate-200 dark:border-slate-800 p-4"
                                    >

                                      <div className="flex items-start justify-between gap-4">

                                        <div>

                                          <p className="font-medium text-sm">
                                            {
                                              item.topic ||
                                              "Content opportunity"
                                            }
                                          </p>

                                          {item.reason && (
                                            <p className="text-xs text-slate-500 mt-1">
                                              {
                                                item.reason
                                              }
                                            </p>
                                          )}

                                        </div>

                                        <Badge
                                          variant="outline"
                                        >
                                          {
                                            item.priority ||
                                            "medium"
                                          }
                                        </Badge>

                                      </div>

                                      {item.recommended_asset && (
                                        <div className="mt-3 text-xs text-slate-600 dark:text-slate-300">
                                          <strong>
                                            Recommended asset:
                                          </strong>{" "}
                                          {
                                            item.recommended_asset
                                          }
                                        </div>
                                      )}

                                    </div>
                                  )
                                )}

                              </div>

                            </StrategySection>
                          )}


                        {/* Keyword strategy */}

                        {strategy.keyword_strategy && (
                          <StrategySection
                            icon={
                              Search
                            }
                            title="Keyword Strategy"
                          >

                            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">

                              <KeywordBox
                                title="Target Terms"
                                items={
                                  strategy
                                    .keyword_strategy
                                    .target_terms
                                }
                              />

                              <KeywordBox
                                title="Long-tail Opportunities"
                                items={
                                  strategy
                                    .keyword_strategy
                                    .long_tail_opportunities
                                }
                              />

                              <KeywordBox
                                title="Intent Clusters"
                                items={
                                  strategy
                                    .keyword_strategy
                                    .intent_clusters
                                }
                              />

                            </div>

                            {strategy.keyword_strategy.gap_status && (
                              <p className="text-xs text-slate-500 mt-4">
                                Gap status:{" "}
                                <strong>
                                  {
                                    strategy
                                      .keyword_strategy
                                      .gap_status
                                  }
                                </strong>
                              </p>
                            )}

                          </StrategySection>
                        )}


                        {/* Technical */}

                        {strategy.technical_strategy &&
                          strategy.technical_strategy.length > 0 && (
                            <StrategySection
                              icon={
                                Wrench
                              }
                              title="Technical SEO & UX Strategy"
                            >

                              <div className="space-y-3">

                                {strategy.technical_strategy.map(
                                  (
                                    item,
                                    index
                                  ) => (
                                    <div
                                      key={
                                        `${item.issue}-${index}`
                                      }
                                      className="rounded-lg border border-slate-200 dark:border-slate-800 p-4"
                                    >

                                      <div className="flex items-center justify-between gap-3">

                                        <p className="font-medium text-sm">
                                          {
                                            item.issue ||
                                            "Technical opportunity"
                                          }
                                        </p>

                                        <Badge
                                          variant="outline"
                                        >
                                          {
                                            item.priority ||
                                            "medium"
                                          }
                                        </Badge>

                                      </div>

                                      {item.impact && (
                                        <p className="text-xs text-slate-500 mt-2">
                                          <strong>
                                            Impact:
                                          </strong>{" "}
                                          {
                                            item.impact
                                          }
                                        </p>
                                      )}

                                      {item.recommendation && (
                                        <p className="text-sm text-slate-600 dark:text-slate-300 mt-2">
                                          {
                                            item.recommendation
                                          }
                                        </p>
                                      )}

                                    </div>
                                  )
                                )}

                              </div>

                            </StrategySection>
                          )}


                        {/* Local SEO */}

                        <ListSection
                          title="Local SEO Strategy"
                          items={
                            strategy.local_seo_strategy
                          }
                          icon={
                            MapPin
                          }
                          tone="green"
                        />


                        {/* SERP */}

                        <ListSection
                          title="SERP Strategy"
                          items={
                            strategy.serp_strategy
                          }
                          icon={
                            BarChart3
                          }
                          tone="blue"
                        />


                        {/* Backlinks */}

                        <ListSection
                          title="Backlink Strategy"
                          items={
                            strategy.backlink_strategy
                          }
                          icon={
                            Link2
                          }
                          tone="amber"
                        />


                        {/* AI search */}

                        <ListSection
                          title="AI Search / GEO Strategy"
                          items={
                            strategy.ai_search_strategy
                          }
                          icon={
                            Sparkles
                          }
                          tone="purple"
                        />


                        {/* Conversion */}

                        <ListSection
                          title="Conversion Strategy"
                          items={
                            strategy.conversion_strategy
                          }
                          icon={
                            TrendingUp
                          }
                          tone="green"
                        />


                        {/* Quick wins */}

                        <ListSection
                          title="Quick Wins"
                          items={
                            strategy.quick_wins
                          }
                          icon={
                            Lightbulb
                          }
                          tone="amber"
                        />


                        {/* 90 day plan */}

                        {strategy.action_plan && (
                          <StrategySection
                            icon={
                              Clock3
                            }
                            title="90-Day Competitive Action Plan"
                          >

                            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">

                              <ActionColumn
                                title="0–30 Days"
                                items={
                                  strategy
                                    .action_plan
                                    .days_0_30
                                }
                              />

                              <ActionColumn
                                title="31–60 Days"
                                items={
                                  strategy
                                    .action_plan
                                    .days_31_60
                                }
                              />

                              <ActionColumn
                                title="61–90 Days"
                                items={
                                  strategy
                                    .action_plan
                                    .days_61_90
                                }
                              />

                            </div>

                          </StrategySection>
                        )}


                        {/* KPI */}

                        <ListSection
                          title="Recommended KPIs"
                          items={
                            strategy.kpis
                          }
                          icon={
                            BarChart3
                          }
                          tone="blue"
                        />


                        {/* Website technical facts */}

                        {evidence && (
                          <StrategySection
                            icon={
                              ShieldCheck
                            }
                            title="Observed Website Evidence"
                          >

                            <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-4">

                              <ObservedValue
                                label="Missing Titles"
                                value={
                                  metrics?.missing_title ||
                                  0
                                }
                              />

                              <ObservedValue
                                label="Missing Meta Descriptions"
                                value={
                                  metrics?.missing_meta_description ||
                                  0
                                }
                              />

                              <ObservedValue
                                label="Missing H1"
                                value={
                                  metrics?.missing_h1 ||
                                  0
                                }
                              />

                              <ObservedValue
                                label="Missing Canonicals"
                                value={
                                  metrics?.missing_canonical ||
                                  0
                                }
                              />

                            </div>

                            {evidence.pages &&
                              evidence.pages.length > 0 && (
                                <div className="overflow-x-auto">
                                  <table className="w-full text-sm">
                                    <thead>
                                      <tr className="border-b border-slate-200 dark:border-slate-800">
                                        <th className="text-left py-3 pr-4">
                                          Page
                                        </th>
                                        <th className="text-left py-3 pr-4">
                                          Status
                                        </th>
                                        <th className="text-left py-3 pr-4">
                                          Title
                                        </th>
                                        <th className="text-left py-3 pr-4">
                                          H1
                                        </th>
                                        <th className="text-left py-3">
                                          Words
                                        </th>
                                      </tr>
                                    </thead>

                                    <tbody>
                                      {evidence.pages.map(
                                        (
                                          page,
                                          index
                                        ) => (
                                          <tr
                                            key={
                                              `${page.url}-${index}`
                                            }
                                            className="border-b border-slate-100 dark:border-slate-900"
                                          >

                                            <td className="py-3 pr-4 max-w-[260px] truncate">
                                              {
                                                page.url
                                              }
                                            </td>

                                            <td className="py-3 pr-4">
                                              {
                                                page.status_code ??
                                                "—"
                                              }
                                            </td>

                                            <td className="py-3 pr-4 max-w-[240px] truncate">
                                              {
                                                page.title ||
                                                "Missing"
                                              }
                                            </td>

                                            <td className="py-3 pr-4 max-w-[180px] truncate">
                                              {
                                                page.h1?.[0] ||
                                                "Missing"
                                              }
                                            </td>

                                            <td className="py-3">
                                              {
                                                page.word_count ??
                                                0
                                              }
                                            </td>

                                          </tr>
                                        )
                                      )}
                                    </tbody>
                                  </table>
                                </div>
                              )}

                          </StrategySection>
                        )}

                      </div>
                    )}

                  </CardContent>

                </Card>
              );
            }
          )}

        </div>
      )}

    </div>
  );
}


/* ============================================================
   Shared UI components
   ============================================================ */

function Metric({
  icon: Icon,
  label,
  value,
  color,
}: {
  icon: any;
  label: string;
  value: string;
  color: string;
}) {
  return (
    <div className="rounded-xl border border-slate-200 dark:border-slate-800 p-4">

      <p className="text-xs text-slate-500 flex items-center gap-1">
        <Icon className="size-3" />
        {label}
      </p>

      <p
        className={cn(
          "font-serif text-lg font-bold mt-2 break-words",
          color
        )}
      >
        {value}
      </p>

    </div>
  );
}


function EvidenceCard({
  icon: Icon,
  label,
  value,
}: {
  icon: any;
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-xl bg-slate-50 dark:bg-slate-900 p-4">

      <div className="flex items-center gap-2 text-slate-500">
        <Icon className="size-4" />
        <span className="text-xs">
          {label}
        </span>
      </div>

      <p className="text-xl font-bold mt-2">
        {value}
      </p>

    </div>
  );
}


function StrategySection({
  icon: Icon,
  title,
  children,
}: {
  icon: any;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-xl border border-slate-200 dark:border-slate-800 p-5">

      <div className="flex items-center gap-2 mb-4">

        <Icon className="size-4 text-emerald-600" />

        <h3 className="font-serif font-semibold">
          {title}
        </h3>

      </div>

      {children}

    </section>
  );
}


function ListSection({
  title,
  items,
  icon: Icon,
  tone,
}: {
  title: string;
  items?: string[];
  icon: any;
  tone:
    | "green"
    | "red"
    | "blue"
    | "amber"
    | "purple";
}) {
  if (
    !items ||
    items.length === 0
  ) {
    return null;
  }

  const toneClasses = {
    green:
      "text-emerald-600",
    red:
      "text-rose-600",
    blue:
      "text-blue-600",
    amber:
      "text-amber-600",
    purple:
      "text-purple-600",
  };

  return (
    <section className="rounded-xl border border-slate-200 dark:border-slate-800 p-5">

      <div className="flex items-center gap-2 mb-4">

        <Icon
          className={cn(
            "size-4",
            toneClasses[tone]
          )}
        />

        <h3 className="font-serif font-semibold">
          {title}
        </h3>

      </div>

      <div className="space-y-2">

        {items.map(
          (
            item,
            index
          ) => (
            <div
              key={
                `${item}-${index}`
              }
              className="flex gap-3 text-sm text-slate-600 dark:text-slate-300"
            >

              <span className="size-5 rounded-full bg-slate-100 dark:bg-slate-900 flex items-center justify-center text-xs shrink-0">
                {index + 1}
              </span>

              <span className="leading-6">
                {item}
              </span>

            </div>
          )
        )}

      </div>

    </section>
  );
}


function KeywordBox({
  title,
  items,
}: {
  title: string;
  items?: string[];
}) {
  return (
    <div className="rounded-lg bg-slate-50 dark:bg-slate-900 p-4">

      <p className="font-medium text-sm mb-3">
        {title}
      </p>

      {!items ||
      items.length === 0 ? (
        <p className="text-xs text-slate-500">
          No items returned.
        </p>
      ) : (
        <div className="flex flex-wrap gap-2">

          {items.map(
            (
              item,
              index
            ) => (
              <Badge
                key={
                  `${item}-${index}`
                }
                variant="outline"
              >
                {item}
              </Badge>
            )
          )}

        </div>
      )}

    </div>
  );
}


function ActionColumn({
  title,
  items,
}: {
  title: string;
  items?: string[];
}) {
  return (
    <div className="rounded-lg border border-slate-200 dark:border-slate-800 p-4">

      <p className="font-semibold text-sm mb-3">
        {title}
      </p>

      {!items ||
      items.length === 0 ? (
        <p className="text-xs text-slate-500">
          No action items returned.
        </p>
      ) : (
        <div className="space-y-2">

          {items.map(
            (
              item,
              index
            ) => (
              <div
                key={
                  `${item}-${index}`
                }
                className="flex gap-2 text-xs text-slate-600 dark:text-slate-300"
              >
                <span className="font-semibold">
                  {index + 1}.
                </span>

                <span className="leading-5">
                  {item}
                </span>
              </div>
            )
          )}

        </div>
      )}

    </div>
  );
}


function ObservedValue({
  label,
  value,
}: {
  label: string;
  value: number;
}) {
  return (
    <div className="rounded-lg bg-slate-50 dark:bg-slate-900 p-3">

      <p className="text-xs text-slate-500">
        {label}
      </p>

      <p className="text-lg font-bold mt-1">
        {value}
      </p>

    </div>
  );
}