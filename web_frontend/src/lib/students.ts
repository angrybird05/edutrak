import api from "@/lib/api";

export type StudentRecord = {
  id: string;
  user_id: string;
  full_name: string | null;
  school_id: string;
  class_id: string;
  section_id: string;
  admission_number: string;
  roll_number: string | null;
  dob: string | null;
  guardian_name: string | null;
  guardian_relation: string | null;
  guardian_phone: string | null;
  parent_joining_code: string | null;
};

export type StudentListResponse = {
  items: StudentRecord[];
  total: number;
  page: number;
  page_size: number;
};

export type StudentCreatePayload = {
  full_name: string;
  admission_number: string;
  roll_number?: string;
  dob?: string;
  school_id?: string;
  class_id: string;
  section_id: string;
  guardian_name: string;
  guardian_relation: string;
  guardian_phone: string;
};

export type StudentCreateResponse = StudentRecord & {
  parent_account_created: boolean;
};

export type StudentProfileSummary = {
  profile: {
    student_id: string;
    full_name: string | null;
    admission_number: string;
    roll_number: string | null;
    guardian_name: string | null;
    guardian_relation: string | null;
    guardian_phone: string | null;
    parent_joining_code: string | null;
    class: string | null;
    section: string | null;
  };
  subject_performance: Array<{
    subject: string;
    average_marks: number;
    records_count: number;
  }>;
  attendance: {
    present_days: number;
    total_days: number;
    attendance_percentage: number;
  };
  ai_summary: {
    insight_text: string | null;
    recommendations: string[] | null;
  };
  latest_report: {
    id: string;
    term_name: string;
    generated_at: string;
    pdf_url: string | null;
  } | null;
};

export type ParentChildRecord = {
  id: string;
  user_id: string;
  full_name: string | null;
  admission_number: string;
  roll_number: string | null;
  class_id: string;
  section_id: string;
  guardian_name: string | null;
  guardian_relation: string | null;
  guardian_phone: string | null;
  parent_joining_code: string | null;
};

export const fetchStudents = async (search?: string) => {
  const response = await api.get<StudentListResponse>("/identity/students/query", {
    params: { search: search || undefined, page_size: 100 },
  });
  return response.data;
};

const normalizeStudentResponse = (
  data: Partial<StudentCreateResponse>,
  payload: StudentCreatePayload,
): StudentCreateResponse => ({
  id: data.id || "",
  user_id: data.user_id || "",
  full_name: data.full_name ?? payload.full_name ?? null,
  school_id: data.school_id || payload.school_id || "",
  class_id: data.class_id || payload.class_id,
  section_id: data.section_id || payload.section_id,
  admission_number: data.admission_number || payload.admission_number,
  roll_number: data.roll_number ?? payload.roll_number ?? null,
  dob: data.dob ?? payload.dob ?? null,
  guardian_name: data.guardian_name ?? payload.guardian_name ?? null,
  guardian_relation: data.guardian_relation ?? payload.guardian_relation ?? null,
  guardian_phone: data.guardian_phone ?? payload.guardian_phone ?? null,
  parent_joining_code: data.parent_joining_code ?? null,
  parent_account_created: Boolean(data.parent_account_created),
});

const shouldRetryWithLegacyPayload = (error: any) => {
  if (error?.response?.status !== 422) {
    return false;
  }

  const details = error?.response?.data?.details;
  if (!Array.isArray(details)) {
    return false;
  }

  const failingFields = new Set(
    details
      .map((detail: any) => {
        const loc = Array.isArray(detail?.loc) ? detail.loc : [];
        return String(loc[loc.length - 1] || "");
      })
      .filter(Boolean),
  );

  return failingFields.has("phone") || failingFields.has("school_id");
};

export const createStudent = async (payload: StudentCreatePayload) => {
  try {
    const response = await api.post<StudentCreateResponse>("/identity/students", payload);
    return normalizeStudentResponse(response.data, payload);
  } catch (error: any) {
    if (payload.school_id && shouldRetryWithLegacyPayload(error)) {
      const legacyPayload = {
        ...payload,
        phone: payload.guardian_phone,
        school_id: payload.school_id,
      };
      const retryResponse = await api.post<Partial<StudentCreateResponse>>("/identity/students", legacyPayload);
      return normalizeStudentResponse(retryResponse.data, payload);
    }
    throw error;
  }
};

export const fetchStudentProfileSummary = async (studentId: string) => {
  const response = await api.get<StudentProfileSummary>(`/identity/students/${studentId}/profile-summary`);
  return response.data;
};

export const fetchParentChildren = async () => {
  const response = await api.get<ParentChildRecord[]>("/identity/parents/me/children");
  return response.data;
};

export const linkChildByCode = async (joiningCode: string) => {
  const response = await api.post<ParentChildRecord>("/identity/parents/link-by-code", {
    joining_code: joiningCode,
  });
  return response.data;
};
