import axios from "axios";
import { getAuthToken, clearAuthToken } from "@/utils/tokenManager";

const LMS_API_URL =
  process.env.NEXT_PUBLIC_LMS_API_URL || "http://localhost:8081/api/v1";

export const lmsApiClient = axios.create({
  baseURL: LMS_API_URL,
  headers: { "Content-Type": "application/json" },
  withCredentials: true,
});

lmsApiClient.interceptors.request.use(async (config) => {
  const token = await getAuthToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

lmsApiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      clearAuthToken();
      if (typeof window !== "undefined") {
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  }
);