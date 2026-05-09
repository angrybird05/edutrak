import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { useMutation, useQuery } from "@tanstack/react-query";
import { AlertCircle, BookOpen, CheckCircle2, CloudUpload, GraduationCap, Loader2, Trophy, Users } from "lucide-react";
import { toast } from "sonner";

import AppLayout from "@/components/AppLayout";
import GlassCard from "@/components/GlassCard";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/contexts/AuthContext";
import api from "@/lib/api";

type SectionOption = {
  id: string;
  name: string;
  class_id: string;
  class_name: string;
};

type SubjectOption = {
  id: string;
  name: string;
  code: string | null;
};

type ExamOption = {
  id: string;
  name: string;
  exam_date: string | null;
};

type GradebookContext = {
  class_id: string;
  class_name: string;
  section_id: string;
  section_name: string;
  subjects: SubjectOption[];
  exams: ExamOption[];
};

type GradebookStudent = {
  student_id: string;
  full_name: string | null;
  admission_number: string;
  roll_number: string | null;
  marks_obtained: number | null;
  max_marks: number;
  mark_status: string;
  comments: string | null;
  percentage: number | null;
};

type GradebookMatrix = {
  class_id: string;
  class_name: string;
  section_id: string;
  section_name: string;
  subject_id: string;
  exam_id: string;
  students: GradebookStudent[];
  summary: {
    total_students: number;
    entered_marks: number;
    average_percentage: number;
    highest_percentage: number;
    lowest_percentage: number;
  };
};

const getGradeColor = (percentage: number | null) => {
  if (percentage === null) return "text-muted-foreground";
  if (percentage >= 90) return "text-emerald-400";
  if (percentage >= 75) return "text-sky-400";
  if (percentage >= 60) return "text-amber-400";
  return "text-red-400";
};

const Gradebook = () => {
  const { role } = useAuth();
  const [selectedSectionId, setSelectedSectionId] = useState("");
  const [selectedSubjectId, setSelectedSubjectId] = useState("");
  const [selectedExamId, setSelectedExamId] = useState("");
  const [draftMarks, setDraftMarks] = useState<Record<string, string>>({});
  const [maxMarks, setMaxMarks] = useState("100");
  const [newExamName, setNewExamName] = useState("");
  const [newExamDate, setNewExamDate] = useState(new Date().toISOString().split("T")[0]);
  const [synced, setSynced] = useState(false);

  const { data: sections = [], isLoading: sectionsLoading } = useQuery<SectionOption[]>({
    queryKey: ["gradebook-sections"],
    queryFn: async () => {
      const response = await api.get("/assessment/attendance/sections");
      return response.data;
    },
  });

  useEffect(() => {
    if (!sections.length) {
      setSelectedSectionId("");
      return;
    }

    if (!selectedSectionId || !sections.some((section) => section.id === selectedSectionId)) {
      setSelectedSectionId(sections[0].id);
    }
  }, [sections, selectedSectionId]);

  const {
    data: context,
    isLoading: contextLoading,
    refetch: refetchContext,
  } = useQuery<GradebookContext>({
    queryKey: ["gradebook-context", selectedSectionId],
    enabled: !!selectedSectionId,
    queryFn: async () => {
      const response = await api.get(`/assessment/gradebook/sections/${selectedSectionId}`);
      return response.data;
    },
  });

  useEffect(() => {
    if (!context) {
      setSelectedSubjectId("");
      setSelectedExamId("");
      return;
    }

    if (!context.subjects.some((subject) => subject.id === selectedSubjectId)) {
      setSelectedSubjectId(context.subjects[0]?.id || "");
    }

    if (!context.exams.some((exam) => exam.id === selectedExamId)) {
      setSelectedExamId(context.exams[0]?.id || "");
    }
  }, [context, selectedExamId, selectedSubjectId]);

  const {
    data: matrix,
    isLoading: matrixLoading,
    refetch: refetchMatrix,
  } = useQuery<GradebookMatrix>({
    queryKey: ["gradebook-matrix", selectedSectionId, selectedSubjectId, selectedExamId],
    enabled: !!selectedSectionId && !!selectedSubjectId && !!selectedExamId,
    queryFn: async () => {
      const response = await api.get(`/assessment/gradebook/sections/${selectedSectionId}/matrix`, {
        params: {
          subject_id: selectedSubjectId,
          exam_id: selectedExamId,
        },
      });
      return response.data;
    },
  });

  useEffect(() => {
    if (!matrix) {
      setDraftMarks({});
      setMaxMarks("100");
      return;
    }

    setDraftMarks(
      Object.fromEntries(
        matrix.students.map((student) => [
          student.student_id,
          student.marks_obtained === null ? "" : String(student.marks_obtained),
        ]),
      ),
    );

    const firstFilledMark = matrix.students.find((student) => student.marks_obtained !== null);
    setMaxMarks(String(firstFilledMark?.max_marks || matrix.students[0]?.max_marks || 100));
  }, [matrix]);

  const createExamMutation = useMutation({
    mutationFn: async () => {
      const response = await api.post("/assessment/exams", null, {
        params: {
          name: newExamName.trim(),
          section_id: selectedSectionId,
          exam_date: newExamDate || undefined,
        },
      });
      return response.data as { id: string; name: string };
    },
    onSuccess: async (exam) => {
      toast.success("Exam created.");
      setNewExamName("");
      await refetchContext();
      setSelectedExamId(exam.id);
    },
    onError: (error: any) => {
      toast.error(error?.response?.data?.detail || "Unable to create exam.");
    },
  });

  const saveMatrixMutation = useMutation({
    mutationFn: async () => {
      const parsedMaxMarks = Number(maxMarks);
      if (!Number.isFinite(parsedMaxMarks) || parsedMaxMarks <= 0) {
        throw new Error("Enter a valid max marks value greater than zero.");
      }

      const records = Object.entries(draftMarks)
        .filter(([, value]) => value.trim() !== "")
        .map(([student_id, value]) => ({
          student_id,
          marks_obtained: Math.min(parsedMaxMarks, Math.max(0, Number(value))),
          max_marks: parsedMaxMarks,
          mark_status: "present",
        }));

      if (!records.length) {
        throw new Error("Enter at least one mark before saving.");
      }

      const response = await api.post(`/assessment/gradebook/sections/${selectedSectionId}/matrix`, {
        exam_id: selectedExamId,
        subject_id: selectedSubjectId,
        records,
      });
      return response.data as GradebookMatrix;
    },
    onSuccess: async (data) => {
      setSynced(true);
      setDraftMarks(
        Object.fromEntries(
          data.students.map((student) => [
            student.student_id,
            student.marks_obtained === null ? "" : String(student.marks_obtained),
          ]),
        ),
      );
      toast.success("Marks saved to the database.");
      await refetchMatrix();
      window.setTimeout(() => setSynced(false), 2500);
    },
    onError: (error: any) => {
      toast.error(error?.message || error?.response?.data?.detail || "Unable to save marks.");
    },
  });

  const handleMarkChange = (studentId: string, value: string) => {
    if (value !== "" && !/^\d*\.?\d*$/.test(value)) {
      return;
    }
    setDraftMarks((current) => ({
      ...current,
      [studentId]: value,
    }));
  };

  const handleCreateExam = () => {
    if (!selectedSectionId) {
      toast.error("Choose a section first.");
      return;
    }
    if (!newExamName.trim()) {
      toast.error("Enter an exam name.");
      return;
    }
    createExamMutation.mutate();
  };

  const handleSave = () => {
    if (!selectedSectionId || !selectedSubjectId || !selectedExamId) {
      toast.error("Choose a section, subject, and exam first.");
      return;
    }
    saveMatrixMutation.mutate();
  };

  const selectedSection = sections.find((section) => section.id === selectedSectionId) || null;
  const students = matrix?.students || [];
  const pageLoading = sectionsLoading || (selectedSectionId ? contextLoading : false);
  const saveDisabled = saveMatrixMutation.isPending || !students.length;
  const title = role === "teacher" ? "Section Gradebook" : "Exam & Marks Matrix";

  return (
    <AppLayout>
      <div className="space-y-6">
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between"
        >
          <div>
            <h1 className="text-2xl font-display font-bold text-foreground">{title}</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Review live marks by section, subject, and exam, then save them directly to the database.
            </p>
          </div>

          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <select
              value={selectedSectionId}
              onChange={(event) => setSelectedSectionId(event.target.value)}
              className="glass-input rounded-xl px-4 py-2 text-sm"
              disabled={sectionsLoading || !sections.length}
            >
              <option value="">{sectionsLoading ? "Loading sections..." : "Select section"}</option>
              {sections.map((section) => (
                <option key={section.id} value={section.id}>
                  {section.class_name} - Section {section.name}
                </option>
              ))}
            </select>

            <select
              value={selectedSubjectId}
              onChange={(event) => setSelectedSubjectId(event.target.value)}
              className="glass-input rounded-xl px-4 py-2 text-sm"
              disabled={!context?.subjects.length}
            >
              <option value="">{contextLoading ? "Loading subjects..." : "Select subject"}</option>
              {(context?.subjects || []).map((subject) => (
                <option key={subject.id} value={subject.id}>
                  {subject.name}
                  {subject.code ? ` (${subject.code})` : ""}
                </option>
              ))}
            </select>

            <select
              value={selectedExamId}
              onChange={(event) => setSelectedExamId(event.target.value)}
              className="glass-input rounded-xl px-4 py-2 text-sm"
              disabled={!context?.exams.length}
            >
              <option value="">{contextLoading ? "Loading exams..." : "Select exam"}</option>
              {(context?.exams || []).map((exam) => (
                <option key={exam.id} value={exam.id}>
                  {exam.name}
                  {exam.exam_date ? ` - ${exam.exam_date}` : ""}
                </option>
              ))}
            </select>

            <input
              type="number"
              min="1"
              step="1"
              value={maxMarks}
              onChange={(event) => setMaxMarks(event.target.value)}
              className="glass-input rounded-xl px-4 py-2 text-sm"
              placeholder="Max marks"
            />
          </div>
        </motion.div>

        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          {[
            { label: "Students", value: matrix?.summary.total_students || 0, icon: Users, color: "from-primary/30 to-secondary/20" },
            { label: "Entered", value: matrix?.summary.entered_marks || 0, icon: BookOpen, color: "from-sky-500/30 to-blue-500/20" },
            { label: "Average", value: `${Math.round(matrix?.summary.average_percentage || 0)}%`, icon: GraduationCap, color: "from-amber-500/30 to-orange-500/20" },
            { label: "Highest", value: `${Math.round(matrix?.summary.highest_percentage || 0)}%`, icon: Trophy, color: "from-emerald-500/30 to-teal-500/20" },
          ].map((stat, index) => (
            <motion.div
              key={stat.label}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.05 }}
              className="glass-card flex items-center gap-3 p-4"
            >
              <div className={`rounded-xl bg-gradient-to-br p-2.5 ${stat.color}`}>
                <stat.icon className="h-4 w-4 text-foreground" />
              </div>
              <div>
                <p className="font-display text-2xl font-bold text-foreground">{stat.value}</p>
                <p className="text-xs text-muted-foreground">{stat.label}</p>
              </div>
            </motion.div>
          ))}
        </div>

        <GlassCard delay={0.1} hover={false}>
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <p className="text-sm font-semibold text-foreground">
                {selectedSection ? `${selectedSection.class_name} - Section ${selectedSection.name}` : "Gradebook workspace"}
              </p>
              <p className="text-xs text-muted-foreground">
                Create an exam here if the selected section does not have one yet.
              </p>
            </div>

            <div className="grid gap-3 sm:grid-cols-[minmax(0,220px)_180px_auto]">
              <input
                value={newExamName}
                onChange={(event) => setNewExamName(event.target.value)}
                className="glass-input rounded-xl px-4 py-2 text-sm"
                placeholder="New exam name"
              />
              <input
                type="date"
                value={newExamDate}
                onChange={(event) => setNewExamDate(event.target.value)}
                className="glass-input rounded-xl px-4 py-2 text-sm"
              />
              <Button
                variant="outline"
                onClick={handleCreateExam}
                disabled={createExamMutation.isPending || !selectedSectionId}
              >
                {createExamMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : "Create Exam"}
              </Button>
            </div>
          </div>
        </GlassCard>

        <GlassCard delay={0.15} hover={false} className="overflow-x-auto">
          <div className="space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-sm font-semibold text-foreground">
                  {context?.subjects.find((subject) => subject.id === selectedSubjectId)?.name || "Subject"}{" "}
                  {context?.exams.find((exam) => exam.id === selectedExamId)?.name
                    ? `• ${context.exams.find((exam) => exam.id === selectedExamId)?.name}`
                    : ""}
                </p>
                <p className="text-xs text-muted-foreground">
                  {matrix
                    ? `${matrix.summary.entered_marks} of ${matrix.summary.total_students} students have marks recorded.`
                    : "Select a section, subject, and exam to load marks."}
                </p>
              </div>
              {(matrixLoading || saveMatrixMutation.isPending) && <Loader2 className="h-4 w-4 animate-spin text-primary" />}
            </div>

            {pageLoading && (
              <div className="rounded-2xl border border-dashed border-white/10 bg-white/[0.02] p-6 text-sm text-muted-foreground">
                Loading gradebook workspace...
              </div>
            )}

            {!pageLoading && !sections.length && (
              <div className="rounded-2xl border border-dashed border-white/10 bg-white/[0.02] p-6 text-sm text-muted-foreground">
                No sections are available for this account yet.
              </div>
            )}

            {!pageLoading && !!sections.length && !(context?.subjects.length || 0) && (
              <div className="rounded-2xl border border-dashed border-white/10 bg-white/[0.02] p-6 text-sm text-muted-foreground">
                This section does not have any subjects assigned yet.
              </div>
            )}

            {!pageLoading && !!sections.length && !!context?.subjects.length && !(context?.exams.length || 0) && (
              <div className="rounded-2xl border border-dashed border-white/10 bg-white/[0.02] p-6 text-sm text-muted-foreground">
                No exams exist for this section yet. Create one above to start entering marks.
              </div>
            )}

            {!pageLoading && !!selectedExamId && !!selectedSubjectId && !matrixLoading && !students.length && (
              <div className="rounded-2xl border border-dashed border-white/10 bg-white/[0.02] p-6 text-sm text-muted-foreground">
                This section does not have any students yet.
              </div>
            )}

            {!!students.length && (
              <table className="w-full min-w-[760px]">
                <thead>
                  <tr className="border-b border-white/[0.06]">
                    <th className="w-16 px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                      Roll
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                      Student
                    </th>
                    <th className="w-32 px-3 py-3 text-center text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                      Marks
                    </th>
                    <th className="w-24 px-3 py-3 text-center text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                      %
                    </th>
                    <th className="w-14 px-3 py-3 text-center text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                      Flag
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {students.map((student, index) => {
                    const rawValue = draftMarks[student.student_id] ?? "";
                    const numericValue = rawValue.trim() === "" ? null : Number(rawValue);
                    const percentage =
                      numericValue === null || !Number.isFinite(numericValue) || Number(maxMarks) <= 0
                        ? null
                        : Math.round((Math.min(Number(maxMarks), Math.max(0, numericValue)) / Number(maxMarks)) * 100);
                    const hasRisk = percentage !== null && percentage < 40;

                    return (
                      <motion.tr
                        key={student.student_id}
                        initial={{ opacity: 0, x: -10 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: index * 0.02 }}
                        className={`border-b border-white/[0.03] transition-colors hover:bg-white/[0.02] ${
                          hasRisk ? "bg-red-500/[0.03]" : ""
                        }`}
                      >
                        <td className="px-4 py-3 text-sm font-mono text-muted-foreground">{student.roll_number || "--"}</td>
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-2.5">
                            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-primary/30 to-accent/20 text-[10px] font-bold text-foreground">
                              {(student.full_name || "S")
                                .split(" ")
                                .map((part) => part[0])
                                .join("")
                                .slice(0, 2)}
                            </div>
                            <div>
                              <p className="text-sm font-medium text-foreground">{student.full_name || "Unnamed student"}</p>
                              <p className="text-xs text-muted-foreground">
                                {student.admission_number}
                                {student.roll_number ? ` · Roll ${student.roll_number}` : ""}
                              </p>
                            </div>
                          </div>
                        </td>
                        <td className="px-3 py-3 text-center">
                          <input
                            type="number"
                            min="0"
                            max={maxMarks || "100"}
                            step="0.1"
                            value={rawValue}
                            onChange={(event) => handleMarkChange(student.student_id, event.target.value)}
                            className={`h-9 w-20 rounded-lg border border-white/[0.08] bg-white/[0.04] text-center text-sm font-semibold transition-all focus:border-primary/50 focus:ring-1 focus:ring-primary/20 ${getGradeColor(percentage)}`}
                          />
                        </td>
                        <td className="px-3 py-3 text-center">
                          <span className={`text-sm font-bold ${getGradeColor(percentage)}`}>
                            {percentage === null ? "--" : `${percentage}%`}
                          </span>
                        </td>
                        <td className="px-3 py-3 text-center">
                          {hasRisk && <AlertCircle className="mx-auto h-4 w-4 text-red-400" />}
                        </td>
                      </motion.tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>
        </GlassCard>

        {!!students.length && (
          <div className="fixed bottom-6 left-1/2 z-50 -translate-x-1/2">
            <Button variant="gradient" className="h-12 px-8 text-base shadow-2xl glow-primary" onClick={handleSave} disabled={saveDisabled}>
              {saveMatrixMutation.isPending ? (
                <span className="flex items-center gap-2">
                  <Loader2 className="h-5 w-5 animate-spin" /> Saving...
                </span>
              ) : synced ? (
                <motion.span initial={{ scale: 0.9 }} animate={{ scale: 1 }} className="flex items-center gap-2">
                  <CheckCircle2 className="h-5 w-5" /> Saved!
                </motion.span>
              ) : (
                <span className="flex items-center gap-2">
                  <CloudUpload className="h-5 w-5" /> Save Marks
                </span>
              )}
            </Button>
          </div>
        )}
      </div>
    </AppLayout>
  );
};

export default Gradebook;
