import { useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import {
  LayoutDashboard, Sparkles, BookOpen, BarChart3,
  Settings, ChevronLeft, ChevronRight, GraduationCap, Bell,
} from "lucide-react";
import { cn } from "@/lib/utils";

const navItems = [
  { label: "My Dashboard", icon: LayoutDashboard, path: "/student" },
  { label: "AI Coach", icon: Sparkles, path: "/student/coach" },
  { label: "Weekly Path", icon: BookOpen, path: "/student/path" },
  { label: "My Charts", icon: BarChart3, path: "/student/charts" },
  { label: "Notifications", icon: Bell, path: "/student/notifications" },
  { label: "Settings", icon: Settings, path: "/student/settings" },
];

const StudentSidebar = () => {
  const [collapsed, setCollapsed] = useState(false);
  const location = useLocation();

  return (
    <motion.aside
      animate={{ width: collapsed ? 72 : 260 }}
      transition={{ duration: 0.3, ease: "easeInOut" }}
      className="fixed left-0 top-0 h-screen z-40 glass-strong flex flex-col border-r border-white/[0.08]"
    >
      <div className="h-16 flex items-center px-4 border-b border-white/[0.08]">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-amber-500 to-orange-500 flex items-center justify-center flex-shrink-0">
            <GraduationCap className="h-5 w-5 text-white" />
          </div>
          <AnimatePresence>
            {!collapsed && (
              <motion.div initial={{ opacity: 0, width: 0 }} animate={{ opacity: 1, width: "auto" }}
                exit={{ opacity: 0, width: 0 }} className="overflow-hidden whitespace-nowrap">
                <span className="font-display font-bold text-lg gradient-text">EduTrack</span>
                <span className="block text-[10px] text-amber-400 -mt-1">Student Portal</span>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>

      <nav className="flex-1 py-4 px-3 space-y-1 overflow-y-auto scrollbar-hidden">
        {navItems.map((item) => {
          const isActive = location.pathname === item.path;
          return (
            <Link key={item.path} to={item.path}
              className={cn(
                "flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all duration-300 group relative",
                isActive ? "bg-amber-500/20 text-foreground" : "text-muted-foreground hover:bg-white/[0.06] hover:text-foreground"
              )}>
              {isActive && (
                <motion.div layoutId="student-sidebar-active"
                  className="absolute inset-0 rounded-xl bg-amber-500/15 border border-amber-500/20"
                  transition={{ type: "spring", bounce: 0.2, duration: 0.6 }} />
              )}
              <item.icon className={cn("h-5 w-5 flex-shrink-0 relative z-10", isActive && "text-amber-400")} />
              <AnimatePresence>
                {!collapsed && (
                  <motion.span initial={{ opacity: 0, width: 0 }} animate={{ opacity: 1, width: "auto" }}
                    exit={{ opacity: 0, width: 0 }}
                    className="text-sm font-medium whitespace-nowrap overflow-hidden relative z-10">
                    {item.label}
                  </motion.span>
                )}
              </AnimatePresence>
            </Link>
          );
        })}
      </nav>

      <div className="p-3 border-t border-white/[0.08]">
        <button onClick={() => setCollapsed(!collapsed)}
          className="w-full flex items-center justify-center p-2 rounded-xl hover:bg-white/[0.06] text-muted-foreground transition-all duration-300">
          {collapsed ? <ChevronRight className="h-5 w-5" /> : <ChevronLeft className="h-5 w-5" />}
        </button>
      </div>
    </motion.aside>
  );
};

export default StudentSidebar;
