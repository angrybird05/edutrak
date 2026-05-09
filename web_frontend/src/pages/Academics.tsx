import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  BookOpen,
  ChevronDown,
  ChevronRight,
  GraduationCap,
  Layers3,
  Loader2,
  Pencil,
  Plus,
  Save,
  Trash2,
  Users,
  X,
} from "lucide-react";
import { toast } from "sonner";

import AppLayout from "@/components/AppLayout";
import GlassCard from "@/components/GlassCard";
import { Button } from "@/components/ui/button";
import api from "@/lib/api";

type UserProfile = {
  id: string;
  school_id: string | null;
};

type AcademicSubject = {
  id: string;
  name: string;
  code?: string | null;
};

type AcademicSection = {
  id: string;
  name: string;
  class_id: string;
  subjects: AcademicSubject[];
};

type AcademicClass = {
  id: string;
  name: string;
  class_number: number;
  school_id: string;
  sections: AcademicSection[];
};

type AcademicStructureResponse = {
  classes: AcademicClass[];
  subjects: AcademicSubject[];
};

const getErrorMessage = (error: any, fallback: string) =>
  error?.response?.data?.message || error?.response?.data?.detail || fallback;

const normalize = (value: string) => value.trim().toLowerCase();

const Academics = () => {
  const queryClient = useQueryClient();
  const [expandedClasses, setExpandedClasses] = useState<Set<string>>(new Set());
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set());
  const [selectedSectionId, setSelectedSectionId] = useState<string | null>(null);
  const [selectedSectionSubjectIds, setSelectedSectionSubjectIds] = useState<string[]>([]);
  const [classForm, setClassForm] = useState({ name: "", class_number: "" });
  const [sectionForm, setSectionForm] = useState({ class_id: "", name: "" });
  const [subjectForm, setSubjectForm] = useState({ name: "", code: "" });
  const [showClassForm, setShowClassForm] = useState(false);
  const [showSectionForm, setShowSectionForm] = useState(false);
  const [showSubjectForm, setShowSubjectForm] = useState(false);
  const [editingClassId, setEditingClassId] = useState<string | null>(null);
  const [editingSectionId, setEditingSectionId] = useState<string | null>(null);
  const [editingSubjectId, setEditingSubjectId] = useState<string | null>(null);
  const [inlineSectionClassId, setInlineSectionClassId] = useState<string | null>(null);
  const [inlineSectionName, setInlineSectionName] = useState("");

  const { data: me } = useQuery<UserProfile>({
    queryKey: ["me"],
    queryFn: async () => {
      const response = await api.get("/identity/me");
      return response.data;
    },
  });

  const schoolId = me?.school_id || null;

  const { data: structure, isLoading } = useQuery<AcademicStructureResponse>({
    queryKey: ["academic-structure", schoolId],
    enabled: !!schoolId,
    queryFn: async () => {
      try {
        const response = await api.get(`/academic/structure/${schoolId}`);
        return response.data;
      } catch (error: any) {
        if (error?.response?.status !== 404) {
          throw error;
        }

        const [classesResponse, subjectsResponse] = await Promise.all([
          api.get(`/academic/classes/${schoolId}`),
          api.get(`/academic/subjects/${schoolId}`),
        ]);

        const classesWithSections = await Promise.all(
          (classesResponse.data as AcademicClass[]).map(async (classItem) => {
            const sectionsResponse = await api.get(`/academic/sections/${classItem.id}`);
            return {
              ...classItem,
              sections: ((sectionsResponse.data || []) as AcademicSection[]).map((section) => ({
                ...section,
                subjects: [],
              })),
            };
          }),
        );

        return {
          classes: classesWithSections,
          subjects: subjectsResponse.data || [],
        } satisfies AcademicStructureResponse;
      }
    },
  });

  const classes = structure?.classes || [];
  const subjects = structure?.subjects || [];
  const totalClasses = classes.length;
  const totalSections = classes.reduce((sum, item) => sum + item.sections.length, 0);
  const totalSectionSubjectLinks = classes.reduce(
    (sum, item) => sum + item.sections.reduce((sectionSum, section) => sectionSum + section.subjects.length, 0),
    0,
  );

  const selectedSection =
    classes.flatMap((classItem) => classItem.sections).find((section) => section.id === selectedSectionId) || null;

  useEffect(() => {
    if (!classes.length) {
      setSelectedSectionId(null);
      return;
    }

    const allSections = classes.flatMap((item) => item.sections);
    const existingSelection = allSections.some((section) => section.id === selectedSectionId);
    if (!selectedSectionId || !existingSelection) {
      setSelectedSectionId(allSections[0]?.id || null);
    }

    if (!expandedClasses.size) {
      setExpandedClasses(new Set(classes.map((item) => item.id)));
    }
  }, [classes, selectedSectionId, expandedClasses.size]);

  useEffect(() => {
    if (!selectedSection) {
      setSelectedSectionSubjectIds([]);
      return;
    }
    setSelectedSectionSubjectIds(selectedSection.subjects.map((subject) => subject.id));
    setExpandedSections((current) => {
      const next = new Set(current);
      next.add(selectedSection.id);
      return next;
    });
  }, [selectedSection]);

  const academicStructureKey = ["academic-structure", schoolId];

  const setAcademicStructure = (
    updater: (current: AcademicStructureResponse | undefined) => AcademicStructureResponse | undefined,
  ) => {
    queryClient.setQueryData<AcademicStructureResponse | undefined>(academicStructureKey, updater);
  };

  const refreshStructure = () => queryClient.invalidateQueries({ queryKey: academicStructureKey });

  const createClassMutation = useMutation({
    mutationFn: async () => {
      if (!schoolId) throw new Error("School not found");
      const response = await api.post("/academic/classes", {
        name: classForm.name.trim(),
        class_number: Number(classForm.class_number),
        school_id: schoolId,
      });
      return response.data as AcademicClass;
    },
    onSuccess: (createdClass) => {
      toast.success("Class created.");
      setClassForm({ name: "", class_number: "" });
      setShowClassForm(false);
      setExpandedClasses((current) => new Set(current).add(createdClass.id));
      setAcademicStructure((current) => {
        if (!current) return current;
        return {
          ...current,
          classes: [...current.classes, { ...createdClass, sections: [] }].sort(
            (a, b) => a.class_number - b.class_number || a.name.localeCompare(b.name),
          ),
        };
      });
      refreshStructure();
    },
    onError: (error) => {
      toast.error(getErrorMessage(error, "Unable to create class."));
    },
  });

  const createSectionMutation = useMutation({
    mutationFn: async (payload: { class_id: string; name: string }) => {
      const response = await api.post("/academic/sections", payload);
      return response.data as AcademicSection;
    },
    onSuccess: (createdSection, variables) => {
      toast.success("Section created.");
      const targetClassId = variables.class_id;
      const targetClass = classes.find((item) => item.id === targetClassId);
      setSectionForm({ class_id: "", name: "" });
      setShowSectionForm(false);
      setInlineSectionClassId(null);
      setInlineSectionName("");
      setSelectedSectionId(createdSection.id);
      setExpandedClasses((current) => new Set(current).add(targetClassId));
      setExpandedSections((current) => new Set(current).add(createdSection.id));
      setAcademicStructure((current) => {
        if (!current) return current;
        return {
          ...current,
          classes: current.classes.map((classItem) =>
            classItem.id === targetClassId
              ? {
                  ...classItem,
                  sections: [...classItem.sections, { ...createdSection, subjects: [] }].sort((a, b) =>
                    a.name.localeCompare(b.name),
                  ),
                }
              : classItem,
          ),
        };
      });
      if (targetClass) {
        toast.success(`${createdSection.name} added to ${targetClass.name}.`);
      }
      refreshStructure();
    },
    onError: (error) => {
      toast.error(getErrorMessage(error, "Unable to create section."));
    },
  });

  const updateClassMutation = useMutation({
    mutationFn: async () => {
      if (!editingClassId) throw new Error("Class not selected");
      const response = await api.patch(`/academic/classes/${editingClassId}`, {
        name: classForm.name.trim(),
        class_number: Number(classForm.class_number),
      });
      return response.data as AcademicClass;
    },
    onSuccess: (updatedClass) => {
      toast.success("Class updated.");
      setAcademicStructure((current) => {
        if (!current) return current;
        return {
          ...current,
          classes: current.classes
            .map((item) => (item.id === updatedClass.id ? { ...item, ...updatedClass } : item))
            .sort((a, b) => a.class_number - b.class_number || a.name.localeCompare(b.name)),
        };
      });
      resetClassForm();
      refreshStructure();
    },
    onError: (error) => {
      toast.error(getErrorMessage(error, "Unable to update class."));
    },
  });

  const deleteClassMutation = useMutation({
    mutationFn: async (classId: string) => {
      await api.delete(`/academic/classes/${classId}`);
      return classId;
    },
    onSuccess: (deletedClassId) => {
      toast.success("Class deleted.");
      setAcademicStructure((current) => {
        if (!current) return current;
        return {
          ...current,
          classes: current.classes.filter((item) => item.id !== deletedClassId),
        };
      });
      if (editingClassId === deletedClassId) {
        resetClassForm();
      }
      refreshStructure();
    },
    onError: (error) => {
      toast.error(getErrorMessage(error, "Unable to delete class."));
    },
  });

  const updateSectionMutation = useMutation({
    mutationFn: async () => {
      if (!editingSectionId) throw new Error("Section not selected");
      const response = await api.patch(`/academic/sections/${editingSectionId}`, {
        name: sectionForm.name.trim(),
      });
      return response.data as AcademicSection;
    },
    onSuccess: (updatedSection) => {
      toast.success("Section updated.");
      setAcademicStructure((current) => {
        if (!current) return current;
        return {
          ...current,
          classes: current.classes.map((classItem) =>
            classItem.id === updatedSection.class_id
              ? {
                  ...classItem,
                  sections: classItem.sections
                    .map((item) => (item.id === updatedSection.id ? { ...item, name: updatedSection.name } : item))
                    .sort((a, b) => a.name.localeCompare(b.name)),
                }
              : classItem,
          ),
        };
      });
      resetSectionForm();
      refreshStructure();
    },
    onError: (error) => {
      toast.error(getErrorMessage(error, "Unable to update section."));
    },
  });

  const deleteSectionMutation = useMutation({
    mutationFn: async (sectionId: string) => {
      await api.delete(`/academic/sections/${sectionId}`);
      return sectionId;
    },
    onSuccess: (deletedSectionId) => {
      toast.success("Section deleted.");
      setAcademicStructure((current) => {
        if (!current) return current;
        return {
          ...current,
          classes: current.classes.map((classItem) => ({
            ...classItem,
            sections: classItem.sections.filter((item) => item.id !== deletedSectionId),
          })),
        };
      });
      if (selectedSectionId === deletedSectionId) {
        setSelectedSectionId(null);
      }
      if (editingSectionId === deletedSectionId) {
        resetSectionForm();
      }
      refreshStructure();
    },
    onError: (error) => {
      toast.error(getErrorMessage(error, "Unable to delete section."));
    },
  });

  const createSubjectMutation = useMutation({
    mutationFn: async () => {
      if (!schoolId) throw new Error("School not found");
      const response = await api.post("/academic/subjects", {
        name: subjectForm.name.trim(),
        code: subjectForm.code.trim() || undefined,
        school_id: schoolId,
      });
      return response.data as AcademicSubject;
    },
    onSuccess: (createdSubject) => {
      toast.success("Subject created.");
      setSubjectForm({ name: "", code: "" });
      setShowSubjectForm(false);
      setAcademicStructure((current) => {
        if (!current) return current;
        return {
          ...current,
          subjects: [...current.subjects, createdSubject].sort((a, b) => a.name.localeCompare(b.name)),
        };
      });
      refreshStructure();
    },
    onError: (error) => {
      toast.error(getErrorMessage(error, "Unable to create subject."));
    },
  });

  const updateSubjectMutation = useMutation({
    mutationFn: async () => {
      if (!editingSubjectId) throw new Error("Subject not selected");
      const response = await api.patch(`/academic/subjects/${editingSubjectId}`, {
        name: subjectForm.name.trim(),
        code: subjectForm.code.trim() || null,
      });
      return response.data as AcademicSubject;
    },
    onSuccess: (updatedSubject) => {
      toast.success("Subject updated.");
      setAcademicStructure((current) => {
        if (!current) return current;
        return {
          ...current,
          subjects: current.subjects
            .map((item) => (item.id === updatedSubject.id ? updatedSubject : item))
            .sort((a, b) => a.name.localeCompare(b.name)),
          classes: current.classes.map((classItem) => ({
            ...classItem,
            sections: classItem.sections.map((section) => ({
              ...section,
              subjects: section.subjects
                .map((item) => (item.id === updatedSubject.id ? updatedSubject : item))
                .sort((a, b) => a.name.localeCompare(b.name)),
            })),
          })),
        };
      });
      resetSubjectForm();
      refreshStructure();
    },
    onError: (error) => {
      toast.error(getErrorMessage(error, "Unable to update subject."));
    },
  });

  const deleteSubjectMutation = useMutation({
    mutationFn: async (subjectId: string) => {
      await api.delete(`/academic/subjects/${subjectId}`);
      return subjectId;
    },
    onSuccess: (deletedSubjectId) => {
      toast.success("Subject deleted.");
      setAcademicStructure((current) => {
        if (!current) return current;
        return {
          ...current,
          subjects: current.subjects.filter((item) => item.id !== deletedSubjectId),
          classes: current.classes.map((classItem) => ({
            ...classItem,
            sections: classItem.sections.map((section) => ({
              ...section,
              subjects: section.subjects.filter((item) => item.id !== deletedSubjectId),
            })),
          })),
        };
      });
      setSelectedSectionSubjectIds((current) => current.filter((id) => id !== deletedSubjectId));
      if (editingSubjectId === deletedSubjectId) {
        resetSubjectForm();
      }
      refreshStructure();
    },
    onError: (error) => {
      toast.error(getErrorMessage(error, "Unable to delete subject."));
    },
  });

  const assignSectionSubjectsMutation = useMutation({
    mutationFn: async () => {
      if (!selectedSectionId) throw new Error("Section not selected");
      const response = await api.put(`/academic/sections/${selectedSectionId}/subjects`, {
        subject_ids: selectedSectionSubjectIds,
      });
      return response.data as AcademicStructureResponse;
    },
    onSuccess: (updatedStructure) => {
      toast.success("Section subjects updated.");
      queryClient.setQueryData<AcademicStructureResponse>(academicStructureKey, updatedStructure);
      refreshStructure();
    },
    onError: (error) => {
      toast.error(getErrorMessage(error, "Unable to update section subjects."));
    },
  });

  const toggleClass = (classId: string) => {
    setExpandedClasses((current) => {
      const next = new Set(current);
      next.has(classId) ? next.delete(classId) : next.add(classId);
      return next;
    });
  };

  const toggleSection = (sectionId: string) => {
    setExpandedSections((current) => {
      const next = new Set(current);
      next.has(sectionId) ? next.delete(sectionId) : next.add(sectionId);
      return next;
    });
  };

  const handleCreateClass = () => {
    const className = classForm.name.trim();
    if (!className) {
      toast.error("Class name is required.");
      return;
    }
    const classNumber = Number(classForm.class_number);
    if (!Number.isInteger(classNumber) || classNumber <= 0) {
      toast.error("Class number must be a positive whole number.");
      return;
    }
    const duplicateName = classes.some(
      (item) => normalize(item.name) === normalize(className) && item.id !== editingClassId,
    );
    if (duplicateName) {
      toast.error("A class with this name already exists.");
      return;
    }
    const duplicateNumber = classes.some(
      (item) => item.class_number === classNumber && item.id !== editingClassId,
    );
    if (duplicateNumber) {
      toast.error("A class with this number already exists.");
      return;
    }
    if (editingClassId) {
      updateClassMutation.mutate();
      return;
    }
    createClassMutation.mutate();
  };

  const handleCreateSection = () => {
    const sectionName = sectionForm.name.trim();
    if (!sectionForm.class_id) {
      toast.error("Choose a class for the new section.");
      return;
    }
    if (!sectionName) {
      toast.error("Section name is required.");
      return;
    }
    const parentClass = classes.find((item) => item.id === sectionForm.class_id);
    const duplicateSection = parentClass?.sections.some(
      (item) => normalize(item.name) === normalize(sectionName) && item.id !== editingSectionId,
    );
    if (duplicateSection) {
      toast.error("A section with this name already exists in the class.");
      return;
    }
    if (editingSectionId) {
      updateSectionMutation.mutate();
      return;
    }
    createSectionMutation.mutate({
      class_id: sectionForm.class_id,
      name: sectionName,
    });
  };

  const handleCreateSubject = () => {
    const subjectName = subjectForm.name.trim();
    const subjectCode = subjectForm.code.trim();
    if (!subjectName) {
      toast.error("Subject name is required.");
      return;
    }
    const duplicateName = subjects.some(
      (item) => normalize(item.name) === normalize(subjectName) && item.id !== editingSubjectId,
    );
    if (duplicateName) {
      toast.error("A subject with this name already exists.");
      return;
    }
    if (subjectCode) {
      const duplicateCode = subjects.some(
        (item) => normalize(item.code || "") === normalize(subjectCode) && item.id !== editingSubjectId,
      );
      if (duplicateCode) {
        toast.error("A subject with this code already exists.");
        return;
      }
    }
    if (editingSubjectId) {
      updateSubjectMutation.mutate();
      return;
    }
    createSubjectMutation.mutate();
  };

  const handleInlineSectionCreate = (classId: string) => {
    const sectionName = inlineSectionName.trim();
    if (!sectionName) {
      toast.error("Section name is required.");
      return;
    }
    const parentClass = classes.find((item) => item.id === classId);
    const duplicateSection = parentClass?.sections.some((item) => normalize(item.name) === normalize(sectionName));
    if (duplicateSection) {
      toast.error("A section with this name already exists in the class.");
      return;
    }
    createSectionMutation.mutate({
      class_id: classId,
      name: sectionName,
    });
  };

  const toggleSectionSubject = (subjectId: string) => {
    setSelectedSectionSubjectIds((current) =>
      current.includes(subjectId) ? current.filter((id) => id !== subjectId) : [...current, subjectId],
    );
  };

  const resetClassForm = () => {
    setClassForm({ name: "", class_number: "" });
    setEditingClassId(null);
    setShowClassForm(false);
  };

  const resetSectionForm = () => {
    setSectionForm({ class_id: "", name: "" });
    setEditingSectionId(null);
    setShowSectionForm(false);
  };

  const resetSubjectForm = () => {
    setSubjectForm({ name: "", code: "" });
    setEditingSubjectId(null);
    setShowSubjectForm(false);
  };

  return (
    <AppLayout>
      <div className="space-y-6">
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between"
        >
          <div>
            <h1 className="text-2xl font-display font-bold text-foreground">Academic Structure</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Create live classes, sections, and subjects, then map the right subjects to each section.
            </p>
            <p className="mt-2 text-xs text-muted-foreground">
              One class can have many sections, like Class 1 with Section A, Section B, and Section C.
            </p>
          </div>
          <Button
            variant="gradient"
            size="sm"
            className="gap-1.5"
            onClick={() => {
              if (!showClassForm) {
                setEditingClassId(null);
                setClassForm({ name: "", class_number: "" });
              }
              setShowClassForm((value) => !value);
            }}
          >
            <Plus className="h-4 w-4" /> Add Class
          </Button>
        </motion.div>

        {showClassForm && (
          <GlassCard className="space-y-4" hover={false} glow="accent">
            <div>
              <h2 className="text-lg font-display font-semibold text-foreground">
                {editingClassId ? "Edit Class" : "Create Class"}
              </h2>
              <p className="text-xs text-muted-foreground">
                {editingClassId ? "Update the selected class." : "Add a new class to your school's academic structure."}
              </p>
            </div>
            <div className="grid gap-3 md:grid-cols-3">
              <input
                type="text"
                value={classForm.name}
                onChange={(event) => setClassForm((current) => ({ ...current, name: event.target.value }))}
                placeholder="Class name"
                className="glass-input w-full px-4 py-2.5 text-sm"
              />
              <input
                type="number"
                min="1"
                value={classForm.class_number}
                onChange={(event) => setClassForm((current) => ({ ...current, class_number: event.target.value }))}
                placeholder="Class number"
                className="glass-input w-full px-4 py-2.5 text-sm"
              />
              <div className="flex gap-2">
                <Button
                  variant="gradient"
                  className="flex-1"
                  disabled={createClassMutation.isPending || updateClassMutation.isPending}
                  onClick={handleCreateClass}
                >
                  {createClassMutation.isPending || updateClassMutation.isPending ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Save className="h-4 w-4" />
                  )}
                  {editingClassId ? "Update Class" : "Save Class"}
                </Button>
                {editingClassId && (
                  <Button variant="outline" onClick={resetClassForm}>
                    <X className="h-4 w-4" />
                  </Button>
                )}
              </div>
            </div>
          </GlassCard>
        )}

        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          {[
            { label: "Classes", value: totalClasses, icon: BookOpen, color: "from-primary/30 to-secondary/20" },
            { label: "Sections", value: totalSections, icon: Users, color: "from-accent/30 to-primary/20" },
            { label: "Section Subject Links", value: totalSectionSubjectLinks, icon: GraduationCap, color: "from-emerald-500/30 to-teal-500/20" },
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

        <div className="grid grid-cols-1 gap-6 xl:grid-cols-[1.25fr_0.75fr]">
          <GlassCard className="overflow-hidden p-0" hover={false}>
            <div className="border-b border-white/[0.05] px-5 py-4">
              <h2 className="text-lg font-display font-semibold text-foreground">Live Academic Tree</h2>
              <p className="text-xs text-muted-foreground">These classes, sections, and subject mappings come from the backend.</p>
            </div>

            {isLoading ? (
              <div className="flex items-center justify-center p-12">
                <Loader2 className="h-8 w-8 animate-spin text-primary" />
              </div>
            ) : classes.length === 0 ? (
              <div className="p-8 text-center text-sm text-muted-foreground">
                No classes exist yet. Create your first class to start building the school structure.
              </div>
            ) : (
              <div className="divide-y divide-white/[0.04]">
                {classes.map((classItem) => (
                  <div key={classItem.id}>
                    <div className="flex items-center gap-3 px-5 py-4 transition-colors hover:bg-white/[0.03]">
                      <button
                        onClick={() => toggleClass(classItem.id)}
                        className="flex min-w-0 flex-1 items-center gap-3 text-left"
                      >
                      {expandedClasses.has(classItem.id) ? (
                        <ChevronDown className="h-4 w-4 flex-shrink-0 text-primary" />
                      ) : (
                        <ChevronRight className="h-4 w-4 flex-shrink-0 text-muted-foreground" />
                      )}
                      <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-primary/30 to-secondary/20">
                        <BookOpen className="h-4 w-4 text-foreground" />
                      </div>
                      <div className="text-left">
                        <p className="text-sm font-semibold text-foreground">{classItem.name}</p>
                        <p className="text-xs text-muted-foreground">Class number {classItem.class_number}</p>
                      </div>
                      <span className="ml-auto text-xs text-muted-foreground">{classItem.sections.length} sections</span>
                      </button>
                      <div className="flex gap-2">
                        <Button
                          variant="glass"
                          size="sm"
                          onClick={() => {
                            setEditingClassId(classItem.id);
                            setShowClassForm(true);
                            setClassForm({
                              name: classItem.name,
                              class_number: String(classItem.class_number),
                            });
                          }}
                        >
                          <Pencil className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          disabled={deleteClassMutation.isPending}
                          onClick={() => deleteClassMutation.mutate(classItem.id)}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>

                    {expandedClasses.has(classItem.id) && (
                      <div className="border-t border-white/[0.04] bg-black/5">
                        <div className="flex items-center justify-between px-5 py-3">
                          <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">Sections</p>
                          <Button
                            variant="glass"
                            size="sm"
                            onClick={() => {
                              setInlineSectionClassId((current) => (current === classItem.id ? null : classItem.id));
                              setInlineSectionName("");
                            }}
                          >
                            <Plus className="h-4 w-4" />
                            Add Section
                          </Button>
                        </div>

                        {inlineSectionClassId === classItem.id && (
                          <div className="px-5 pb-4">
                            <div className="flex gap-2 rounded-2xl border border-white/10 bg-white/[0.03] p-3">
                              <input
                                type="text"
                                value={inlineSectionName}
                                onChange={(event) => setInlineSectionName(event.target.value)}
                                placeholder={`Add a new section to ${classItem.name}`}
                                className="glass-input flex-1 px-4 py-2.5 text-sm"
                              />
                              <Button
                                variant="gradient"
                                disabled={createSectionMutation.isPending}
                                onClick={() => handleInlineSectionCreate(classItem.id)}
                              >
                                {createSectionMutation.isPending ? (
                                  <Loader2 className="h-4 w-4 animate-spin" />
                                ) : (
                                  <Save className="h-4 w-4" />
                                )}
                                Save
                              </Button>
                              <Button
                                variant="outline"
                                onClick={() => {
                                  setInlineSectionClassId(null);
                                  setInlineSectionName("");
                                }}
                              >
                                <X className="h-4 w-4" />
                              </Button>
                            </div>
                          </div>
                        )}

                        {classItem.sections.length === 0 ? (
                          <div className="px-5 pb-4 text-sm text-muted-foreground">No sections have been created for this class yet.</div>
                        ) : (
                          classItem.sections.map((section) => {
                            const isSelected = selectedSectionId === section.id;
                            return (
                              <div key={section.id} className="border-t border-white/[0.03]">
                                <div
                                  className={`flex items-center gap-3 px-10 py-3 transition-colors ${
                                    isSelected ? "bg-primary/10" : "hover:bg-white/[0.02]"
                                  }`}
                                >
                                  <button
                                    onClick={() => {
                                      setSelectedSectionId(section.id);
                                      toggleSection(section.id);
                                    }}
                                    className="flex min-w-0 flex-1 items-center gap-3 text-left"
                                  >
                                  {expandedSections.has(section.id) ? (
                                    <ChevronDown className="h-3.5 w-3.5 flex-shrink-0 text-secondary" />
                                  ) : (
                                    <ChevronRight className="h-3.5 w-3.5 flex-shrink-0 text-muted-foreground" />
                                  )}
                                  <Users className="h-3.5 w-3.5 text-muted-foreground" />
                                  <span className="text-sm text-foreground">{section.name}</span>
                                  <span className="ml-auto text-xs text-muted-foreground">
                                    {section.subjects.length} subjects
                                  </span>
                                  </button>
                                  <div className="flex gap-2">
                                    <Button
                                      variant="glass"
                                      size="sm"
                                      onClick={() => {
                                        setEditingSectionId(section.id);
                                        setShowSectionForm(true);
                                        setSectionForm({ class_id: section.class_id, name: section.name });
                                      }}
                                    >
                                      <Pencil className="h-4 w-4" />
                                    </Button>
                                    <Button
                                      variant="outline"
                                      size="sm"
                                      disabled={deleteSectionMutation.isPending}
                                      onClick={() => deleteSectionMutation.mutate(section.id)}
                                    >
                                      <Trash2 className="h-4 w-4" />
                                    </Button>
                                  </div>
                                </div>

                                {expandedSections.has(section.id) && (
                                  <div className="space-y-2 px-16 pb-4 pt-1">
                                    {section.subjects.length === 0 ? (
                                      <div className="rounded-xl border border-dashed border-white/10 bg-white/[0.02] px-4 py-3 text-xs text-muted-foreground">
                                        No subjects assigned to this section yet.
                                      </div>
                                    ) : (
                                      section.subjects.map((subject) => (
                                        <div
                                          key={subject.id}
                                          className="flex items-center gap-2 rounded-xl bg-white/[0.03] px-4 py-2 text-sm"
                                        >
                                          <div className="h-1.5 w-1.5 rounded-full bg-primary/60" />
                                          <span className="text-foreground">{subject.name}</span>
                                          {subject.code && (
                                            <span className="rounded-full bg-white/[0.05] px-2 py-1 text-[11px] text-muted-foreground">
                                              {subject.code}
                                            </span>
                                          )}
                                        </div>
                                      ))
                                    )}
                                  </div>
                                )}
                              </div>
                            );
                          })
                        )}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </GlassCard>

          <div className="space-y-6">
            <GlassCard className="space-y-4" hover={false}>
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-lg font-display font-semibold text-foreground">
                    {editingSectionId ? "Edit Section" : "Create Section"}
                  </h2>
                  <p className="text-xs text-muted-foreground">
                    {editingSectionId
                      ? "Rename the selected section."
                      : "Add a section inside an existing class."}
                  </p>
                </div>
                <Button
                  variant="glass"
                  size="sm"
                  onClick={() => {
                    if (showSectionForm && editingSectionId) {
                      resetSectionForm();
                      return;
                    }
                    setShowSectionForm((value) => !value);
                  }}
                >
                  <Plus className="h-4 w-4" />
                  {showSectionForm ? "Hide" : editingSectionId ? "Edit" : "Add"}
                </Button>
              </div>

              {showSectionForm && (
                <div className="space-y-3">
                  <select
                    value={sectionForm.class_id}
                    onChange={(event) => setSectionForm((current) => ({ ...current, class_id: event.target.value }))}
                    className="glass-input w-full px-4 py-2.5 text-sm"
                  >
                    <option value="">Choose class</option>
                    {classes.map((classItem) => (
                      <option key={classItem.id} value={classItem.id}>
                        {classItem.name}
                      </option>
                    ))}
                  </select>
                  <input
                    type="text"
                    value={sectionForm.name}
                    onChange={(event) => setSectionForm((current) => ({ ...current, name: event.target.value }))}
                    placeholder="Section name"
                    className="glass-input w-full px-4 py-2.5 text-sm"
                  />
                  <div className="flex gap-2">
                    <Button
                      variant="gradient"
                      className="flex-1"
                      disabled={createSectionMutation.isPending || updateSectionMutation.isPending}
                      onClick={handleCreateSection}
                    >
                      {createSectionMutation.isPending || updateSectionMutation.isPending ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <Save className="h-4 w-4" />
                      )}
                      {editingSectionId ? "Update Section" : "Save Section"}
                    </Button>
                    {editingSectionId && (
                      <Button variant="outline" onClick={resetSectionForm}>
                        <X className="h-4 w-4" />
                      </Button>
                    )}
                  </div>
                </div>
              )}
            </GlassCard>

            <GlassCard className="space-y-4" hover={false} glow="accent">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-lg font-display font-semibold text-foreground">
                    {editingSubjectId ? "Edit Subject" : "Subject Bank"}
                  </h2>
                  <p className="text-xs text-muted-foreground">
                    {editingSubjectId
                      ? "Update the selected subject details."
                      : "Create school subjects, then map them to sections."}
                  </p>
                </div>
                <Button
                  variant="glass"
                  size="sm"
                  onClick={() => {
                    if (showSubjectForm && editingSubjectId) {
                      resetSubjectForm();
                      return;
                    }
                    setShowSubjectForm((value) => !value);
                  }}
                >
                  <Plus className="h-4 w-4" />
                  {showSubjectForm ? "Hide" : editingSubjectId ? "Edit" : "Add"}
                </Button>
              </div>

              {showSubjectForm && (
                <div className="grid gap-3">
                  <input
                    type="text"
                    value={subjectForm.name}
                    onChange={(event) => setSubjectForm((current) => ({ ...current, name: event.target.value }))}
                    placeholder="Subject name"
                    className="glass-input w-full px-4 py-2.5 text-sm"
                  />
                  <input
                    type="text"
                    value={subjectForm.code}
                    onChange={(event) => setSubjectForm((current) => ({ ...current, code: event.target.value }))}
                    placeholder="Subject code (optional)"
                    className="glass-input w-full px-4 py-2.5 text-sm"
                  />
                  <div className="flex gap-2">
                    <Button
                      variant="gradient"
                      className="flex-1"
                      disabled={createSubjectMutation.isPending || updateSubjectMutation.isPending}
                      onClick={handleCreateSubject}
                    >
                      {createSubjectMutation.isPending || updateSubjectMutation.isPending ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <Save className="h-4 w-4" />
                      )}
                      {editingSubjectId ? "Update Subject" : "Save Subject"}
                    </Button>
                    {editingSubjectId && (
                      <Button variant="outline" onClick={resetSubjectForm}>
                        <X className="h-4 w-4" />
                      </Button>
                    )}
                  </div>
                </div>
              )}

              <div className="space-y-2">
                {subjects.map((subject) => (
                  <div
                    key={subject.id}
                    className="flex items-center justify-between gap-3 rounded-2xl border border-white/10 bg-white/[0.03] px-4 py-3"
                  >
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium text-foreground">{subject.name}</p>
                      <p className="text-xs text-muted-foreground">
                        {subject.code ? `Code: ${subject.code}` : "No subject code set"}
                      </p>
                    </div>
                    <div className="flex gap-2">
                      <Button
                        variant="glass"
                        size="sm"
                        onClick={() => {
                          setEditingSubjectId(subject.id);
                          setShowSubjectForm(true);
                          setSubjectForm({ name: subject.name, code: subject.code || "" });
                        }}
                      >
                        <Pencil className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={deleteSubjectMutation.isPending}
                        onClick={() => deleteSubjectMutation.mutate(subject.id)}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                ))}
                {!subjects.length && <p className="text-sm text-muted-foreground">No subjects created yet.</p>}
              </div>
            </GlassCard>

            <GlassCard className="space-y-4" hover={false}>
              <div>
                <h2 className="text-lg font-display font-semibold text-foreground">Section Subject Mapping</h2>
                <p className="text-xs text-muted-foreground">
                  Select a section from the left, then choose which subjects belong to it.
                </p>
              </div>

              {!selectedSection ? (
                <div className="rounded-2xl border border-dashed border-white/10 bg-white/[0.02] p-5 text-sm text-muted-foreground">
                  Choose a section from the academic tree to manage its subject list.
                </div>
              ) : (
                <>
                  <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
                    <p className="text-xs uppercase tracking-[0.2em] text-primary">Selected Section</p>
                    <p className="mt-2 text-base font-semibold text-foreground">{selectedSection.name}</p>
                    <p className="text-xs text-muted-foreground">Assign the subjects taught in this section.</p>
                  </div>

                  <div className="space-y-2">
                    {subjects.map((subject) => {
                      const selected = selectedSectionSubjectIds.includes(subject.id);
                      return (
                        <button
                          key={subject.id}
                          type="button"
                          onClick={() => toggleSectionSubject(subject.id)}
                          className={`flex w-full items-center justify-between rounded-2xl border px-4 py-3 text-left transition-all ${
                            selected
                              ? "border-primary/30 bg-primary/12 text-foreground"
                              : "border-white/10 bg-white/[0.03] text-muted-foreground hover:bg-white/[0.05]"
                          }`}
                        >
                          <div>
                            <p className="text-sm font-medium">{subject.name}</p>
                            {subject.code && <p className="text-xs opacity-80">{subject.code}</p>}
                          </div>
                          <div className={`h-3 w-3 rounded-full ${selected ? "bg-primary" : "bg-white/10"}`} />
                        </button>
                      );
                    })}
                  </div>

                  <Button
                    variant="gradient"
                    className="w-full"
                    disabled={assignSectionSubjectsMutation.isPending}
                    onClick={() => assignSectionSubjectsMutation.mutate()}
                  >
                    {assignSectionSubjectsMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Layers3 className="h-4 w-4" />}
                    Save Section Subjects
                  </Button>
                </>
              )}
            </GlassCard>
          </div>
        </div>
      </div>
    </AppLayout>
  );
};

export default Academics;
