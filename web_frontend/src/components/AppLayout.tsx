import { ReactNode } from "react";
import { motion } from "framer-motion";
import Navbar from "./Navbar";
import { useAuth, UserRole } from "@/contexts/AuthContext";
import AdminSidebar from "./sidebars/AdminSidebar";
import TeacherSidebar from "./sidebars/TeacherSidebar";
import StudentSidebar from "./sidebars/StudentSidebar";
import ParentSidebar from "./sidebars/ParentSidebar";

interface AppLayoutProps {
  children: ReactNode;
}

const AppLayout = ({ children }: AppLayoutProps) => {
  const { role } = useAuth();

  const SidebarComponent = (() => {
    switch (role) {
      case "teacher": return TeacherSidebar;
      case "student": return StudentSidebar;
      case "parent": return ParentSidebar;
      default: return AdminSidebar;
    }
  })();

  return (
    <div className="min-h-screen flex">
      <SidebarComponent />
      <div className="flex-1 ml-[260px] transition-all duration-300 flex flex-col">
        <Navbar />
        <motion.main
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.3 }}
          className="flex-1 p-6"
        >
          {children}
        </motion.main>
      </div>
    </div>
  );
};

export default AppLayout;
