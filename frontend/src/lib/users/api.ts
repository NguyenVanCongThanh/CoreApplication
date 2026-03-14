import { API_BASE_URL } from "@/constants";
import { mapServerUserToClient } from "./mappers";
import { User } from "@/types";
import { getCookie } from "@/utils/cookies";

const BASE = API_BASE_URL;

function authHeaders() {
  const token = getCookie("authToken");
  return {
    Accept: "*/*",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    "Content-Type": "application/json",
  };
}

export async function fetchUsers(): Promise<User[]> {
  const res = await fetch(`${BASE}/api/users`, {
    method: "GET",
    headers: authHeaders(),
  });

  if (!res.ok) {
    const txt = await res.text().catch(() => "");
    throw new Error(`Fetch users failed: ${res.status} ${res.statusText}${txt ? " - " + txt : ""}`);
  }

  const data = await res.json();
  if (!Array.isArray(data)) return [];
  return data.map(mapServerUserToClient);
}

export async function postBulkRegister(
  payload: Array<{
    name: string;
    email: string;
    role: string;
    team: string;
    code?: string;
    type: string;
  }>
) {
  const res = await fetch(`${BASE}/api/auth/register/bulk`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({ users: payload }),
  });
  if (!res.ok) {
    const txt = await res.text().catch(() => "");
    throw new Error(`Bulk register failed: ${res.status} ${res.statusText}${txt ? " - " + txt : ""}`);
  }
  return res.json();
}

export async function postCreateUserSingle(user: {
  name: string;
  email: string;
  role: string;
  team: string;
  code: string;
  type: string;
}) {
  return postBulkRegister([user]);
}