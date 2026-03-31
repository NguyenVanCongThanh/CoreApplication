import axios from "axios";

export const lmsApiClient = axios.create({
  baseURL: "/lmsapiv1",
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