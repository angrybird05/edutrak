import { motion, AnimatePresence } from "framer-motion";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import AppLayout from "@/components/AppLayout";
import GlassCard from "@/components/GlassCard";
import { Button } from "@/components/ui/button";
import {
  Bell, AlertTriangle, FileText, Calendar, CheckCircle2, Info, Trash2, CheckCheck,
} from "lucide-react";
import { toast } from "sonner";
import api from "@/lib/api";

type NotificationItem = {
  id: string;
  event_type: string;
  payload: Record<string, any>;
  channel: string;
  status: string;
  read_at: string | null;
  created_at: string;
};

const typeConfig: Record<string, { icon: typeof Bell; color: string; bg: string }> = {
  alert: { icon: AlertTriangle, color: "text-red-400", bg: "bg-red-500/20" },
  report: { icon: FileText, color: "text-sky-400", bg: "bg-sky-500/20" },
  attendance: { icon: Calendar, color: "text-emerald-400", bg: "bg-emerald-500/20" },
  success: { icon: CheckCircle2, color: "text-emerald-400", bg: "bg-emerald-500/20" },
  info: { icon: Info, color: "text-amber-400", bg: "bg-amber-500/20" },
};

const formatEventType = (eventType: string) => eventType.split(".").slice(-1)[0].replace(/_/g, " ");

const inferType = (item: NotificationItem): keyof typeof typeConfig => {
  const eventType = (item.event_type || "").toLowerCase();
  if (eventType.includes("attendance")) return "attendance";
  if (eventType.includes("report")) return "report";
  if (eventType.includes("alert") || eventType.includes("risk") || eventType.includes("warning")) return "alert";
  if (item.status === "read") return "info";
  return "success";
};

const getTitle = (item: NotificationItem) =>
  item.payload?.title || item.payload?.summary || formatEventType(item.event_type || "notification");

const getMessage = (item: NotificationItem) =>
  item.payload?.message || item.payload?.insight_text || item.payload?.summary || "Notification received.";

const formatTime = (value: string) => {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
};

const Notifications = () => {
  const queryClient = useQueryClient();

  const { data: notifications = [], isLoading } = useQuery<NotificationItem[]>({
    queryKey: ["notifications"],
    queryFn: async () => {
      const response = await api.get("/notifications");
      return response.data;
    },
  });

  const unreadCount = notifications.filter((item) => item.status !== "read").length;

  const markAllReadMutation = useMutation({
    mutationFn: async () => {
      await api.patch("/notifications/read-all");
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["notifications"] });
      toast.success("All notifications marked as read.");
    },
    onError: () => toast.error("Unable to mark notifications as read."),
  });

  const markReadMutation = useMutation({
    mutationFn: async (id: string) => {
      await api.patch(`/notifications/${id}/read`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["notifications"] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async (id: string) => {
      await api.delete(`/notifications/${id}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["notifications"] });
      toast.success("Notification dismissed.");
    },
    onError: () => toast.error("Unable to dismiss notification."),
  });

  return (
    <AppLayout>
      <div className="space-y-6">
        <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}
          className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-display font-bold text-foreground">Notifications</h1>
            <p className="text-sm text-muted-foreground mt-1">
              {unreadCount > 0 ? `${unreadCount} unread notification${unreadCount > 1 ? "s" : ""}` : "All caught up!"}
            </p>
          </div>
          <div className="flex gap-2">
            <Button
              variant="glass"
              size="sm"
              onClick={() => markAllReadMutation.mutate()}
              disabled={unreadCount === 0 || markAllReadMutation.isPending}
              className="gap-1.5 text-xs"
            >
              <CheckCheck className="h-4 w-4" /> Mark All Read
            </Button>
          </div>
        </motion.div>

        <div className="space-y-2">
          <AnimatePresence>
            {isLoading ? (
              <GlassCard delay={0.1} hover={false} className="text-center py-12">
                <Bell className="h-10 w-10 text-muted-foreground mx-auto mb-3 opacity-40" />
                <p className="text-sm text-muted-foreground">Loading notifications...</p>
              </GlassCard>
            ) : notifications.length === 0 ? (
              <GlassCard delay={0.1} hover={false} className="text-center py-12">
                <Bell className="h-10 w-10 text-muted-foreground mx-auto mb-3 opacity-40" />
                <p className="text-sm text-muted-foreground">No notifications to show</p>
              </GlassCard>
            ) : (
              notifications.map((notif, i) => {
                const type = inferType(notif);
                const config = typeConfig[type];
                const Icon = config.icon;
                const isRead = notif.status === "read";
                return (
                  <motion.div
                    key={notif.id}
                    layout
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: 30, height: 0, marginBottom: 0 }}
                    transition={{ delay: 0.02 * i }}
                    className={`glass-card p-4 flex items-start gap-4 group cursor-pointer ${!isRead ? "border-l-2 border-l-primary" : ""}`}
                    onClick={() => {
                      if (!isRead) markReadMutation.mutate(notif.id);
                    }}
                  >
                    <div className={`p-2.5 rounded-xl flex-shrink-0 ${config.bg}`}>
                      <Icon className={`h-4 w-4 ${config.color}`} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <p className={`text-sm font-medium ${isRead ? "text-muted-foreground" : "text-foreground"}`}>
                          {getTitle(notif)}
                        </p>
                        {!isRead && <span className="w-2 h-2 rounded-full bg-primary flex-shrink-0" />}
                      </div>
                      <p className="text-xs text-muted-foreground mt-0.5">{getMessage(notif)}</p>
                      <p className="text-[10px] text-muted-foreground/60 mt-1">{formatTime(notif.created_at)}</p>
                    </div>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        deleteMutation.mutate(notif.id);
                      }}
                      className="p-1.5 rounded-lg hover:bg-red-500/10 opacity-0 group-hover:opacity-100 transition-all flex-shrink-0"
                      disabled={deleteMutation.isPending}
                    >
                      <Trash2 className="h-3.5 w-3.5 text-muted-foreground hover:text-red-400" />
                    </button>
                  </motion.div>
                );
              })
            )}
          </AnimatePresence>
        </div>
      </div>
    </AppLayout>
  );
};

export default Notifications;
