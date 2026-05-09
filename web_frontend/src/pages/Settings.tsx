import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import AppLayout from "@/components/AppLayout";
import GlassCard from "@/components/GlassCard";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/contexts/AuthContext";
import api from "@/lib/api";
import {
  User, Shield, Globe, Palette, Bell, Key, Monitor, Save,
  ChevronRight, LogOut, Mail, Phone,
} from "lucide-react";
import { toast } from "sonner";

const settingsSections = [
  { id: "profile", label: "Profile", icon: User },
  { id: "security", label: "Security", icon: Shield },
  { id: "notifications", label: "Notifications", icon: Bell },
  { id: "appearance", label: "Appearance", icon: Palette },
  { id: "language", label: "Language", icon: Globe },
];

type MeResponse = {
  id: string;
  phone: string;
  full_name: string | null;
  role: string;
  language_pref: string;
  school_id: string | null;
};

type UserSettingsResponse = {
  theme: string;
  language: string;
  email_notifications: boolean;
  sms_notifications: boolean;
  push_notifications: boolean;
  custom_prefs?: Record<string, any> | null;
};

const ToggleSwitch = ({ enabled, onToggle }: { enabled: boolean; onToggle: () => void }) => (
  <button onClick={onToggle}
    className={`w-11 h-6 rounded-full transition-all duration-300 relative ${
      enabled ? "bg-primary/60" : "bg-white/[0.1]"
    }`}>
    <motion.div
      animate={{ x: enabled ? 20 : 2 }}
      transition={{ type: "spring", stiffness: 500, damping: 30 }}
      className={`w-5 h-5 rounded-full absolute top-0.5 ${
        enabled ? "bg-primary" : "bg-muted-foreground/60"
      }`}
    />
  </button>
);

const Settings = () => {
  const queryClient = useQueryClient();
  const { logout } = useAuth();
  const [activeSection, setActiveSection] = useState("profile");

  const { data: me } = useQuery<MeResponse>({
    queryKey: ["me"],
    queryFn: async () => {
      const response = await api.get("/identity/me");
      return response.data;
    },
  });

  const { data: settings } = useQuery<UserSettingsResponse>({
    queryKey: ["user-settings"],
    queryFn: async () => {
      const response = await api.get("/platform/settings");
      return response.data;
    },
  });

  const [profileForm, setProfileForm] = useState({ full_name: "", language_pref: "en" });
  const [securityState, setSecurityState] = useState({ two_factor: false });

  const [prefs, setPrefs] = useState({
    theme: "light",
    language: "en",
    email_notifications: true,
    sms_notifications: true,
    push_notifications: true,
  });

  useEffect(() => {
    if (!me || !settings) return;
    setProfileForm({
      full_name: me.full_name || "",
      language_pref: me.language_pref || "en",
    });
    setSecurityState({
      two_factor: Boolean(settings.custom_prefs?.two_factor),
    });
    setPrefs({
      theme: settings.theme || "light",
      language: settings.language || "en",
      email_notifications: settings.email_notifications,
      sms_notifications: settings.sms_notifications,
      push_notifications: settings.push_notifications,
    });
  }, [me, settings]);

  const profileMutation = useMutation({
    mutationFn: async () => {
      await api.patch("/identity/me", profileForm);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["me"] });
      toast.success("Profile updated.");
    },
    onError: () => toast.error("Unable to update profile."),
  });

  const settingsMutation = useMutation({
    mutationFn: async (payload: Partial<UserSettingsResponse> & { custom_prefs?: Record<string, any> }) => {
      await api.patch("/platform/settings", null, { params: payload });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["user-settings"] });
      toast.success("Settings saved.");
    },
    onError: () => toast.error("Unable to save settings."),
  });

  const saveNotificationSettings = () => {
    settingsMutation.mutate({
      email_notifications: prefs.email_notifications,
      sms_notifications: prefs.sms_notifications,
      push_notifications: prefs.push_notifications,
    });
  };

  const saveAppearanceSettings = () => {
    settingsMutation.mutate({ theme: prefs.theme });
  };

  const saveLanguageSettings = () => {
    Promise.all([
      api.patch("/identity/me", { language_pref: profileForm.language_pref }),
      api.patch("/platform/settings", null, { params: { language: prefs.language } }),
    ])
      .then(() => {
        queryClient.invalidateQueries({ queryKey: ["me"] });
        queryClient.invalidateQueries({ queryKey: ["user-settings"] });
        toast.success("Language settings updated.");
      })
      .catch(() => toast.error("Unable to save language settings."));
  };

  const saveSecuritySettings = () => {
    settingsMutation.mutate({
      custom_prefs: {
        ...(settings?.custom_prefs || {}),
        two_factor: securityState.two_factor,
      },
    });
  };

  return (
    <AppLayout>
      <div className="space-y-6">
        <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}>
          <h1 className="text-2xl font-display font-bold text-foreground">Settings</h1>
          <p className="text-sm text-muted-foreground mt-1">Manage your account and preferences</p>
        </motion.div>

        <div className="grid grid-cols-1 lg:grid-cols-[240px_1fr] gap-6">
          <GlassCard delay={0.05} hover={false} className="p-2 h-fit">
            <nav className="space-y-1">
              {settingsSections.map((section) => (
                <button key={section.id} onClick={() => setActiveSection(section.id)}
                  className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-200 ${
                    activeSection === section.id
                      ? "bg-primary/15 text-foreground border border-primary/20"
                      : "text-muted-foreground hover:bg-white/[0.04] border border-transparent"
                  }`}>
                  <section.icon className={`h-4 w-4 ${activeSection === section.id ? "text-primary" : ""}`} />
                  {section.label}
                  <ChevronRight className="h-3.5 w-3.5 ml-auto opacity-50" />
                </button>
              ))}
              <div className="border-t border-white/[0.06] my-2" />
              <button
                onClick={logout}
                className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium text-red-400 hover:bg-red-500/10 transition-all border border-transparent"
              >
                <LogOut className="h-4 w-4" /> Logout
              </button>
            </nav>
          </GlassCard>

          <div className="space-y-6">
            {activeSection === "profile" && (
              <motion.div key="profile" initial={{ opacity: 0, x: 10 }} animate={{ opacity: 1, x: 0 }} className="space-y-6">
                <GlassCard hover={false} delay={0.1}>
                  <h3 className="text-lg font-display font-semibold text-foreground mb-6">Profile Information</h3>
                  <div className="flex items-center gap-5 mb-6">
                    <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-primary/40 to-accent/30 flex items-center justify-center text-2xl font-bold text-foreground">
                      {(me?.full_name || me?.role || "U").slice(0, 1).toUpperCase()}
                    </div>
                    <div>
                      <p className="font-semibold text-foreground">{me?.full_name || "User"}</p>
                      <p className="text-sm text-muted-foreground capitalize">{me?.role || "Account"}</p>
                    </div>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div className="space-y-1.5">
                      <label className="text-xs text-muted-foreground font-medium">Full Name</label>
                      <div className="relative">
                        <User className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                        <input
                          type="text"
                          value={profileForm.full_name}
                          onChange={(e) => setProfileForm((current) => ({ ...current, full_name: e.target.value }))}
                          className="w-full glass-input pl-10 pr-4 py-2.5 text-sm"
                        />
                      </div>
                    </div>
                    <div className="space-y-1.5">
                      <label className="text-xs text-muted-foreground font-medium">Phone</label>
                      <div className="relative">
                        <Phone className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                        <input type="text" value={me?.phone || ""} disabled className="w-full glass-input pl-10 pr-4 py-2.5 text-sm disabled:opacity-50" />
                      </div>
                    </div>
                    <div className="space-y-1.5">
                      <label className="text-xs text-muted-foreground font-medium">Role</label>
                      <div className="relative">
                        <Shield className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                        <input type="text" value={me?.role || ""} disabled className="w-full glass-input pl-10 pr-4 py-2.5 text-sm capitalize disabled:opacity-50" />
                      </div>
                    </div>
                    <div className="space-y-1.5">
                      <label className="text-xs text-muted-foreground font-medium">Language Preference</label>
                      <div className="relative">
                        <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                        <input type="text" value={profileForm.language_pref} disabled className="w-full glass-input pl-10 pr-4 py-2.5 text-sm disabled:opacity-50" />
                      </div>
                    </div>
                  </div>
                  <Button variant="gradient" size="sm" className="mt-6 gap-1.5" onClick={() => profileMutation.mutate()}>
                    <Save className="h-4 w-4" /> Save Changes
                  </Button>
                </GlassCard>
              </motion.div>
            )}

            {activeSection === "security" && (
              <motion.div key="security" initial={{ opacity: 0, x: 10 }} animate={{ opacity: 1, x: 0 }} className="space-y-6">
                <GlassCard hover={false} delay={0.1}>
                  <h3 className="text-lg font-display font-semibold text-foreground mb-6">Security Settings</h3>
                  <div className="space-y-5">
                    <div className="flex items-center justify-between p-4 rounded-xl bg-white/[0.02]">
                      <div className="flex items-center gap-3">
                        <Key className="h-5 w-5 text-primary" />
                        <div>
                          <p className="text-sm font-medium text-foreground">Two-Factor Authentication</p>
                          <p className="text-xs text-muted-foreground">Stored in user custom preferences</p>
                        </div>
                      </div>
                      <ToggleSwitch enabled={securityState.two_factor} onToggle={() => setSecurityState((current) => ({ ...current, two_factor: !current.two_factor }))} />
                    </div>
                    <div className="flex items-center justify-between p-4 rounded-xl bg-white/[0.02]">
                      <div className="flex items-center gap-3">
                        <Monitor className="h-5 w-5 text-secondary" />
                        <div>
                          <p className="text-sm font-medium text-foreground">Active Sessions</p>
                          <p className="text-xs text-muted-foreground">Session management is not exposed yet, but this section is now live-backed.</p>
                        </div>
                      </div>
                    </div>
                    <Button variant="gradient" size="sm" className="gap-1.5" onClick={saveSecuritySettings}>
                      <Save className="h-4 w-4" /> Save Security Settings
                    </Button>
                  </div>
                </GlassCard>
              </motion.div>
            )}

            {activeSection === "notifications" && (
              <motion.div key="notifications" initial={{ opacity: 0, x: 10 }} animate={{ opacity: 1, x: 0 }} className="space-y-6">
                <GlassCard hover={false} delay={0.1}>
                  <h3 className="text-lg font-display font-semibold text-foreground mb-6">Notification Preferences</h3>
                  <div className="space-y-4">
                    {[
                      { label: "Email Notifications", desc: "Receive reports and alerts via email", key: "email_notifications" as const },
                      { label: "Push Notifications", desc: "Browser and mobile push alerts", key: "push_notifications" as const },
                      { label: "SMS Notifications", desc: "Text message alerts for critical events", key: "sms_notifications" as const },
                    ].map((item) => (
                      <div key={item.label} className="flex items-center justify-between p-4 rounded-xl bg-white/[0.02]">
                        <div>
                          <p className="text-sm font-medium text-foreground">{item.label}</p>
                          <p className="text-xs text-muted-foreground">{item.desc}</p>
                        </div>
                        <ToggleSwitch enabled={prefs[item.key]} onToggle={() => setPrefs((current) => ({ ...current, [item.key]: !current[item.key] }))} />
                      </div>
                    ))}
                  </div>
                  <Button variant="gradient" size="sm" className="gap-1.5 mt-6" onClick={saveNotificationSettings}>
                    <Save className="h-4 w-4" /> Save Notification Preferences
                  </Button>
                </GlassCard>
              </motion.div>
            )}

            {activeSection === "appearance" && (
              <motion.div key="appearance" initial={{ opacity: 0, x: 10 }} animate={{ opacity: 1, x: 0 }}>
                <GlassCard hover={false} delay={0.1}>
                  <h3 className="text-lg font-display font-semibold text-foreground mb-6">Appearance</h3>
                  <div className="space-y-4">
                    <p className="text-sm text-muted-foreground">Theme</p>
                    <div className="grid grid-cols-2 gap-3">
                      {[
                        { label: "Light", value: "light" },
                        { label: "Dark", value: "dark" },
                      ].map((theme) => (
                        <button key={theme.value}
                          onClick={() => setPrefs((current) => ({ ...current, theme: theme.value }))}
                          className={`p-4 rounded-xl text-sm font-medium transition-all ${
                            prefs.theme === theme.value
                              ? "bg-primary/15 text-foreground border border-primary/30"
                              : "bg-white/[0.03] text-muted-foreground border border-white/[0.06] hover:bg-white/[0.05]"
                          }`}>
                          <Palette className={`h-5 w-5 mb-2 ${prefs.theme === theme.value ? "text-primary" : ""}`} />
                          {theme.label}
                        </button>
                      ))}
                    </div>
                    <Button variant="gradient" size="sm" className="gap-1.5 mt-2" onClick={saveAppearanceSettings}>
                      <Save className="h-4 w-4" /> Save Theme
                    </Button>
                  </div>
                </GlassCard>
              </motion.div>
            )}

            {activeSection === "language" && (
              <motion.div key="language" initial={{ opacity: 0, x: 10 }} animate={{ opacity: 1, x: 0 }}>
                <GlassCard hover={false} delay={0.1}>
                  <h3 className="text-lg font-display font-semibold text-foreground mb-6">Language & Region</h3>
                  <div className="space-y-4">
                    <div className="space-y-1.5">
                      <label className="text-xs text-muted-foreground font-medium">Display Language</label>
                      <select
                        value={prefs.language}
                        onChange={(e) => setPrefs((current) => ({ ...current, language: e.target.value }))}
                        className="w-full glass-input px-4 py-2.5 text-sm rounded-xl"
                      >
                        <option value="en">English</option>
                        <option value="hi">Hindi</option>
                        <option value="ta">Tamil</option>
                        <option value="te">Telugu</option>
                        <option value="kn">Kannada</option>
                      </select>
                    </div>
                    <div className="space-y-1.5">
                      <label className="text-xs text-muted-foreground font-medium">Profile Language Preference</label>
                      <select
                        value={profileForm.language_pref}
                        onChange={(e) => setProfileForm((current) => ({ ...current, language_pref: e.target.value }))}
                        className="w-full glass-input px-4 py-2.5 text-sm rounded-xl"
                      >
                        <option value="en">English</option>
                        <option value="hi">Hindi</option>
                        <option value="ta">Tamil</option>
                        <option value="te">Telugu</option>
                        <option value="kn">Kannada</option>
                      </select>
                    </div>
                    <Button variant="gradient" size="sm" className="gap-1.5 mt-2" onClick={saveLanguageSettings}>
                      <Save className="h-4 w-4" /> Save
                    </Button>
                  </div>
                </GlassCard>
              </motion.div>
            )}
          </div>
        </div>
      </div>
    </AppLayout>
  );
};

export default Settings;
