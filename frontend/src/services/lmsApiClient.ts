import axios from "axios";

const LMS_API_URL =
  process.env.NEXT_PUBLIC_LMS_API_URL || "http://localhost:8081/api/v1";

export const lmsApiClient = axios.create({
  baseURL: LMS_API_URL,
  headers: { "Content-Type": "application/json" },
  withCredentials: true,
});

lmsApiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401) {
      const { signOut } = await import("next-auth/react");
      if (typeof window !== "undefined") {
        signOut({ callbackUrl: "/login" });
      }
    }
    return Promise.reject(error);
  }
);