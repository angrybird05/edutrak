import { motion } from "framer-motion";
import AppLayout from "@/components/AppLayout";
import MetricCard from "@/components/MetricCard";
import GlassCard from "@/components/GlassCard";
import { useAuth } from "@/contexts/AuthContext";
import { useQuery } from "@tanstack/react-query";
import api from "@/lib/api";
import {
  Users, AlertTriangle, Calendar, BookOpen, Clock, Loader2,
} from "lucide-react";

type TeacherDashboardResponse = {
  my_students: number;
  today_classes: number;
  avg_attendance: number;
  at_risk_students: number;
  schedule: Array<{ time: string; class: string; subject: string; room: string }>;
  risk_alerts: Array<{ student: string; class: string; issue: string; severity: string }>;
  my_classes: Array<{ name: string; students: number; section: string; avg_score: number }>;
};

const TeacherDashboard = () => {
  const { userName } = useAuth();
  const { data, isLoading } = useQuery<TeacherDashboardResponse>({
    queryKey: ["teacher-dashboard"],
    queryFn: async () => {
      const response = await api.get("/analytics/dashboard/teacher/me");
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

  return (
    <AppLayout>
      <div className="space-y-6">
        <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}>
          <h1 className="text-2xl font-display font-bold text-foreground">
            Good Morning, {userName}!
          </h1>
          <p className="text-sm text-muted-foreground mt-1">Here&apos;s your classroom overview for today</p>
        </motion.div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <MetricCard title="My Students" value={String(data?.my_students || 0)} change={`Across ${data?.my_classes.length || 0} sections`} changeType="neutral" icon={Users} gradient="bg-gradient-to-br from-emerald-500/30 to-teal-500/20" delay={0} />
          <MetricCard title="Today's Classes" value={String(data?.today_classes || 0)} change={data?.schedule[0] ? `Next: ${data.schedule[0].time}` : "No classes today"} changeType="neutral" icon={Calendar} gradient="bg-gradient-to-br from-sky-500/30 to-blue-500/20" delay={0.1} />
          <MetricCard title="Avg Attendance" value={`${Math.round(data?.avg_attendance || 0)}%`} change="Across assigned sections" changeType="positive" icon={BookOpen} gradient="bg-gradient-to-br from-amber-500/30 to-orange-500/20" delay={0.2} />
          <MetricCard title="At-Risk Students" value={String(data?.at_risk_students || 0)} change="Need attention" changeType="negative" icon={AlertTriangle} gradient="bg-gradient-to-br from-red-500/30 to-rose-500/20" delay={0.3} />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <GlassCard delay={0.2} hover={false}>
            <h3 className="text-lg font-display font-semibold text-foreground mb-4 flex items-center gap-2">
              <Clock className="h-5 w-5 text-primary" /> Today's Schedule
            </h3>
            <div className="space-y-2">
              {(data?.schedule || []).map((item, i) => (
                <motion.div key={`${item.time}-${item.class}-${i}`} initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.3 + i * 0.05 }}
                  className="flex items-center gap-4 p-3 rounded-xl bg-white/[0.02] hover:bg-white/[0.04] transition-colors">
                  <span className="text-sm font-mono text-primary font-semibold w-20">{item.time}</span>
                  <div className="flex-1">
                    <p className="text-sm font-medium text-foreground">{item.class} - {item.subject}</p>
                    <p className="text-xs text-muted-foreground">{item.room}</p>
                  </div>
                </motion.div>
              ))}
              {!data?.schedule.length && <p className="text-sm text-muted-foreground">No timetable entries for today.</p>}
            </div>
          </GlassCard>

          <GlassCard delay={0.3} hover={false}>
            <h3 className="text-lg font-display font-semibold text-foreground mb-4 flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-red-400" /> Risk Alerts
            </h3>
            <div className="space-y-2">
              {(data?.risk_alerts || []).map((alert, i) => (
                <motion.div key={`${alert.student}-${i}`} initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.4 + i * 0.05 }}
                  className="flex items-start gap-3 p-3 rounded-xl bg-white/[0.02] hover:bg-white/[0.04] transition-colors">
                  <div className={`p-2 rounded-lg flex-shrink-0 ${alert.severity === "high" ? "bg-red-500/20" : "bg-amber-500/20"}`}>
                    <AlertTriangle className={`h-4 w-4 ${alert.severity === "high" ? "text-red-400" : "text-amber-400"}`} />
                  </div>
                  <div>
                    <p className="text-sm font-medium text-foreground">{alert.student} <span className="text-xs text-muted-foreground">({alert.class})</span></p>
                    <p className="text-xs text-muted-foreground">{alert.issue}</p>
                  </div>
                </motion.div>
              ))}
              {!data?.risk_alerts.length && <p className="text-sm text-muted-foreground">No current risk alerts.</p>}
            </div>
          </GlassCard>
        </div>

        <GlassCard delay={0.4} hover={false}>
          <h3 className="text-lg font-display font-semibold text-foreground mb-4">My Assigned Sections</h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            {(data?.my_classes || []).map((cls, i) => (
              <motion.div key={cls.name} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.5 + i * 0.05 }}
                className="p-4 rounded-xl bg-white/[0.03] border border-white/[0.06] hover:bg-white/[0.05] transition-all cursor-pointer">
                <p className="text-sm font-semibold text-foreground">{cls.name}</p>
                <p className="text-xs text-muted-foreground mb-3">{cls.section}</p>
                <div className="flex items-center justify-between text-xs">
                  <span className="text-muted-foreground">{cls.students} students</span>
                  <span className="text-primary font-semibold">{Math.round(cls.avg_score)}% avg</span>
                </div>
              </motion.div>
            ))}
          </div>
        </GlassCard>
      </div>
    </AppLayout>
  );
};

export default TeacherDashboard;
