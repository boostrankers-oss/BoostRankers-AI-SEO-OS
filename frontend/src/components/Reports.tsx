import { useEffect, useMemo, useState } from "react";
import {
  FileText,
  Download,
  Eye,
  FileCode,
  FileSpreadsheet,
  Clock,
  CheckCircle2,
  Loader2,
  AlertCircle,
  Trash2,
  FileDown,
  Search,
  X,
} from "lucide-react";

import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";

import { cn } from "@/lib/utils";
import { toast } from "sonner";
import { api } from "@/lib/api";

interface Report {
  id: string;
  title: string;
  client_name: string;
  date: string;
  score: number;
  format: string;
  content: string;
  summary: string;
  audit_id?: string | null;
}

export function Reports() {
  const [reports, setReports] = useState<Report[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");

  const [selectedReport, setSelectedReport] =
    useState<Report | null>(null);

  const [viewing, setViewing] = useState(false);
  const [downloading, setDownloading] =
    useState<string | null>(null);

  const [deleteId, setDeleteId] =
    useState<string | null>(null);

  const [error, setError] =
    useState<string | null>(null);

  useEffect(() => {
    void fetchReports();
  }, []);

  const fetchReports = async () => {
    setLoading(true);
    setError(null);

    try {
      const data =
        await api.get<Report[]>(
          "/api/reports/"
        );

      setReports(
        Array.isArray(data)
          ? data
          : []
      );
    } catch (err) {
      console.error(
        "Failed to fetch reports:",
        err
      );

      const message =
        "Could not load reports.";

      setError(message);
      toast.error(message);
    } finally {
      setLoading(false);
    }
  };

  const handleView = async (
    report: Report
  ) => {
    try {
      /*
       * The list endpoint already returns full content.
       * We still refresh the individual report to ensure
       * the viewer always displays the latest stored version.
       */
      const detail =
        await api.get<Report>(
          `/api/reports/${report.id}`
        );

      setSelectedReport(detail);
      setViewing(true);
    } catch (err) {
      console.error(
        "Failed to load report details:",
        err
      );

      /*
       * Fallback to the list payload if the detail
       * request fails for any reason.
       */
      setSelectedReport(report);
      setViewing(true);

      toast.error(
        "Could not refresh the report. Showing the saved copy."
      );
    }
  };

  const handleDownload = async (
    report: Report,
    format: "pdf" | "docx"
  ) => {
    const key =
      `${report.id}-${format}`;

    setDownloading(key);

    try {
      const blob =
        await api.download(
          `/api/reports/${report.id}/download?format=${format}`
        );

      const url =
        URL.createObjectURL(blob);

      const anchor =
        document.createElement("a");

      anchor.href = url;

      const safeTitle =
        report.title
          .replace(/[\\/:*?"<>|]+/g, "-")
          .trim() ||
        "seo-audit-report";

      anchor.download =
        `${safeTitle}.${format}`;

      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();

      URL.revokeObjectURL(url);

      toast.success(
        `${format.toUpperCase()} report downloaded successfully.`
      );
    } catch (err) {
      console.error(
        `Failed to download ${format}:`,
        err
      );

      toast.error(
        `Could not download the ${format.toUpperCase()} report.`
      );
    } finally {
      setDownloading(null);
    }
  };

  const handleDelete = async (
    reportId: string
  ) => {
    try {
      await api.delete(
        `/api/reports/${reportId}`
      );

      setReports(
        (current) =>
          current.filter(
            (report) =>
              report.id !== reportId
          )
      );

      if (
        selectedReport?.id === reportId
      ) {
        setSelectedReport(null);
        setViewing(false);
      }

      setDeleteId(null);

      toast.success(
        "Report deleted successfully."
      );
    } catch (err) {
      console.error(
        "Failed to delete report:",
        err
      );

      toast.error(
        "Could not delete report."
      );
    }
  };

  const getScoreColor = (
    score: number
  ) => {
    if (score >= 80) {
      return (
        "text-emerald-700 bg-emerald-50 " +
        "dark:text-emerald-400 dark:bg-emerald-500/10"
      );
    }

    if (score >= 60) {
      return (
        "text-amber-700 bg-amber-50 " +
        "dark:text-amber-400 dark:bg-amber-500/10"
      );
    }

    return (
      "text-rose-700 bg-rose-50 " +
      "dark:text-rose-400 dark:bg-rose-500/10"
    );
  };

  const filteredReports =
    useMemo(() => {
      const query =
        search.trim().toLowerCase();

      if (!query) {
        return reports;
      }

      return reports.filter(
        (report) =>
          report.title
            .toLowerCase()
            .includes(query) ||
          report.client_name
            .toLowerCase()
            .includes(query) ||
          report.summary
            .toLowerCase()
            .includes(query)
      );
    }, [reports, search]);

  if (loading) {
    return (
      <div className="p-8 flex justify-center items-center">
        <div className="flex items-center gap-2 text-slate-500">
          <Loader2 className="size-5 animate-spin" />
          Loading reports...
        </div>
      </div>
    );
  }

  return (
    <div className="p-8 space-y-6">
      {/* =======================================================
          Header
      ======================================================= */}

      <header className="flex items-start justify-between flex-wrap gap-4">
        <div>
          <h2 className="font-serif text-3xl font-bold tracking-tight">
            Reports
          </h2>

          <p className="text-slate-500 dark:text-slate-400 mt-1">
            View, download, and manage completed SEO audit reports.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            onClick={() => void fetchReports()}
          >
            Refresh
          </Button>
        </div>
      </header>

      {/* =======================================================
          Error
      ======================================================= */}

      {error && (
        <Card className="border-rose-200 dark:border-rose-800">
          <CardContent className="p-4">
            <div className="flex items-center gap-2 text-rose-600 dark:text-rose-400">
              <AlertCircle className="size-4" />
              {error}
            </div>
          </CardContent>
        </Card>
      )}

      {/* =======================================================
          Search
      ======================================================= */}

      <div className="relative max-w-md">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-slate-400" />

        <Input
          placeholder="Search reports..."
          value={search}
          onChange={(event) =>
            setSearch(event.target.value)
          }
          className="pl-9"
        />
      </div>

      {/* =======================================================
          Reports
      ======================================================= */}

      {filteredReports.length === 0 ? (
        <Card className="border-slate-200 dark:border-slate-800 shadow-sm">
          <CardContent className="p-12 text-center">
            <FileText className="size-12 text-slate-300 mx-auto mb-4" />

            <h3 className="font-semibold text-lg">
              No reports found
            </h3>

            <p className="text-sm text-slate-500 dark:text-slate-400 mt-2">
              Complete an SEO audit to automatically generate
              a full report.
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
          {filteredReports.map(
            (report) => {
              const pdfKey =
                `${report.id}-pdf`;

              const docxKey =
                `${report.id}-docx`;

              return (
                <Card
                  key={report.id}
                  className="border-slate-200 dark:border-slate-800 shadow-sm hover:shadow-md transition-shadow"
                >
                  <CardHeader>
                    <div className="flex items-start justify-between gap-4">
                      <div className="size-11 rounded-xl bg-gradient-to-br from-emerald-500 to-teal-600 flex items-center justify-center shadow-md">
                        <FileText className="size-5 text-white" />
                      </div>

                      <span
                        className={cn(
                          "px-2.5 py-1 rounded-lg text-xs font-bold",
                          getScoreColor(
                            report.score
                          )
                        )}
                      >
                        {Number(
                          report.score || 0
                        ).toFixed(1)}
                      </span>
                    </div>

                    <CardTitle className="font-serif text-lg mt-3">
                      {report.title}
                    </CardTitle>

                    <CardDescription>
                      {report.client_name}
                    </CardDescription>
                  </CardHeader>

                  <CardContent>
                    <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500 dark:text-slate-400 mb-4">
                      <Clock className="size-3.5" />

                      {report.date
                        ? new Date(
                            report.date
                          ).toLocaleString()
                        : "Unknown date"}

                      <span>•</span>

                      <CheckCircle2 className="size-3.5 text-emerald-500" />

                      Ready
                    </div>

                    {report.summary && (
                      <div className="rounded-lg bg-slate-50 dark:bg-slate-900 p-3 mb-4">
                        <p className="text-xs text-slate-600 dark:text-slate-300 line-clamp-3">
                          {report.summary}
                        </p>
                      </div>
                    )}

                    <div className="flex flex-wrap gap-2">
                      {/* View */}

                      <Button
                        size="sm"
                        onClick={() =>
                          void handleView(
                            report
                          )
                        }
                        className="bg-emerald-600 hover:bg-emerald-700 text-white"
                      >
                        <Eye className="size-3.5" />
                        View
                      </Button>

                      {/* PDF */}

                      <Button
                        size="sm"
                        variant="outline"
                        disabled={
                          downloading ===
                          pdfKey
                        }
                        onClick={() =>
                          void handleDownload(
                            report,
                            "pdf"
                          )
                        }
                      >
                        {downloading ===
                        pdfKey ? (
                          <Loader2 className="size-3.5 animate-spin" />
                        ) : (
                          <FileDown className="size-3.5" />
                        )}

                        PDF
                      </Button>

                      {/* DOCX */}

                      <Button
                        size="sm"
                        variant="outline"
                        disabled={
                          downloading ===
                          docxKey
                        }
                        onClick={() =>
                          void handleDownload(
                            report,
                            "docx"
                          )
                        }
                      >
                        {downloading ===
                        docxKey ? (
                          <Loader2 className="size-3.5 animate-spin" />
                        ) : (
                          <FileSpreadsheet className="size-3.5" />
                        )}

                        DOCX
                      </Button>

                      {/* Delete */}

                      <Button
                        size="sm"
                        variant="outline"
                        className="text-rose-600 border-rose-200 hover:bg-rose-50 dark:text-rose-400 dark:border-rose-800"
                        onClick={() =>
                          setDeleteId(
                            report.id
                          )
                        }
                      >
                        <Trash2 className="size-3.5" />
                        Delete
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              );
            }
          )}
        </div>
      )}

      {/* =======================================================
          Report Viewer
      ======================================================= */}

      <Dialog
        open={viewing}
        onOpenChange={(open) => {
          setViewing(open);

          if (!open) {
            setSelectedReport(
              null
            );
          }
        }}
      >
        <DialogContent className="max-w-6xl h-[90vh] flex flex-col">
          <DialogHeader>
            <div className="flex items-start justify-between gap-4">
              <div>
                <DialogTitle className="font-serif text-2xl">
                  {selectedReport?.title ||
                    "SEO Audit Report"}
                </DialogTitle>

                <DialogDescription className="mt-1">
                  {selectedReport?.client_name ||
                    "SEO Audit"}
                </DialogDescription>
              </div>

              <Button
                variant="ghost"
                size="icon"
                onClick={() => {
                  setViewing(false);
                  setSelectedReport(
                    null
                  );
                }}
              >
                <X className="size-4" />
              </Button>
            </div>
          </DialogHeader>

          {selectedReport && (
            <>
              <div className="flex flex-wrap items-center gap-2 pb-3 border-b border-slate-200 dark:border-slate-800">
                <span
                  className={cn(
                    "px-3 py-1.5 rounded-lg text-sm font-bold",
                    getScoreColor(
                      selectedReport.score
                    )
                  )}
                >
                  SEO Score:{" "}
                  {Number(
                    selectedReport.score ||
                      0
                  ).toFixed(1)}/100
                </span>

                <span className="text-xs text-slate-500">
                  {selectedReport.date
                    ? new Date(
                        selectedReport.date
                      ).toLocaleString()
                    : ""}
                </span>

                <div className="ml-auto flex gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={
                      downloading ===
                      `${selectedReport.id}-pdf`
                    }
                    onClick={() =>
                      void handleDownload(
                        selectedReport,
                        "pdf"
                      )
                    }
                  >
                    <Download className="size-3.5" />
                    PDF
                  </Button>

                  <Button
                    size="sm"
                    variant="outline"
                    disabled={
                      downloading ===
                      `${selectedReport.id}-docx`
                    }
                    onClick={() =>
                      void handleDownload(
                        selectedReport,
                        "docx"
                      )
                    }
                  >
                    <Download className="size-3.5" />
                    DOCX
                  </Button>
                </div>
              </div>

              <div className="flex-1 min-h-0 overflow-auto rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-950">
                <article className="p-6 lg:p-10">
                  <pre className="whitespace-pre-wrap break-words font-sans text-sm leading-7 text-slate-700 dark:text-slate-300">
                    {selectedReport.content ||
                      "This report does not contain any content."}
                  </pre>
                </article>
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>

      {/* =======================================================
          Delete Confirmation
      ======================================================= */}

      <Dialog
        open={deleteId !== null}
        onOpenChange={(open) => {
          if (!open) {
            setDeleteId(null);
          }
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              Delete Report?
            </DialogTitle>

            <DialogDescription>
              This action permanently removes the saved
              report from your company account.
            </DialogDescription>
          </DialogHeader>

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() =>
                setDeleteId(null)
              }
            >
              Cancel
            </Button>

            <Button
              className="bg-rose-600 hover:bg-rose-700 text-white"
              onClick={() => {
                if (deleteId) {
                  void handleDelete(
                    deleteId
                  );
                }
              }}
            >
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* =======================================================
          Information
      ======================================================= */}

      <Card className="border-slate-200 dark:border-slate-800 shadow-sm">
        <CardHeader>
          <CardTitle className="font-serif">
            Report Output
          </CardTitle>

          <CardDescription>
            Completed audits automatically generate the report
            stored in your account.
          </CardDescription>
        </CardHeader>

        <CardContent className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800">
            <FileText className="size-6 text-emerald-600 mb-3" />
            <h4 className="font-semibold text-sm">
              Full Audit
            </h4>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
              Includes the actual findings returned by the SEO agents.
            </p>
          </div>

          <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800">
            <FileDown className="size-6 text-blue-600 mb-3" />
            <h4 className="font-semibold text-sm">
              PDF
            </h4>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
              Professional PDF suitable for sharing with clients.
            </p>
          </div>

          <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800">
            <FileCode className="size-6 text-indigo-600 mb-3" />
            <h4 className="font-semibold text-sm">
              DOCX
            </h4>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
              Editable Microsoft Word report generated from the same stored report.
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}