import { ReactNode } from "react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";

interface GlassCardProps {
  children: ReactNode;
  className?: string;
  hover?: boolean;
  glow?: "primary" | "accent" | "none";
  delay?: number;
}

const GlassCard = ({ children, className, hover = true, glow = "none", delay = 0 }: GlassCardProps) => {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay }}
      className={cn(
        "glass-card p-6",
        hover && "glass-hover cursor-pointer",
        glow === "primary" && "glow-primary",
        glow === "accent" && "glow-accent",
        className
      )}
    >
      {children}
    </motion.div>
  );
};

export default GlassCard;
