let cachedToken: string | null = null;
let fetchPromise: Promise<string | null> | null = null;

export async function getAuthToken(): Promise<string | null> {
  if (cachedToken !== null) return cachedToken;

  if (typeof window === "undefined") return null;

  if (fetchPromise) return fetchPromise;

  fetchPromise = fetch("/api/auth/token", {
    credentials: "include",
    cache: "no-store",
  })
    .then((res) => {
      if (!res.ok) return null;
      return res.json() as Promise<{ token: string | null }>;
    })
    .then((data) => {
      cachedToken = data?.token ?? null;
      fetchPromise = null;
      return cachedToken;
    })
    .catch(() => {
      fetchPromise = null;
      return null;
    });

  return fetchPromise;
}

export function clearAuthToken(): void {
  cachedToken = null;
  fetchPromise = null;
}

export function setAuthToken(token: string): void {
  cachedToken = token;
  fetchPromise = null;
}