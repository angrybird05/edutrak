import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { GraduationCap, ArrowRight, ArrowLeft, Shield, Building2, User as UserIcon, Lock, Mail, MapPin, Globe } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useNavigate, Link } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import api from "@/lib/api";
import { toast } from "sonner";

const RegisterAdmin = () => {
  const [step, setStep] = useState(1);
  const [formData, setFormData] = useState({
    full_name: "",
    username: "",
    password: "",
    school_name: "",
    school_email: "",
    village: "",
    mandal: "",
    district_city: "",
    pincode: "",
  });
  const [isLoading, setIsLoading] = useState(false);
  const navigate = useNavigate();
  const { login } = useAuth();

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const nextStep = () => {
    if (step === 1 && (!formData.full_name || !formData.username || !formData.password)) {
      toast.error("Please fill in all administrator details");
      return;
    }
    setStep(step + 1);
  };

  const prevStep = () => setStep(step - 1);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.school_name || !formData.district_city || !formData.pincode) {
      toast.error("School name, District/City, and Pincode are required");
      return;
    }

    const payload = {
      ...formData,
      full_name: formData.full_name.trim(),
      username: formData.username.trim(),
      school_name: formData.school_name.trim(),
      school_email: formData.school_email.trim(),
      village: formData.village.trim(),
      mandal: formData.mandal.trim(),
      district_city: formData.district_city.trim(),
      pincode: formData.pincode.trim(),
    };

    setIsLoading(true);
    try {
      const response = await api.post("/user/auth/register/admin", payload);
      login(response.data);
      toast.success("Registration successful! Welcome to EduTrack.");
      navigate("/");
    } catch (error: any) {
      toast.error(error.response?.data?.detail || "Registration failed. Please try again.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4 relative overflow-hidden bg-slate-950">
      {/* Background orbs */}
      <div className="absolute top-20 left-20 w-72 h-72 bg-primary/20 rounded-full blur-[120px] animate-float" />
      <div className="absolute bottom-20 right-20 w-96 h-96 bg-accent/15 rounded-full blur-[120px] animate-float" style={{ animationDelay: "2s" }} />
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-80 h-80 bg-secondary/10 rounded-full blur-[100px]" />

      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        className="glass-strong p-8 md:p-12 w-full max-w-2xl relative"
      >
        <div className="flex items-center gap-3 mb-8 justify-center">
          <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-primary to-secondary flex items-center justify-center glow-primary">
            <GraduationCap className="h-7 w-7 text-white" />
          </div>
          <h1 className="text-2xl font-display font-bold gradient-text">EduTrack</h1>
        </div>

        <div className="mb-8">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-xl font-display font-semibold text-foreground">
              {step === 1 ? "Administrator Account" : "School Profile"}
            </h2>
            <span className="text-xs font-medium px-3 py-1 rounded-full bg-primary/10 text-primary border border-primary/20">
              Step {step} of 2
            </span>
          </div>
          <div className="h-1.5 w-full bg-white/5 rounded-full overflow-hidden">
            <motion.div 
              className="h-full bg-gradient-to-r from-primary to-secondary"
              initial={{ width: "50%" }}
              animate={{ width: step === 1 ? "50%" : "100%" }}
            />
          </div>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6">
          <AnimatePresence mode="wait">
            {step === 1 ? (
              <motion.div
                key="step1"
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 20 }}
                className="grid md:grid-cols-2 gap-4"
              >
                <div className="md:col-span-2 space-y-4">
                   <div className="relative">
                    <UserIcon className="absolute left-4 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                    <input
                      type="text"
                      name="full_name"
                      placeholder="Full Name"
                      value={formData.full_name}
                      onChange={handleChange}
                      className="w-full glass-input pl-12 pr-4 py-3 text-sm"
                    />
                  </div>
                  <div className="relative">
                    <Shield className="absolute left-4 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                    <input
                      type="text"
                      name="username"
                      placeholder="Custom Username (unique)"
                      value={formData.username}
                      onChange={handleChange}
                      className="w-full glass-input pl-12 pr-4 py-3 text-sm"
                    />
                  </div>
                  <div className="relative">
                    <Lock className="absolute left-4 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                    <input
                      type="password"
                      name="password"
                      placeholder="Secure Password"
                      value={formData.password}
                      onChange={handleChange}
                      className="w-full glass-input pl-12 pr-4 py-3 text-sm"
                    />
                  </div>
                </div>
              </motion.div>
            ) : (
              <motion.div
                key="step2"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                className="grid md:grid-cols-2 gap-4"
              >
                <div className="md:col-span-2 relative">
                  <Building2 className="absolute left-4 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                  <input
                    type="text"
                    name="school_name"
                    placeholder="Name of the School"
                    value={formData.school_name}
                    onChange={handleChange}
                    className="w-full glass-input pl-12 pr-4 py-3 text-sm"
                  />
                </div>
                <div className="md:col-span-2 relative">
                  <Mail className="absolute left-4 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                  <input
                    type="email"
                    name="school_email"
                    placeholder="School Email Address"
                    value={formData.school_email}
                    onChange={handleChange}
                    className="w-full glass-input pl-12 pr-4 py-3 text-sm"
                  />
                </div>
                <div className="relative">
                  <MapPin className="absolute left-4 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                  <input
                    type="text"
                    name="village"
                    placeholder="Village"
                    value={formData.village}
                    onChange={handleChange}
                    className="w-full glass-input pl-12 pr-4 py-3 text-sm"
                  />
                </div>
                <div className="relative">
                  <Globe className="absolute left-4 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                  <input
                    type="text"
                    name="mandal"
                    placeholder="Mandal"
                    value={formData.mandal}
                    onChange={handleChange}
                    className="w-full glass-input pl-12 pr-4 py-3 text-sm"
                  />
                </div>
                <div className="relative">
                  <MapPin className="absolute left-4 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                  <input
                    type="text"
                    name="district_city"
                    placeholder="District / City"
                    value={formData.district_city}
                    onChange={handleChange}
                    className="w-full glass-input pl-12 pr-4 py-3 text-sm"
                  />
                </div>
                <div className="relative">
                  <MapPin className="absolute left-4 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                  <input
                    type="text"
                    name="pincode"
                    placeholder="Pincode"
                    value={formData.pincode}
                    onChange={handleChange}
                    className="w-full glass-input pl-12 pr-4 py-3 text-sm"
                  />
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          <div className="flex gap-3 pt-4">
            {step === 2 && (
              <Button 
                type="button" 
                variant="outline" 
                className="flex-1 py-3 h-12 glass-button" 
                onClick={prevStep}
              >
                <ArrowLeft className="mr-2 h-4 w-4" /> Back
              </Button>
            )}
            {step === 1 ? (
              <Button 
                type="button" 
                variant="gradient" 
                className="w-full py-3 h-12" 
                onClick={nextStep}
              >
                School Details <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            ) : (
              <Button 
                type="submit" 
                variant="gradient" 
                className="flex-[2] py-3 h-12" 
                disabled={isLoading}
              >
                {isLoading ? "Setting up your institution..." : "Establish Institution"} <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            )}
          </div>

          <p className="text-center text-xs text-muted-foreground mt-4">
            Already have an account?{" "}
            <Link to="/login" className="text-primary hover:underline">
              Back to Login
            </Link>
          </p>
        </form>
      </motion.div>
    </div>
  );
};

export default RegisterAdmin;
