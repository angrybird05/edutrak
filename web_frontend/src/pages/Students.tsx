import { useDeferredValue, useEffect, useState } from "react";
import { motion } from "framer-motion";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  BadgeCheck,
  GraduationCap,
  IdCard,
  Loader2,
  Phone,
  Plus,
  Search,
  ShieldCheck,
  Sparkles,
  Users,
} from "lucide-react";
import { toast } from "sonner";

import AppLayout from "@/components/AppLayout";
import GlassCard from "@/components/GlassCard";
import MetricCard from "@/components/MetricCard";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/contexts/AuthContext";
import api from "@/lib/api";
import {
  StudentCreatePayload,
  StudentCreateResponse,
  StudentRecord,
  StudentProfileSummary,
  createStudent,
  fetchStudentProfileSummary,
  fetchStudents,
} from "@/lib/students";

type UserProfile = {
  id: string;
  school_id: string | null;
};

type ClassItem = {
  id: string;
  name: string;
};

type SectionItem = {
  id: string;
  name: string;
  class_id: string;
};

type ClassWithSections = ClassItem & {
  sections: SectionItem[];
};

const getErrorMessage = (error: any, fallback: string) =>
  error?.response?.data?.message ||
  error?.response?.data?.detail ||
  (Array.isArray(error?.response?.data?.details)
    ? `Validation failed: ${error.response.data.details
        .map((detail: any) => {
          const loc = Array.isArray(detail?.loc) ? detail.loc : [];
          return loc[loc.length - 1];
        })
        .filter(Boolean)
        .join(", ")}`
    : fallback);

const emptyCreateForm: StudentCreatePayload = {
  full_name: "",
  admission_number: "",
  roll_number: "",
  dob: "",
  class_id: "",
  section_id: "",
  guardian_name: "",
  guardian_relation: "",
  guardian_phone: "",
};

const Students = () => {
  const queryClient = useQueryClient();
  const { role } = useAuth();
  const isAdmin = role === "admin";

  const [search, setSearch] = useState("");
  const deferredSearch = useDeferredValue(search);
  const [selectedStudentId, setSelectedStudentId] = useState<string | null>(null);
  const [createForm, setCreateForm] = useState<StudentCreatePayload>(emptyCreateForm);
  const [createdStudent, setCreatedStudent] = useState<StudentCreateResponse | null>(null);

  const { data: me } = useQuery<UserProfile>({
    queryKey: ["me"],
    queryFn: async () => {
      const response = await api.get("/identity/me");
      return response.data;
    },
  });

  const schoolId = me?.school_id || null;

  const { data: studentsData, isLoading: studentsLoading } = useQuery({
    queryKey: ["students", deferredSearch],
    queryFn: () => fetchStudents(deferredSearch),
  });

  const { data: classesWithSections = [], isLoading: classesLoading } = useQuery<ClassWithSections[]>({
    queryKey: ["student-classes", schoolId],
    enabled: !!schoolId,
    queryFn: async () => {
      const classesResponse = await api.get(`/academic/classes/${schoolId}`);
      const classes = classesResponse.data as ClassItem[];
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

  const { data: selectedStudentSummary, isLoading: summaryLoading } = useQuery<StudentProfileSummary>({
    queryKey: ["student-summary", selectedStudentId],
    enabled: !!selectedStudentId,
    queryFn: () => fetchStudentProfileSummary(selectedStudentId as string),
  });

  useEffect(() => {
    if (studentsLoading) {
      return;
    }
    const firstStudent = studentsData?.items?.[0] || null;
    if (!studentsData?.items?.length) {
      setSelectedStudentId(null);
      return;
    }
    if (!selectedStudentId || !studentsData.items.some((student) => student.id === selectedStudentId)) {
      setSelectedStudentId(firstStudent.id);
    }
  }, [selectedStudentId, studentsData, studentsLoading]);

  useEffect(() => {
    if (!createForm.class_id) {
      setCreateForm((current) => ({ ...current, section_id: "" }));
      return;
    }
    const currentClass = classesWithSections.find((item) => item.id === createForm.class_id);
    if (!currentClass?.sections.some((section) => section.id === createForm.section_id)) {
      setCreateForm((current) => ({ ...current, section_id: currentClass?.sections[0]?.id || "" }));
    }
  }, [classesWithSections, createForm.class_id, createForm.section_id]);

  const createStudentMutation = useMutation({
    mutationFn: () =>
      createStudent({
        ...createForm,
        full_name: createForm.full_name.trim(),
        admission_number: createForm.admission_number.trim(),
        roll_number: createForm.roll_number?.trim() || undefined,
        dob: createForm.dob || undefined,
        school_id: schoolId || undefined,
        guardian_name: createForm.guardian_name.trim(),
        guardian_relation: createForm.guardian_relation.trim(),
        guardian_phone: createForm.guardian_phone.trim(),
      }),
    onSuccess: (student) => {
      setCreatedStudent(student);
      setCreateForm(emptyCreateForm);
      queryClient.invalidateQueries({ queryKey: ["students"] });
      queryClient.invalidateQueries({ queryKey: ["student-summary"] });
      setSelectedStudentId(student.id);
      toast.success(student.parent_account_created ? "Student and parent account created." : "Student created and linked to existing parent.");
    },
    onError: (error) => {
      toast.error(getErrorMessage(error, "Unable to create student."));
    },
  });

  const students = (studentsData?.items || []) as StudentRecord[];
  const totalStudents = studentsData?.total || 0;
  const guardianReuseCount = students.filter((student) => student.guardian_phone).length;
  const selectedStudent = students.find((student) => student.id === selectedStudentId) || null;
  const selectedClass = classesWithSections.find((item) => item.id === createForm.class_id) || null;

  const handleCreateStudent = () => {
    if (!isAdmin) {
      toast.error("Only admins can create students.");
      return;
    }
    if (!createForm.full_name.trim()) {
      toast.error("Student full name is required.");
      return;
    }
    if (!createForm.admission_number.trim()) {
      toast.error("Admission number is required.");
      return;
    }
    if (!createForm.class_id || !createForm.section_id) {
      toast.error("Choose the class and section.");
      return;
    }
    if (!createForm.guardian_name.trim() || !createForm.guardian_relation.trim() || !createForm.guardian_phone.trim()) {
      toast.error("Guardian name, relation, and phone are required.");
      return;
    }
    createStudentMutation.mutate();
  };

  return (
    <AppLayout>
      <div className="space-y-6">
        <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} className="space-y-2">
          <h1 className="text-2xl font-display font-bold text-foreground">Student Enrollment Hub</h1>
          <p className="text-sm text-muted-foreground">
            Build the student roster, capture guardian login details, and hand over join-code access from one admin workspace.
          </p>
        </motion.div>

        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
          <MetricCard
            title="Students"
            value={totalStudents}
            change="Live school roster"
            changeType="neutral"
            icon={Users}
            gradient="bg-gradient-to-br from-primary/30 to-secondary/20"
          />
          <MetricCard
            title="Guardians Captured"
            value={guardianReuseCount}
            change="Phone-based login ready"
            changeType="positive"
            icon={Phone}
            gradient="bg-gradient-to-br from-emerald-500/30 to-teal-500/20"
            delay={0.05}
          />
          <MetricCard
            title="Selected Student"
            value={selectedStudent ? 1 : 0}
            change={selectedStudent ? selectedStudent.admission_number : "Pick a student"}
            changeType="neutral"
            icon={GraduationCap}
            gradient="bg-gradient-to-br from-amber-500/30 to-orange-500/20"
            delay={0.1}
          />
          <MetricCard
            title="Join Code Ready"
            value={createdStudent?.parent_joining_code ? 1 : 0}
            change={createdStudent?.parent_joining_code || "Create a student"}
            changeType="neutral"
            icon={BadgeCheck}
            gradient="bg-gradient-to-br from-sky-500/30 to-cyan-500/20"
            delay={0.15}
          />
        </div>

        <div className="grid grid-cols-1 gap-6 xl:grid-cols-[360px_minmax(0,1fr)]">
          <div className="space-y-6">
            <GlassCard className="space-y-4" hover={false}>
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-lg font-display font-semibold text-foreground">Student Roster</h2>
                  <p className="text-xs text-muted-foreground">Search by student name, admission number, guardian name, or guardian phone.</p>
                </div>
                {studentsLoading && <Loader2 className="h-4 w-4 animate-spin text-primary" />}
              </div>

              <div className="relative">
                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <input
                  type="text"
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder="Search students"
                  className="glass-input w-full py-2.5 pl-10 pr-4 text-sm"
                />
              </div>

              <div className="space-y-3">
                {students.map((student, index) => {
                  const isSelected = student.id === selectedStudentId;
                  return (
                    <motion.button
                      key={student.id}
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: index * 0.03 }}
                      onClick={() => setSelectedStudentId(student.id)}
                      className={`w-full rounded-2xl border p-4 text-left transition-all ${
                        isSelected
                          ? "border-primary/40 bg-primary/12 shadow-[0_0_0_1px_rgba(124,58,237,0.1)]"
                          : "border-white/8 bg-white/[0.03] hover:border-white/15 hover:bg-white/[0.05]"
                      }`}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="text-sm font-semibold text-foreground">{student.full_name || "Unnamed student"}</p>
                          <p className="mt-1 text-xs text-muted-foreground">Admission: {student.admission_number}</p>
                          <p className="mt-1 text-xs text-muted-foreground">
                            Guardian: {student.guardian_name || "Not recorded"} {student.guardian_phone ? `· ${student.guardian_phone}` : ""}
                          </p>
                        </div>
                        <span className="rounded-full bg-white/[0.06] px-2 py-1 text-[11px] text-muted-foreground">
                          {student.roll_number || "No roll"}
                        </span>
                      </div>
                    </motion.button>
                  );
                })}

                {!studentsLoading && students.length === 0 && (
                  <div className="rounded-2xl border border-dashed border-white/10 bg-white/[0.02] p-5 text-sm text-muted-foreground">
                    No students found yet. Create the first enrollment record on the right.
                  </div>
                )}
              </div>
            </GlassCard>

            {createdStudent && (
              <GlassCard className="space-y-4" hover={false}>
                <div className="flex items-center gap-3">
                  <div className="rounded-2xl bg-emerald-500/15 p-3">
                    <BadgeCheck className="h-5 w-5 text-emerald-300" />
                  </div>
                  <div>
                    <h3 className="text-lg font-display font-semibold text-foreground">Enrollment Ready</h3>
                    <p className="text-xs text-muted-foreground">Share this join code with the guardian to link the child when needed.</p>
                  </div>
                </div>

                <div className="rounded-2xl border border-white/8 bg-white/[0.03] p-4">
                  <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">Join Code</p>
                  <p className="mt-2 text-2xl font-display font-bold text-foreground">{createdStudent.parent_joining_code}</p>
                  <p className="mt-2 text-xs text-muted-foreground">
                    Parent account {createdStudent.parent_account_created ? "created" : "reused"} for {createdStudent.guardian_phone}.
                  </p>
                </div>
              </GlassCard>
            )}
          </div>

          <div className="space-y-6">
            {isAdmin && (
              <GlassCard className="space-y-5" hover={false}>
                <div className="flex items-center justify-between">
                  <div>
                    <h2 className="text-lg font-display font-semibold text-foreground">Add Student</h2>
                    <p className="text-xs text-muted-foreground">Admins create students, assign sections, and set guardian login data here.</p>
                  </div>
                  {(classesLoading || createStudentMutation.isPending) && <Loader2 className="h-4 w-4 animate-spin text-primary" />}
                </div>

                <div className="grid gap-4 md:grid-cols-2">
                  <label className="space-y-2 text-sm">
                    <span className="text-muted-foreground">Student Name</span>
                    <input
                      type="text"
                      value={createForm.full_name}
                      onChange={(event) => setCreateForm((current) => ({ ...current, full_name: event.target.value }))}
                      placeholder="Aarav Kumar"
                      className="glass-input w-full px-4 py-2.5 text-sm"
                    />
                  </label>
                  <label className="space-y-2 text-sm">
                    <span className="text-muted-foreground">Admission Number</span>
                    <input
                      type="text"
                      value={createForm.admission_number}
                      onChange={(event) => setCreateForm((current) => ({ ...current, admission_number: event.target.value }))}
                      placeholder="ADM-2026-001"
                      className="glass-input w-full px-4 py-2.5 text-sm"
                    />
                  </label>
                  <label className="space-y-2 text-sm">
                    <span className="text-muted-foreground">Roll Number</span>
                    <input
                      type="text"
                      value={createForm.roll_number || ""}
                      onChange={(event) => setCreateForm((current) => ({ ...current, roll_number: event.target.value }))}
                      placeholder="12"
                      className="glass-input w-full px-4 py-2.5 text-sm"
                    />
                  </label>
                  <label className="space-y-2 text-sm">
                    <span className="text-muted-foreground">Date of Birth</span>
                    <input
                      type="date"
                      value={createForm.dob || ""}
                      onChange={(event) => setCreateForm((current) => ({ ...current, dob: event.target.value }))}
                      className="glass-input w-full px-4 py-2.5 text-sm"
                    />
                  </label>
                  <label className="space-y-2 text-sm">
                    <span className="text-muted-foreground">Class</span>
                    <select
                      value={createForm.class_id}
                      onChange={(event) => setCreateForm((current) => ({ ...current, class_id: event.target.value }))}
                      className="glass-input w-full px-4 py-2.5 text-sm"
                    >
                      <option value="">Select class</option>
                      {classesWithSections.map((classItem) => (
                        <option key={classItem.id} value={classItem.id}>
                          {classItem.name}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="space-y-2 text-sm">
                    <span className="text-muted-foreground">Section</span>
                    <select
                      value={createForm.section_id}
                      onChange={(event) => setCreateForm((current) => ({ ...current, section_id: event.target.value }))}
                      className="glass-input w-full px-4 py-2.5 text-sm"
                    >
                      <option value="">Select section</option>
                      {selectedClass?.sections.map((section) => (
                        <option key={section.id} value={section.id}>
                          {section.name}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>

                <div className="grid gap-4 md:grid-cols-3">
                  <label className="space-y-2 text-sm">
                    <span className="text-muted-foreground">Guardian Name</span>
                    <input
                      type="text"
                      value={createForm.guardian_name}
                      onChange={(event) => setCreateForm((current) => ({ ...current, guardian_name: event.target.value }))}
                      placeholder="Sanjay Kumar"
                      className="glass-input w-full px-4 py-2.5 text-sm"
                    />
                  </label>
                  <label className="space-y-2 text-sm">
                    <span className="text-muted-foreground">Relation</span>
                    <input
                      type="text"
                      value={createForm.guardian_relation}
                      onChange={(event) => setCreateForm((current) => ({ ...current, guardian_relation: event.target.value }))}
                      placeholder="Father"
                      className="glass-input w-full px-4 py-2.5 text-sm"
                    />
                  </label>
                  <label className="space-y-2 text-sm">
                    <span className="text-muted-foreground">Guardian Phone</span>
                    <input
                      type="tel"
                      value={createForm.guardian_phone}
                      onChange={(event) => setCreateForm((current) => ({ ...current, guardian_phone: event.target.value }))}
                      placeholder="+919999999999"
                      className="glass-input w-full px-4 py-2.5 text-sm"
                    />
                  </label>
                </div>

                <div className="flex flex-wrap gap-3">
                  <Button variant="gradient" disabled={createStudentMutation.isPending} onClick={handleCreateStudent}>
                    {createStudentMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
                    Create Student
                  </Button>
                  <Button variant="outline" onClick={() => setCreateForm(emptyCreateForm)}>
                    Reset Form
                  </Button>
                </div>
              </GlassCard>
            )}

            <GlassCard className="space-y-5" hover={false}>
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-lg font-display font-semibold text-foreground">Student Detail Snapshot</h2>
                  <p className="text-xs text-muted-foreground">Identity, guardian login info, attendance, and AI snapshot for the selected student.</p>
                </div>
                {summaryLoading && <Loader2 className="h-4 w-4 animate-spin text-primary" />}
              </div>

              {!selectedStudent && (
                <div className="rounded-2xl border border-dashed border-white/10 bg-white/[0.02] p-6 text-sm text-muted-foreground">
                  Select a student from the roster to load their detail view.
                </div>
              )}

              {selectedStudent && selectedStudentSummary && (
                <>
                  <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                    <div className="rounded-3xl border border-white/8 bg-white/[0.03] p-5">
                      <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Student</p>
                      <p className="mt-3 text-lg font-display font-semibold text-foreground">{selectedStudentSummary.profile.full_name}</p>
                      <p className="mt-1 text-xs text-muted-foreground">{selectedStudentSummary.profile.admission_number}</p>
                    </div>
                    <div className="rounded-3xl border border-white/8 bg-white/[0.03] p-5">
                      <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Class</p>
                      <p className="mt-3 text-lg font-display font-semibold text-foreground">{selectedStudentSummary.profile.class || "Unassigned"}</p>
                      <p className="mt-1 text-xs text-muted-foreground">{selectedStudentSummary.profile.section || "No section"}</p>
                    </div>
                    <div className="rounded-3xl border border-white/8 bg-white/[0.03] p-5">
                      <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Attendance</p>
                      <p className="mt-3 text-lg font-display font-semibold text-foreground">{selectedStudentSummary.attendance.attendance_percentage}%</p>
                      <p className="mt-1 text-xs text-muted-foreground">
                        {selectedStudentSummary.attendance.present_days}/{selectedStudentSummary.attendance.total_days} present days
                      </p>
                    </div>
                    <div className="rounded-3xl border border-white/8 bg-white/[0.03] p-5">
                      <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Join Code</p>
                      <p className="mt-3 text-lg font-display font-semibold text-foreground">{selectedStudentSummary.profile.parent_joining_code || "Pending"}</p>
                      <p className="mt-1 text-xs text-muted-foreground">Backup code for manual guardian linking</p>
                    </div>
                  </div>

                  <div className="grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
                    <div className="space-y-4 rounded-3xl border border-white/8 bg-white/[0.03] p-5">
                      <div className="flex items-center gap-3">
                        <div className="rounded-2xl bg-primary/15 p-3">
                          <ShieldCheck className="h-5 w-5 text-primary" />
                        </div>
                        <div>
                          <p className="text-sm font-semibold text-foreground">Guardian Login Identity</p>
                          <p className="text-xs text-muted-foreground">This phone number can be used for both parent and student OTP access.</p>
                        </div>
                      </div>
                      <div className="grid gap-3 md:grid-cols-2">
                        <div>
                          <p className="text-xs text-muted-foreground">Guardian Name</p>
                          <p className="mt-1 text-sm text-foreground">{selectedStudentSummary.profile.guardian_name || "Not recorded"}</p>
                        </div>
                        <div>
                          <p className="text-xs text-muted-foreground">Relation</p>
                          <p className="mt-1 text-sm text-foreground">{selectedStudentSummary.profile.guardian_relation || "Not recorded"}</p>
                        </div>
                        <div>
                          <p className="text-xs text-muted-foreground">Guardian Phone</p>
                          <p className="mt-1 text-sm text-foreground">{selectedStudentSummary.profile.guardian_phone || "Not recorded"}</p>
                        </div>
                        <div>
                          <p className="text-xs text-muted-foreground">Roll Number</p>
                          <p className="mt-1 text-sm text-foreground">{selectedStudentSummary.profile.roll_number || "Not assigned"}</p>
                        </div>
                      </div>
                    </div>

                    <div className="space-y-4 rounded-3xl border border-white/8 bg-gradient-to-br from-primary/10 to-secondary/10 p-5">
                      <div className="flex items-center gap-3">
                        <div className="rounded-2xl bg-white/10 p-3">
                          <Sparkles className="h-5 w-5 text-primary" />
                        </div>
                        <div>
                          <p className="text-sm font-semibold text-foreground">AI Snapshot</p>
                          <p className="text-xs text-muted-foreground">Latest recommendation summary from the analytics layer.</p>
                        </div>
                      </div>
                      <p className="text-sm leading-6 text-muted-foreground">
                        {selectedStudentSummary.ai_summary.insight_text || "No AI summary has been generated for this student yet."}
                      </p>
                    </div>
                  </div>

                  <div className="grid gap-4 xl:grid-cols-[1fr_0.8fr]">
                    <div className="rounded-3xl border border-white/8 bg-white/[0.03] p-5">
                      <div className="mb-4 flex items-center gap-3">
                        <div className="rounded-2xl bg-amber-500/15 p-3">
                          <IdCard className="h-5 w-5 text-amber-300" />
                        </div>
                        <div>
                          <p className="text-sm font-semibold text-foreground">Subject Performance</p>
                          <p className="text-xs text-muted-foreground">Latest subject averages for the selected student.</p>
                        </div>
                      </div>
                      <div className="space-y-3">
                        {selectedStudentSummary.subject_performance.length ? (
                          selectedStudentSummary.subject_performance.map((subject) => (
                            <div key={subject.subject} className="flex items-center justify-between rounded-2xl border border-white/8 bg-black/10 px-4 py-3">
                              <div>
                                <p className="text-sm font-medium text-foreground">{subject.subject}</p>
                                <p className="text-xs text-muted-foreground">{subject.records_count} record(s)</p>
                              </div>
                              <span className="rounded-full bg-white/[0.06] px-3 py-1 text-xs text-foreground">
                                {subject.average_marks}%
                              </span>
                            </div>
                          ))
                        ) : (
                          <div className="rounded-2xl border border-dashed border-white/10 bg-white/[0.02] p-5 text-sm text-muted-foreground">
                            No subject performance data has been recorded yet.
                          </div>
                        )}
                      </div>
                    </div>

                    <div className="rounded-3xl border border-white/8 bg-white/[0.03] p-5">
                      <div className="mb-4 flex items-center gap-3">
                        <div className="rounded-2xl bg-sky-500/15 p-3">
                          <BadgeCheck className="h-5 w-5 text-sky-300" />
                        </div>
                        <div>
                          <p className="text-sm font-semibold text-foreground">Latest Report</p>
                          <p className="text-xs text-muted-foreground">Most recent generated report metadata.</p>
                        </div>
                      </div>
                      {selectedStudentSummary.latest_report ? (
                        <div className="space-y-2">
                          <p className="text-lg font-display font-semibold text-foreground">{selectedStudentSummary.latest_report.term_name}</p>
                          <p className="text-xs text-muted-foreground">{selectedStudentSummary.latest_report.generated_at}</p>
                          <p className="text-xs text-muted-foreground break-all">{selectedStudentSummary.latest_report.pdf_url || "PDF path unavailable"}</p>
                        </div>
                      ) : (
                        <div className="rounded-2xl border border-dashed border-white/10 bg-white/[0.02] p-5 text-sm text-muted-foreground">
                          No report card has been generated for this student yet.
                        </div>
                      )}
                    </div>
                  </div>
                </>
              )}
            </GlassCard>
          </div>
        </div>
      </div>
    </AppLayout>
  );
};

export default Students;
