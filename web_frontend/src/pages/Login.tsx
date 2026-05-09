import { useState } from "react";
import { motion } from "framer-motion";
import {
  ArrowRight,
  Backpack,
  BookOpen,
  GraduationCap,
  Heart,
  Lock,
  Phone,
  Shield,
  User as UserIcon,
  Users,
} from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { useAuth, UserRole } from "@/contexts/AuthContext";
import {
  loginWithPassword,
  RequestedLoginRole,
  StudentLoginChoice,
  requestOtp,
  selectStudentProfile,
  verifyOtp,
} from "@/lib/auth";
import api from "@/lib/api";

const roles: { id: UserRole; label: string; icon: typeof Users; desc: string; color: string }[] = [
  { id: "admin", label: "Administrator", icon: Shield, desc: "School management & oversight", color: "from-primary/40 to-secondary/30" },
  { id: "teacher", label: "Teacher", icon: BookOpen, desc: "Classroom & student management", color: "from-emerald-500/40 to-teal-500/30" },
  { id: "student", label: "Student", icon: Backpack, desc: "My academics & learning", color: "from-amber-500/40 to-orange-500/30" },
  { id: "parent", label: "Parent", icon: Heart, desc: "Monitor child's progress", color: "from-rose-500/40 to-pink-500/30" },
];

const routes: Record<UserRole, string> = {
  admin: "/",
  teacher: "/teacher",
  student: "/student",
  parent: "/parent",
};

const Login = () => {
  const navigate = useNavigate();
  const { login } = useAuth();

  const [selectedRole, setSelectedRole] = useState<UserRole | null>(null);
  const [step, setStep] = useState<"role" | "phone" | "otp" | "password" | "student-select">("role");
  const [phone, setPhone] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [otp, setOtp] = useState(["", "", "", "", "", ""]);
  const [isLoading, setIsLoading] = useState(false);
  const [selectionToken, setSelectionToken] = useState("");
  const [studentChoices, setStudentChoices] = useState<StudentLoginChoice[]>([]);
  const [selectedStudentId, setSelectedStudentId] = useState("");

  const handleOtpChange = (index: number, value: string) => {
    if (value.length > 1) return;
    const next = [...otp];
    next[index] = value;
    setOtp(next);
    if (value && index < 5) {
      document.getElementById(`otp-${index + 1}`)?.focus();
    }
  };

  const resetOtpFlow = () => {
    setPhone("");
    setOtp(["", "", "", "", "", ""]);
    setSelectionToken("");
    setStudentChoices([]);
    setSelectedStudentId("");
  };

  const handleRoleSelect = (role: UserRole) => {
    setSelectedRole(role);
    resetOtpFlow();
    setUsername("");
    setPassword("");
    if (role === "admin" || role === "teacher") {
      setStep("password");
      return;
    }
    setStep("phone");
  };

  const handleSendOtp = async () => {
    if (!selectedRole || selectedRole === "admin" || selectedRole === "teacher") return;
    if (!phone.trim()) {
      toast.error("Please enter a phone number");
      return;
    }

    setIsLoading(true);
    try {
      await requestOtp(phone.trim(), selectedRole as RequestedLoginRole);
      setStep("otp");
      toast.success("OTP sent successfully");
    } catch (error: any) {
      toast.error(error.response?.data?.detail || "Failed to send OTP");
    } finally {
      setIsLoading(false);
    }
  };

  const handleVerify = async () => {
    if (!selectedRole || selectedRole === "admin" || selectedRole === "teacher") return;

    const otpCode = otp.join("");
    if (otpCode.length < 6) {
      toast.error("Please enter the 6-digit code");
      return;
    }

    setIsLoading(true);
    try {
      const response = await verifyOtp(phone.trim(), otpCode, selectedRole as RequestedLoginRole);

      if ("selection_required" in response) {
        setSelectionToken(response.selection_token);
        setStudentChoices(response.profiles);
        setSelectedStudentId(response.profiles[0]?.student_id || "");
        setStep("student-select");
        toast.success("Choose the student profile to continue");
        return;
      }

      login(response);
      navigate(routes[response.role as UserRole] || "/");
      toast.success("Login successful");
    } catch (error: any) {
      toast.error(error.response?.data?.detail || "Invalid OTP");
    } finally {
      setIsLoading(false);
    }
  };

  const handleStudentSelection = async () => {
    if (!selectedStudentId || !selectionToken) {
      toast.error("Select a student profile to continue");
      return;
    }

    setIsLoading(true);
    try {
      const response = await selectStudentProfile(selectionToken, selectedStudentId);
      login(response);
      navigate("/student");
      toast.success("Student profile selected");
    } catch (error: any) {
      toast.error(error.response?.data?.detail || "Could not finish student login");
    } finally {
      setIsLoading(false);
    }
  };

  const handlePasswordLogin = async () => {
    if (!username.trim() || !password) {
      toast.error("Please enter both username and password");
      return;
    }

    setIsLoading(true);
    try {
      const response = await loginWithPassword(username.trim(), password);
      login(response);
      navigate(routes[response.role as UserRole] || "/");
      toast.success(
        response.role === "teacher" ? "Welcome back, Teacher" : "Welcome back, Administrator",
      );
    } catch (error: any) {
      toast.error(error.response?.data?.detail || "Invalid credentials");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-slate-950 p-4">
      <div className="absolute left-20 top-20 h-72 w-72 rounded-full bg-primary/20 blur-[120px] animate-float" />
      <div className="absolute bottom-20 right-20 h-96 w-96 rounded-full bg-accent/15 blur-[120px] animate-float" style={{ animationDelay: "2s" }} />
      <div className="absolute left-1/2 top-1/2 h-80 w-80 -translate-x-1/2 -translate-y-1/2 rounded-full bg-secondary/10 blur-[100px]" />

      <motion.div
        initial={{ opacity: 0, y: 30 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6 }}
        className="glass-strong relative w-full max-w-md p-8 md:p-12"
      >
        <div className="mb-8 flex items-center justify-center gap-3">
          <div className="glow-primary flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-primary to-secondary">
            <GraduationCap className="h-7 w-7 text-white" />
          </div>
          <h1 className="gradient-text text-2xl font-display font-bold">EduTrack</h1>
        </div>

        {step === "role" && (
          <motion.div key="role" initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }} className="space-y-5">
            <div className="space-y-2 text-center">
              <h2 className="text-xl font-display font-semibold text-foreground">Welcome to EduTrack</h2>
              <p className="text-sm text-muted-foreground">Select your role to continue</p>
            </div>

            <div className="grid grid-cols-2 gap-3">
              {roles.map((role) => (
                <button
                  key={role.id}
                  onClick={() => handleRoleSelect(role.id)}
                  className="group rounded-2xl border border-white/[0.08] bg-white/[0.03] p-4 text-left transition-all duration-300 hover:border-white/[0.15] hover:bg-white/[0.06]"
                >
                  <div className={`mb-3 flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br ${role.color} transition-transform duration-300 group-hover:scale-110`}>
                    <role.icon className="h-5 w-5 text-foreground" />
                  </div>
                  <p className="text-sm font-semibold text-foreground">{role.label}</p>
                  <p className="mt-0.5 text-[10px] text-muted-foreground">{role.desc}</p>
                </button>
              ))}
            </div>
          </motion.div>
        )}

        {step === "password" && (
          <motion.div key="password" initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }} className="space-y-6">
            <div className="space-y-2 text-center">
              <div className="mb-1 flex items-center justify-center gap-2">
                <span className="rounded-full bg-primary/15 px-2.5 py-1 text-xs font-medium text-primary">
                  {selectedRole === "teacher" ? "Teacher" : "Administrator"}
                </span>
              </div>
              <h2 className="text-xl font-display font-semibold text-foreground">
                {selectedRole === "teacher" ? "Teacher Login" : "Admin Login"}
              </h2>
              <p className="text-sm text-muted-foreground">
                Enter your username and password to continue
              </p>
            </div>

            <div className="space-y-4">
              <div className="space-y-2">
                <div className="relative">
                  <UserIcon className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                  <input
                    type="text"
                    placeholder="Username"
                    value={username}
                    onChange={(event) => setUsername(event.target.value)}
                    className="glass-input w-full py-3 pl-12 pr-4 text-sm"
                  />
                </div>
                <div className="relative">
                  <Lock className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                  <input
                    type="password"
                    placeholder="Password"
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    className="glass-input w-full py-3 pl-12 pr-4 text-sm"
                  />
                </div>
              </div>

              <Button variant="gradient" className="h-12 w-full py-3" onClick={handlePasswordLogin} disabled={isLoading}>
                {isLoading ? "Authenticating..." : selectedRole === "teacher" ? "Login to Dashboard" : "Login to Console"} <ArrowRight className="ml-2 h-4 w-4" />
              </Button>

              <div className="space-y-3 text-center">
                {selectedRole === "admin" && (
                  <p className="text-xs text-muted-foreground">
                    Don&apos;t have an institution registered?{" "}
                    <Link to="/register-admin" className="font-medium text-primary hover:underline">
                      Register as Administrator
                    </Link>
                  </p>
                )}
                <button
                  onClick={() => {
                    setStep("role");
                    setSelectedRole(null);
                  }}
                  className="w-full text-center text-xs text-muted-foreground transition-colors hover:text-foreground"
                >
                  Back to role selection
                </button>
              </div>
            </div>
          </motion.div>
        )}

        {step === "phone" && (
          <motion.div key="phone" initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }} className="space-y-6">
            <div className="space-y-2 text-center">
              <div className="mb-1 flex items-center justify-center gap-2">
                <span className="rounded-full bg-primary/15 px-2.5 py-1 text-xs font-medium capitalize text-primary">
                  {selectedRole}
                </span>
              </div>
              <h2 className="text-xl font-display font-semibold text-foreground">Enter Phone Number</h2>
              <p className="text-sm text-muted-foreground">We&apos;ll send you a verification code</p>
            </div>

            <div className="space-y-4">
              <div className="relative">
                <Phone className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <input
                  type="tel"
                  placeholder="+91 Enter phone number"
                  value={phone}
                  onChange={(event) => setPhone(event.target.value)}
                  className="glass-input w-full py-3 pl-12 pr-4 text-sm"
                />
              </div>

              <Button variant="gradient" className="h-12 w-full py-3" onClick={handleSendOtp} disabled={isLoading}>
                {isLoading ? "Sending..." : "Get Login Code"} <ArrowRight className="ml-2 h-4 w-4" />
              </Button>

              <button
                onClick={() => {
                  setStep("role");
                  setSelectedRole(null);
                }}
                className="w-full text-center text-xs text-muted-foreground transition-colors hover:text-foreground"
              >
                Back to role selection
              </button>
            </div>
          </motion.div>
        )}

        {step === "otp" && (
          <motion.div key="otp" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} className="space-y-6">
            <div className="space-y-2 text-center">
              <Shield className="mx-auto mb-2 h-10 w-10 text-primary" />
              <h2 className="text-xl font-display font-semibold text-foreground">Verification</h2>
              <p className="text-sm text-muted-foreground">Enter the 6-digit code sent to your phone</p>
            </div>

            <div className="flex justify-center gap-2">
              {otp.map((digit, index) => (
                <input
                  key={index}
                  id={`otp-${index}`}
                  type="text"
                  inputMode="numeric"
                  maxLength={1}
                  value={digit}
                  onChange={(event) => handleOtpChange(index, event.target.value)}
                  className="glass-input h-14 w-12 rounded-xl text-center text-lg font-bold outline-none transition-all focus:border-primary/50"
                />
              ))}
            </div>

            <Button variant="gradient" className="h-12 w-full py-3" onClick={handleVerify} disabled={isLoading}>
              {isLoading ? "Verifying..." : "Verify & Enter"} <ArrowRight className="ml-2 h-4 w-4" />
            </Button>

            <div className="flex items-center justify-between">
              <button onClick={() => setStep("phone")} className="text-xs text-muted-foreground transition-colors hover:text-foreground">
                Change number
              </button>
              <button onClick={handleSendOtp} className="text-xs text-primary hover:underline">
                Resend code
              </button>
            </div>
          </motion.div>
        )}

        {step === "student-select" && (
          <motion.div key="student-select" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} className="space-y-6">
            <div className="space-y-2 text-center">
              <Backpack className="mx-auto mb-2 h-10 w-10 text-amber-400" />
              <h2 className="text-xl font-display font-semibold text-foreground">Choose Student Profile</h2>
              <p className="text-sm text-muted-foreground">This phone is linked to more than one student account.</p>
            </div>

            <div className="space-y-3">
              {studentChoices.map((profile) => {
                const selected = profile.student_id === selectedStudentId;
                return (
                  <button
                    key={profile.student_id}
                    onClick={() => setSelectedStudentId(profile.student_id)}
                    className={`w-full rounded-2xl border p-4 text-left transition-all ${
                      selected
                        ? "border-amber-400/40 bg-amber-500/10"
                        : "border-white/[0.08] bg-white/[0.03] hover:bg-white/[0.06]"
                    }`}
                  >
                    <p className="text-sm font-semibold text-foreground">{profile.full_name}</p>
                    <p className="mt-1 text-xs text-muted-foreground">Admission: {profile.admission_number}</p>
                    <p className="mt-1 text-xs text-muted-foreground">Roll: {profile.roll_number || "Not assigned"}</p>
                  </button>
                );
              })}
            </div>

            <Button variant="gradient" className="h-12 w-full py-3" onClick={handleStudentSelection} disabled={isLoading}>
              {isLoading ? "Opening profile..." : "Continue as Student"} <ArrowRight className="ml-2 h-4 w-4" />
            </Button>

            <button
              onClick={() => {
                setSelectedRole(null);
                resetOtpFlow();
                setStep("role");
              }}
              className="w-full text-center text-xs text-muted-foreground transition-colors hover:text-foreground"
            >
              Start over
            </button>
          </motion.div>
        )}
      </motion.div>
    </div>
  );
};

export default Login;
