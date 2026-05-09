import { useEffect, useMemo, useState } from "react";
import { useLocation } from "react-router-dom";
import { motion } from "framer-motion";
import {
  AlertTriangle,
  Bell,
  CheckCircle2,
  FileText,
  Heart,
  Link2,
  Loader2,
  Shield,
  Users,
} from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import AppLayout from "@/components/AppLayout";
import GlassCard from "@/components/GlassCard";
import { Button } from "@/components/ui/button";
import api from "@/lib/api";
import { linkChildByCode } from "@/lib/students";

type ParentDashboardResponse = {
  children_count: number;
  children: Array<{
    student_id: string;
    full_name: string;
    admission_number: string;
    roll_number: string | null;
    class_name: string | null;
    section_name: string | null;
    average_marks: number | null;
    attendance_percentage: number;
    status_orb: "green" | "yellow" | "red";
    guardian_relation: string | null;
    latest_report: {
      id: string;
      term_name: string;
      generated_at: string;
      pdf_url: string | null;
    } | null;
  }>;
  kpis: {
    low_grade_children: number;
    low_attendance_children: number;
    unread_alerts: number;
  };
  recent_alerts: Array<{
    notification_id: string;
    event_type: string;
    status: string;
    created_at: string | null;
    payload: Record<string, any>;
  }>;
};

const statusStyles = {
  green: "bg-emerald-500/15 text-emerald-300",
  yellow: "bg-amber-500/15 text-amber-300",
  red: "bg-red-500/15 text-red-300",
};

const ParentDashboard = () => {
  const queryClient = useQueryClient();
  const location = useLocation();
  const pathTab = location.pathname.split("/").pop();
  const tabMap: Record<string, "overview" | "report" | "alerts" | "security"> = {
    parent: "overview",
    report: "report",
    alerts: "alerts",
    security: "security",
  };

  const [activeTab, setActiveTab] = useState<"overview" | "report" | "alerts" | "security">(tabMap[pathTab || "parent"] || "overview");
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [joiningCode, setJoiningCode] = useState("");

  useEffect(() => {
    setActiveTab(tabMap[pathTab || "parent"] || "overview");
  }, [pathTab]);

  const { data, isLoading } = useQuery<ParentDashboardResponse>({
    queryKey: ["parent-dashboard"],
    queryFn: async () => {
      const response = await api.get("/analytics/dashboard/parent/me");
      return response.data;
    },
  });

  const linkMutation = useMutation({
    mutationFn: () => linkChildByCode(joiningCode.trim().toUpperCase()),
    onSuccess: () => {
      toast.success("Child linked successfully.");
      setJoiningCode("");
      queryClient.invalidateQueries({ queryKey: ["parent-dashboard"] });
      setActiveTab("overview");
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || "Unable to link child.");
    },
  });

  const children = data?.children || [];
  const selectedChild = children[selectedIndex] || children[0] || null;

  useEffect(() => {
    if (!children.length) {
      setSelectedIndex(0);
      return;
    }
    if (!children[selectedIndex]) {
      setSelectedIndex(0);
    }
  }, [children, selectedIndex]);

  const childReportSummary = useMemo(() => {
    if (!selectedChild) {
      return {
        strengths: [],
        concerns: [],
        tips: [],
      };
    }

    const strengths = [];
    const concerns = [];
    const tips = [];

    if ((selectedChild.average_marks || 0) >= 75) {
      strengths.push(`${selectedChild.full_name} is maintaining strong academic performance.`);
    } else {
      concerns.push(`${selectedChild.full_name}'s average marks need closer follow-up this term.`);
      tips.push("Set a regular revision routine at home and review classwork together.");
    }

    if (selectedChild.attendance_percentage >= 90) {
      strengths.push(`Attendance is excellent at ${selectedChild.attendance_percentage}%.`);
    } else if (selectedChild.attendance_percentage < 75) {
      concerns.push(`Attendance is at ${selectedChild.attendance_percentage}% and needs attention.`);
      tips.push("Check daily attendance closely and coordinate with the school on missed days.");
    } else {
      tips.push("A steady daily routine can help improve attendance consistency.");
    }

    if (selectedChild.latest_report) {
      strengths.push(`Latest report available: ${selectedChild.latest_report.term_name}.`);
    } else {
      concerns.push("No report card has been generated yet for this child.");
    }

    if (!tips.length) {
      tips.push("Keep reviewing progress weekly and use school alerts to stay ahead of issues.");
    }

    return { strengths, concerns, tips };
  }, [selectedChild]);

  return (
    <AppLayout>
      <div className="space-y-6">
        <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}>
          <h1 className="text-2xl font-display font-bold text-foreground">Parent Dashboard</h1>
          <p className="mt-1 text-sm text-muted-foreground">See every linked child, track alerts, and add new child access with a join code.</p>
        </motion.div>

        {isLoading ? (
          <div className="flex h-[50vh] items-center justify-center">
            <Loader2 className="h-8 w-8 animate-spin text-primary" />
          </div>
        ) : (
          <>
            <div className="grid gap-4 md:grid-cols-3">
              <GlassCard hover={false} className="p-5">
                <div className="flex items-center gap-3">
                  <Users className="h-5 w-5 text-primary" />
                  <div>
                    <p className="text-xs text-muted-foreground">Linked Children</p>
                    <p className="text-2xl font-display font-bold text-foreground">{data?.children_count || 0}</p>
                  </div>
                </div>
              </GlassCard>
              <GlassCard hover={false} className="p-5">
                <div className="flex items-center gap-3">
                  <AlertTriangle className="h-5 w-5 text-amber-300" />
                  <div>
                    <p className="text-xs text-muted-foreground">Needs Attention</p>
                    <p className="text-2xl font-display font-bold text-foreground">{data?.kpis.low_grade_children || 0}</p>
                  </div>
                </div>
              </GlassCard>
              <GlassCard hover={false} className="p-5">
                <div className="flex items-center gap-3">
                  <Bell className="h-5 w-5 text-rose-300" />
                  <div>
                    <p className="text-xs text-muted-foreground">Unread Alerts</p>
                    <p className="text-2xl font-display font-bold text-foreground">{data?.kpis.unread_alerts || 0}</p>
                  </div>
                </div>
              </GlassCard>
            </div>

            <div className="flex gap-2 overflow-x-auto pb-1 scrollbar-hidden">
              {[
                { id: "overview" as const, label: "Dashboard", icon: Users },
                { id: "report" as const, label: "Health Report", icon: Heart },
                { id: "alerts" as const, label: "Alerts", icon: Bell },
                { id: "security" as const, label: "Security & Link", icon: Shield },
              ].map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`flex items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-medium transition-all ${
                    activeTab === tab.id
                      ? "border border-rose-500/20 bg-rose-500/15 text-foreground"
                      : "border border-transparent bg-white/[0.03] text-muted-foreground hover:bg-white/[0.06]"
                  }`}
                >
                  <tab.icon className={`h-4 w-4 ${activeTab === tab.id ? "text-rose-300" : ""}`} />
                  {tab.label}
                </button>
              ))}
            </div>

            <div className="flex gap-3 overflow-x-auto pb-1 scrollbar-hidden">
              {children.map((child, index) => (
                <button
                  key={child.student_id}
                  onClick={() => setSelectedIndex(index)}
                  className={`rounded-2xl border px-4 py-3 text-left transition-all ${
                    selectedIndex === index
                      ? "border-primary/30 bg-primary/12"
                      : "border-white/[0.08] bg-white/[0.03] hover:bg-white/[0.06]"
                  }`}
                >
                  <p className="text-sm font-semibold text-foreground">{child.full_name}</p>
                  <p className="mt-1 text-[11px] text-muted-foreground">
                    Admission {child.admission_number} � {child.class_name || "Class"} {child.section_name ? `� ${child.section_name}` : ""}
                  </p>
                </button>
              ))}
            </div>

            {!children.length && (
              <GlassCard hover={false} className="p-6 text-sm text-muted-foreground">
                No child is linked to this parent account yet. Open the Security & Link tab and enter the join code from the admin portal.
              </GlassCard>
            )}

            {activeTab === "overview" && selectedChild && (
              <motion.div key="overview" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="grid gap-4 xl:grid-cols-[1fr_0.9fr]">
                <GlassCard hover={false} className="space-y-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <h2 className="text-lg font-display font-semibold text-foreground">{selectedChild.full_name}</h2>
                      <p className="text-xs text-muted-foreground">
                        Admission {selectedChild.admission_number} � {selectedChild.class_name || "Class not set"} {selectedChild.section_name ? `� ${selectedChild.section_name}` : ""}
                      </p>
                    </div>
                    <span className={`rounded-full px-3 py-1 text-xs font-medium ${statusStyles[selectedChild.status_orb]}`}>
                      {selectedChild.status_orb === "green" ? "On Track" : selectedChild.status_orb === "yellow" ? "Needs Attention" : "At Risk"}
                    </span>
                  </div>

                  <div className="grid gap-3 md:grid-cols-3">
                    <div className="rounded-2xl border border-white/[0.08] bg-white/[0.03] p-4">
                      <p className="text-xs text-muted-foreground">Average Marks</p>
                      <p className="mt-2 text-xl font-display font-semibold text-foreground">
                        {selectedChild.average_marks !== null ? `${selectedChild.average_marks}%` : "Pending"}
                      </p>
                    </div>
                    <div className="rounded-2xl border border-white/[0.08] bg-white/[0.03] p-4">
                      <p className="text-xs text-muted-foreground">Attendance</p>
                      <p className="mt-2 text-xl font-display font-semibold text-foreground">{selectedChild.attendance_percentage}%</p>
                    </div>
                    <div className="rounded-2xl border border-white/[0.08] bg-white/[0.03] p-4">
                      <p className="text-xs text-muted-foreground">Latest Report</p>
                      <p className="mt-2 text-xl font-display font-semibold text-foreground">
                        {selectedChild.latest_report?.term_name || "Not ready"}
                      </p>
                    </div>
                  </div>
                </GlassCard>

                <GlassCard hover={false} className="space-y-4">
                  <h3 className="text-lg font-display font-semibold text-foreground">Quick Guidance</h3>
                  <div className="space-y-3 text-sm text-muted-foreground">
                    {childReportSummary.strengths.map((item) => (
                      <div key={item} className="flex items-start gap-2 rounded-xl bg-emerald-500/10 p-3">
                        <CheckCircle2 className="mt-0.5 h-4 w-4 text-emerald-300" />
                        <span>{item}</span>
                      </div>
                    ))}
                    {childReportSummary.concerns.map((item) => (
                      <div key={item} className="flex items-start gap-2 rounded-xl bg-amber-500/10 p-3">
                        <AlertTriangle className="mt-0.5 h-4 w-4 text-amber-300" />
                        <span>{item}</span>
                      </div>
                    ))}
                  </div>
                </GlassCard>
              </motion.div>
            )}

            {activeTab === "report" && selectedChild && (
              <motion.div key="report" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
                <GlassCard hover={false} className="space-y-5">
                  <div>
                    <h2 className="text-lg font-display font-semibold text-foreground">Health Report for {selectedChild.full_name}</h2>
                    <p className="text-xs text-muted-foreground">A compact live summary generated from current academic and attendance signals.</p>
                  </div>

                  <div className="space-y-3">
                    {childReportSummary.strengths.map((item) => (
                      <div key={item} className="flex items-start gap-2 rounded-xl bg-emerald-500/10 p-3 text-sm text-muted-foreground">
                        <CheckCircle2 className="mt-0.5 h-4 w-4 text-emerald-300" />
                        <span>{item}</span>
                      </div>
                    ))}
                    {childReportSummary.concerns.map((item) => (
                      <div key={item} className="flex items-start gap-2 rounded-xl bg-amber-500/10 p-3 text-sm text-muted-foreground">
                        <AlertTriangle className="mt-0.5 h-4 w-4 text-amber-300" />
                        <span>{item}</span>
                      </div>
                    ))}
                    {childReportSummary.tips.map((item) => (
                      <div key={item} className="flex items-start gap-2 rounded-xl bg-sky-500/10 p-3 text-sm text-muted-foreground">
                        <Heart className="mt-0.5 h-4 w-4 text-sky-300" />
                        <span>{item}</span>
                      </div>
                    ))}
                  </div>
                </GlassCard>
              </motion.div>
            )}

            {activeTab === "alerts" && (
              <motion.div key="alerts" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="space-y-3">
                {data?.recent_alerts.length ? (
                  data.recent_alerts.map((alert) => (
                    <GlassCard key={alert.notification_id} hover={false} className="p-4">
                      <div className="flex items-start gap-3">
                        <div className="rounded-xl bg-rose-500/10 p-2">
                          <Bell className="h-4 w-4 text-rose-300" />
                        </div>
                        <div>
                          <p className="text-sm font-medium text-foreground">{alert.event_type}</p>
                          <p className="mt-1 text-xs text-muted-foreground">{alert.created_at || "Just now"}</p>
                          <p className="mt-2 text-sm text-muted-foreground">
                            {alert.payload?.message || alert.payload?.summary || "Notification payload received."}
                          </p>
                        </div>
                      </div>
                    </GlassCard>
                  ))
                ) : (
                  <GlassCard hover={false} className="p-6 text-sm text-muted-foreground">
                    No recent alerts are available for this parent account.
                  </GlassCard>
                )}
              </motion.div>
            )}

            {activeTab === "security" && (
              <motion.div key="security" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="grid gap-4 xl:grid-cols-[0.95fr_1.05fr]">
                <GlassCard hover={false} className="space-y-4">
                  <div className="flex items-center gap-3">
                    <div className="rounded-2xl bg-rose-500/10 p-3">
                      <Shield className="h-5 w-5 text-rose-300" />
                    </div>
                    <div>
                      <h2 className="text-lg font-display font-semibold text-foreground">Link Child by Join Code</h2>
                      <p className="text-xs text-muted-foreground">Use the join code provided from the admin student workspace.</p>
                    </div>
                  </div>

                  <label className="space-y-2 text-sm">
                    <span className="text-muted-foreground">Join Code</span>
                    <input
                      type="text"
                      value={joiningCode}
                      onChange={(event) => setJoiningCode(event.target.value.toUpperCase())}
                      placeholder="ABC123"
                      className="glass-input w-full px-4 py-3 text-sm uppercase tracking-[0.2em]"
                    />
                  </label>

                  <Button
                    variant="gradient"
                    className="h-11 px-6"
                    disabled={linkMutation.isPending || !joiningCode.trim()}
                    onClick={() => linkMutation.mutate()}
                  >
                    {linkMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Link2 className="h-4 w-4" />}
                    Link Child
                  </Button>
                </GlassCard>

                <GlassCard hover={false} className="space-y-4">
                  <div className="flex items-center gap-3">
                    <div className="rounded-2xl bg-white/10 p-3">
                      <FileText className="h-5 w-5 text-primary" />
                    </div>
                    <div>
                      <h2 className="text-lg font-display font-semibold text-foreground">Linked Child Access</h2>
                      <p className="text-xs text-muted-foreground">Every child connected to this phone-backed parent account appears here automatically.</p>
                    </div>
                  </div>

                  <div className="space-y-3">
                    {children.map((child) => (
                      <div key={child.student_id} className="rounded-2xl border border-white/[0.08] bg-white/[0.03] p-4">
                        <div className="flex items-center justify-between gap-3">
                          <div>
                            <p className="text-sm font-semibold text-foreground">{child.full_name}</p>
                            <p className="mt-1 text-xs text-muted-foreground">
                              Admission {child.admission_number} � {child.class_name || "Class"} {child.section_name ? `� ${child.section_name}` : ""}
                            </p>
                          </div>
                          <span className={`rounded-full px-3 py-1 text-xs font-medium ${statusStyles[child.status_orb]}`}>
                            {child.status_orb}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </GlassCard>
              </motion.div>
            )}
          </>
        )}
      </div>
    </AppLayout>
  );
};

export default ParentDashboard;

