import { useMemo, useState, useCallback, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import AppLayout from "@/components/AppLayout";
import GlassCard from "@/components/GlassCard";
import { Button } from "@/components/ui/button";
import {
  Download,
  Eye,
  Printer,
  CheckCircle2,
  Clock,
  Loader2,
  Search,
  FileText,
  Sparkles,
  X,
  Users,
  GraduationCap,
  RefreshCw,
} from "lucide-react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "@/lib/api";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { toast } from "sonner";

/* ────────────────────────── types ────────────────────────── */
type ReportsOverviewResponse = {
  terms: string[];
  items: Array<{
    id: string;
    name: string;
    roll_number?: string;
    admission_number?: string;
    class: string;
    generated: string | null;
    status: "ready" | "pending" | "not_started";
    grade: string | null;
    report_id: string | null;
    term_name: string | null;
    pdf_url: string | null;
  }>;
  ready_count: number;
  pending_count: number;
};

/* ────────────────────────── helpers ────────────────────────── */
const gradeColors: Record<string, string> = {
  "A+": "text-emerald-400 bg-emerald-500/15 border-emerald-500/20",
  A: "text-emerald-400 bg-emerald-500/15 border-emerald-500/20",
  B: "text-sky-400 bg-sky-500/15 border-sky-500/20",
  C: "text-amber-400 bg-amber-500/15 border-amber-500/20",
  "D/F": "text-red-400 bg-red-500/15 border-red-500/20",
};

const gradeBadge: Record<string, string> = {
  "A+": "🏆", A: "⭐", B: "📘", C: "📒", "D/F": "📕",
};

const getApiErrorDetail = (error: any) =>
  error?.response?.data?.detail ||
  error?.response?.data?.message ||
  error?.response?.data?.error?.message ||
  error?.message ||
  "Please try again.";

/* ────────────────────────── page ────────────────────────── */
const Reports = () => {
  const queryClient = useQueryClient();
  const apiBaseUrl = String(api.defaults.baseURL || "");

  /* ─── state ─── */
  const [selectedTerm, setSelectedTerm] = useState<string>("all");
  const [searchTerm, setSearchTerm] = useState("");
  const [previewStudentId, setPreviewStudentId] = useState<string | null>(null);
  const [previewTermName, setPreviewTermName] = useState<string>("Current Term");
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewHtml, setPreviewHtml] = useState<string | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [generateStudentId, setGenerateStudentId] = useState<string | null>(null);
  const [generateTermInput, setGenerateTermInput] = useState("Term 1 Final");
  const [generateDialogOpen, setGenerateDialogOpen] = useState(false);
  const [generateAllDialogOpen, setGenerateAllDialogOpen] = useState(false);
  const [generatingId, setGeneratingId] = useState<string | null>(null);
  const [isGeneratingAll, setIsGeneratingAll] = useState(false);

  /* ─── queries ─── */
  const { data, isLoading, refetch } = useQuery<ReportsOverviewResponse>({
    queryKey: ["reports-overview"],
    queryFn: async () => {
      const response = await api.get("/analytics/reports/overview");
      return response.data;
    },
    refetchInterval: (query) => {
      return query.state.data?.pending_count ? 3000 : false;
    },
  });

  /* ─── mutations ─── */
  const generateMutation = useMutation({
    mutationFn: async ({ studentId, termName }: { studentId: string; termName: string }) => {
      try {
        const response = await api.post("/analytics/reports/generate", {
          student_id: studentId,
          term_name: termName,
        });
        return response.data;
      } catch (error: any) {
        const status = error?.response?.status;
        if (status !== 404 && status !== 405 && status !== 422) throw error;
        const fallback = await api.post("/analytics/reports/generate", null, {
          params: { student_id: studentId, term_name: termName },
        });
        return fallback.data;
      }
    },
    onSuccess: () => {
      toast.success("Report card generation started", {
        description: "The PDF is being generated in the background. It will be ready shortly.",
        icon: <CheckCircle2 className="h-4 w-4" />,
      });
      queryClient.invalidateQueries({ queryKey: ["reports-overview"] });
      setGeneratingId(null);
      setGenerateDialogOpen(false);
    },
    onError: (error: any) => {
      toast.error("Failed to generate report", {
        description: getApiErrorDetail(error),
      });
      setGeneratingId(null);
    },
  });

  const generateAllMutation = useMutation({
    mutationFn: async ({ termName }: { termName: string }) => {
      const studentIds = Array.from(new Set((data?.items || []).map((item) => item.id)));
      if (studentIds.length === 0) {
        return { generated: 0, failed: 0, total: 0 };
      }

      let generated = 0;
      let failed = 0;
      const batchSize = 8;

      for (let i = 0; i < studentIds.length; i += batchSize) {
        const batch = studentIds.slice(i, i + batchSize);
        const results = await Promise.allSettled(
          batch.map(async (studentId) => {
            try {
              await api.post("/analytics/reports/generate", {
                student_id: studentId,
                term_name: termName,
              });
              return;
            } catch (error: any) {
              const status = error?.response?.status;
              if (status === 404 || status === 405 || status === 422) {
                await api.post("/analytics/reports/generate", null, {
                  params: { student_id: studentId, term_name: termName },
                });
                return;
              }
              throw error;
            }
          })
        );

        for (const result of results) {
          if (result.status === "fulfilled") generated += 1;
          else failed += 1;
        }
      }

      return { generated, failed, total: studentIds.length };
    },
    onSuccess: (data) => {
      toast.success(`Batch generation started!`, {
        description:
          data.failed > 0
            ? `Queued ${data.generated}/${data.total} reports. ${data.failed} failed.`
            : `Queued ${data.generated} reports in the background.`,
        icon: <CheckCircle2 className="h-4 w-4" />,
      });
      queryClient.invalidateQueries({ queryKey: ["reports-overview"] });
      setIsGeneratingAll(false);
      setGenerateAllDialogOpen(false);
    },
    onError: (error: any) => {
      toast.error("Failed to generate batch reports", {
        description: getApiErrorDetail(error),
      });
      setIsGeneratingAll(false);
    },
  });

  const stopGenerationMutation = useMutation({
    mutationFn: async ({ termName }: { termName?: string }) => {
      try {
        const response = await api.post("/analytics/reports/stop-generation", {
          term_name: termName ?? null,
        });
        return response.data as { cancelled: number };
      } catch (error: any) {
        const status = error?.response?.status;
        if (status !== 404 && status !== 405 && status !== 422) throw error;
        const fallback = await api.post("/analytics/reports/stop-generation", null, {
          params: termName ? { term_name: termName } : undefined,
        });
        return fallback.data as { cancelled: number };
      }
    },
    onSuccess: (data) => {
      toast.success("Stopped pending generation", {
        description: `Cancelled ${data.cancelled} pending report jobs.`,
      });
      queryClient.invalidateQueries({ queryKey: ["reports-overview"] });
    },
    onError: (error: any) => {
      toast.error("Failed to stop report generation", {
        description: getApiErrorDetail(error),
      });
    },
  });

  /* ─── derived data ─── */
  const terms = useMemo(() => ["all", ...(data?.terms || [])], [data]);

  const termScopedCards = useMemo(() => {
    const items = data?.items || [];
    return selectedTerm === "all"
      ? items
      : items.filter((item) => item.term_name === selectedTerm);
  }, [data, selectedTerm]);

  const termReadyCount = useMemo(
    () => termScopedCards.filter((item) => item.status === "ready").length,
    [termScopedCards]
  );
  const termPendingCount = useMemo(
    () => termScopedCards.filter((item) => item.status === "pending").length,
    [termScopedCards]
  );

  const reportCards = useMemo(() => {
    let filtered = termScopedCards;

    if (searchTerm.trim()) {
      const lower = searchTerm.toLowerCase();
      filtered = filtered.filter(
        (item) =>
          item.name.toLowerCase().includes(lower) ||
          (item.roll_number && item.roll_number.toLowerCase().includes(lower)) ||
          (item.admission_number && item.admission_number.toLowerCase().includes(lower))
      );
    }

    return filtered;
  }, [termScopedCards, searchTerm]);

  /* ─── handlers ─── */
  /* Fetch report HTML when preview dialog opens */
  useEffect(() => {
    if (!previewOpen || !previewStudentId) {
      setPreviewHtml(null);
      return;
    }
    let cancelled = false;
    setPreviewLoading(true);
    setPreviewHtml(null);
    api
      .get("/analytics/reports/preview/html", {
        params: { student_id: previewStudentId, term_name: previewTermName },
        responseType: "text",
        headers: { Accept: "text/html" },
      })
      .then((res) => {
        if (!cancelled) setPreviewHtml(res.data);
      })
      .catch(() => {
        if (!cancelled) setPreviewHtml("<div style='padding:40px;text-align:center;color:#888;'>Unable to load report preview. The student may not have any marks recorded yet.</div>");
      })
      .finally(() => {
        if (!cancelled) setPreviewLoading(false);
      });
    return () => { cancelled = true; };
  }, [previewOpen, previewStudentId, previewTermName]);

  const openPreview = useCallback((studentId: string, termName: string | null) => {
    setPreviewStudentId(studentId);
    setPreviewTermName(termName || "Current Term");
    setPreviewOpen(true);
  }, []);

  const openGenerate = useCallback((studentId: string) => {
    setGenerateStudentId(studentId);
    setGenerateDialogOpen(true);
  }, []);

  const handleGenerate = useCallback(() => {
    if (!generateStudentId || !generateTermInput.trim()) return;
    setGeneratingId(generateStudentId);
    generateMutation.mutate({
      studentId: generateStudentId,
      termName: generateTermInput.trim(),
    });
  }, [generateStudentId, generateTermInput, generateMutation]);

  const handleGenerateAll = useCallback(() => {
    if (!generateTermInput.trim()) return;
    setIsGeneratingAll(true);
    generateAllMutation.mutate({
      termName: generateTermInput.trim(),
    });
  }, [generateTermInput, generateAllMutation]);

  return (
    <AppLayout>
      <div className="space-y-6">
        {/* ─── Page Header ─── */}
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4"
        >
          <div>
            <h1 className="text-2xl font-display font-bold text-foreground flex items-center gap-2">
              <span className="p-2 rounded-xl bg-gradient-to-br from-primary/20 to-accent/10">
                <FileText className="h-6 w-6 text-primary" />
              </span>
              Terminal Reports
            </h1>
            <p className="text-sm text-muted-foreground mt-1">
              Generate, preview, and manage student report cards with AI insights
            </p>
          </div>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              className="gap-1.5 border-white/10 hover:bg-white/[0.06]"
              onClick={() => refetch()}
            >
              <RefreshCw className="h-4 w-4" /> Refresh
            </Button>
            <Button 
              variant="gradient" 
              size="sm" 
              className="gap-1.5"
              onClick={() => setGenerateAllDialogOpen(true)}
              disabled={isGeneratingAll}
            >
              {isGeneratingAll ? <Loader2 className="h-4 w-4 animate-spin" /> : <Printer className="h-4 w-4" />} 
              Generate All Reports
            </Button>
          </div>
        </motion.div>

        {isLoading ? (
          <div className="flex h-[50vh] items-center justify-center flex-col gap-3">
            <div className="relative">
              <div className="absolute inset-0 rounded-full bg-primary/20 animate-ping" />
              <Loader2 className="h-10 w-10 animate-spin text-primary relative z-10" />
            </div>
            <p className="text-sm text-muted-foreground animate-pulse">Loading reports…</p>
          </div>
        ) : (
          <>


            {/* ─── Stats Row ─── */}
            <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
              <GlassCard delay={0.05} className="p-4 sm:col-span-1">
                <p className="text-xs text-muted-foreground uppercase tracking-wider font-semibold mb-3 flex items-center gap-1.5">
                  <GraduationCap className="h-3.5 w-3.5" /> Select Term
                </p>
                <div className="space-y-1.5 max-h-[180px] overflow-y-auto scrollbar-hidden">
                  {terms.map((term) => (
                    <button
                      key={term}
                      onClick={() => setSelectedTerm(term)}
                      className={`w-full text-left px-4 py-2.5 rounded-xl text-sm font-medium transition-all duration-200 ${
                        selectedTerm === term
                          ? "bg-primary/20 text-foreground border border-primary/30 shadow-sm shadow-primary/10"
                          : "bg-white/[0.03] text-muted-foreground hover:bg-white/[0.06] border border-transparent"
                      }`}
                    >
                      {term === "all" ? "📋 All Terms" : `📅 ${term}`}
                    </button>
                  ))}
                </div>
              </GlassCard>

              <GlassCard delay={0.1} className="p-5 flex items-center gap-4">
                <div className="p-3 rounded-xl bg-gradient-to-br from-emerald-500/30 to-teal-500/20 shadow-inner">
                  <CheckCircle2 className="h-6 w-6 text-emerald-400" />
                </div>
                <div>
                  <p className="text-3xl font-bold font-display text-foreground">
                    {termReadyCount}
                  </p>
                  <p className="text-sm text-muted-foreground">Reports Ready</p>
                </div>
              </GlassCard>

              <GlassCard delay={0.15} className="p-5 flex items-center gap-4">
                <div className="p-3 rounded-xl bg-gradient-to-br from-amber-500/30 to-orange-500/20 shadow-inner">
                  <Clock className="h-6 w-6 text-amber-400" />
                </div>
                <div>
                  <p className="text-3xl font-bold font-display text-foreground">
                    {termPendingCount}
                  </p>
                  <p className="text-sm text-muted-foreground">Pending</p>
                </div>
              </GlassCard>

              <GlassCard delay={0.2} className="p-5 flex items-center gap-4">
                <div className="p-3 rounded-xl bg-gradient-to-br from-violet-500/30 to-purple-500/20 shadow-inner">
                  <Users className="h-6 w-6 text-violet-400" />
                </div>
                <div>
                  <p className="text-3xl font-bold font-display text-foreground">
                    {termScopedCards.length}
                  </p>
                  <p className="text-sm text-muted-foreground">Total Students</p>
                </div>
              </GlassCard>
            </div>

            {/* ─── Report Cards Table ─── */}
            <GlassCard delay={0.25} hover={false}>
              <div className="space-y-2">
                {/* Search bar */}
                <div className="px-5 pt-4 flex flex-col sm:flex-row gap-3 items-start sm:items-center justify-between">
                  <div className="relative w-full sm:w-96">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                    <Input
                      id="report-search"
                      placeholder="Search by name, roll, or admission number..."
                      value={searchTerm}
                      onChange={(e) => setSearchTerm(e.target.value)}
                      className="pl-9 bg-white/[0.03] border-white/[0.05]"
                    />
                  </div>
                  <div className="text-sm text-muted-foreground flex items-center gap-1.5">
                    <FileText className="h-3.5 w-3.5" />
                    {reportCards.length} student{reportCards.length !== 1 ? "s" : ""}
                  </div>
                </div>

                {/* Table header */}
                <div className="hidden sm:grid grid-cols-[1fr_100px_90px_100px_140px_160px] gap-4 px-5 py-2 text-xs font-semibold text-muted-foreground uppercase tracking-wider border-b border-white/[0.05]">
                  <span>Student</span>
                  <span>Class</span>
                  <span>Grade</span>
                  <span>Status</span>
                  <span>Generated</span>
                  <span className="text-right">Actions</span>
                </div>

                {/* Table rows */}
                <div className="max-h-[520px] overflow-y-auto scrollbar-hidden">
                  <AnimatePresence mode="popLayout">
                    {reportCards.length === 0 ? (
                      <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        className="flex flex-col items-center justify-center py-16 text-muted-foreground"
                      >
                        <FileText className="h-12 w-12 opacity-30 mb-3" />
                        <p className="text-sm font-medium">No report cards found</p>
                        <p className="text-xs mt-1">Try adjusting your search or term filter</p>
                      </motion.div>
                    ) : (
                      reportCards.map((report, i) => (
                        <motion.div
                          key={report.id}
                          initial={{ opacity: 0, x: -10 }}
                          animate={{ opacity: 1, x: 0 }}
                          exit={{ opacity: 0, x: 10 }}
                          transition={{ delay: 0.02 * Math.min(i, 15) }}
                          className="grid grid-cols-1 sm:grid-cols-[1fr_100px_90px_100px_140px_160px] gap-2 sm:gap-4 items-center px-5 py-3 rounded-xl hover:bg-white/[0.03] transition-colors group"
                        >
                          {/* Student */}
                          <div className="flex items-center gap-3">
                            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-primary/30 to-accent/20 flex items-center justify-center text-xs font-bold text-foreground flex-shrink-0 border border-white/10">
                              {report.name
                                .split(" ")
                                .map((n) => n[0])
                                .join("")
                                .slice(0, 2)}
                            </div>
                            <div className="min-w-0">
                              <span className="text-sm font-medium text-foreground block truncate">
                                {report.name}
                              </span>
                              {report.admission_number && (
                                <span className="text-[10px] text-muted-foreground">
                                  #{report.admission_number}
                                </span>
                              )}
                            </div>
                          </div>

                          {/* Class */}
                          <span className="text-sm text-muted-foreground">{report.class}</span>

                          {/* Grade */}
                          {report.grade ? (
                            <span
                              className={`text-xs font-bold px-3 py-1 rounded-full w-fit flex items-center gap-1 border ${
                                gradeColors[report.grade] || "text-muted-foreground bg-white/[0.05] border-white/10"
                              }`}
                            >
                              {gradeBadge[report.grade] || "📄"} {report.grade}
                            </span>
                          ) : (
                            <span className="text-xs text-muted-foreground">—</span>
                          )}

                          {/* Status */}
                          {report.status === "ready" ? (
                            <span className="text-xs font-medium text-emerald-400 flex items-center gap-1">
                              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                              Ready
                            </span>
                          ) : report.status === "pending" ? (
                            <span className="text-xs font-medium text-amber-400 flex items-center gap-1">
                              <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse" />
                              Generating
                            </span>
                          ) : (
                            <span className="text-xs font-medium text-muted-foreground flex items-center gap-1">
                              <span className="w-1.5 h-1.5 rounded-full bg-white/20" />
                              Not Started
                            </span>
                          )}

                          {/* Generated date */}
                          <span className="text-xs text-muted-foreground">
                            {report.generated
                              ? new Date(report.generated).toLocaleDateString("en-IN", {
                                  day: "2-digit",
                                  month: "short",
                                  year: "numeric",
                                })
                              : "Not generated"}
                          </span>

                          {/* Actions */}
                          <div className="flex items-center gap-1 sm:justify-end">
                            {/* Always show Preview */}
                            <button
                              onClick={() => openPreview(report.id, report.term_name)}
                              className="p-2 rounded-lg hover:bg-white/[0.08] transition-colors text-muted-foreground hover:text-foreground group/btn"
                              title="Preview Report"
                            >
                              <Eye className="h-4 w-4" />
                            </button>

                            {report.status === "ready" && report.report_id && report.pdf_url ? (
                              <a
                                href={`${apiBaseUrl}/analytics/reports/${report.report_id}/download`}
                                target="_blank"
                                rel="noreferrer"
                                className="p-2 rounded-lg hover:bg-white/[0.08] transition-colors text-muted-foreground hover:text-foreground"
                                title="Download PDF"
                              >
                                <Download className="h-4 w-4" />
                              </a>
                            ) : null}

                            {/* Generate button */}
                            <button
                              onClick={() => openGenerate(report.id)}
                              disabled={generatingId === report.id}
                              className="p-2 rounded-lg hover:bg-primary/10 transition-colors text-primary/60 hover:text-primary disabled:opacity-40"
                              title="Generate Report Card"
                            >
                              {generatingId === report.id ? (
                                <Loader2 className="h-4 w-4 animate-spin" />
                              ) : (
                                <Sparkles className="h-4 w-4" />
                              )}
                            </button>
                          </div>
                        </motion.div>
                      ))
                    )}
                  </AnimatePresence>
                </div>
              </div>
            </GlassCard>
          </>
        )}

        {/* ─── Report Card Preview Dialog ─── */}
        <Dialog open={previewOpen} onOpenChange={setPreviewOpen}>
          <DialogContent className="max-w-[900px] w-[95vw] h-[90vh] p-0 overflow-hidden bg-[#0f1629] border-white/10">
            <div className="flex flex-col h-full">
              {/* Dialog header */}
              <div className="flex items-center justify-between px-5 py-3 border-b border-white/[0.08] bg-white/[0.02]">
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-lg bg-gradient-to-br from-primary/20 to-accent/10">
                    <FileText className="h-4 w-4 text-primary" />
                  </div>
                  <div>
                    <DialogTitle className="text-sm font-semibold text-foreground">
                      Report Card Preview
                    </DialogTitle>
                    <p className="text-[11px] text-muted-foreground">{previewTermName}</p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    className="gap-1.5 text-xs border-white/10 hover:bg-white/[0.06]"
                    onClick={() => {
                      if (previewStudentId) {
                        openGenerate(previewStudentId);
                      }
                    }}
                  >
                    <Sparkles className="h-3.5 w-3.5" /> Generate PDF
                  </Button>
                  <button
                    onClick={() => setPreviewOpen(false)}
                    className="p-1.5 rounded-lg hover:bg-white/[0.08] text-muted-foreground hover:text-foreground transition-colors"
                  >
                    <X className="h-4 w-4" />
                  </button>
                </div>
              </div>

              {/* Report HTML preview */}
              <div className="flex-1 bg-gray-100 overflow-hidden">
                {previewLoading ? (
                  <div className="flex flex-col items-center justify-center h-full gap-3">
                    <Loader2 className="h-8 w-8 animate-spin text-primary" />
                    <p className="text-sm text-gray-500">Loading report card…</p>
                  </div>
                ) : previewHtml ? (
                  <iframe
                    srcDoc={previewHtml}
                    className="w-full h-full border-0"
                    title="Report Card Preview"
                    sandbox="allow-same-origin"
                  />
                ) : (
                  <div className="flex items-center justify-center h-full text-gray-400">
                    <p>Select a student to preview their report card</p>
                  </div>
                )}
              </div>
            </div>
          </DialogContent>
        </Dialog>

        {/* ─── Generate Report Dialog ─── */}
        <Dialog open={generateDialogOpen} onOpenChange={setGenerateDialogOpen}>
          <DialogContent className="max-w-md bg-[#0f1629] border-white/10">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2 text-foreground">
                <div className="p-2 rounded-lg bg-gradient-to-br from-primary/20 to-accent/10">
                  <Sparkles className="h-4 w-4 text-primary" />
                </div>
                Generate Report Card
              </DialogTitle>
            </DialogHeader>
            <div className="space-y-4 pt-2">
              <div>
                <label className="text-xs text-muted-foreground uppercase tracking-wider font-semibold mb-2 block">
                  Term / Exam Name
                </label>
                <Select value={generateTermInput} onValueChange={setGenerateTermInput}>
                  <SelectTrigger className="bg-white/[0.05] border-white/[0.08]">
                    <SelectValue placeholder="Select term" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="Term 1 Final">Term 1 Final</SelectItem>
                    <SelectItem value="Term 2 Final">Term 2 Final</SelectItem>
                    <SelectItem value="Mid-Term">Mid-Term</SelectItem>
                    <SelectItem value="Annual Exam">Annual Exam</SelectItem>
                    <SelectItem value="Unit Test 1">Unit Test 1</SelectItem>
                    <SelectItem value="Unit Test 2">Unit Test 2</SelectItem>
                    {data?.terms
                      ?.filter(
                        (t) =>
                          ![
                            "Term 1 Final",
                            "Term 2 Final",
                            "Mid-Term",
                            "Annual Exam",
                            "Unit Test 1",
                            "Unit Test 2",
                          ].includes(t)
                      )
                      .map((t) => (
                        <SelectItem key={t} value={t}>
                          {t}
                        </SelectItem>
                      ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="bg-white/[0.03] rounded-xl p-3 border border-white/[0.06]">
                <p className="text-xs text-muted-foreground leading-relaxed">
                  📋 This will generate a beautifully designed PDF report card with subject-wise
                  performance, attendance summary, and AI-powered insights for the student.
                </p>
              </div>

              <div className="flex gap-2 justify-end">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setGenerateDialogOpen(false)}
                  className="border-white/10"
                >
                  Cancel
                </Button>
                <Button
                  variant="gradient"
                  size="sm"
                  onClick={handleGenerate}
                  disabled={generateMutation.isPending}
                  className="gap-1.5"
                >
                  {generateMutation.isPending ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" /> Generating…
                    </>
                  ) : (
                    <>
                      <Sparkles className="h-4 w-4" /> Generate Report
                    </>
                  )}
                </Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>

        {/* ─── Generate All Reports Dialog ─── */}
        <Dialog open={generateAllDialogOpen} onOpenChange={setGenerateAllDialogOpen}>
          <DialogContent className="max-w-md bg-[#0f1629] border-white/10">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2 text-foreground">
                <div className="p-2 rounded-lg bg-gradient-to-br from-primary/20 to-accent/10">
                  <Printer className="h-4 w-4 text-primary" />
                </div>
                Generate All Reports
              </DialogTitle>
            </DialogHeader>
            <div className="space-y-4 pt-2">
              <div>
                <label className="text-xs text-muted-foreground uppercase tracking-wider font-semibold mb-2 block">
                  Term / Exam Name
                </label>
                <Select value={generateTermInput} onValueChange={setGenerateTermInput}>
                  <SelectTrigger className="bg-white/[0.05] border-white/[0.08]">
                    <SelectValue placeholder="Select term" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="Term 1 Final">Term 1 Final</SelectItem>
                    <SelectItem value="Term 2 Final">Term 2 Final</SelectItem>
                    <SelectItem value="Mid-Term">Mid-Term</SelectItem>
                    <SelectItem value="Annual Exam">Annual Exam</SelectItem>
                    <SelectItem value="Unit Test 1">Unit Test 1</SelectItem>
                    <SelectItem value="Unit Test 2">Unit Test 2</SelectItem>
                    {data?.terms
                      ?.filter(
                        (t) =>
                          ![
                            "Term 1 Final",
                            "Term 2 Final",
                            "Mid-Term",
                            "Annual Exam",
                            "Unit Test 1",
                            "Unit Test 2",
                          ].includes(t)
                      )
                      .map((t) => (
                        <SelectItem key={t} value={t}>
                          {t}
                        </SelectItem>
                      ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="bg-white/[0.03] rounded-xl p-3 border border-white/[0.06]">
                <p className="text-xs text-muted-foreground leading-relaxed">
                  🚀 This will queue all students for background report generation. 
                  The PDFs will be generated autonomously without freezing the application.
                </p>
              </div>

              <div className="flex gap-2 justify-end">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setGenerateAllDialogOpen(false)}
                  className="border-white/10"
                >
                  Cancel
                </Button>
                <Button
                  variant="gradient"
                  size="sm"
                  onClick={handleGenerateAll}
                  disabled={generateAllMutation.isPending}
                  className="gap-1.5"
                >
                  {generateAllMutation.isPending ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" /> Queuing...
                    </>
                  ) : (
                    <>
                      <Printer className="h-4 w-4" /> Start Batch Generation
                    </>
                  )}
                </Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>
      </div>
    </AppLayout>
  );
};

export default Reports;
