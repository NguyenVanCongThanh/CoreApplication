import { API_BASE_URL } from "@/constants";
import { getAuthToken } from "@/utils/tokenManager";

export class ApiClient {
  readonly baseURL: string;

  constructor(baseURL: string) {
    this.baseURL = baseURL;
  }

  private async getHeaders(): Promise<HeadersInit> {
    const token = await getAuthToken();
    return {
      "Content-Type": "application/json",
      Accept: "*/*",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    };
  }

  async get<T>(endpoint: string): Promise<T> {
    const response = await fetch(`${this.baseURL}${endpoint}`, {
      method: "GET",
      headers: await this.getHeaders(),
      credentials: "include",
    });
    if (!response.ok) {
      const text = await response.text().catch(() => "");
      throw new Error(`GET ${endpoint} failed (${response.status})${text ? `: ${text}` : ""}`);
    }
    return response.json();
  }

  async post<T>(endpoint: string, data: unknown): Promise<T> {
    const response = await fetch(`${this.baseURL}${endpoint}`, {
      method: "POST",
      headers: await this.getHeaders(),
      credentials: "include",
      body: JSON.stringify(data),
    });
    if (!response.ok) {
      const errorText = await response.text();
      console.log(response)
      throw new Error(errorText || `POST ${endpoint} failed (${response.status})`);
    }
    return response.json();
  }

  async patch<T>(endpoint: string, data: unknown): Promise<T> {
    const response = await fetch(`${this.baseURL}${endpoint}`, {
      method: "PATCH",
      headers: await this.getHeaders(),
      credentials: "include",
      body: JSON.stringify(data),
    });
    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(errorText || `PATCH ${endpoint} failed (${response.status})`);
    }
    return response.json();
  }

  async put<T>(endpoint: string, data: unknown): Promise<T> {
    const response = await fetch(`${this.baseURL}${endpoint}`, {
      method: "PUT",
      headers: await this.getHeaders(),
      credentials: "include",
      body: JSON.stringify(data),
    });
    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(errorText || `PUT ${endpoint} failed (${response.status})`);
    }
    return response.json();
  }

  async delete(endpoint: string): Promise<void> {
    const response = await fetch(`${this.baseURL}${endpoint}`, {
      method: "DELETE",
      headers: await this.getHeaders(),
      credentials: "include",
    });
    if (!response.ok) {
      throw new Error(`DELETE ${endpoint} failed (${response.status})`);
    }
  }

  async uploadFile<T>(endpoint: string, formData: FormData): Promise<T> {
    const token = await getAuthToken();
    const response = await fetch(`${this.baseURL}${endpoint}`, {
      method: "POST",
      credentials: "include",
      headers: {
        Accept: "*/*",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        // Không set Content-Type → browser tự thêm multipart/form-data + boundary
      },
      body: formData,
    });
    if (!response.ok) {
      const text = await response.text().catch(() => "");
      throw new Error(`Upload ${endpoint} failed (${response.status})${text ? `: ${text}` : ""}`);
    }
    return response.json();
  }
}

export const apiClient = new ApiClient(API_BASE_URL);