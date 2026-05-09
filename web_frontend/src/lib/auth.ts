import api from "@/lib/api";

export type RequestedLoginRole = "teacher" | "student" | "parent";

export type AuthResponse = {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user_id: string;
  role: string;
  full_name?: string | null;
};

export const loginWithPassword = async (username: string, password: string) => {
  const response = await api.post<AuthResponse>("/user/auth/login/password", {
    username: username.trim(),
    password,
  });
  return response.data;
};

export type StudentLoginChoice = {
  student_id: string;
  user_id: string;
  full_name: string;
  admission_number: string;
  roll_number?: string | null;
};

export type StudentSelectionResponse = {
  selection_required: true;
  selection_token: string;
  role: "student";
  phone: string;
  profiles: StudentLoginChoice[];
};

export const requestOtp = async (phone: string, requestedRole: RequestedLoginRole) => {
  const response = await api.post("/user/auth/login/otp", {
    phone,
    requested_role: requestedRole,
  });
  return response.data;
};

export const verifyOtp = async (phone: string, otpCode: string, requestedRole: RequestedLoginRole) => {
  const response = await api.post<AuthResponse | StudentSelectionResponse>("/user/auth/verify/otp", {
    phone,
    otp_code: otpCode,
    requested_role: requestedRole,
  });
  return response.data;
};

export const selectStudentProfile = async (selectionToken: string, studentId: string) => {
  const response = await api.post<AuthResponse>("/user/auth/select-profile", {
    selection_token: selectionToken,
    student_id: studentId,
  });
  return response.data;
};
