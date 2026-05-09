import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Route, Routes, Navigate } from "react-router-dom";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { Toaster } from "@/components/ui/toaster";
import { TooltipProvider } from "@/components/ui/tooltip";
import { AuthProvider, useAuth } from "@/contexts/AuthContext";

// Admin pages
import Dashboard from "./pages/Dashboard";
import Students from "./pages/Students";
import Teachers from "./pages/Teachers";
import Performance from "./pages/Performance";
import Attendance from "./pages/Attendance";
import Gradebook from "./pages/Gradebook";
import AIInsights from "./pages/AIInsights";
import Reports from "./pages/Reports";
import Academics from "./pages/Academics";
import Settings from "./pages/Settings";
import Notifications from "./pages/Notifications";

// Role-specific pages
import Login from "./pages/Login";
import TeacherDashboard from "./pages/TeacherDashboard";
import StudentDashboard from "./pages/StudentDashboard";
import ParentDashboard from "./pages/ParentDashboard";
import RegisterAdmin from "./pages/RegisterAdmin";
import NotFound from "./pages/NotFound";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000,
      refetchOnMount: false,
      refetchOnWindowFocus: false,
      refetchOnReconnect: false,
    },
  },
});

const RoleRedirect = () => {
  const { role, isAuthenticated } = useAuth();
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  switch (role) {
    case "teacher": return <Navigate to="/teacher" replace />;
    case "student": return <Navigate to="/student" replace />;
    case "parent": return <Navigate to="/parent" replace />;
    default: return <Dashboard />;
  }
};

const AppRoutes = () => {
  const { isAuthenticated, role } = useAuth();

  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/register-admin" element={<RegisterAdmin />} />

      {/* Root redirect */}
      <Route path="/" element={<RoleRedirect />} />

      {/* Admin routes */}
      <Route path="/students" element={<Students />} />
      <Route path="/teachers" element={<Teachers />} />
      <Route path="/performance" element={<Performance />} />
      <Route path="/academics" element={<Academics />} />
      <Route path="/attendance" element={<Attendance />} />
      <Route path="/gradebook" element={<Gradebook />} />
      <Route path="/ai-insights" element={<AIInsights />} />
      <Route path="/reports" element={<Reports />} />
      <Route path="/notifications" element={<Notifications />} />
      <Route path="/settings" element={<Settings />} />

      {/* Teacher routes */}
      <Route path="/teacher" element={<TeacherDashboard />} />
      <Route path="/teacher/attendance" element={<Attendance />} />
      <Route path="/teacher/gradebook" element={<Gradebook />} />
      <Route path="/teacher/ai-insights" element={<AIInsights />} />
      <Route path="/teacher/students" element={<Students />} />
      <Route path="/teacher/reports" element={<Reports />} />
      <Route path="/teacher/notifications" element={<Notifications />} />
      <Route path="/teacher/settings" element={<Settings />} />

      {/* Student routes */}
      <Route path="/student" element={<StudentDashboard />} />
      <Route path="/student/coach" element={<StudentDashboard />} />
      <Route path="/student/path" element={<StudentDashboard />} />
      <Route path="/student/charts" element={<StudentDashboard />} />
      <Route path="/student/notifications" element={<Notifications />} />
      <Route path="/student/settings" element={<Settings />} />

      {/* Parent routes */}
      <Route path="/parent" element={<ParentDashboard />} />
      <Route path="/parent/report" element={<ParentDashboard />} />
      <Route path="/parent/alerts" element={<ParentDashboard />} />
      <Route path="/parent/security" element={<ParentDashboard />} />
      <Route path="/parent/settings" element={<Settings />} />

      <Route path="*" element={<NotFound />} />
    </Routes>
  );
};

const App = () => (
  <QueryClientProvider client={queryClient}>
    <TooltipProvider>
      <Toaster />
      <Sonner />
      <BrowserRouter>
        <AuthProvider>
          <AppRoutes />
        </AuthProvider>
      </BrowserRouter>
    </TooltipProvider>
  </QueryClientProvider>
);

export default App;
