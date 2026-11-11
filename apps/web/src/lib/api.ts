import type {
  CropSpec,
  FarmConstraints,
  FieldGeometry,
  FieldProfile,
  GoldenField,
  RecommendJobStatus,
  RecommendRequest,
  StrategyRecommendation,
  SuitabilityItem,
} from "@/types/api";
import { adaptStrategiesForHorizon } from "@/lib/fallbackStrategies";
import { generateFallbackProfile } from "@/lib/fallbackProfile";

// On Vercel:
// - In the browser: uses relative `/api` (routed to the FastAPI service via top-level rewrite).
// - On the server: uses `process.env.API_URL` injected by the Vercel service binding.
// - In local standalone dev: falls back to NEXT_PUBLIC_API_URL or http://localhost:8000.
export const API_URL = (
  typeof window === "undefined"
    ? (process.env.API_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000")
    : (process.env.NEXT_PUBLIC_API_URL || "/api")
).replace(/\/$/, "");

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let backendError: string | null = null;
  try {
    const res = await fetch(`${API_URL}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    });
    if (res.ok) {
      return (await res.json()) as T;
    }
    const errData = await res.json().catch(() => null);
    if (errData?.detail) {
      backendError = String(errData.detail);
    }
  } catch {
    // API not running or unreachable, fallback below
  }

  // Fallback to static public/golden data for demo resilience
  if (path === "/golden") {
    const localRes = await fetch("/golden/fields.json");
    if (localRes.ok) return localRes.json() as Promise<T>;
  }
  if (path === "/crops") {
    const localRes = await fetch("/golden/crops.json");
    if (localRes.ok) return localRes.json() as Promise<T>;
  }
  const goldenMatch = path.match(/^\/golden\/([^/]+)\/profile$/);
  if (goldenMatch) {
    const fieldId = goldenMatch[1];
    const localRes = await fetch(`/golden/${fieldId}/profile.json`);
    if (localRes.ok) return localRes.json() as Promise<T>;
  }
  const goldenRecMatch = path.match(/^\/golden\/([^/]+)\/recommendations$/);
  if (goldenRecMatch) {
    const fieldId = goldenRecMatch[1];
    const localRes = await fetch(`/golden/${fieldId}/recommendations.json`);
    if (localRes.ok) return localRes.json() as Promise<T>;
  }

  // If live /recommend is requested while backend API is offline, serve precomputed golden recommendations
  // ONLY if reqBody.field.id exactly matches a known demo benchmark field ID (WS-B2)
  if (path === "/recommend" && init?.body) {
    try {
      const reqBody = JSON.parse(init.body as string) as RecommendRequest;
      const fieldId = reqBody.field?.id;
      if (fieldId) {
        const fieldsRes = await fetch("/golden/fields.json");
        if (fieldsRes.ok) {
          const fields = (await fieldsRes.json()) as GoldenField[];
          const exact = fields.find((f) => f.id === fieldId);
          if (exact) {
            await new Promise((resolve) => setTimeout(resolve, 300));
            const recRes = await fetch(`/golden/${exact.id}/recommendations.json`);
            if (recRes.ok) {
              const recs = (await recRes.json()) as StrategyRecommendation[];
              const effYears = reqBody.constraints?.rotation_years ?? 1;
              const stamped = recs.map((r) => ({
                ...r,
                served_from: "demo_snapshot" as const,
              }));
              return adaptStrategiesForHorizon(stamped, effYears) as T;
            }
          }
        }
      }
    } catch {
      // Ignore and proceed to throw
    }
  }

  // If live /profile is requested but backend API is offline, serve golden profile if field.id matches,
  // or generate location-calibrated regional fallback profile for custom parcels (WS-B2)
  if (path === "/profile" && init?.body) {
    try {
      const field = JSON.parse(init.body as string) as FieldGeometry;
      const fieldId = field?.id;
      if (fieldId) {
        const fieldsRes = await fetch("/golden/fields.json");
        if (fieldsRes.ok) {
          const fields = (await fieldsRes.json()) as GoldenField[];
          const exact = fields.find((f) => f.id === fieldId);
          if (exact) {
            const profRes = await fetch(`/golden/${exact.id}/profile.json`);
            if (profRes.ok) {
              const prof = (await profRes.json()) as FieldProfile;
              return {
                ...prof,
                served_from: "demo_snapshot" as const,
              } as T;
            }
          }
        }
      }
      // Resilient fallback for any custom coordinate on Earth
      return generateFallbackProfile(field) as T;
    } catch {
      // Ignore and proceed to throw
    }
  }

  const geocodeMatch = path.match(/^\/geocode\?q=([^&]+)/);
  if (geocodeMatch) {
    const raw = decodeURIComponent(geocodeMatch[1]).trim();
    // Protobuf !1d(lon)!2d(lat)
    const mProto = raw.match(/!1d(-?\d+\.\d+)!2d(-?\d+\.\d+)/);
    if (mProto) {
      const lon = parseFloat(mProto[1]);
      const lat = parseFloat(mProto[2]);
      return { lat, lon, name: `Google Maps Location (${lat.toFixed(3)}°, ${lon.toFixed(3)}°)` } as T;
    }
    // Regex parse Google Maps URLs or coordinates offline
    const m1 = raw.match(/@(-?\d+\.\d+),(-?\d+\.\d+)/);
    if (m1) {
      const lat = parseFloat(m1[1]);
      const lon = parseFloat(m1[2]);
      return { lat, lon, name: `Google Maps Location (${lat.toFixed(3)}°, ${lon.toFixed(3)}°)` } as T;
    }
    const m2 = raw.match(/[?&](?:q|query|ll)=(-?\d+\.\d+),(-?\d+\.\d+)/);
    if (m2) {
      const lat = parseFloat(m2[1]);
      const lon = parseFloat(m2[2]);
      return { lat, lon, name: `Google Maps Location (${lat.toFixed(3)}°, ${lon.toFixed(3)}°)` } as T;
    }
    const m3 = raw.match(/^(-?\d+\.?\d*)[,\s]+(-?\d+\.?\d*)$/);
    if (m3) {
      const lat = parseFloat(m3[1]);
      const lon = parseFloat(m3[2]);
      return { lat, lon, name: `Coordinates (${lat.toFixed(3)}°, ${lon.toFixed(3)}°)` } as T;
    }
    // Attempt direct Nominatim fetch in browser if backend was offline
    try {
      const geoRes = await fetch(`https://nominatim.openstreetmap.org/search?q=${encodeURIComponent(raw)}&format=json&limit=1`);
      if (geoRes.ok) {
        const geoData = await geoRes.json();
        if (geoData && geoData.length > 0) {
          const item = geoData[0];
          const parts = (item.display_name ?? raw).split(",");
          const shortName = parts.length === 1 ? parts[0] : `${parts[0].trim()}, ${parts[parts.length - 1].trim()}`;
          return { lat: parseFloat(Number(item.lat).toFixed(4)), lon: parseFloat(Number(item.lon).toFixed(4)), name: shortName } as T;
        }
      }
    } catch {
      // Fall through
    }

    if (backendError) {
      throw new Error(backendError);
    }
    throw new Error(`Location or address "${raw}" could not be found`);
  }

  throw new Error(backendError ?? `Failed to load ${path}`);
}

export const api = {
  goldenFields: () => request<GoldenField[]>("/golden"),
  goldenProfile: (id: string) => request<FieldProfile>(`/golden/${id}/profile`),
  goldenRecommendations: (id: string) =>
    request<StrategyRecommendation[]>(`/golden/${id}/recommendations`),
  crops: () => request<CropSpec[]>("/crops"),
  profile: (field: FieldGeometry) =>
    request<FieldProfile>("/profile", { method: "POST", body: JSON.stringify(field) }),
  suitability: (req: { field: FieldGeometry; constraints?: FarmConstraints }) =>
    request<SuitabilityItem[]>("/suitability", { method: "POST", body: JSON.stringify(req) }),
  recommend: (req: RecommendRequest) =>
    request<StrategyRecommendation[]>("/recommend", { method: "POST", body: JSON.stringify(req) }),
  recommendAsync: (req: RecommendRequest) =>
    request<RecommendJobStatus>("/recommend/async", { method: "POST", body: JSON.stringify(req) }),
  getRecommendJob: (jobId: string) =>
    request<RecommendJobStatus>(`/recommend/jobs/${jobId}`),
  geocode: (q: string) => request<import("@/types/api").GeocodeResult>(`/geocode?q=${encodeURIComponent(q)}`),
};

export type ProgressCallback = (status: {
  stage: "profile" | "weather" | "simulating" | "ranking" | "done" | "failed";
  progressPct: number;
  message?: string;
}) => void;

export async function recommendWithProgress(
  req: RecommendRequest,
  onProgress?: ProgressCallback
): Promise<StrategyRecommendation[]> {
  try {
    const job = await api.recommendAsync(req);
    const jobId = job.job_id;
    try {
      if (typeof window !== "undefined" && window.sessionStorage) {
        sessionStorage.setItem("terraloop_active_job_id", jobId);
      }
    } catch {
      // Ignore sessionStorage errors
    }

    onProgress?.({
      stage: (job.stage || job.step || "profile") as "profile" | "weather" | "simulating" | "ranking" | "done" | "failed",
      progressPct: Math.round(job.progress_pct ?? (job.progress ? job.progress * 100 : 10)),
      message: job.message ?? undefined,
    });

    const maxWaitMs = 60000;
    const startTime = Date.now();

    while (Date.now() - startTime < maxWaitMs) {
      await new Promise((r) => setTimeout(r, 400));
      const poll = await api.getRecommendJob(jobId);

      const stage = (poll.stage || poll.step || "simulating") as "profile" | "weather" | "simulating" | "ranking" | "done" | "failed";
      const pct = Math.round(poll.progress_pct ?? (poll.progress ? poll.progress * 100 : 50));
      onProgress?.({ stage, progressPct: pct, message: poll.message ?? undefined });

      if (poll.status === "completed" && poll.result) {
        try {
          if (typeof window !== "undefined" && window.sessionStorage) {
            sessionStorage.removeItem("terraloop_active_job_id");
          }
        } catch {}
        onProgress?.({ stage: "done", progressPct: 100 });
        return poll.result;
      }
      if (poll.status === "failed") {
        try {
          if (typeof window !== "undefined" && window.sessionStorage) {
            sessionStorage.removeItem("terraloop_active_job_id");
          }
        } catch {}
        throw new Error(poll.error || "Simulation job failed");
      }
    }
    throw new Error("Simulation timed out");
  } catch {
    try {
      if (typeof window !== "undefined" && window.sessionStorage) {
        sessionStorage.removeItem("terraloop_active_job_id");
      }
    } catch {}
    onProgress?.({ stage: "simulating", progressPct: 50 });
    const res = await api.recommend(req);
    onProgress?.({ stage: "done", progressPct: 100 });
    return res;
  }
}
