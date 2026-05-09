import { useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import {
  LayoutDashboard, Heart, Bell, Shield,
  Settings, ChevronLeft, ChevronRight, GraduationCap,
} from "lucide-react";
import { cn } from "@/lib/utils";

const navItems = [
  { label: "Family Dashboard", icon: LayoutDashboard, path: "/parent" },
  { label: "Health Report", icon: Heart, path: "/parent/report" },
  { label: "Alerts", icon: Bell, path: "/parent/alerts" },
  { label: "Security & Link", icon: Shield, path: "/parent/security" },
  { label: "Settings", icon: Settings, path: "/parent/settings" },
];

const ParentSidebar = () => {
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
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-rose-500 to-pink-500 flex items-center justify-center flex-shrink-0">
            <GraduationCap className="h-5 w-5 text-white" />
          </div>
          <AnimatePresence>
            {!collapsed && (
              <motion.div initial={{ opacity: 0, width: 0 }} animate={{ opacity: 1, width: "auto" }}
                exit={{ opacity: 0, width: 0 }} className="overflow-hidden whitespace-nowrap">
                <span className="font-display font-bold text-lg gradient-text">EduTrack</span>
                <span className="block text-[10px] text-rose-400 -mt-1">Parent Portal</span>
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
                isActive ? "bg-rose-500/20 text-foreground" : "text-muted-foreground hover:bg-white/[0.06] hover:text-foreground"
              )}>
              {isActive && (
                <motion.div layoutId="parent-sidebar-active"
                  className="absolute inset-0 rounded-xl bg-rose-500/15 border border-rose-500/20"
                  transition={{ type: "spring", bounce: 0.2, duration: 0.6 }} />
              )}
              <item.icon className={cn("h-5 w-5 flex-shrink-0 relative z-10", isActive && "text-rose-400")} />
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

export default ParentSidebar;
