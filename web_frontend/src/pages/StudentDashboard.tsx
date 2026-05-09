import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { useLocation } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  BarChart3,
  BookOpen,
  CheckCircle2,
  Clock,
  Loader2,
  Sparkles,
  Target,
  TrendingDown,
  TrendingUp,
} from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import AppLayout from "@/components/AppLayout";
import GlassCard from "@/components/GlassCard";
import api from "@/lib/api";

type StudentDashboardResponse = {
  profile: {
    student_id: string;
    full_name: string;
    admission_number: string;
    roll_number: string | null;
    class_name: string | null;
    section_name: string | null;
  };
  metrics: {
    attendance_percentage: number;
    average_marks: number | null;
    status_orb: "green" | "yellow" | "red";
    assignments_done: number;
    assignments_total: number;
  };
  best_subject: {
    subject: string;
    score: number;
  } | null;
  weakest_subject: {
    subject: string;
    score: number;
  } | null;
  subject_scores: Array<{
    subject: string;
    score: number;
  }>;
  performance_trend: Array<{
    month: string;
    average_score: number;
  }>;
  weekly_tasks: Array<{
    id: string;
    task_name: string;
    description: string | null;
    subject: string;
    due_date: string;
    is_done: boolean;
  }>;
  ai_summary: {
    insight_text: string | null;
    recommendations: string[] | null;
  };
  latest_report: {
    id: string;
    term_name: string;
    generated_at: string;
    pdf_url: string | null;
  } | null;
};

const statusText = {
  green: "On Track",
  yellow: "Needs Attention",
  red: "At Risk",
};

const CircularMeter = ({ value, label, color, size = 140 }: { value: number; label: string; color: string; size?: number }) => {
  const radius = (size - 16) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (value / 100) * circumference;

  return (
    <div className="flex flex-col items-center gap-2">
      <div className="relative" style={{ width: size, height: size }}>
        <svg width={size} height={size} className="-rotate-90">
          <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="8" />
          <motion.circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke={color}
            strokeWidth="8"
            strokeLinecap="round"
            strokeDasharray={circumference}
            initial={{ strokeDashoffset: circumference }}
            animate={{ strokeDashoffset: offset }}
            transition={{ duration: 1.5, ease: "easeOut" }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-2xl font-bold font-display text-foreground">{Math.round(value)}%</span>
        </div>
      </div>
      <span className="text-xs font-medium text-muted-foreground">{label}</span>
    </div>
  );
};

const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="glass-strong rounded-xl p-3 text-sm">
      <p className="font-medium text-foreground">{label}</p>
      {payload.map((entry: any, index: number) => (
        <p key={index} style={{ color: entry.color }} className="text-xs">
          {entry.name}: {entry.value}
        </p>
      ))}
    </div>
  );
};

const StudentDashboard = () => {
  const location = useLocation();
  const pathTab = location.pathname.split("/").pop();
  const tabMap: Record<string, "dashboard" | "coach" | "path" | "charts"> = {
    student: "dashboard",
    coach: "coach",
    path: "path",
    charts: "charts",
  };

  const [activeTab, setActiveTab] = useState<"dashboard" | "coach" | "path" | "charts">(tabMap[pathTab || "student"] || "dashboard");
  const [chartTab, setChartTab] = useState<"subjects" | "time">("subjects");

  useEffect(() => {
    setActiveTab(tabMap[pathTab || "student"] || "dashboard");
  }, [pathTab]);

  const { data, isLoading } = useQuery<StudentDashboardResponse>({
    queryKey: ["student-dashboard"],
    queryFn: async () => {
      const response = await api.get("/analytics/dashboard/student/me");
      return response.data;
    },
  });

  if (isLoading) {
    return (
      <AppLayout>
        <div className="flex h-[60vh] items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
        </div>
      </AppLayout>
    );
  }

  if (!data) {
    return (
      <AppLayout>
        <div className="flex h-[60vh] items-center justify-center text-red-300">
          Student dashboard data could not be loaded.
        </div>
      </AppLayout>
    );
  }

  const tabs = [
    { id: "dashboard" as const, label: "My Dashboard", icon: Target },
    { id: "coach" as const, label: "AI Coach", icon: Sparkles },
    { id: "path" as const, label: "Weekly Path", icon: BookOpen },
    { id: "charts" as const, label: "My Charts", icon: BarChart3 },
  ];

  const chartData = data.subject_scores.map((item, index) => ({
    ...item,
    fill: `hsl(${240 + index * 18}, 75%, ${58 + index * 3}%)`,
  }));

  return (
    <AppLayout>
      <div className="space-y-6">
        <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}>
          <h1 className="text-2xl font-display font-bold text-foreground">
            Hey, {data.profile.full_name}! <span className="text-2xl">Hi</span>
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {data.profile.class_name || "Class"} {data.profile.section_name ? `· ${data.profile.section_name}` : ""} · Admission {data.profile.admission_number}
          </p>
        </motion.div>

        <div className="flex gap-2 overflow-x-auto pb-1 scrollbar-hidden">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-medium transition-all ${
                activeTab === tab.id
                  ? "border border-primary/20 bg-primary/15 text-foreground"
                  : "border border-transparent bg-white/[0.03] text-muted-foreground hover:bg-white/[0.06]"
              }`}
            >
              <tab.icon className={`h-4 w-4 ${activeTab === tab.id ? "text-primary" : ""}`} />
              {tab.label}
            </button>
          ))}
        </div>

        {activeTab === "dashboard" && (
          <motion.div key="dashboard" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="space-y-6">
            <div className="grid grid-cols-1 gap-6 sm:grid-cols-3">
              <GlassCard delay={0.05} className="flex justify-center py-8">
                <CircularMeter value={data.metrics.attendance_percentage} label="Attendance" color="hsl(160, 70%, 45%)" />
              </GlassCard>
              <GlassCard delay={0.1} className="flex justify-center py-8">
                <CircularMeter value={data.metrics.average_marks || 0} label="Average Grade" color="hsl(250, 90%, 65%)" />
              </GlassCard>
              <GlassCard delay={0.15} className="flex flex-col items-center justify-center gap-3 py-8 text-center">
                <div className="flex h-16 w-16 items-center justify-center rounded-full bg-gradient-to-br from-primary/40 to-secondary/40">
                  <Sparkles className="h-7 w-7 text-foreground" />
                </div>
                <div>
                  <p className="text-sm font-semibold text-foreground">{statusText[data.metrics.status_orb]}</p>
                  <p className="text-xs text-muted-foreground">Current AI status</p>
                </div>
              </GlassCard>
            </div>

            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              {[
                {
                  label: "Best Subject",
                  value: data.best_subject?.subject || "Pending",
                  sub: data.best_subject ? `${Math.round(data.best_subject.score)}%` : "No marks yet",
                  icon: TrendingUp,
                  color: "from-emerald-500/30 to-teal-500/20",
                },
                {
                  label: "Needs Focus",
                  value: data.weakest_subject?.subject || "Pending",
                  sub: data.weakest_subject ? `${Math.round(data.weakest_subject.score)}%` : "No marks yet",
                  icon: TrendingDown,
                  color: "from-amber-500/30 to-orange-500/20",
                },
                {
                  label: "Assignments",
                  value: `${data.metrics.assignments_done}/${data.metrics.assignments_total}`,
                  sub: "Completed",
                  icon: CheckCircle2,
                  color: "from-sky-500/30 to-blue-500/20",
                },
                {
                  label: "Latest Report",
                  value: data.latest_report?.term_name || "Pending",
                  sub: data.latest_report ? "Ready" : "Not generated",
                  icon: Clock,
                  color: "from-rose-500/30 to-pink-500/20",
                },
              ].map((item, index) => (
                <motion.div
                  key={item.label}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.2 + index * 0.05 }}
                  className="glass-card p-4"
                >
                  <div className={`mb-3 flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br ${item.color}`}>
                    <item.icon className="h-4 w-4 text-foreground" />
                  </div>
                  <p className="text-lg font-display font-bold text-foreground">{item.value}</p>
                  <p className="text-xs text-muted-foreground">{item.label} · {item.sub}</p>
                </motion.div>
              ))}
            </div>
          </motion.div>
        )}

        {activeTab === "coach" && (
          <motion.div key="coach" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
            <GlassCard delay={0.05} hover={false} className="space-y-5 ai-glow">
              <div className="flex items-center gap-3 border-b border-white/[0.06] pb-4">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-primary/40 to-accent/30">
                  <Sparkles className="h-5 w-5 text-foreground" />
                </div>
                <div>
                  <p className="text-sm font-semibold text-foreground">AI Study Coach</p>
                  <p className="text-xs text-muted-foreground">Live summary based on your current academic record</p>
                </div>
              </div>

              <div className="rounded-2xl bg-white/[0.03] p-4 text-sm leading-6 text-muted-foreground">
                {data.ai_summary.insight_text || "No AI coaching summary is available yet. Once marks and attendance data are recorded, your coach summary will appear here."}
              </div>

              {data.ai_summary.recommendations?.length ? (
                <div className="space-y-2">
                  {data.ai_summary.recommendations.map((item, index) => (
                    <div key={`${item}-${index}`} className="flex items-start gap-2 rounded-xl bg-white/[0.03] p-3 text-sm text-muted-foreground">
                      <Sparkles className="mt-0.5 h-4 w-4 text-primary" />
                      <span>{item}</span>
                    </div>
                  ))}
                </div>
              ) : null}
            </GlassCard>
          </motion.div>
        )}

        {activeTab === "path" && (
          <motion.div key="path" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
            <GlassCard delay={0.05} hover={false} className="space-y-5">
              <div>
                <h3 className="text-lg font-display font-semibold text-foreground">This Week&apos;s Learning Path</h3>
                <p className="text-xs text-muted-foreground">Tasks generated from the live learning-task table.</p>
              </div>

              <div className="flex gap-3 overflow-x-auto pb-2 scrollbar-hidden">
                {data.weekly_tasks.length ? (
                  data.weekly_tasks.map((task, index) => (
                    <motion.div
                      key={task.id}
                      initial={{ opacity: 0, y: 20 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: 0.1 + index * 0.08 }}
                      className={`min-w-[200px] rounded-2xl border p-4 ${
                        task.is_done
                          ? "border-emerald-500/20 bg-emerald-500/[0.08]"
                          : "border-white/[0.08] bg-white/[0.03]"
                      }`}
                    >
                      <div className="mb-3 flex items-center justify-between">
                        <span className={`text-xs font-bold uppercase tracking-wider ${task.is_done ? "text-emerald-300" : "text-primary"}`}>
                          {task.subject}
                        </span>
                        {task.is_done && <CheckCircle2 className="h-4 w-4 text-emerald-300" />}
                      </div>
                      <p className="text-sm font-medium text-foreground">{task.task_name}</p>
                      <p className="mt-2 text-xs text-muted-foreground">{task.description || "No extra description provided."}</p>
                      <p className="mt-3 text-[11px] text-muted-foreground">Due {task.due_date}</p>
                    </motion.div>
                  ))
                ) : (
                  <div className="rounded-2xl border border-dashed border-white/[0.10] bg-white/[0.02] p-5 text-sm text-muted-foreground">
                    No weekly tasks have been assigned yet.
                  </div>
                )}
              </div>
            </GlassCard>
          </motion.div>
        )}

        {activeTab === "charts" && (
          <motion.div key="charts" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="space-y-4">
            <div className="flex gap-2">
              {[
                { id: "subjects" as const, label: "Across Subjects" },
                { id: "time" as const, label: "Over Time" },
              ].map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setChartTab(tab.id)}
                  className={`rounded-xl px-4 py-2 text-sm font-medium transition-all ${
                    chartTab === tab.id
                      ? "border border-primary/20 bg-primary/15 text-foreground"
                      : "border border-transparent bg-white/[0.03] text-muted-foreground hover:bg-white/[0.06]"
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            <GlassCard delay={0.1} hover={false}>
              {chartTab === "subjects" ? (
                <>
                  <h3 className="mb-4 text-lg font-display font-semibold text-foreground">Subject Performance</h3>
                  <ResponsiveContainer width="100%" height={300}>
                    <BarChart data={chartData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                      <XAxis dataKey="subject" stroke="rgba(255,255,255,0.4)" fontSize={12} />
                      <YAxis stroke="rgba(255,255,255,0.4)" fontSize={12} />
                      <Tooltip content={<CustomTooltip />} />
                      <Bar dataKey="score" name="Score" radius={[8, 8, 0, 0]}>
                        {chartData.map((item) => (
                          <Cell key={item.subject} fill={item.fill} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </>
              ) : (
                <>
                  <h3 className="mb-4 text-lg font-display font-semibold text-foreground">Performance Over Time</h3>
                  <ResponsiveContainer width="100%" height={300}>
                    <LineChart data={data.performance_trend}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                      <XAxis dataKey="month" stroke="rgba(255,255,255,0.4)" fontSize={12} />
                      <YAxis stroke="rgba(255,255,255,0.4)" fontSize={12} />
                      <Tooltip content={<CustomTooltip />} />
                      <Line type="monotone" dataKey="average_score" name="Average" stroke="hsl(250, 90%, 65%)" strokeWidth={3} dot={{ fill: "hsl(250, 90%, 65%)", r: 5 }} />
                    </LineChart>
                  </ResponsiveContainer>
                </>
              )}
            </GlassCard>
          </motion.div>
        )}
      </div>
    </AppLayout>
  );
};

export default StudentDashboard;
