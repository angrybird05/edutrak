import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Calendar, Check, CheckCircle2, Clock, Loader2, Users, X } from "lucide-react";
import { toast } from "sonner";

import AppLayout from "@/components/AppLayout";
import GlassCard from "@/components/GlassCard";
import { Button } from "@/components/ui/button";
import api from "@/lib/api";

type AttendanceStatus = "Present" | "Absent" | "Late" | null;

type AttendanceSection = {
  id: string;
  name: string;
  class_id: string;
  class_name: string;
};

type AttendanceSheetStudent = {
  student_id: string;
  full_name: string | null;
  admission_number: string;
  roll_number: string | null;
  status: AttendanceStatus;
};

type AttendanceSheetResponse = {
  date: string;
  class_id: string;
  class_name: string;
  section_id: string;
  section_name: string;
  students: AttendanceSheetStudent[];
  totals: {
    total: number;
    marked: number;
    present: number;
    absent: number;
    late: number;
  };
};

const statusStyles: Record<Exclude<AttendanceStatus, null>, string> = {
  Present: "bg-emerald-500/30 text-emerald-300 border-emerald-500/40",
  Absent: "bg-red-500/30 text-red-300 border-red-500/40",
  Late: "bg-amber-500/30 text-amber-300 border-amber-500/40",
};

const statusLabel: Record<Exclude<AttendanceStatus, null>, string> = {
  Present: "P",
  Absent: "A",
  Late: "L",
};

const Attendance = () => {
  const [date, setDate] = useState(new Date().toISOString().split("T")[0]);
  const [selectedSectionId, setSelectedSectionId] = useState<string>("");
  const [attendance, setAttendance] = useState<Record<string, AttendanceStatus>>({});
  const [submitted, setSubmitted] = useState(false);

  const { data: availableSections = [], isLoading: sectionsLoading } = useQuery<AttendanceSection[]>({
    queryKey: ["attendance-sections"],
    queryFn: async () => {
      const response = await api.get("/assessment/attendance/sections");
      return response.data;
    },
  });

  useEffect(() => {
    if (!availableSections.length) {
      setSelectedSectionId("");
      return;
    }

    if (!selectedSectionId || !availableSections.some((section) => section.id === selectedSectionId)) {
      setSelectedSectionId(availableSections[0].id);
    }
  }, [availableSections, selectedSectionId]);

  const { data: sheet, isLoading: sheetLoading, refetch: refetchSheet } = useQuery<AttendanceSheetResponse>({
    queryKey: ["attendance-sheet", selectedSectionId, date],
    enabled: !!selectedSectionId && !!date,
    queryFn: async () => {
      const response = await api.get(`/assessment/attendance/sections/${selectedSectionId}`, {
        params: { attendance_date: date },
      });
      return response.data;
    },
  });

  useEffect(() => {
    if (!sheet) {
      setAttendance({});
      return;
    }

    setAttendance(
      Object.fromEntries(sheet.students.map((student) => [student.student_id, student.status ?? null])),
    );
  }, [sheet]);

  const selectedSection = availableSections.find((section) => section.id === selectedSectionId) || null;
  const students = sheet?.students || [];
  const markedCount = Object.values(attendance).filter((value) => value !== null).length;
  const presentCount = Object.values(attendance).filter((value) => value === "Present").length;
  const absentCount = Object.values(attendance).filter((value) => value === "Absent").length;
  const lateCount = Object.values(attendance).filter((value) => value === "Late").length;

  const saveAttendanceMutation = useMutation({
    mutationFn: async () => {
      const records = Object.entries(attendance)
        .filter((entry): entry is [string, Exclude<AttendanceStatus, null>] => entry[1] !== null)
        .map(([student_id, status]) => ({ student_id, status }));

      const response = await api.post(`/assessment/attendance/sections/${selectedSectionId}`, {
        date,
        records,
      });
      return response.data as AttendanceSheetResponse;
    },
    onSuccess: async (data) => {
      setSubmitted(true);
      setAttendance(Object.fromEntries(data.students.map((student) => [student.student_id, student.status ?? null])));
      toast.success("Attendance saved to the database.");
      await refetchSheet();
      window.setTimeout(() => setSubmitted(false), 2500);
    },
    onError: (error: any) => {
      toast.error(error?.response?.data?.detail || "Unable to save attendance.");
    },
  });

  const toggleStatus = (studentId: string, status: Exclude<AttendanceStatus, null>) => {
    setAttendance((current) => ({
      ...current,
      [studentId]: current[studentId] === status ? null : status,
    }));
  };

  const handleSubmit = () => {
    if (!selectedSectionId) {
      toast.error("Choose a class section first.");
      return;
    }
    if (!students.length) {
      toast.error("No students found in this section.");
      return;
    }
    if (!markedCount) {
      toast.error("Mark at least one student before saving.");
      return;
    }
    saveAttendanceMutation.mutate();
  };

  const pageLoading = sectionsLoading;

  return (
    <AppLayout>
      <div className="space-y-6">
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between"
        >
          <div>
            <h1 className="text-2xl font-display font-bold text-foreground">Digital Attendance Pad</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Mark attendance from a lightweight live section roster backed by the database.
            </p>
          </div>

          <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
            <div className="relative">
              <Calendar className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <input
                type="date"
                value={date}
                onChange={(event) => setDate(event.target.value)}
                className="glass-input py-2 pl-10 pr-4 text-sm"
              />
            </div>

            <select
              value={selectedSectionId}
              onChange={(event) => setSelectedSectionId(event.target.value)}
              className="glass-input rounded-xl px-4 py-2 text-sm"
              disabled={pageLoading || !availableSections.length}
            >
              <option value="">{pageLoading ? "Loading sections..." : "Select section"}</option>
              {availableSections.map((section) => (
                <option key={section.id} value={section.id}>
                  {section.class_name} - Section {section.name}
                </option>
              ))}
            </select>
          </div>
        </motion.div>

        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {[
            { label: "Total", value: students.length, icon: Users, color: "from-primary/30 to-secondary/20" },
            { label: "Present", value: presentCount, icon: Check, color: "from-emerald-500/30 to-teal-500/20" },
            { label: "Absent", value: absentCount, icon: X, color: "from-red-500/30 to-rose-500/20" },
            { label: "Late", value: lateCount, icon: Clock, color: "from-amber-500/30 to-orange-500/20" },
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

        <GlassCard delay={0.15} hover={false}>
          <div className="space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-sm font-semibold text-foreground">
                  {selectedSection ? `${selectedSection.class_name} - Section ${selectedSection.name}` : "Section roster"}
                </p>
                <p className="text-xs text-muted-foreground">
                  {sheet ? `${sheet.totals.marked} of ${sheet.totals.total} students marked for ${date}` : "Choose a date and section to load attendance."}
                </p>
              </div>
              {(sheetLoading || saveAttendanceMutation.isPending) && <Loader2 className="h-4 w-4 animate-spin text-primary" />}
            </div>

            {pageLoading && (
              <div className="rounded-2xl border border-dashed border-white/10 bg-white/[0.02] p-6 text-sm text-muted-foreground">
                Loading attendance workspace...
              </div>
            )}

            {!pageLoading && !availableSections.length && (
              <div className="rounded-2xl border border-dashed border-white/10 bg-white/[0.02] p-6 text-sm text-muted-foreground">
                No class sections are available for this account yet.
              </div>
            )}

            {!pageLoading && !!availableSections.length && !sheetLoading && students.length === 0 && (
              <div className="rounded-2xl border border-dashed border-white/10 bg-white/[0.02] p-6 text-sm text-muted-foreground">
                This section does not have any students yet.
              </div>
            )}

            {!!students.length && (
              <div className="space-y-2">
                <div className="grid grid-cols-[1fr_auto] gap-4 px-4 py-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground sm:grid-cols-[72px_1fr_auto]">
                  <span className="hidden sm:block">Roll</span>
                  <span>Student Name</span>
                  <span className="text-right">Status</span>
                </div>

                {students.map((student, index) => (
                  <motion.div
                    key={student.student_id}
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: index * 0.02 }}
                    className="grid grid-cols-[1fr_auto] items-center gap-4 rounded-xl px-4 py-3 transition-colors duration-200 hover:bg-white/[0.03] sm:grid-cols-[72px_1fr_auto]"
                  >
                    <span className="hidden font-mono text-sm text-muted-foreground sm:block">
                      {student.roll_number || "--"}
                    </span>

                    <div className="flex items-center gap-3">
                      <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-primary/30 to-accent/20 text-xs font-bold text-foreground">
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

                    <div className="flex gap-1.5">
                      {(["Present", "Absent", "Late"] as Exclude<AttendanceStatus, null>[]).map((status) => (
                        <button
                          key={status}
                          onClick={() => toggleStatus(student.student_id, status)}
                          className={`h-9 w-10 rounded-lg border text-xs font-bold transition-all duration-200 ${
                            attendance[student.student_id] === status
                              ? statusStyles[status]
                              : "border-white/[0.08] bg-white/[0.03] text-muted-foreground hover:bg-white/[0.06]"
                          }`}
                        >
                          {statusLabel[status]}
                        </button>
                      ))}
                    </div>
                  </motion.div>
                ))}
              </div>
            )}
          </div>
        </GlassCard>

        <AnimatePresence>
          {(markedCount > 0 || saveAttendanceMutation.isPending) && !!students.length && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 20 }}
              className="fixed bottom-6 left-1/2 z-50 -translate-x-1/2"
            >
              <Button
                variant="gradient"
                className="h-12 px-8 text-base shadow-2xl glow-primary"
                onClick={handleSubmit}
                disabled={saveAttendanceMutation.isPending}
              >
                {saveAttendanceMutation.isPending ? (
                  <span className="flex items-center gap-2">
                    <Loader2 className="h-5 w-5 animate-spin" /> Saving...
                  </span>
                ) : submitted ? (
                  <motion.span initial={{ scale: 0.9 }} animate={{ scale: 1 }} className="flex items-center gap-2">
                    <CheckCircle2 className="h-5 w-5" /> Saved!
                  </motion.span>
                ) : (
                  <>Save Attendance for {markedCount} Students</>
                )}
              </Button>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </AppLayout>
  );
};

export default Attendance;
