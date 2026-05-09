import { useEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  AlertCircle,
  Brain,
  CheckCircle2,
  Clock,
  RefreshCw,
  XCircle,
  Zap,
} from "lucide-react";

import AppLayout from "@/components/AppLayout";
import GlassCard from "@/components/GlassCard";
import { Button } from "@/components/ui/button";
import api from "@/lib/api";

type SectionOption = { id: string; name: string; class_id: string; class_name: string };
type ExamOption = { id: string; name: string; exam_date: string | null };

type BatchStatus = {
  exam_id: string;
  total: number;
  pending: number;
  processing: number;
  completed: number;
  failed: number;
  generated: number;
  in_progress: number;
  remaining: number;
  progress_pct: number;
  eta_seconds: number | null;
  eta_completed_at: string | null;
  is_complete: boolean;
  auto_mode: boolean;
};

type StudentRow = {
  student_id: string;
  admission_number: string | null;
  full_name: string | null;
  exam_id: string;
  status: string;
  model_version: string | null;
  generated_at: string | null;
};

type MetricsPayload = {
  task_processing_time_ms_last: number;
  task_processing_time_ms_avg?: number;
  ai_usage_count: number;
  failure_rate: number;
  queue_size: number;
  tasks_started: number;
  tasks_completed: number;
  tasks_failed: number;
  cache_hits: number;
};

type OverviewPayload = {
  total: number;
  generated: number;
  in_progress: number;
  failed: number;
  completion_pct: number;
  task_processing_time_ms_avg: number;
  task_processing_time_ms_last: number;
  top_exams: Array<{
    exam_id: string;
    total: number;
    completed: number;
    in_progress: number;
    failed: number;
  }>;
};

const STORAGE_KEYS = {
  sectionId: "ai_insights:selected_section_id",
  examId: "ai_insights:selected_exam_id",
  tablePage: "ai_insights:table_page",
} as const;

function formatEta(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return "Estimating...";
  if (seconds <= 0) return "Ready";
  const hrs = Math.floor(seconds / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  const secs = seconds % 60;
  if (hrs > 0) return `${hrs}h ${mins}m`;
  if (mins > 0) return `${mins}m ${secs}s`;
  return `${secs}s`;
}

function displayStudentLabel(row: StudentRow): string {
  if (row.admission_number && row.admission_number.trim().length > 0) {
    return row.admission_number;
  }
  if (row.full_name && row.full_name.trim().length > 0) {
    return row.full_name;
  }
  return `${row.student_id.slice(0, 8)}...`;
}

function formatMs(ms: number | null | undefined): string {
  if (ms === null || ms === undefined || Number.isNaN(ms) || ms <= 0) return "-";
  if (ms < 1000) return `${ms.toFixed(0)} ms`;
  return `${(ms / 1000).toFixed(2)} s`;
}

function DonutRing({ data }: { data: BatchStatus | undefined }) {
  const total = data?.total || 0;
  const cx = 60;
  const cy = 60;
  const r = 48;
  const circ = 2 * Math.PI * r;

  const segments = [
    { key: "completed", color: "#22d3ee", val: data?.completed ?? 0, label: "Generated" },
    { key: "processing", color: "#a78bfa", val: data?.processing ?? 0, label: "Processing" },
    { key: "pending", color: "#475569", val: data?.pending ?? 0, label: "Pending" },
    { key: "failed", color: "#f87171", val: data?.failed ?? 0, label: "Failed" },
  ];

  let offset = 0;
  const arcs = segments.map((segment) => {
    const pct = total > 0 ? segment.val / total : 0;
    const dash = pct * circ;
    const arc = { ...segment, dash, gap: circ - dash, offset: circ - offset };
    offset += dash;
    return arc;
  });

  return (
    <div className="flex flex-col items-center gap-4">
      <div className="relative">
        <svg width="120" height="120" viewBox="0 0 120 120" className="-rotate-90">
          <circle cx={cx} cy={cy} r={r} fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth="12" />
          {arcs.map((arc) =>
            arc.dash > 0 ? (
              <circle
                key={arc.key}
                cx={cx}
                cy={cy}
                r={r}
                fill="none"
                stroke={arc.color}
                strokeWidth="12"
                strokeDasharray={`${arc.dash} ${arc.gap}`}
                strokeDashoffset={arc.offset}
                strokeLinecap="butt"
                style={{ transition: "stroke-dasharray 0.6s ease" }}
              />
            ) : null,
          )}
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-xl font-bold text-foreground">{data?.progress_pct ?? 0}%</span>
          <span className="text-[10px] text-muted-foreground">complete</span>
        </div>
      </div>
      <div className="grid grid-cols-2 gap-x-4 gap-y-1 w-full">
        {segments.map((segment) => (
          <div key={segment.key} className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: segment.color }} />
            <span className="text-xs text-muted-foreground">{segment.label}</span>
            <span className="text-xs font-semibold text-foreground ml-auto">{segment.val}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function LiveProgressBar({ batch }: { batch: BatchStatus | undefined }) {
  const pct = batch?.progress_pct ?? 0;

  return (
    <div className="space-y-2">
      <div className="flex justify-between text-xs text-muted-foreground">
        <span>Automatic generation progress</span>
        <span>
          {batch?.generated ?? 0} / {batch?.total ?? 0} students
        </span>
      </div>
      <div className="h-3 w-full rounded-full bg-white/5 overflow-hidden">
        <motion.div
          className="h-full rounded-full"
          style={{ background: "linear-gradient(90deg,hsl(250,90%,65%),hsl(200,80%,55%))" }}
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.6, ease: "easeOut" }}
        />
      </div>
      <div className="flex items-center justify-between text-[11px] text-muted-foreground">
        <span>{batch?.in_progress ?? 0} in progress</span>
        <span>ETA: {formatEta(batch?.eta_seconds)}</span>
      </div>
      {batch?.is_complete && (batch?.total ?? 0) > 0 && (
        <p className="text-[10px] text-emerald-400 flex items-center gap-1">
          <CheckCircle2 className="h-3 w-3" /> All insights generated
        </p>
      )}
    </div>
  );
}

const STATUS_STYLE: Record<string, string> = {
  completed: "bg-emerald-500/20 text-emerald-400 border-emerald-500/30",
  processing: "bg-violet-500/20 text-violet-400 border-violet-500/30",
  pending: "bg-slate-500/20 text-slate-400 border-slate-500/30",
  failed: "bg-red-500/20 text-red-400 border-red-500/30",
};

function StatusBadge({ status }: { status: string }) {
  return (
    <span
      className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border ${
        STATUS_STYLE[status] ?? "bg-white/5 text-muted-foreground border-white/10"
      }`}
    >
      {status}
    </span>
  );
}

function MetricTile({
  label,
  value,
  prev,
  icon: Icon,
  color,
}: {
  label: string;
  value: string | number;
  prev?: number;
  icon: React.ComponentType<{ className?: string }>;
  color: string;
}) {
  const curr = typeof value === "number" ? value : parseFloat(String(value));
  const trend = prev !== undefined && !Number.isNaN(curr) ? (curr > prev ? "up" : curr < prev ? "down" : "flat") : "flat";

  return (
    <div className="glass rounded-xl p-4 flex flex-col gap-1">
      <div className="flex items-center justify-between">
        <p className="text-xs text-muted-foreground">{label}</p>
        <Icon className={`h-4 w-4 ${color}`} />
      </div>
      <p className="text-xl font-bold text-foreground">{value}</p>
      {trend !== "flat" && (
        <p className={`text-[10px] ${trend === "up" ? "text-emerald-400" : "text-red-400"}`}>
          {trend === "up" ? "up" : "down"} vs last poll
        </p>
      )}
    </div>
  );
}

const PAGE_SIZE = 8;

const AIInsights = () => {
  const [sectionId, setSectionId] = useState(() => localStorage.getItem(STORAGE_KEYS.sectionId) ?? "");
  const [examId, setExamId] = useState(() => localStorage.getItem(STORAGE_KEYS.examId) ?? "");
  const [tablePage, setTablePage] = useState(() => {
    const raw = localStorage.getItem(STORAGE_KEYS.tablePage);
    const parsed = raw ? Number.parseInt(raw, 10) : 0;
    return Number.isNaN(parsed) || parsed < 0 ? 0 : parsed;
  });
  const [isPolling, setIsPolling] = useState(false);
  const prevMetrics = useRef<MetricsPayload | null>(null);

  const sectionsQuery = useQuery({
    queryKey: ["ai-sections"],
    queryFn: async () => (await api.get("/assessment/attendance/sections")).data as SectionOption[],
  });

  const examsQuery = useQuery({
    queryKey: ["ai-exams", sectionId],
    enabled: Boolean(sectionId),
    queryFn: async () => (await api.get(`/assessment/exams/${sectionId}`)).data as ExamOption[],
  });

  const batchQuery = useQuery({
    queryKey: ["ai-batch-status", examId],
    enabled: Boolean(examId),
    queryFn: async () => (await api.get("/insights/batch-status", { params: { exam_id: examId } })).data as BatchStatus,
    refetchInterval: isPolling ? 3000 : 15000,
  });

  const listQuery = useQuery({
    queryKey: ["ai-list", examId],
    enabled: Boolean(examId),
    queryFn: async () => (await api.get("/insights/list", { params: { exam_id: examId } })).data as StudentRow[],
    refetchInterval: isPolling ? 5000 : 30000,
  });

  const metricsQuery = useQuery({
    queryKey: ["ai-metrics"],
    queryFn: async () => (await api.get("/insights/metrics")).data as MetricsPayload,
    retry: false,
    refetchInterval: isPolling ? 5000 : 15000,
  });
  const overviewQuery = useQuery({
    queryKey: ["ai-overview"],
    queryFn: async () => (await api.get("/insights/overview")).data as OverviewPayload,
    retry: false,
    refetchInterval: isPolling ? 5000 : 15000,
  });

  useEffect(() => {
    if (!sectionsQuery.data?.length) return;
    const hasSelection = sectionsQuery.data.some((section) => section.id === sectionId);
    if (!hasSelection) {
      setSectionId(sectionsQuery.data[0].id);
    }
  }, [sectionsQuery.data, sectionId]);

  useEffect(() => {
    if (!sectionId || !examsQuery.data?.length) return;
    const hasSelection = examsQuery.data.some((exam) => exam.id === examId);
    if (!hasSelection) {
      setExamId(examsQuery.data[0].id);
    }
  }, [examsQuery.data, examId]);

  useEffect(() => {
    if (!sectionId) return;
    localStorage.setItem(STORAGE_KEYS.sectionId, sectionId);
  }, [sectionId]);

  useEffect(() => {
    if (!examId) return;
    localStorage.setItem(STORAGE_KEYS.examId, examId);
  }, [examId]);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEYS.tablePage, String(tablePage));
  }, [tablePage]);

  useEffect(() => {
    const inProgress = (batchQuery.data?.in_progress ?? 0) > 0;
    setIsPolling(inProgress);
    if (batchQuery.data?.is_complete) {
      listQuery.refetch();
    }
  }, [batchQuery.data?.in_progress, batchQuery.data?.is_complete, listQuery.refetch]);

  const selectedSection = useMemo(
    () => (sectionsQuery.data ?? []).find((section) => section.id === sectionId),
    [sectionsQuery.data, sectionId],
  );

  const selectedExam = useMemo(
    () => (examsQuery.data ?? []).find((exam) => exam.id === examId),
    [examsQuery.data, examId],
  );

  const allRows = listQuery.data ?? [];
  const failedRows = allRows.filter((row) => row.status === "failed");
  const pageRows = allRows.slice(tablePage * PAGE_SIZE, (tablePage + 1) * PAGE_SIZE);
  const pageCount = Math.ceil(allRows.length / PAGE_SIZE);

  useEffect(() => {
    if (allRows.length === 0 && tablePage !== 0) {
      setTablePage(0);
      return;
    }
    const maxPage = Math.max(Math.ceil(allRows.length / PAGE_SIZE) - 1, 0);
    if (tablePage > maxPage) {
      setTablePage(maxPage);
    }
  }, [allRows.length, tablePage]);

  const metrics = metricsQuery.data;
  const prevM = prevMetrics.current;
  useEffect(() => {
    if (metrics) prevMetrics.current = metrics;
  }, [metrics]);

  return (
    <AppLayout>
      <div className="space-y-6 pb-8">
        <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}>
          <h1 className="text-2xl font-display font-bold text-foreground flex items-center gap-2">
            <Brain className="h-6 w-6 text-primary" /> AI Insights V2
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Fully automatic insight generation. Insights are queued when marks or attendance data is recorded.
          </p>
        </motion.div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <GlassCard delay={0.1} hover={false} className="lg:col-span-2 ai-glow py-8">
            <div className="flex items-center gap-3 mb-6">
              <div className="w-10 h-10 rounded-full bg-gradient-to-br from-primary/40 to-accent/30 flex items-center justify-center">
                <Activity className="h-5 w-5 text-foreground" />
              </div>
              <div>
                <h2 className="text-base font-semibold text-foreground">Automatic Insight Orchestration</h2>
                <p className="text-xs text-muted-foreground">Manual generation is disabled. This view is monitor-only.</p>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {[{
                label: "Section",
                value: sectionId,
                onChange: (value: string) => setSectionId(value),
                options: (sectionsQuery.data ?? []).map((section) => ({
                  value: section.id,
                  label: `${section.class_name} - ${section.name}`,
                })),
                placeholder: "Select section",
              }, {
                label: "Exam",
                value: examId,
                onChange: (value: string) => setExamId(value),
                options: (examsQuery.data ?? []).map((exam) => ({
                  value: exam.id,
                  label: `${exam.name}${exam.exam_date ? ` (${exam.exam_date})` : ""}`,
                })),
                placeholder: "Select exam",
                disabled: !sectionId,
              }].map((field) => (
                <label key={field.label} className="text-sm text-foreground">
                  <span className="block mb-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">{field.label}</span>
                  <select
                    className="w-full rounded-xl border border-white/10 bg-background/60 px-3 py-2 text-sm"
                    value={field.value}
                    onChange={(event) => field.onChange(event.target.value)}
                    disabled={"disabled" in field ? Boolean(field.disabled) : false}
                  >
                    <option value="">{field.placeholder}</option>
                    {field.options.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </label>
              ))}
            </div>

            <div className="mt-6 rounded-xl border border-white/10 bg-background/40 p-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-2">System Status</p>
              <div className="flex flex-wrap items-center gap-5">
                <div>
                  <p className="text-[11px] text-muted-foreground">Generated</p>
                  <p className="text-xl font-semibold text-cyan-300">{batchQuery.data?.generated ?? 0}</p>
                </div>
                <div>
                  <p className="text-[11px] text-muted-foreground">In Progress</p>
                  <p className="text-xl font-semibold text-violet-300">{batchQuery.data?.in_progress ?? 0}</p>
                </div>
                <div>
                  <p className="text-[11px] text-muted-foreground">Estimated Time Remaining</p>
                  <p className="text-xl font-semibold text-amber-300">{formatEta(batchQuery.data?.eta_seconds)}</p>
                </div>
              </div>
            </div>

            {isPolling && (
              <div className="mt-4 text-xs text-primary flex items-center gap-1 animate-pulse">
                <Activity className="h-3 w-3" /> Live polling
              </div>
            )}
          </GlassCard>

          <GlassCard delay={0.15} hover={false} className="flex flex-col gap-6">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-3">Progress</p>
              <LiveProgressBar batch={batchQuery.data} />
            </div>
            <div className="border-t border-white/5 pt-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-3">Breakdown</p>
              <DonutRing data={batchQuery.data} />
            </div>
            {selectedSection && selectedExam && (
              <div className="border-t border-white/5 pt-3 text-xs text-muted-foreground space-y-0.5">
                <p>
                  <span className="text-foreground/60">Section:</span> {selectedSection.class_name} - {selectedSection.name}
                </p>
                <p>
                  <span className="text-foreground/60">Exam:</span> {selectedExam.name}
                </p>
              </div>
            )}
          </GlassCard>
        </div>

        <GlassCard delay={0.17} hover={false}>
          <div className="flex items-center justify-between mb-4">
            <p className="text-sm font-semibold text-foreground">Global Insights Overview (All Exams)</p>
            {overviewQuery.isFetching && <RefreshCw className="h-3 w-3 animate-spin text-muted-foreground" />}
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
            <div className="rounded-xl border border-white/10 bg-white/[0.02] p-3">
              <p className="text-[11px] text-muted-foreground">Generated</p>
              <p className="text-lg font-semibold text-cyan-300">{overviewQuery.data?.generated ?? "-"}</p>
            </div>
            <div className="rounded-xl border border-white/10 bg-white/[0.02] p-3">
              <p className="text-[11px] text-muted-foreground">In Progress</p>
              <p className="text-lg font-semibold text-violet-300">{overviewQuery.data?.in_progress ?? "-"}</p>
            </div>
            <div className="rounded-xl border border-white/10 bg-white/[0.02] p-3">
              <p className="text-[11px] text-muted-foreground">Avg Time / Generation</p>
              <p className="text-lg font-semibold text-amber-300">{formatMs(overviewQuery.data?.task_processing_time_ms_avg)}</p>
            </div>
            <div className="rounded-xl border border-white/10 bg-white/[0.02] p-3">
              <p className="text-[11px] text-muted-foreground">Last Generation Time</p>
              <p className="text-lg font-semibold text-emerald-300">{formatMs(overviewQuery.data?.task_processing_time_ms_last)}</p>
            </div>
          </div>
          <p className="text-xs text-muted-foreground">
            Completion: {overviewQuery.data?.completion_pct ?? 0}% · Total rows: {overviewQuery.data?.total ?? 0}
          </p>
        </GlassCard>

        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-3 px-1">
            Real-time Metrics
            {metricsQuery.isFetching && <RefreshCw className="h-3 w-3 ml-2 inline animate-spin" />}
          </p>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
            <MetricTile label="Queue Size" value={metrics?.queue_size ?? "-"} prev={prevM?.queue_size} icon={Clock} color="text-violet-400" />
            <MetricTile label="AI Usage" value={metrics?.ai_usage_count ?? "-"} prev={prevM?.ai_usage_count} icon={Brain} color="text-cyan-400" />
            <MetricTile label="Cache Hits" value={metrics?.cache_hits ?? "-"} prev={prevM?.cache_hits} icon={Zap} color="text-amber-400" />
            <MetricTile label="Completed" value={metrics?.tasks_completed ?? "-"} prev={prevM?.tasks_completed} icon={CheckCircle2} color="text-emerald-400" />
            <MetricTile label="Failed" value={metrics?.tasks_failed ?? "-"} prev={prevM?.tasks_failed} icon={XCircle} color="text-red-400" />
            <MetricTile
              label="Failure Rate"
              value={metrics ? `${(metrics.failure_rate * 100).toFixed(1)}%` : "-"}
              prev={prevM ? prevM.failure_rate * 100 : undefined}
              icon={AlertCircle}
              color="text-orange-400"
            />
          </div>
        </div>

        <GlassCard delay={0.2} hover={false}>
          <div className="flex items-center justify-between mb-4">
            <p className="text-sm font-semibold text-foreground flex items-center gap-2">
              <Activity className="h-4 w-4 text-primary" /> Per-Student Status
              {listQuery.isFetching && <RefreshCw className="h-3 w-3 animate-spin text-muted-foreground" />}
            </p>
            <span className="text-xs text-muted-foreground">{allRows.length} students</span>
          </div>

          {allRows.length === 0 ? (
            <p className="text-sm text-muted-foreground py-6 text-center">
              {examId ? "No students available for this exam section yet." : "Select an exam to view automatic generation status."}
            </p>
          ) : (
            <>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-white/5">
                      <th className="text-left text-xs font-semibold text-muted-foreground pb-2 pr-4">Admission No.</th>
                      <th className="text-left text-xs font-semibold text-muted-foreground pb-2 pr-4">Status</th>
                      <th className="text-left text-xs font-semibold text-muted-foreground pb-2 pr-4">Model</th>
                      <th className="text-left text-xs font-semibold text-muted-foreground pb-2">Generated At</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/5">
                    <AnimatePresence mode="popLayout">
                      {pageRows.map((row) => (
                        <motion.tr key={row.student_id} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                          <td className="py-2 pr-4 text-xs text-muted-foreground">{displayStudentLabel(row)}</td>
                          <td className="py-2 pr-4">
                            <StatusBadge status={row.status} />
                          </td>
                          <td className="py-2 pr-4 text-xs text-muted-foreground">{row.model_version ?? "-"}</td>
                          <td className="py-2 text-xs text-muted-foreground">
                            {row.generated_at ? new Date(row.generated_at).toLocaleString() : "-"}
                          </td>
                        </motion.tr>
                      ))}
                    </AnimatePresence>
                  </tbody>
                </table>
              </div>

              {pageCount > 1 && (
                <div className="flex items-center justify-between mt-4 pt-4 border-t border-white/5">
                  <Button variant="ghost" size="sm" disabled={tablePage === 0} onClick={() => setTablePage((page) => page - 1)}>
                    Prev
                  </Button>
                  <span className="text-xs text-muted-foreground">
                    Page {tablePage + 1} / {pageCount}
                  </span>
                  <Button
                    variant="ghost"
                    size="sm"
                    disabled={tablePage === pageCount - 1}
                    onClick={() => setTablePage((page) => page + 1)}
                  >
                    Next
                  </Button>
                </div>
              )}
            </>
          )}
        </GlassCard>

        <AnimatePresence>
          {failedRows.length > 0 && (
            <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
              <GlassCard hover={false} className="border border-red-500/20">
                <div className="flex items-center gap-2 mb-3">
                  <XCircle className="h-4 w-4 text-red-400" />
                  <p className="text-sm font-semibold text-red-400">Failed Students ({failedRows.length})</p>
                </div>
                <p className="text-xs text-muted-foreground mb-3">
                  Automatic worker retries are enabled. If failures remain, check backend logs for root-cause errors.
                </p>
                <div className="space-y-2 max-h-64 overflow-y-auto scrollbar-hidden">
                  {failedRows.map((row) => (
                    <div key={row.student_id} className="rounded-xl bg-red-500/5 border border-red-500/10 px-4 py-2.5">
                      <div className="flex items-center gap-3">
                        <AlertCircle className="h-4 w-4 text-red-400 flex-shrink-0" />
                        <span className="text-xs text-muted-foreground">{displayStudentLabel(row)}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </GlassCard>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </AppLayout>
  );
};

export default AIInsights;
