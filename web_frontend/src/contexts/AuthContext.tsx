import { createContext, useContext, useState, ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";

export type UserRole = "admin" | "teacher" | "student" | "parent";

interface AuthContextType {
  role: UserRole | null;
  userName: string;
  userId: string | null;
  login: (data: { access_token: string; refresh_token: string; role: string; full_name?: string; user_id: string }) => void;
  logout: () => void;
  isAuthenticated: boolean;
}

const AuthContext = createContext<AuthContextType>({
  role: null,
  userName: "",
  userId: null,
  login: () => {},
  logout: () => {},
  isAuthenticated: false,
});

export const useAuth = () => useContext(AuthContext);

export const AuthProvider = ({ children }: { children: ReactNode }) => {
  const queryClient = useQueryClient();
  const [role, setRole] = useState<UserRole | null>(() => {
    const saved = localStorage.getItem("edutrack_role");
    return saved as UserRole | null;
  });
  const [userName, setUserName] = useState(() => {
    return localStorage.getItem("edutrack_user") || "";
  });
  const [userId, setUserId] = useState(() => {
    return localStorage.getItem("edutrack_user_id") || null;
  });

  const login = (data: { access_token: string; refresh_token: string; role: string; full_name?: string; user_id: string }) => {
    // Prevent the next account from seeing cached data from the previous login.
    queryClient.clear();

    const { access_token, refresh_token, role: newRole, full_name, user_id } = data;
    
    setRole(newRole as UserRole);
    const displayName = full_name || (newRole === "admin" ? "Admin" : newRole === "teacher" ? "Teacher" : newRole === "student" ? "Student" : "Parent");
    setUserName(displayName);
    setUserId(user_id);

    localStorage.setItem("edutrack_access_token", access_token);
    localStorage.setItem("edutrack_refresh_token", refresh_token);
    localStorage.setItem("edutrack_role", newRole);
    localStorage.setItem("edutrack_user", displayName);
    localStorage.setItem("edutrack_user_id", user_id);
  };

  const logout = () => {
    queryClient.clear();
    setRole(null);
    setUserName("");
    setUserId(null);
    localStorage.removeItem("edutrack_access_token");
    localStorage.removeItem("edutrack_refresh_token");
    localStorage.removeItem("edutrack_role");
    localStorage.removeItem("edutrack_user");
    localStorage.removeItem("edutrack_user_id");
  };

  return (
    <AuthContext.Provider value={{ role, userName, userId, login, logout, isAuthenticated: !!role }}>
      {children}
    </AuthContext.Provider>
  );
};
