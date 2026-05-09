import axios from "axios";

// The backend API base URL
const API_URL = import.meta.env.VITE_API_URL || "/api/v1";

const api = axios.create({
  baseURL: API_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

const clearStoredAuth = () => {
  localStorage.removeItem("edutrack_access_token");
  localStorage.removeItem("edutrack_refresh_token");
  localStorage.removeItem("edutrack_role");
  localStorage.removeItem("edutrack_user");
  localStorage.removeItem("edutrack_user_id");
};

const isAuthRefreshCandidate = (error: any) => {
  const status = error.response?.status;
  const detail = error.response?.data?.detail || error.response?.data?.message || "";

  if (status === 401) {
    return true;
  }

  if (status === 403) {
    return [
      "Could not validate credentials",
      "Invalid access token type",
      "Token has been revoked",
    ].includes(detail);
  }

  return false;
};

// Request interceptor for adding the bearer token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem("edutrack_access_token");
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor for handling expired or invalid auth state
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    if (isAuthRefreshCandidate(error) && !originalRequest._retry) {
      originalRequest._retry = true;
      const refreshToken = localStorage.getItem("edutrack_refresh_token");

      if (refreshToken) {
        try {
          const response = await axios.post(`${API_URL}/user/auth/refresh`, {
            refresh_token: refreshToken,
          });

          const { access_token, refresh_token: newRefreshToken } = response.data;
          localStorage.setItem("edutrack_access_token", access_token);
          localStorage.setItem("edutrack_refresh_token", newRefreshToken);

          originalRequest.headers.Authorization = `Bearer ${access_token}`;
          return api(originalRequest);
        } catch (refreshError) {
          clearStoredAuth();
          window.location.href = "/login";
          return Promise.reject(refreshError);
        }
      } else {
        clearStoredAuth();
        if (typeof window !== "undefined" && window.location.pathname !== "/login") {
          window.location.href = "/login";
        }
      }
    }

    return Promise.reject(error);
  }
);

export default api;
