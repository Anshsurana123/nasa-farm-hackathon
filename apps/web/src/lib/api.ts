import type {
  CropSpec,
  FieldGeometry,
  FieldProfile,
  GoldenField,
  ProfileJobStatus,
  ProfileProgressStage,
  RecommendJobStatus,
  RecommendRequest,
  StrategyRecommendation,
  SuitabilityItem,
  SuitabilityRequest,
  TacticalAdvisory,
} from "@/types/api";

export function isAbortError(err: unknown): boolean {
  return (
    (err instanceof DOMException && err.name === "AbortError") ||
    (err instanceof Error && err.name === "AbortError")
  );
}

class ApiHttpError extends Error {
  status: number | null;
  constructor(message: string, status: number | null) {
    super(message);
    this.status = status;
  }
}

function abortableSleep(ms: number, signal?: AbortSignal): Promise<void> {
  if (!signal) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }
  if (signal.aborted) {
    return Promise.reject(new DOMException("Aborted", "AbortError"));
  }
  return new Promise((resolve, reject) => {
    const onAbort = () => {
      clearTimeout(timer);
      reject(new DOMException("Aborted", "AbortError"));
    };
    const timer = setTimeout(() => {
      signal.removeEventListener("abort", onAbort);
      resolve();
    }, ms);
    signal.addEventListener("abort", onAbort, { once: true });
  });
}
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
    if (init?.signal?.aborted) {
      throw err instanceof Error ? err : new DOMException("Aborted", "AbortError");
    }
    if (err instanceof DOMException && err.name === "AbortError") {
      backendError = `Request timed out after ${Math.round(timeoutMs / 1000)}s`;
    }
    // API not running or unreachable, fallback below
  } finally {
    clearTimeout(timer);
  }

  // Never mask validation (400/422), auth (401/403), not-found (404 on explicit lookup), or rate-limit (429) errors
  if (httpStatus !== null && httpStatus < 500 && !(httpStatus === 404 && path.startsWith("/geocode"))) {
    throw new ApiHttpError(backendError ?? `API request failed (${httpStatus})`, httpStatus);
  }

  const isGatewayOrOffline = httpStatus === null || httpStatus >= 502 || (httpStatus === 500 && !backendError);

  // Fallback to static public/golden data ONLY when backend is unreachable or 5xx on static demo endpoints
  if (path === "/golden") {
    const localRes = await fetch("/golden/fields.json");
    if (localRes.ok) return localRes.json() as Promise<T>;
  }
  if (path === "/crops" || path.startsWith("/crops?")) {
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

  // If live /recommend fails because backend API is unreachable (network/proxy timeout/502/503/504),
  // serve precomputed golden snapshot ONLY when field.id matches a golden demo AND no custom params/shocks were requested.
  if (path === "/recommend" && isGatewayOrOffline && init?.body) {
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
  if (path === "/profile" && isGatewayOrOffline && init?.body) {
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

  if (path.startsWith("/tactical-advisory") && isGatewayOrOffline) {
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

  if (path === "/suitability" && isGatewayOrOffline && init?.body) {
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
            const fitPct = Math.round(score * 100);
            const reasonText =
              sReq.language === "pa"
                ? `ਆਫ਼ਲਾਈਨ ਖੇਤਰੀ ਅਨੁਕੂਲਤਾ ਅੰਦਾਜ਼ਾ (${fitPct}% ਢੁਕਵਾਂ)`
                : sReq.language === "hi"
                  ? `ऑफ़लाइन क्षेत्रीय उपयुक्तता अनुमान (${fitPct}% उपयुक्त)`
                  : sReq.language === "es"
                    ? `Estimación regional de aptitud (${fitPct}% compatible)`
                    : sReq.language === "pt"
                      ? `Estimativa regional de aptidão (${fitPct}% compatível)`
                      : sReq.language === "fr"
                        ? `Estimation régionale d'aptitude (${fitPct}% adapté)`
                        : `Offline regional suitability estimate (${fitPct}% fit)`;
            return {
              crop_id: c.id,
              name: c.name,
              score,
              thermal_fit: Number(thermalFit.toFixed(2)),
              water_fit: Number(waterFit.toFixed(2)),
              sowing_months: c.season_type.includes("cool") ? [11] : [6],
              reasons: [reasonText],
            };
          })
          .sort((a, b) => b.score - a.score);
        return items as T;
      }
    } catch {
      // Ignore and throw below
    }
  }

  throw new ApiHttpError(backendError ?? `Failed to load ${path}`, httpStatus);
}

export const api = {
  goldenFields: () => request<GoldenField[]>("/golden"),
  goldenProfile: (id: string, signal?: AbortSignal) =>
    request<FieldProfile>(`/golden/${id}/profile`, { signal }),
  goldenRecommendations: (id: string) =>
    request<StrategyRecommendation[]>(`/golden/${id}/recommendations`),
  crops: (lat?: number, lon?: number) =>
    request<CropSpec[]>(lat !== undefined && lon !== undefined ? `/crops?lat=${lat}&lon=${lon}` : "/crops"),
  profile: (field: FieldGeometry, signal?: AbortSignal) =>
    request<FieldProfile>("/profile", { method: "POST", body: JSON.stringify(field), signal }, 60000),
  profileAsync: (field: FieldGeometry, signal?: AbortSignal) =>
    request<ProfileJobStatus>("/profile/async", { method: "POST", body: JSON.stringify(field), signal }, 50000),
  getProfileJob: (jobId: string, signal?: AbortSignal) =>
    request<ProfileJobStatus>(`/profile/jobs/${jobId}`, { signal }, 15000),
  suitability: (req: SuitabilityRequest) =>
    request<SuitabilityItem[]>("/suitability", { method: "POST", body: JSON.stringify(req) }, 35000),
  recommend: (req: RecommendRequest, signal?: AbortSignal) =>
    request<StrategyRecommendation[]>("/recommend", { method: "POST", body: JSON.stringify(req), signal }, 60000),
  recommendAsync: (req: RecommendRequest, signal?: AbortSignal) =>
    request<RecommendJobStatus>("/recommend/async", { method: "POST", body: JSON.stringify(req), signal }, 50000),
  getRecommendJob: (jobId: string, signal?: AbortSignal) =>
    request<RecommendJobStatus>(`/recommend/jobs/${jobId}`, { signal }, 15000),
  tacticalAdvisory: (lat: number, lon: number) =>
    request<TacticalAdvisory>(`/tactical-advisory?lat=${lat}&lon=${lon}`),
  geocode: (q: string) => request<import("@/types/api").GeocodeResult>(`/geocode?q=${encodeURIComponent(q)}`),
};

export type ProfileProgressCallback = (status: {
  stage: ProfileProgressStage;
  progressPct: number;
}) => void;

export async function profileWithProgress(
  field: FieldGeometry,
  onProgress?: ProfileProgressCallback,
  signal?: AbortSignal
): Promise<FieldProfile> {
  let explicitFailure = false;
  let asyncUnavailable = false;
  try {
    const job = await api.profileAsync(field, signal);
    onProgress?.({
      stage: (job.step || "region") as ProfileProgressStage,
      progressPct: Math.round((job.progress ?? 0.1) * 100),
    });

    if (job.status === "completed" && job.result) {
      onProgress?.({ stage: "done", progressPct: 100 });
      return job.result;
    }
    if (job.status === "failed") {
      explicitFailure = true;
      throw new Error(job.error || "Profile build failed");
    }

    const maxWaitMs = 90000;
    const startTime = Date.now();
    while (Date.now() - startTime < maxWaitMs) {
      await abortableSleep(450, signal);
      let poll: ProfileJobStatus;
      try {
        poll = await api.getProfileJob(job.job_id, signal);
      } catch (pollErr) {
        if (isAbortError(pollErr) || signal?.aborted) {
          throw pollErr;
        }
        if (pollErr instanceof ApiHttpError && pollErr.status === 404) {
          asyncUnavailable = true;
          throw pollErr;
        }
        throw pollErr;
      }

      onProgress?.({
        stage: (poll.step || "satellite") as ProfileProgressStage,
        progressPct: Math.round((poll.progress ?? 0.45) * 100),
      });

      if (poll.status === "completed" && poll.result) {
        onProgress?.({ stage: "done", progressPct: 100 });
        return poll.result;
      }
      if (poll.status === "failed") {
        explicitFailure = true;
        throw new Error(poll.error || "Profile build failed");
      }
    }
    throw new Error("Profile build timed out");
  } catch (err) {
    if (isAbortError(err) || signal?.aborted || explicitFailure) {
      throw err;
    }
    const status = err instanceof ApiHttpError ? err.status : null;
    if (
      asyncUnavailable ||
      status === null ||
      status === 404 ||
      status === 405 ||
      status >= 500
    ) {
      const res = await api.profile(field, signal);
      onProgress?.({ stage: "done", progressPct: 100 });
      return res;
    }
    throw err;
  }
}

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
  onProgress?: ProgressCallback,
  signal?: AbortSignal
): Promise<StrategyRecommendation[]> {
  let simFailedExplicitly = false;
  let asyncFallbackEligible = false;
  try {
    let job: RecommendJobStatus;
    try {
      job = await api.recommendAsync(req, signal);
    } catch (initErr) {
      if (isAbortError(initErr) || signal?.aborted) {
        throw initErr;
      }
      const status = initErr instanceof ApiHttpError ? initErr.status : null;
      if (status === null || status === 404 || status === 405 || status >= 500) {
        asyncFallbackEligible = true;
      }
      throw initErr;
    }

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

    const maxWaitMs = 150000;
    const stallTimeoutMs = 60000;
    const startTime = Date.now();
    let lastProgressKey = `${job.stage || job.step || ""}:${job.progress_pct ?? job.progress ?? 0}`;
    let lastProgressAt = Date.now();

    while (Date.now() - startTime < maxWaitMs) {
      await abortableSleep(400, signal);
      let poll: RecommendJobStatus;
      try {
        poll = await api.getRecommendJob(jobId, signal);
      } catch (pollErr) {
        if (isAbortError(pollErr) || signal?.aborted) {
          throw pollErr;
        }
        if (pollErr instanceof ApiHttpError && pollErr.status === 404) {
          asyncFallbackEligible = true;
        }
        throw pollErr;
      }

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
        simFailedExplicitly = true;
        throw new Error("Simulation stalled");
      }
    }
    simFailedExplicitly = true;
    throw new Error("Simulation timed out");
  } catch (err) {
    try {
      if (typeof window !== "undefined" && window.sessionStorage) {
        sessionStorage.removeItem("terraloop_active_job_id");
      }
    } catch {}
    if (isAbortError(err) || signal?.aborted || simFailedExplicitly || !asyncFallbackEligible) {
      throw err;
    }
    onProgress?.({ stage: "simulating", progressPct: 50 });
    const res = await api.recommend(req, signal);
    onProgress?.({ stage: "done", progressPct: 100 });
    return res;
  }
}
