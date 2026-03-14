import { API_BASE_URL } from "@/constants";
import { getCookie } from "@/utils/cookies";

export class ApiClient {
  readonly baseURL: string;

  constructor(baseURL: string) {
    this.baseURL = baseURL;
  }

  private getHeaders(): HeadersInit {
    const token = getCookie("authToken");
    return {
      "Content-Type": "application/json",
      Accept: "*/*",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    };
  }

  async get<T>(endpoint: string): Promise<T> {
    const response = await fetch(`${this.baseURL}${endpoint}`, {
      method: "GET",
      headers: this.getHeaders(),
    });
    if (!response.ok) throw new Error(`GET ${endpoint} failed`);
    return response.json();
  }

  async post<T>(endpoint: string, data: any): Promise<T> {
    const response = await fetch(`${this.baseURL}${endpoint}`, {
      method: "POST",
      headers: this.getHeaders(),
      body: JSON.stringify(data),
    });
    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(errorText || `POST ${endpoint} failed`);
    }
    return response.json();
  }

  async patch<T>(endpoint: string, data: any): Promise<T> {
    const response = await fetch(`${this.baseURL}${endpoint}`, {
      method: "PATCH",
      headers: this.getHeaders(),
      body: JSON.stringify(data),
    });
    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(errorText || `PATCH ${endpoint} failed`);
    }
    return response.json();
  }

  async put<T>(endpoint: string, data: any): Promise<T> {
    const response = await fetch(`${this.baseURL}${endpoint}`, {
      method: "PUT",
      headers: this.getHeaders(),
      body: JSON.stringify(data),
    });
    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(errorText || `PUT ${endpoint} failed`);
    }
    return response.json();
  }

  async delete(endpoint: string): Promise<void> {
    const response = await fetch(`${this.baseURL}${endpoint}`, {
      method: "DELETE",
      headers: this.getHeaders(),
    });
    if (!response.ok) throw new Error(`DELETE ${endpoint} failed`);
  }

  async uploadFile<T>(endpoint: string, formData: FormData): Promise<T> {
    const token = getCookie("authToken");
    const response = await fetch(`${this.baseURL}${endpoint}`, {
      method: "POST",
      headers: {
        Accept: "*/*",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        // NOTE: Không set Content-Type — browser tự set multipart/form-data + boundary
      },
      body: formData,
    });
    if (!response.ok) throw new Error(`Upload ${endpoint} failed`);
    return response.json();
  }
}

export const apiClient = new ApiClient(API_BASE_URL);