import type { FieldGeometry, FieldProfile, GoldenField } from "@/types/api";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  try {
    const res = await fetch(`${API_URL}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    });
    if (res.ok) {
      return (await res.json()) as T;
    }
  } catch (err) {
    // API not running or unreachable, fallback below
  }

  // Fallback to static public/golden data for demo resilience
  if (path === "/golden") {
    const localRes = await fetch("/golden/fields.json");
    if (localRes.ok) return localRes.json() as Promise<T>;
  }
  const goldenMatch = path.match(/^\/golden\/([^/]+)\/profile$/);
  if (goldenMatch) {
    const fieldId = goldenMatch[1];
    const localRes = await fetch(`/golden/${fieldId}/profile.json`);
    if (localRes.ok) return localRes.json() as Promise<T>;
  }

  throw new Error(`Failed to load ${path}`);
}

export const api = {
  goldenFields: () => request<GoldenField[]>("/golden"),
  goldenProfile: (id: string) => request<FieldProfile>(`/golden/${id}/profile`),
  profile: (field: FieldGeometry) =>
    request<FieldProfile>("/profile", { method: "POST", body: JSON.stringify(field) }),
};
