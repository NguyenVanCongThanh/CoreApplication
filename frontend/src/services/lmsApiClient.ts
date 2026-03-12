import axios from "axios";
import { getCookie } from "@/utils/cookies";

const LMS_API_URL =
  process.env.NEXT_PUBLIC_LMS_API_URL || "http://localhost:8081/api/v1";

export const lmsApiClient = axios.create({
  baseURL: LMS_API_URL,
  headers: { "Content-Type": "application/json" },
});

// Attach auth token to every request
lmsApiClient.interceptors.request.use((config) => {
  const token = getCookie("authToken");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Redirect to login on 401
lmsApiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      window.location.href = "/login";
    }
    return Promise.reject(error);
  }
);