import { useDeferredValue, useEffect, useState } from "react";
import { motion } from "framer-motion";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  BookOpen,
  CalendarClock,
  CheckCircle2,
  KeyRound,
  Loader2,
  Mail,
  Pencil,
  Plus,
  Save,
  Search,
  ShieldCheck,
  Trash2,
  UserCog,
  Users,
} from "lucide-react";
import { toast } from "sonner";

import AppLayout from "@/components/AppLayout";
import GlassCard from "@/components/GlassCard";
import MetricCard from "@/components/MetricCard";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import api from "@/lib/api";

type Teacher = {
  id: string;
  full_name: string | null;
  username: string | null;
  phone: string;
  role: string;
  language_pref: string;
  is_active: boolean;
  school_id: string | null;
};

type TeacherListResponse = {
  items: Teacher[];
  total: number;
  page: number;
  page_size: number;
};

type UserProfile = {
  id: string;
  school_id: string | null;
};

type ClassItem = {
  id: string;
  name: string;
  class_number: number;
  school_id: string;
};

type SectionItem = {
  id: string;
  name: string;
  class_id: string;
};

type ClassWithSections = ClassItem & {
  sections: SectionItem[];
};

type SubjectItem = {
  id: string;
  name: string;
  code?: string | null;
  school_id: string;
};

type AssignmentSection = {
  id: string;
  name: string;
  class_id: string;
  class_name: string;
};

type AssignmentSubject = {
  id: string;
  name: string;
  code?: string | null;
};

type TimetableEntry = {
  id: string;
  section_id: string;
  section_name: string;
  class_id: string;
  class_name: string;
  subject_id: string;
  subject_name: string;
  teacher_id: string;
  day_of_week: number;
  start_time: string;
  end_time: string;
  room?: string | null;
};

type TeacherAssignments = {
  teacher_id: string;
  section_ids: string[];
  subject_ids: string[];
  sections: AssignmentSection[];
  subjects: AssignmentSubject[];
  timetable: TimetableEntry[];
};

const dayOptions = [
  { value: "0", label: "Sunday" },
  { value: "1", label: "Monday" },
  { value: "2", label: "Tuesday" },
  { value: "3", label: "Wednesday" },
  { value: "4", label: "Thursday" },
  { value: "5", label: "Friday" },
  { value: "6", label: "Saturday" },
];

const getErrorMessage = (error: any, fallback: string) =>
  error?.response?.data?.message || error?.response?.data?.detail || fallback;

const Teachers = () => {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const deferredSearch = useDeferredValue(search);
  const [selectedTeacherId, setSelectedTeacherId] = useState<string | null>(null);
  const [assignmentTab, setAssignmentTab] = useState("profile");
  const [createForm, setCreateForm] = useState({
    full_name: "",
    username: "",
    password: "",
    phone: "",
    language_pref: "en",
    is_active: true,
  });
  const [profileForm, setProfileForm] = useState({
    full_name: "",
    phone: "",
    language_pref: "en",
    is_active: true,
  });
  const [credentialsForm, setCredentialsForm] = useState({
    username: "",
    password: "",
  });
  const [sectionDraft, setSectionDraft] = useState<string[]>([]);
  const [subjectDraft, setSubjectDraft] = useState<string[]>([]);
  const [scheduleForm, setScheduleForm] = useState({
    section_id: "",
    subject_id: "",
    day_of_week: "1",
    start_time: "09:00",
    end_time: "10:00",
    room: "",
  });
  const [editingEntryId, setEditingEntryId] = useState<string | null>(null);

  const { data: me } = useQuery<UserProfile>({
    queryKey: ["me"],
    queryFn: async () => {
      const response = await api.get("/identity/me");
      return response.data;
    },
  });

  const schoolId = me?.school_id || null;

  const { data: teachersData, isLoading: teachersLoading } = useQuery<TeacherListResponse>({
    queryKey: ["teachers", deferredSearch],
    queryFn: async () => {
      const response = await api.get("/identity/teachers", {
        params: { search: deferredSearch || undefined, page_size: 100 },
      });
      return response.data;
    },
  });

  const { data: classesWithSections = [], isLoading: classesLoading } = useQuery<ClassWithSections[]>({
    queryKey: ["teacher-classes", schoolId],
    enabled: !!schoolId,
    queryFn: async () => {
      const classesResponse = await api.get(`/academic/classes/${schoolId}`);
      const classes: ClassItem[] = classesResponse.data;
      const sections = await Promise.all(
        classes.map(async (classItem) => {
          const response = await api.get(`/academic/sections/${classItem.id}`);
          return {
            ...classItem,
            sections: response.data as SectionItem[],
          };
        }),
      );
      return sections;
    },
  });

  const { data: subjects = [], isLoading: subjectsLoading } = useQuery<SubjectItem[]>({
    queryKey: ["teacher-subjects", schoolId],
    enabled: !!schoolId,
    queryFn: async () => {
      const response = await api.get(`/academic/subjects/${schoolId}`);
      return response.data;
    },
  });

  const selectedTeacher = teachersData?.items.find((teacher) => teacher.id === selectedTeacherId) || null;

  const { data: assignments, isLoading: assignmentsLoading } = useQuery<TeacherAssignments>({
    queryKey: ["teacher-assignments", selectedTeacherId],
    enabled: !!selectedTeacherId,
    queryFn: async () => {
      const response = await api.get(`/academic/teachers/${selectedTeacherId}/assignments`);
      return response.data;
    },
  });

  useEffect(() => {
    if (teachersLoading) {
      return;
    }
    if (!teachersData?.items.length) {
      setSelectedTeacherId(null);
      return;
    }
    const selectedStillExists = teachersData.items.some((teacher) => teacher.id === selectedTeacherId);
    if (!selectedTeacherId || !selectedStillExists) {
      setSelectedTeacherId(teachersData.items[0].id);
    }
  }, [teachersData, selectedTeacherId, teachersLoading]);

  useEffect(() => {
    if (!selectedTeacherId) {
      setProfileForm({ full_name: "", phone: "", language_pref: "en", is_active: true });
      setCredentialsForm({ username: "", password: "" });
      return;
    }
    if (!selectedTeacher || selectedTeacher.id !== selectedTeacherId) {
      return;
    }
    setProfileForm({
      full_name: selectedTeacher.full_name || "",
      phone: selectedTeacher.phone || "",
      language_pref: selectedTeacher.language_pref || "en",
      is_active: selectedTeacher.is_active,
    });
    setCredentialsForm({
      username: selectedTeacher.username || "",
      password: "",
    });
    setEditingEntryId(null);
    setScheduleForm({
      section_id: "",
      subject_id: "",
      day_of_week: "1",
      start_time: "09:00",
      end_time: "10:00",
      room: "",
    });
  }, [selectedTeacherId, selectedTeacher?.id]);

  useEffect(() => {
    if (!assignments) {
      setSectionDraft([]);
      setSubjectDraft([]);
      return;
    }
    setSectionDraft(assignments.section_ids);
    setSubjectDraft(assignments.subject_ids);
    setScheduleForm((current) => ({
      ...current,
      section_id:
        current.section_id && assignments.section_ids.includes(current.section_id)
          ? current.section_id
          : assignments.section_ids[0] || "",
      subject_id:
        current.subject_id && assignments.subject_ids.includes(current.subject_id)
          ? current.subject_id
          : assignments.subject_ids[0] || "",
    }));
  }, [assignments]);

  const createTeacherMutation = useMutation({
    mutationFn: async () => {
      const payload = {
        full_name: createForm.full_name.trim(),
        username: createForm.username.trim(),
        password: createForm.password,
        phone: createForm.phone.trim() || undefined,
        language_pref: createForm.language_pref,
        is_active: createForm.is_active,
      };
      const response = await api.post("/identity/teachers", payload);
      return response.data as Teacher;
    },
    onSuccess: (teacher) => {
      toast.success("Teacher account created.");
      setCreateForm({
        full_name: "",
        username: "",
        password: "",
        phone: "",
        language_pref: "en",
        is_active: true,
      });
      queryClient.invalidateQueries({ queryKey: ["teachers"] });
      setSelectedTeacherId(teacher.id);
      setAssignmentTab("profile");
    },
    onError: (error) => {
      const message =
        error?.response?.data?.message ||
        error?.response?.data?.detail ||
        (error?.request && !error?.response
          ? "Could not reach the backend. Please check that the API server is running."
          : "Unable to create teacher.");
      toast.error(message);
    },
  });

  const updateTeacherMutation = useMutation({
    mutationFn: async () => {
      if (!selectedTeacherId) return null;
      const response = await api.patch(`/identity/teachers/${selectedTeacherId}`, profileForm);
      return response.data as Teacher;
    },
    onSuccess: () => {
      toast.success("Teacher profile updated.");
      queryClient.invalidateQueries({ queryKey: ["teachers"] });
    },
    onError: (error) => {
      toast.error(getErrorMessage(error, "Unable to update teacher profile."));
    },
  });

  const updateCredentialsMutation = useMutation({
    mutationFn: async () => {
      if (!selectedTeacherId) return null;
      const payload = {
        username: credentialsForm.username.trim() || undefined,
        password: credentialsForm.password.trim() || undefined,
      };
      const response = await api.patch(`/identity/teachers/${selectedTeacherId}/credentials`, payload);
      return response.data as Teacher;
    },
    onSuccess: () => {
      toast.success("Teacher access updated.");
      setCredentialsForm((current) => ({ ...current, password: "" }));
      queryClient.invalidateQueries({ queryKey: ["teachers"] });
    },
    onError: (error) => {
      toast.error(getErrorMessage(error, "Unable to update teacher credentials."));
    },
  });

  const updateSectionsMutation = useMutation({
    mutationFn: async () => {
      if (!selectedTeacherId) return null;
      const response = await api.put(`/academic/teachers/${selectedTeacherId}/sections`, {
        section_ids: sectionDraft,
      });
      return response.data as TeacherAssignments;
    },
    onSuccess: () => {
      toast.success("Teacher class-section coverage updated.");
      queryClient.invalidateQueries({ queryKey: ["teacher-assignments", selectedTeacherId] });
    },
    onError: (error) => {
      toast.error(getErrorMessage(error, "Unable to update teacher sections."));
    },
  });

  const updateSubjectsMutation = useMutation({
    mutationFn: async () => {
      if (!selectedTeacherId) return null;
      const response = await api.put(`/academic/teachers/${selectedTeacherId}/subjects`, {
        subject_ids: subjectDraft,
      });
      return response.data as TeacherAssignments;
    },
    onSuccess: () => {
      toast.success("Teacher subject permissions updated.");
      queryClient.invalidateQueries({ queryKey: ["teacher-assignments", selectedTeacherId] });
    },
    onError: (error) => {
      toast.error(getErrorMessage(error, "Unable to update teacher subjects."));
    },
  });

  const saveScheduleMutation = useMutation({
    mutationFn: async () => {
      if (!selectedTeacherId) return null;
      const payload = {
        section_id: scheduleForm.section_id,
        subject_id: scheduleForm.subject_id,
        teacher_id: selectedTeacherId,
        day_of_week: Number(scheduleForm.day_of_week),
        start_time: scheduleForm.start_time,
        end_time: scheduleForm.end_time,
        room: scheduleForm.room.trim() || null,
      };
      if (editingEntryId) {
        const response = await api.patch(`/academic/timetable/${editingEntryId}`, payload);
        return response.data;
      }
      const response = await api.post("/academic/timetable", payload);
      return response.data;
    },
    onSuccess: () => {
      toast.success(editingEntryId ? "Timetable entry updated." : "Timetable entry created.");
      queryClient.invalidateQueries({ queryKey: ["teacher-assignments", selectedTeacherId] });
      setEditingEntryId(null);
      setScheduleForm((current) => ({
        ...current,
        start_time: "09:00",
        end_time: "10:00",
        room: "",
      }));
    },
    onError: (error) => {
      toast.error(getErrorMessage(error, "Unable to save timetable entry."));
    },
  });

  const deleteScheduleMutation = useMutation({
    mutationFn: async (entryId: string) => {
      await api.delete(`/academic/timetable/${entryId}`);
    },
    onSuccess: () => {
      toast.success("Timetable entry removed.");
      queryClient.invalidateQueries({ queryKey: ["teacher-assignments", selectedTeacherId] });
      if (editingEntryId) {
        setEditingEntryId(null);
        setScheduleForm((current) => ({ ...current, room: "" }));
      }
    },
    onError: (error) => {
      toast.error(getErrorMessage(error, "Unable to delete timetable entry."));
    },
  });

  const teachers = teachersData?.items || [];
  const totalTeachers = teachersData?.total || 0;
  const activeTeachers = teachers.filter((teacher) => teacher.is_active).length;
  const totalCoveredSections = assignments?.sections.length || 0;
  const totalScheduledPeriods = assignments?.timetable.length || 0;

  const toggleSectionDraft = (sectionId: string) => {
    setSectionDraft((current) =>
      current.includes(sectionId) ? current.filter((id) => id !== sectionId) : [...current, sectionId],
    );
  };

  const toggleSubjectDraft = (subjectId: string) => {
    setSubjectDraft((current) =>
      current.includes(subjectId) ? current.filter((id) => id !== subjectId) : [...current, subjectId],
    );
  };

  const loadTimetableEntry = (entry: TimetableEntry) => {
    setEditingEntryId(entry.id);
    setAssignmentTab("schedule");
    setScheduleForm({
      section_id: entry.section_id,
      subject_id: entry.subject_id,
      day_of_week: String(entry.day_of_week),
      start_time: entry.start_time,
      end_time: entry.end_time,
      room: entry.room || "",
    });
  };

  const handleCreateTeacher = () => {
    if (!createForm.full_name.trim()) {
      toast.error("Teacher full name is required.");
      return;
    }
    if (!createForm.username.trim()) {
      toast.error("Teacher username is required.");
      return;
    }
    if (createForm.password.trim().length < 8) {
      toast.error("Teacher password must be at least 8 characters.");
      return;
    }

    createTeacherMutation.mutate();
  };

  return (
    <AppLayout>
      <div className="space-y-6">
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex flex-col gap-2"
        >
          <div>
            <h1 className="text-2xl font-display font-bold text-foreground">Teacher Command Center</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Create teachers, manage credentials, assign coverage, and control class schedules from one admin workspace.
            </p>
          </div>
        </motion.div>

        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
          <MetricCard
            title="Teachers"
            value={totalTeachers}
            change="Roster available to admin"
            changeType="neutral"
            icon={Users}
            gradient="bg-gradient-to-br from-primary/30 to-secondary/20"
          />
          <MetricCard
            title="Active Accounts"
            value={activeTeachers}
            change={`${Math.max(totalTeachers - activeTeachers, 0)} inactive`}
            changeType="positive"
            icon={CheckCircle2}
            gradient="bg-gradient-to-br from-emerald-500/30 to-teal-500/20"
            delay={0.05}
          />
          <MetricCard
            title="Covered Sections"
            value={totalCoveredSections}
            change={selectedTeacher ? "For selected teacher" : "Select a teacher"}
            changeType="neutral"
            icon={BookOpen}
            gradient="bg-gradient-to-br from-amber-500/30 to-orange-500/20"
            delay={0.1}
          />
          <MetricCard
            title="Scheduled Periods"
            value={totalScheduledPeriods}
            change={selectedTeacher ? "Live timetable rows" : "Waiting for selection"}
            changeType="neutral"
            icon={CalendarClock}
            gradient="bg-gradient-to-br from-sky-500/30 to-cyan-500/20"
            delay={0.15}
          />
        </div>

        <div className="grid grid-cols-1 gap-6 xl:grid-cols-[360px_minmax(0,1fr)]">
          <div className="space-y-6">
            <GlassCard className="space-y-4" hover={false}>
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-lg font-display font-semibold text-foreground">Teacher Roster</h2>
                  <p className="text-xs text-muted-foreground">Search and select an account to manage.</p>
                </div>
                {teachersLoading && <Loader2 className="h-4 w-4 animate-spin text-primary" />}
              </div>

              <div className="relative">
                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <input
                  type="text"
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder="Search teacher by name or username"
                  className="glass-input w-full py-2.5 pl-10 pr-4 text-sm"
                />
              </div>

              <div className="space-y-3">
                {teachers.map((teacher, index) => {
                  const isSelected = teacher.id === selectedTeacherId;
                  return (
                    <motion.button
                      key={teacher.id}
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: index * 0.03 }}
                      onClick={() => setSelectedTeacherId(teacher.id)}
                      className={`w-full rounded-2xl border p-4 text-left transition-all ${
                        isSelected
                          ? "border-primary/40 bg-primary/12 shadow-[0_0_0_1px_rgba(124,58,237,0.1)]"
                          : "border-white/8 bg-white/[0.03] hover:border-white/15 hover:bg-white/[0.05]"
                      }`}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="text-sm font-semibold text-foreground">{teacher.full_name || "Unnamed teacher"}</p>
                          <p className="mt-1 text-xs text-muted-foreground">@{teacher.username || "no-username"}</p>
                          <p className="mt-1 text-xs text-muted-foreground">{teacher.phone}</p>
                        </div>
                        <span
                          className={`rounded-full px-2 py-1 text-[11px] font-medium ${
                            teacher.is_active
                              ? "bg-emerald-500/15 text-emerald-300"
                              : "bg-amber-500/15 text-amber-300"
                          }`}
                        >
                          {teacher.is_active ? "Active" : "Inactive"}
                        </span>
                      </div>
                    </motion.button>
                  );
                })}

                {!teachersLoading && teachers.length === 0 && (
                  <div className="rounded-2xl border border-dashed border-white/10 bg-white/[0.02] p-6 text-center text-sm text-muted-foreground">
                    No teachers found yet. Create the first teacher account below.
                  </div>
                )}
              </div>
            </GlassCard>

            <GlassCard className="space-y-4" glow="accent" hover={false}>
              <div>
                <h2 className="text-lg font-display font-semibold text-foreground">Add Teacher</h2>
                <p className="text-xs text-muted-foreground">
                  Create the account with login credentials the teacher will use.
                </p>
              </div>

              <div className="grid gap-3">
                <input
                  type="text"
                  value={createForm.full_name}
                  onChange={(event) => setCreateForm((current) => ({ ...current, full_name: event.target.value }))}
                  placeholder="Full name"
                  className="glass-input w-full py-2.5 px-4 text-sm"
                />
                <input
                  type="text"
                  value={createForm.username}
                  onChange={(event) => setCreateForm((current) => ({ ...current, username: event.target.value }))}
                  placeholder="Username"
                  className="glass-input w-full py-2.5 px-4 text-sm"
                />
                <input
                  type="password"
                  value={createForm.password}
                  onChange={(event) => setCreateForm((current) => ({ ...current, password: event.target.value }))}
                  placeholder="Password"
                  className="glass-input w-full py-2.5 px-4 text-sm"
                />
                <input
                  type="text"
                  value={createForm.phone}
                  onChange={(event) => setCreateForm((current) => ({ ...current, phone: event.target.value }))}
                  placeholder="Phone (optional)"
                  className="glass-input w-full py-2.5 px-4 text-sm"
                />
                <div className="grid grid-cols-2 gap-3">
                  <select
                    value={createForm.language_pref}
                    onChange={(event) => setCreateForm((current) => ({ ...current, language_pref: event.target.value }))}
                    className="glass-input w-full py-2.5 px-4 text-sm"
                  >
                    <option value="en">English</option>
                    <option value="te">Telugu</option>
                    <option value="hi">Hindi</option>
                  </select>
                  <select
                    value={createForm.is_active ? "true" : "false"}
                    onChange={(event) =>
                      setCreateForm((current) => ({ ...current, is_active: event.target.value === "true" }))
                    }
                    className="glass-input w-full py-2.5 px-4 text-sm"
                  >
                    <option value="true">Active</option>
                    <option value="false">Inactive</option>
                  </select>
                </div>
              </div>

              <Button
                variant="gradient"
                className="w-full"
                disabled={createTeacherMutation.isPending}
                onClick={handleCreateTeacher}
              >
                {createTeacherMutation.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Plus className="h-4 w-4" />
                )}
                Create Teacher Account
              </Button>

              <p className="text-xs text-muted-foreground">
                Required: full name, username, and a password with at least 8 characters.
              </p>
            </GlassCard>
          </div>

          <GlassCard className="space-y-6" hover={false}>
            {!selectedTeacher ? (
              <div className="flex h-[540px] flex-col items-center justify-center gap-4 text-center">
                <div className="rounded-2xl bg-primary/10 p-5">
                  <UserCog className="h-10 w-10 text-primary" />
                </div>
                <div>
                  <h2 className="text-xl font-display font-semibold text-foreground">Select a teacher</h2>
                  <p className="mt-2 max-w-md text-sm text-muted-foreground">
                    Choose a teacher from the roster to edit profile details, update credentials, assign sections and
                    subjects, and manage timetable slots.
                  </p>
                </div>
              </div>
            ) : (
              <>
                <div className="flex flex-col gap-4 rounded-3xl border border-white/10 bg-white/[0.03] p-5 lg:flex-row lg:items-center lg:justify-between">
                  <div>
                    <p className="text-xs uppercase tracking-[0.2em] text-primary">Selected Teacher</p>
                    <h2 className="mt-2 text-2xl font-display font-bold text-foreground">
                      {selectedTeacher.full_name || "Unnamed teacher"}
                    </h2>
                    <div className="mt-3 flex flex-wrap gap-2 text-xs text-muted-foreground">
                      <span className="rounded-full bg-white/[0.05] px-3 py-1">@{selectedTeacher.username}</span>
                      <span className="rounded-full bg-white/[0.05] px-3 py-1">{selectedTeacher.phone}</span>
                      <span className="rounded-full bg-white/[0.05] px-3 py-1">
                        {selectedTeacher.is_active ? "Account active" : "Account inactive"}
                      </span>
                    </div>
                  </div>
                  <div className="rounded-2xl border border-white/10 bg-black/10 px-4 py-3 text-sm text-muted-foreground">
                    Admin-controlled access:
                    <div className="mt-2 flex gap-2 text-xs">
                      <span className="rounded-full bg-primary/15 px-2.5 py-1 text-primary">Credentials</span>
                      <span className="rounded-full bg-secondary/15 px-2.5 py-1 text-secondary">Assignments</span>
                      <span className="rounded-full bg-accent/15 px-2.5 py-1 text-accent">Schedule</span>
                    </div>
                  </div>
                </div>

                <Tabs value={assignmentTab} onValueChange={setAssignmentTab}>
                  <TabsList className="grid h-auto grid-cols-2 gap-2 rounded-2xl bg-white/[0.04] p-2 lg:grid-cols-4">
                    <TabsTrigger value="profile">Profile</TabsTrigger>
                    <TabsTrigger value="access">Access</TabsTrigger>
                    <TabsTrigger value="assignments">Assignments</TabsTrigger>
                    <TabsTrigger value="schedule">Schedule</TabsTrigger>
                  </TabsList>

                  <TabsContent value="profile" className="space-y-4">
                    <div className="grid gap-4 lg:grid-cols-2">
                      <GlassCard className="space-y-4" hover={false}>
                        <div>
                          <h3 className="text-lg font-display font-semibold text-foreground">Teacher Profile</h3>
                          <p className="text-xs text-muted-foreground">Update admin-managed teacher identity details.</p>
                        </div>

                        <div className="grid gap-3">
                          <label className="space-y-2 text-sm">
                            <span className="text-muted-foreground">Full name</span>
                            <input
                              type="text"
                              value={profileForm.full_name}
                              onChange={(event) =>
                                setProfileForm((current) => ({ ...current, full_name: event.target.value }))
                              }
                              className="glass-input w-full px-4 py-2.5 text-sm"
                            />
                          </label>

                          <label className="space-y-2 text-sm">
                            <span className="text-muted-foreground">Phone</span>
                            <input
                              type="text"
                              value={profileForm.phone}
                              onChange={(event) =>
                                setProfileForm((current) => ({ ...current, phone: event.target.value }))
                              }
                              className="glass-input w-full px-4 py-2.5 text-sm"
                            />
                          </label>

                          <div className="grid grid-cols-2 gap-3">
                            <label className="space-y-2 text-sm">
                              <span className="text-muted-foreground">Language</span>
                              <select
                                value={profileForm.language_pref}
                                onChange={(event) =>
                                  setProfileForm((current) => ({ ...current, language_pref: event.target.value }))
                                }
                                className="glass-input w-full px-4 py-2.5 text-sm"
                              >
                                <option value="en">English</option>
                                <option value="te">Telugu</option>
                                <option value="hi">Hindi</option>
                              </select>
                            </label>

                            <label className="space-y-2 text-sm">
                              <span className="text-muted-foreground">Status</span>
                              <select
                                value={profileForm.is_active ? "true" : "false"}
                                onChange={(event) =>
                                  setProfileForm((current) => ({
                                    ...current,
                                    is_active: event.target.value === "true",
                                  }))
                                }
                                className="glass-input w-full px-4 py-2.5 text-sm"
                              >
                                <option value="true">Active</option>
                                <option value="false">Inactive</option>
                              </select>
                            </label>
                          </div>
                        </div>

                        <Button
                          variant="gradient"
                          disabled={updateTeacherMutation.isPending}
                          onClick={() => updateTeacherMutation.mutate()}
                        >
                          {updateTeacherMutation.isPending ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                          ) : (
                            <Save className="h-4 w-4" />
                          )}
                          Save Profile
                        </Button>
                      </GlassCard>

                      <GlassCard className="space-y-4" hover={false}>
                        <div>
                          <h3 className="text-lg font-display font-semibold text-foreground">Admin Notes</h3>
                          <p className="text-xs text-muted-foreground">
                            Teachers only appear in scheduling once sections and subjects are assigned.
                          </p>
                        </div>

                        <div className="grid gap-3">
                          <div className="rounded-2xl border border-white/8 bg-white/[0.03] p-4">
                            <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">Coverage</p>
                            <p className="mt-2 text-2xl font-display font-bold text-foreground">
                              {assignments?.sections.length || 0}
                            </p>
                            <p className="text-sm text-muted-foreground">Sections currently assigned</p>
                          </div>

                          <div className="rounded-2xl border border-white/8 bg-white/[0.03] p-4">
                            <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">Subjects</p>
                            <p className="mt-2 text-2xl font-display font-bold text-foreground">
                              {assignments?.subjects.length || 0}
                            </p>
                            <p className="text-sm text-muted-foreground">Subjects authorized for teaching</p>
                          </div>

                          <div className="rounded-2xl border border-white/8 bg-white/[0.03] p-4">
                            <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">Schedule</p>
                            <p className="mt-2 text-2xl font-display font-bold text-foreground">
                              {assignments?.timetable.length || 0}
                            </p>
                            <p className="text-sm text-muted-foreground">Timetable slots configured</p>
                          </div>
                        </div>
                      </GlassCard>
                    </div>
                  </TabsContent>

                  <TabsContent value="access" className="space-y-4">
                    <GlassCard className="space-y-4" hover={false}>
                      <div>
                        <h3 className="text-lg font-display font-semibold text-foreground">Credentials & Access</h3>
                        <p className="text-xs text-muted-foreground">
                          The administrator controls the teacher username and can reset the password at any time.
                        </p>
                      </div>

                      <div className="grid gap-4 lg:grid-cols-[1.2fr_0.8fr]">
                        <div className="grid gap-3">
                          <label className="space-y-2 text-sm">
                            <span className="text-muted-foreground">Username</span>
                            <input
                              type="text"
                              value={credentialsForm.username}
                              onChange={(event) =>
                                setCredentialsForm((current) => ({ ...current, username: event.target.value }))
                              }
                              className="glass-input w-full px-4 py-2.5 text-sm"
                            />
                          </label>
                          <label className="space-y-2 text-sm">
                            <span className="text-muted-foreground">New password</span>
                            <input
                              type="password"
                              value={credentialsForm.password}
                              onChange={(event) =>
                                setCredentialsForm((current) => ({ ...current, password: event.target.value }))
                              }
                              placeholder="Leave blank to keep current password"
                              className="glass-input w-full px-4 py-2.5 text-sm"
                            />
                          </label>

                          <Button
                            variant="gradient"
                            disabled={
                              updateCredentialsMutation.isPending ||
                              (!credentialsForm.username.trim() && !credentialsForm.password.trim())
                            }
                            onClick={() => updateCredentialsMutation.mutate()}
                          >
                            {updateCredentialsMutation.isPending ? (
                              <Loader2 className="h-4 w-4 animate-spin" />
                            ) : (
                              <KeyRound className="h-4 w-4" />
                            )}
                            Update Login Access
                          </Button>
                        </div>

                        <div className="rounded-3xl border border-white/8 bg-gradient-to-br from-primary/10 to-secondary/10 p-5">
                          <div className="flex items-center gap-3">
                            <div className="rounded-2xl bg-white/10 p-3">
                              <ShieldCheck className="h-5 w-5 text-primary" />
                            </div>
                            <div>
                              <p className="text-sm font-semibold text-foreground">Access Policy</p>
                              <p className="text-xs text-muted-foreground">Admin-only credential control</p>
                            </div>
                          </div>
                          <div className="mt-5 space-y-3 text-sm text-muted-foreground">
                            <p>Use strong passwords with at least 8 characters.</p>
                            <p>Username changes take effect immediately on the next login.</p>
                            <p>Keep inactive teachers disabled instead of deleting historic schedule context.</p>
                          </div>
                        </div>
                      </div>
                    </GlassCard>
                  </TabsContent>

                  <TabsContent value="assignments" className="space-y-4">
                    <div className="grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
                      <GlassCard className="space-y-4" hover={false}>
                        <div className="flex items-center justify-between">
                          <div>
                            <h3 className="text-lg font-display font-semibold text-foreground">Class & Section Assignment</h3>
                            <p className="text-xs text-muted-foreground">
                              Choose which class sections this teacher can be scheduled for.
                            </p>
                          </div>
                          {(classesLoading || assignmentsLoading) && <Loader2 className="h-4 w-4 animate-spin text-primary" />}
                        </div>

                        <div className="space-y-4">
                          {classesWithSections.map((classItem) => (
                            <div key={classItem.id} className="rounded-2xl border border-white/8 bg-white/[0.03] p-4">
                              <div className="mb-3 flex items-center justify-between">
                                <div>
                                  <p className="text-sm font-semibold text-foreground">{classItem.name}</p>
                                  <p className="text-xs text-muted-foreground">
                                    {classItem.sections.length} sections available
                                  </p>
                                </div>
                                <Mail className="h-4 w-4 text-muted-foreground" />
                              </div>
                              <div className="flex flex-wrap gap-2">
                                {classItem.sections.map((section) => {
                                  const selected = sectionDraft.includes(section.id);
                                  return (
                                    <button
                                      key={section.id}
                                      type="button"
                                      onClick={() => toggleSectionDraft(section.id)}
                                      className={`rounded-full px-3 py-2 text-sm transition-all ${
                                        selected
                                          ? "border border-primary/30 bg-primary/20 text-primary"
                                          : "border border-white/10 bg-white/[0.03] text-muted-foreground hover:bg-white/[0.06]"
                                      }`}
                                    >
                                      {classItem.name} · {section.name}
                                    </button>
                                  );
                                })}
                              </div>
                            </div>
                          ))}

                          {!classesLoading && classesWithSections.length === 0 && (
                            <div className="rounded-2xl border border-dashed border-white/10 bg-white/[0.02] p-5 text-sm text-muted-foreground">
                              No classes or sections exist yet. Add them in the Academics area first, then return here to
                              assign teachers.
                            </div>
                          )}
                        </div>

                        <Button
                          variant="gradient"
                          disabled={updateSectionsMutation.isPending}
                          onClick={() => updateSectionsMutation.mutate()}
                        >
                          {updateSectionsMutation.isPending ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                          ) : (
                            <Save className="h-4 w-4" />
                          )}
                          Save Section Assignment
                        </Button>
                      </GlassCard>

                      <GlassCard className="space-y-4" hover={false}>
                        <div className="flex items-center justify-between">
                          <div>
                            <h3 className="text-lg font-display font-semibold text-foreground">Subject Permission</h3>
                            <p className="text-xs text-muted-foreground">Choose which subjects the teacher is allowed to teach.</p>
                          </div>
                          {subjectsLoading && <Loader2 className="h-4 w-4 animate-spin text-primary" />}
                        </div>

                        <div className="flex flex-wrap gap-2">
                          {subjects.map((subject) => {
                            const selected = subjectDraft.includes(subject.id);
                            return (
                              <button
                                key={subject.id}
                                type="button"
                                onClick={() => toggleSubjectDraft(subject.id)}
                                className={`rounded-full px-3 py-2 text-sm transition-all ${
                                  selected
                                    ? "border border-secondary/30 bg-secondary/20 text-secondary"
                                    : "border border-white/10 bg-white/[0.03] text-muted-foreground hover:bg-white/[0.06]"
                                }`}
                              >
                                {subject.name}
                                {subject.code ? ` · ${subject.code}` : ""}
                              </button>
                            );
                          })}
                        </div>

                        {!subjectsLoading && subjects.length === 0 && (
                          <div className="rounded-2xl border border-dashed border-white/10 bg-white/[0.02] p-5 text-sm text-muted-foreground">
                            No subjects are available for this school yet.
                          </div>
                        )}

                        <Button
                          variant="gradient"
                          disabled={updateSubjectsMutation.isPending}
                          onClick={() => updateSubjectsMutation.mutate()}
                        >
                          {updateSubjectsMutation.isPending ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                          ) : (
                            <Save className="h-4 w-4" />
                          )}
                          Save Subject Permission
                        </Button>
                      </GlassCard>
                    </div>
                  </TabsContent>

                  <TabsContent value="schedule" className="space-y-4">
                    <div className="grid gap-4 xl:grid-cols-[0.9fr_1.1fr]">
                      <GlassCard className="space-y-4" hover={false}>
                        <div>
                          <h3 className="text-lg font-display font-semibold text-foreground">Teaching Slot</h3>
                          <p className="text-xs text-muted-foreground">
                            Assign the teacher to a specific section, subject, day, and hour.
                          </p>
                        </div>

                        <div className="grid gap-3">
                          <label className="space-y-2 text-sm">
                            <span className="text-muted-foreground">Section</span>
                            <select
                              value={scheduleForm.section_id}
                              onChange={(event) =>
                                setScheduleForm((current) => ({ ...current, section_id: event.target.value }))
                              }
                              className="glass-input w-full px-4 py-2.5 text-sm"
                            >
                              <option value="">Select section</option>
                              {assignments?.sections.map((section) => (
                                <option key={section.id} value={section.id}>
                                  {section.class_name} · {section.name}
                                </option>
                              ))}
                            </select>
                          </label>

                          <label className="space-y-2 text-sm">
                            <span className="text-muted-foreground">Subject</span>
                            <select
                              value={scheduleForm.subject_id}
                              onChange={(event) =>
                                setScheduleForm((current) => ({ ...current, subject_id: event.target.value }))
                              }
                              className="glass-input w-full px-4 py-2.5 text-sm"
                            >
                              <option value="">Select subject</option>
                              {assignments?.subjects.map((subject) => (
                                <option key={subject.id} value={subject.id}>
                                  {subject.name}
                                  {subject.code ? ` · ${subject.code}` : ""}
                                </option>
                              ))}
                            </select>
                          </label>

                          <div className="grid grid-cols-3 gap-3">
                            <label className="space-y-2 text-sm">
                              <span className="text-muted-foreground">Day</span>
                              <select
                                value={scheduleForm.day_of_week}
                                onChange={(event) =>
                                  setScheduleForm((current) => ({ ...current, day_of_week: event.target.value }))
                                }
                                className="glass-input w-full px-4 py-2.5 text-sm"
                              >
                                {dayOptions.map((day) => (
                                  <option key={day.value} value={day.value}>
                                    {day.label}
                                  </option>
                                ))}
                              </select>
                            </label>

                            <label className="space-y-2 text-sm">
                              <span className="text-muted-foreground">Start</span>
                              <input
                                type="time"
                                value={scheduleForm.start_time}
                                onChange={(event) =>
                                  setScheduleForm((current) => ({ ...current, start_time: event.target.value }))
                                }
                                className="glass-input w-full px-4 py-2.5 text-sm"
                              />
                            </label>

                            <label className="space-y-2 text-sm">
                              <span className="text-muted-foreground">End</span>
                              <input
                                type="time"
                                value={scheduleForm.end_time}
                                onChange={(event) =>
                                  setScheduleForm((current) => ({ ...current, end_time: event.target.value }))
                                }
                                className="glass-input w-full px-4 py-2.5 text-sm"
                              />
                            </label>
                          </div>

                          <label className="space-y-2 text-sm">
                            <span className="text-muted-foreground">Room</span>
                            <input
                              type="text"
                              value={scheduleForm.room}
                              onChange={(event) =>
                                setScheduleForm((current) => ({ ...current, room: event.target.value }))
                              }
                              placeholder="Optional room or lab"
                              className="glass-input w-full px-4 py-2.5 text-sm"
                            />
                          </label>
                        </div>

                        <div className="flex flex-wrap gap-3">
                          <Button
                            variant="gradient"
                            disabled={saveScheduleMutation.isPending || !scheduleForm.section_id || !scheduleForm.subject_id}
                            onClick={() => saveScheduleMutation.mutate()}
                          >
                            {saveScheduleMutation.isPending ? (
                              <Loader2 className="h-4 w-4 animate-spin" />
                            ) : editingEntryId ? (
                              <Save className="h-4 w-4" />
                            ) : (
                              <Plus className="h-4 w-4" />
                            )}
                            {editingEntryId ? "Update Slot" : "Add Slot"}
                          </Button>

                          {editingEntryId && (
                            <Button
                              variant="outline"
                              onClick={() => {
                                setEditingEntryId(null);
                                setScheduleForm({
                                  section_id: assignments?.section_ids[0] || "",
                                  subject_id: assignments?.subject_ids[0] || "",
                                  day_of_week: "1",
                                  start_time: "09:00",
                                  end_time: "10:00",
                                  room: "",
                                });
                              }}
                            >
                              Cancel Edit
                            </Button>
                          )}
                        </div>

                        {(!assignments?.sections.length || !assignments?.subjects.length) && (
                          <div className="rounded-2xl border border-dashed border-white/10 bg-white/[0.02] p-4 text-sm text-muted-foreground">
                            Assign at least one section and one subject before adding timetable slots.
                          </div>
                        )}
                      </GlassCard>

                      <GlassCard className="space-y-4" hover={false}>
                        <div className="flex items-center justify-between">
                          <div>
                            <h3 className="text-lg font-display font-semibold text-foreground">Current Timetable</h3>
                            <p className="text-xs text-muted-foreground">
                              Click edit to change an existing slot or remove it entirely.
                            </p>
                          </div>
                          {assignmentsLoading && <Loader2 className="h-4 w-4 animate-spin text-primary" />}
                        </div>

                        <div className="space-y-3">
                          {assignments?.timetable.map((entry) => (
                            <div key={entry.id} className="rounded-2xl border border-white/8 bg-white/[0.03] p-4">
                              <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                                <div>
                                  <p className="text-sm font-semibold text-foreground">
                                    {dayOptions.find((day) => Number(day.value) === entry.day_of_week)?.label} ·{" "}
                                    {entry.start_time} - {entry.end_time}
                                  </p>
                                  <p className="mt-1 text-xs text-muted-foreground">
                                    {entry.class_name} · {entry.section_name} · {entry.subject_name}
                                    {entry.room ? ` · ${entry.room}` : ""}
                                  </p>
                                </div>
                                <div className="flex gap-2">
                                  <Button variant="glass" size="sm" onClick={() => loadTimetableEntry(entry)}>
                                    <Pencil className="h-4 w-4" />
                                    Edit
                                  </Button>
                                  <Button
                                    variant="outline"
                                    size="sm"
                                    disabled={deleteScheduleMutation.isPending}
                                    onClick={() => deleteScheduleMutation.mutate(entry.id)}
                                  >
                                    <Trash2 className="h-4 w-4" />
                                    Remove
                                  </Button>
                                </div>
                              </div>
                            </div>
                          ))}

                          {!assignmentsLoading && !assignments?.timetable.length && (
                            <div className="rounded-2xl border border-dashed border-white/10 bg-white/[0.02] p-6 text-center text-sm text-muted-foreground">
                              No timetable slots have been scheduled for this teacher yet.
                            </div>
                          )}
                        </div>
                      </GlassCard>
                    </div>
                  </TabsContent>
                </Tabs>
              </>
            )}
          </GlassCard>
        </div>
      </div>
    </AppLayout>
  );
};

export default Teachers;
