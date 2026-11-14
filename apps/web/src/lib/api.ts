import type {
  CropSpec,
  FieldGeometry,
  FieldProfile,
  GoldenField,
  RecommendJobStatus,
  RecommendRequest,
  StrategyRecommendation,
  SuitabilityItem,
  SuitabilityRequest,
  TacticalAdvisory,
} from "@/types/api";
import { adaptStrategiesForHorizon } from "@/lib/fallbackStrategies";
import { attachFallbackMeteomatics, generateFallbackProfile } from "@/lib/fallbackProfile";

// On Vercel:
// - In the browser: uses relative `/api` (routed to the FastAPI service via top-level rewrite).
// - On the server: uses `process.env.API_URL` injected by the Vercel service binding.
// - In local standalone dev: falls back to NEXT_PUBLIC_API_URL or http://localhost:8000.
export const API_URL = (
  typeof window === "undefined"
    ? (process.env.API_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000")
    : (process.env.NEXT_PUBLIC_API_URL || "/api")
).replace(/\/$/, "");

async function request<T>(path: string, init?: RequestInit, timeoutMs = 25000): Promise<T> {
  let backendError: string | null = null;
  let httpStatus: number | null = null;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  if (init?.signal) {
    if (init.signal.aborted) {
      controller.abort();
    } else {
      init.signal.addEventListener("abort", () => controller.abort(), { once: true });
    }
  }
  try {
    const res = await fetch(`${API_URL}${path}`, {
      ...init,
      signal: controller.signal,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    });
    if (res.ok) {
      return (await res.json()) as T;
    }
    httpStatus = res.status;
    const errData = await res.json().catch(() => null);
    if (errData?.detail) {
      backendError = String(errData.detail);
    }
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      backendError = `Request timed out after ${Math.round(timeoutMs / 1000)}s`;
    }
    // API not running or unreachable, fallback below
  } finally {
    clearTimeout(timer);
  }

  // Never mask validation (400/422), auth (401/403), not-found (404 on explicit lookup), or rate-limit (429) errors
  if (httpStatus !== null && httpStatus < 500 && !(httpStatus === 404 && path.startsWith("/geocode"))) {
    throw new Error(backendError ?? `API request failed (${httpStatus})`);
  }

  // Fallback to static public/golden data ONLY when backend is unreachable or 5xx on static demo endpoints
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
    if (localRes.ok) {
      const prof = (await localRes.json()) as FieldProfile;
      return attachFallbackMeteomatics(prof) as T;
    }
  }
  const goldenRecMatch = path.match(/^\/golden\/([^/]+)\/recommendations$/);
  if (goldenRecMatch) {
    const fieldId = goldenRecMatch[1];
    const localRes = await fetch(`/golden/${fieldId}/recommendations.json`);
    if (localRes.ok) return localRes.json() as Promise<T>;
  }

  // If live /recommend fails because backend API is unreachable (network/502/503/504),
  // serve precomputed golden snapshot ONLY when field.id matches a golden demo AND no custom params/shocks were requested.
  if (path === "/recommend" && (httpStatus === null || httpStatus >= 502) && init?.body) {
    try {
      const reqBody = JSON.parse(init.body as string) as RecommendRequest;
      const fieldId = reqBody.field?.id;
      const hasCustomShocks =
        Boolean(reqBody.drought_shock_pct) ||
        Boolean(reqBody.price_shock_pct) ||
        Boolean(reqBody.fertilizer_shock_pct) ||
        (reqBody.climate_scenario && reqBody.climate_scenario !== "historical");
      if (fieldId && !hasCustomShocks && !reqBody.baseline_override && !reqBody.soil_health_card) {
        const fieldsRes = await fetch("/golden/fields.json");
        if (fieldsRes.ok) {
          const fields = (await fieldsRes.json()) as GoldenField[];
          const exact = fields.find((f) => f.id === fieldId);
          if (exact) {
            await new Promise((resolve) => setTimeout(resolve, 250));
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

  // If live /profile is unreachable offline, serve golden profile if field.id matches,
  // or generate location-calibrated regional fallback profile for custom parcels
  if (path === "/profile" && (httpStatus === null || httpStatus >= 502) && init?.body) {
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
              return attachFallbackMeteomatics({
                ...prof,
                served_from: "demo_snapshot" as const,
              }) as T;
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
    const mProto = raw.match(/!1d(-?\d+(?:\.\d+)?)!2d(-?\d+(?:\.\d+)?)/);
    if (mProto) {
      const lon = parseFloat(mProto[1]);
      const lat = parseFloat(mProto[2]);
      if (Math.abs(lat) <= 90 && Math.abs(lon) <= 180) {
        return { lat, lon, name: `Google Maps Location (${lat.toFixed(3)}°, ${lon.toFixed(3)}°)` } as T;
      }
    }
    // Regex parse Google Maps URLs or coordinates offline (handles both decimal & integer coordinates)
    const m1 = raw.match(/@(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)/);
    if (m1) {
      const lat = parseFloat(m1[1]);
      const lon = parseFloat(m1[2]);
      if (Math.abs(lat) <= 90 && Math.abs(lon) <= 180) {
        return { lat, lon, name: `Google Maps Location (${lat.toFixed(3)}°, ${lon.toFixed(3)}°)` } as T;
      }
    }
    const m2 = raw.match(/[?&](?:q|query|ll)=(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)/);
    if (m2) {
      const lat = parseFloat(m2[1]);
      const lon = parseFloat(m2[2]);
      if (Math.abs(lat) <= 90 && Math.abs(lon) <= 180) {
        return { lat, lon, name: `Google Maps Location (${lat.toFixed(3)}°, ${lon.toFixed(3)}°)` } as T;
      }
    }
    const m3 = raw.match(/^(-?\d+(?:\.\d+)?)[,\s]+(-?\d+(?:\.\d+)?)$/);
    if (m3) {
      const lat = parseFloat(m3[1]);
      const lon = parseFloat(m3[2]);
      if (Math.abs(lat) <= 90 && Math.abs(lon) <= 180) {
        return { lat, lon, name: `Coordinates (${lat.toFixed(3)}°, ${lon.toFixed(3)}°)` } as T;
      }
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

  if (path.startsWith("/tactical-advisory") && (httpStatus === null || httpStatus >= 502)) {
    try {
      const qs = path.split("?")[1] ?? "";
      const qParams = new URLSearchParams(qs);
      const lat = parseFloat(qParams.get("lat") ?? "30.25");
      const lon = parseFloat(qParams.get("lon") ?? "75.84");
      if (Number.isFinite(lat) && Number.isFinite(lon)) {
        const fbProf = generateFallbackProfile({ lat, lon });
        if (fbProf.tactical_advisory) {
          return fbProf.tactical_advisory as T;
        }
      }
    } catch {
      // Ignore and throw below
    }
  }

  if (path === "/suitability" && (httpStatus === null || httpStatus >= 502) && init?.body) {
    try {
      const sReq = JSON.parse(init.body as string) as SuitabilityRequest;
      const cropsRes = await fetch("/golden/crops.json");
      if (cropsRes.ok) {
        const cropsList = (await cropsRes.json()) as CropSpec[];
        const prof = sReq.profile ?? generateFallbackProfile(sReq.field);
        const meanTemp = (prof.climate.mean_tmax_c + prof.climate.mean_tmin_c) / 2;
        const annualPrecip = prof.climate.annual_precip_mm || 700;
        const excluded = sReq.constraints?.exclude ?? [];
        const irrigationMode = sReq.constraints?.irrigation ?? "full";
        const items: SuitabilityItem[] = cropsList
          .filter((c) => c.id !== "fallow" && !excluded.includes(c.id))
          .map((c) => {
            const [tLo, tHi] = c.optimal_temp_c;
            const thermalDiff = meanTemp < tLo ? tLo - meanTemp : meanTemp > tHi ? meanTemp - tHi : 0;
            const thermalFit = Math.max(0.15, Math.min(1.0, 1.0 - thermalDiff * 0.06));
            const [wLo, wHi] = c.water_requirement_mm;
            const effSupply = irrigationMode === "full" ? Math.max(annualPrecip, wLo) : annualPrecip * 1.15;
            const waterFit =
              effSupply >= wLo && effSupply <= wHi * 1.5
                ? 0.92
                : effSupply < wLo
                ? Math.max(0.2, effSupply / Math.max(1, wLo))
                : 0.78;
            const droughtBonus =
              (prof.hazards.meteorological_drought_idx ?? 0) < -1.5 && c.drought_tolerance >= 4 ? 0.05 : 0;
            const score = Math.max(0, Math.min(1, Number((thermalFit * waterFit + droughtBonus).toFixed(3))));
            return {
              crop_id: c.id,
              name: c.name,
              score,
              thermal_fit: Number(thermalFit.toFixed(2)),
              water_fit: Number(waterFit.toFixed(2)),
              sowing_months: c.season_type.includes("cool") ? [11] : [6],
              reasons: [`Offline regional suitability estimate (${Math.round(score * 100)}% fit)`],
            };
          })
          .sort((a, b) => b.score - a.score);
        return items as T;
      }
    } catch {
      // Ignore and throw below
    }
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
    request<FieldProfile>("/profile", { method: "POST", body: JSON.stringify(field) }, 45000),
  suitability: (req: SuitabilityRequest) =>
    request<SuitabilityItem[]>("/suitability", { method: "POST", body: JSON.stringify(req) }, 35000),
  recommend: (req: RecommendRequest) =>
    request<StrategyRecommendation[]>("/recommend", { method: "POST", body: JSON.stringify(req) }, 50000),
  recommendAsync: (req: RecommendRequest) =>
    request<RecommendJobStatus>("/recommend/async", { method: "POST", body: JSON.stringify(req) }, 50000),
  getRecommendJob: (jobId: string) =>
    request<RecommendJobStatus>(`/recommend/jobs/${jobId}`, undefined, 10000),
  tacticalAdvisory: (lat: number, lon: number) =>
    request<TacticalAdvisory>(`/tactical-advisory?lat=${lat}&lon=${lon}`),
  geocode: (q: string) => request<import("@/types/api").GeocodeResult>(`/geocode?q=${encodeURIComponent(q)}`),
};

export type ProgressStage =
  | "profile"
  | "weather"
  | "generating"
  | "simulating"
  | "selecting"
  | "explaining"
  | "ranking"
  | "done"
  | "failed";

export type ProgressCallback = (status: {
  stage: ProgressStage;
  progressPct: number;
  message?: string;
}) => void;

export async function recommendWithProgress(
  req: RecommendRequest,
  onProgress?: ProgressCallback
): Promise<StrategyRecommendation[]> {
  let simFailedExplicitly = false;
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
      stage: (job.stage || job.step || "profile") as ProgressStage,
      progressPct: Math.round(job.progress_pct ?? (job.progress ? job.progress * 100 : 10)),
      message: job.message ?? undefined,
    });

    if (job.status === "completed" && job.result) {
      try {
        if (typeof window !== "undefined" && window.sessionStorage) {
          sessionStorage.removeItem("terraloop_active_job_id");
        }
      } catch {}
      onProgress?.({ stage: "done", progressPct: 100 });
      return job.result;
    }
    if (job.status === "failed") {
      simFailedExplicitly = true;
      try {
        if (typeof window !== "undefined" && window.sessionStorage) {
          sessionStorage.removeItem("terraloop_active_job_id");
        }
      } catch {}
      throw new Error(job.error || "Simulation job failed");
    }

    const maxWaitMs = 45000;
    const stallTimeoutMs = 20000;
    const startTime = Date.now();
    let lastProgressKey = `${job.stage || job.step || ""}:${job.progress_pct ?? job.progress ?? 0}`;
    let lastProgressAt = Date.now();

    while (Date.now() - startTime < maxWaitMs) {
      await new Promise((r) => setTimeout(r, 400));
      const poll = await api.getRecommendJob(jobId);

      const stage = (poll.stage || poll.step || "simulating") as ProgressStage;
      const pct = Math.round(poll.progress_pct ?? (poll.progress ? poll.progress * 100 : 50));
      const progressKey = `${stage}:${pct}:${poll.status}`;
      if (progressKey !== lastProgressKey) {
        lastProgressKey = progressKey;
        lastProgressAt = Date.now();
      }
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
        simFailedExplicitly = true;
        try {
          if (typeof window !== "undefined" && window.sessionStorage) {
            sessionStorage.removeItem("terraloop_active_job_id");
          }
        } catch {}
        throw new Error(poll.error || "Simulation job failed");
      }
      if (Date.now() - lastProgressAt > stallTimeoutMs) {
        throw new Error("Simulation stalled");
      }
    }
    throw new Error("Simulation timed out");
  } catch (err) {
    try {
      if (typeof window !== "undefined" && window.sessionStorage) {
        sessionStorage.removeItem("terraloop_active_job_id");
      }
    } catch {}
    // Re-throw real simulation errors instead of duplicating heavy compute; fall back to sync /recommend only
    // when async endpoint or in-flight lambda job handle is unavailable (e.g. cold serverless hop / 404).
    if (simFailedExplicitly) {
      throw err;
    }
    const msg = err instanceof Error ? err.message : "";
    if (/exceeded|rate limit|422|validation/i.test(msg)) {
      throw err;
    }
    onProgress?.({ stage: "simulating", progressPct: 50 });
    const res = await api.recommend(req);
    onProgress?.({ stage: "done", progressPct: 100 });
    return res;
  }
}
