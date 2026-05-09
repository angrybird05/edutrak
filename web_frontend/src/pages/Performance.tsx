import { useState } from "react";
import { motion } from "framer-motion";
import AppLayout from "@/components/AppLayout";
import GlassCard from "@/components/GlassCard";
import {
  BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  AreaChart, Area, RadarChart, PolarGrid, PolarAngleAxis, Radar,
} from "recharts";
import { Filter, Download, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useQuery } from "@tanstack/react-query";
import api from "@/lib/api";

const gradeColors: Record<string, string> = {
  "A+": "#34d399",
  "A": "#60a5fa",
  "B": "#a78bfa",
  "C": "#fbbf24",
  "D/F": "#f87171",
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

const Performance = () => {
  const [selectedClass] = useState("all");
  const [selectedSubject] = useState("all");

  const { data, isLoading } = useQuery({
    queryKey: ["performance-overview", selectedClass, selectedSubject],
    queryFn: async () => {
      const response = await api.get("/analytics/performance/overview");
      return response.data;
    },
  });

  const monthlyData = data?.monthly_trend || [];
  const classData = data?.class_averages || [];
  const gradeDistribution = (data?.grade_distribution || []).map((item: any) => ({
    ...item,
    color: gradeColors[item.name] || "#60a5fa",
  }));
  const radarData = data?.subject_competency || [];

  return (
    <AppLayout>
      <div className="space-y-6">
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4"
        >
          <div>
            <h1 className="text-2xl font-display font-bold text-foreground">Performance Analysis</h1>
            <p className="text-sm text-muted-foreground mt-1">Deep dive into student academic performance</p>
          </div>
          <div className="flex gap-2">
            <Button variant="glass" size="sm">
              <Filter className="h-4 w-4 mr-1" /> Live Data
            </Button>
            <Button variant="gradient" size="sm">
              <Download className="h-4 w-4 mr-1" /> Export
            </Button>
          </div>
        </motion.div>

        {isLoading ? (
          <div className="flex h-[50vh] items-center justify-center">
            <Loader2 className="h-8 w-8 animate-spin text-primary" />
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <GlassCard delay={0.2}>
              <h3 className="text-lg font-display font-semibold text-foreground mb-4">Score Trends Over Time</h3>
              <ResponsiveContainer width="100%" height={300}>
                <AreaChart data={monthlyData}>
                  <defs>
                    <linearGradient id="gAvg" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#a78bfa" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#a78bfa" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                  <XAxis dataKey="month" stroke="rgba(255,255,255,0.4)" fontSize={12} />
                  <YAxis stroke="rgba(255,255,255,0.4)" fontSize={12} />
                  <Tooltip content={<CustomTooltip />} />
                  <Area type="monotone" dataKey="math" stroke="#a78bfa" fill="url(#gAvg)" name="Math" strokeWidth={2} />
                  <Area type="monotone" dataKey="science" stroke="#60a5fa" fill="url(#gAvg)" name="Science" strokeWidth={2} />
                  <Area type="monotone" dataKey="english" stroke="#34d399" fill="url(#gAvg)" name="English" strokeWidth={2} />
                </AreaChart>
              </ResponsiveContainer>
            </GlassCard>

            <GlassCard delay={0.3}>
              <h3 className="text-lg font-display font-semibold text-foreground mb-4">Class-wise Average</h3>
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={classData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                  <XAxis dataKey="name" stroke="rgba(255,255,255,0.4)" fontSize={12} />
                  <YAxis stroke="rgba(255,255,255,0.4)" fontSize={12} />
                  <Tooltip content={<CustomTooltip />} />
                  <Bar dataKey="avg" name="Average" radius={[8, 8, 0, 0]}>
                    {classData.map((_: any, i: number) => (
                      <Cell key={i} fill={`hsl(${240 + i * 12}, 75%, ${60 + i * 3}%)`} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </GlassCard>

            <GlassCard delay={0.4}>
              <h3 className="text-lg font-display font-semibold text-foreground mb-4">Grade Distribution</h3>
              <ResponsiveContainer width="100%" height={280}>
                <PieChart>
                  <Pie data={gradeDistribution} cx="50%" cy="50%" innerRadius={60} outerRadius={100} dataKey="value" strokeWidth={0}>
                    {gradeDistribution.map((entry: any, i: number) => (
                      <Cell key={i} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip content={<CustomTooltip />} />
                </PieChart>
              </ResponsiveContainer>
              <div className="flex justify-center gap-4 flex-wrap">
                {gradeDistribution.map((item: any) => (
                  <div key={item.name} className="flex items-center gap-1.5 text-xs text-muted-foreground">
                    <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: item.color }} />
                    {item.name} ({item.value})
                  </div>
                ))}
              </div>
            </GlassCard>

            <GlassCard delay={0.5} className="ai-glow">
              <h3 className="text-lg font-display font-semibold text-foreground mb-4">
                Subject Competency Radar
                <span className="ml-2 text-xs gradient-accent-text font-medium">Live</span>
              </h3>
              <ResponsiveContainer width="100%" height={300}>
                <RadarChart data={radarData}>
                  <PolarGrid stroke="rgba(255,255,255,0.1)" />
                  <PolarAngleAxis dataKey="subject" stroke="rgba(255,255,255,0.5)" fontSize={12} />
                  <Radar name="Score" dataKey="score" stroke="hsl(250, 90%, 65%)" fill="hsl(250, 90%, 65%)" fillOpacity={0.2} strokeWidth={2} />
                </RadarChart>
              </ResponsiveContainer>
            </GlassCard>
          </div>
        )}
      </div>
    </AppLayout>
  );
};

export default Performance;
