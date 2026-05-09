import { motion } from "framer-motion";
import {
  Users,
  TrendingUp,
  Calendar,
  AlertTriangle,
  Loader2,
} from "lucide-react";
import AppLayout from "@/components/AppLayout";
import MetricCard from "@/components/MetricCard";
import GlassCard from "@/components/GlassCard";
import { useQuery } from "@tanstack/react-query";
import api from "@/lib/api";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

const riskColors: Record<string, string> = {
  "Low Risk": "#34d399",
  "Medium Risk": "#fbbf24",
  "High Risk": "#f87171",
};

const CustomTooltip = ({ active, payload, label }: any) => {
  if (active && payload && payload.length) {
    return (
      <div className="glass-strong p-3 rounded-xl text-sm">
        <p className="font-medium text-foreground">{label}</p>
        {payload.map((entry: any, i: number) => (
          <p key={i} style={{ color: entry.color }} className="text-xs">
            {entry.name}: {entry.value}
          </p>
        ))}
      </div>
    );
  }
  return null;
};

const Dashboard = () => {
  const { data: stats, isLoading } = useQuery({
    queryKey: ["dashboard-stats"],
    queryFn: async () => {
      const response = await api.get("/analytics/dashboard/stats");
      return response.data;
    }
  });

  const { data: overview } = useQuery({
    queryKey: ["admin-dashboard-overview"],
    queryFn: async () => {
      const response = await api.get("/analytics/dashboard/admin/overview");
      return response.data;
    }
  });

  const performanceData = overview?.performance_trend || [];
  const subjectData = overview?.subject_performance || [];
  const riskData = (overview?.risk_distribution || []).map((item: any) => ({
    ...item,
    color: riskColors[item.name] || "#60a5fa",
  }));
  const recentActivity = overview?.recent_activity || [];

  return (
    <AppLayout>
      <div className="space-y-6">
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex items-center justify-between"
        >
          <div>
            <h1 className="text-2xl font-display font-bold text-foreground">Executive Dashboard</h1>
            <p className="text-sm text-muted-foreground mt-1">Welcome back. Here&apos;s your institution overview.</p>
          </div>
        </motion.div>

        {isLoading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {[...Array(4)].map((_, i) => (
              <GlassCard key={i} className="h-32 flex items-center justify-center">
                <Loader2 className="h-6 w-6 text-primary animate-spin" />
              </GlassCard>
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <MetricCard title="Total Students" value={stats?.total_students.toLocaleString() || "0"} change="Live school total" changeType="positive" icon={Users} gradient="bg-gradient-to-br from-primary/30 to-secondary/20" delay={0} />
            <MetricCard title="Avg Performance" value={`${stats?.avg_performance || 0}%`} change={stats?.performance_change || "Live average"} changeType="positive" icon={TrendingUp} gradient="bg-gradient-to-br from-emerald-500/30 to-teal-500/20" delay={0.1} />
            <MetricCard title="Attendance Rate" value={`${stats?.attendance_rate || 0}%`} change="Current recorded attendance" changeType="neutral" icon={Calendar} gradient="bg-gradient-to-br from-amber-500/30 to-orange-500/20" delay={0.2} />
            <MetricCard title="At-Risk Students" value={stats?.at_risk_count?.toString() || "0"} change="Risk engine placeholder still limited" changeType="neutral" icon={AlertTriangle} gradient="bg-gradient-to-br from-red-500/30 to-rose-500/20" delay={0.3} />
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <GlassCard delay={0.2}>
            <h3 className="text-lg font-display font-semibold text-foreground mb-4">Institutional Performance</h3>
            <div className="h-[280px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={performanceData}>
                  <defs>
                    <linearGradient id="colorScore" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="hsl(250, 90%, 65%)" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="hsl(250, 90%, 65%)" stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="colorAttendance" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="hsl(200, 80%, 55%)" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="hsl(200, 80%, 55%)" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                  <XAxis dataKey="month" stroke="rgba(255,255,255,0.4)" fontSize={12} />
                  <YAxis stroke="rgba(255,255,255,0.4)" fontSize={12} />
                  <Tooltip content={<CustomTooltip />} />
                  <Area type="monotone" dataKey="score" stroke="hsl(250, 90%, 65%)" fill="url(#colorScore)" name="Score" strokeWidth={2} />
                  <Area type="monotone" dataKey="attendance" stroke="hsl(200, 80%, 55%)" fill="url(#colorAttendance)" name="Attendance" strokeWidth={2} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </GlassCard>

          <GlassCard delay={0.3}>
            <h3 className="text-lg font-display font-semibold text-foreground mb-4">Subject-wise Performance</h3>
            <div className="h-[280px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={subjectData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                  <XAxis dataKey="subject" stroke="rgba(255,255,255,0.4)" fontSize={12} />
                  <YAxis stroke="rgba(255,255,255,0.4)" fontSize={12} />
                  <Tooltip content={<CustomTooltip />} />
                  <Bar dataKey="avg" name="Average" radius={[8, 8, 0, 0]}>
                    {subjectData.map((_: any, index: number) => (
                      <Cell key={index} fill={`hsl(${250 + index * 15}, 80%, ${55 + index * 5}%)`} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </GlassCard>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <GlassCard delay={0.4}>
            <h3 className="text-lg font-display font-semibold text-foreground mb-4">Risk Distribution</h3>
            <div className="h-[200px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={riskData} cx="50%" cy="50%" innerRadius={50} outerRadius={80} dataKey="value" strokeWidth={0}>
                    {riskData.map((entry: any, index: number) => (
                      <Cell key={index} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip content={<CustomTooltip />} />
                </PieChart>
              </ResponsiveContainer>
            </div>
            <div className="flex justify-center gap-4 mt-2">
              {riskData.map((item: any) => (
                <div key={item.name} className="flex items-center gap-1.5 text-xs text-muted-foreground">
                  <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: item.color }} />
                  {item.name}
                </div>
              ))}
            </div>
          </GlassCard>

          <GlassCard delay={0.5} className="lg:col-span-2">
            <h3 className="text-lg font-display font-semibold text-foreground mb-4">Recent Activity</h3>
            <div className="space-y-3">
              {recentActivity.map((item: any, i: number) => (
                <motion.div
                  key={`${item.name}-${i}`}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.5 + i * 0.1 }}
                  className="flex items-center justify-between p-3 rounded-xl bg-white/[0.03] hover:bg-white/[0.06] transition-all duration-300"
                >
                  <div>
                    <p className="text-sm font-medium text-foreground">{item.name}</p>
                    <p className="text-xs text-muted-foreground">{item.time}</p>
                  </div>
                  <span className="text-xs font-medium px-3 py-1 rounded-full bg-emerald-500/20 text-emerald-400">
                    {item.status}
                  </span>
                </motion.div>
              ))}
              {!recentActivity.length && <p className="text-sm text-muted-foreground">No recent activity yet.</p>}
            </div>
          </GlassCard>
        </div>
      </div>
    </AppLayout>
  );
};

export default Dashboard;
