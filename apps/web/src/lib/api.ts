import type {
  CropSpec,
  FarmConstraints,
  FieldGeometry,
  FieldProfile,
  GoldenField,
  RecommendRequest,
  StrategyRecommendation,
  SuitabilityItem,
} from "@/types/api";

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
  if (path === "/recommend" && init?.body) {
    try {
      const reqBody = JSON.parse(init.body as string) as RecommendRequest;
      const fieldsRes = await fetch("/golden/fields.json");
      if (fieldsRes.ok) {
        const fields = (await fieldsRes.json()) as GoldenField[];
        if (fields.length > 0) {
          let closest = fields[0];
          let minDist = Infinity;
          for (const f of fields) {
            const d = Math.hypot(f.lat - reqBody.field.lat, f.lon - reqBody.field.lon);
            if (d < minDist) {
              minDist = d;
              closest = f;
            }
          }
          const recRes = await fetch(`/golden/${closest.id}/recommendations.json`);
          if (recRes.ok) {
            return (await recRes.json()) as T;
          }
        }
      }
    } catch {
      // Ignore and proceed
    }
  }

  // If live /profile is requested but backend API is offline, adapt closest golden field
  if (path === "/profile" && init?.body) {
    try {
      const field = JSON.parse(init.body as string) as FieldGeometry;
      const fieldsRes = await fetch("/golden/fields.json");
      if (fieldsRes.ok) {
        const fields = (await fieldsRes.json()) as GoldenField[];
        if (fields.length > 0) {
          // Find closest golden field by distance
          let closest = fields[0];
          let minDist = Infinity;
          for (const f of fields) {
            const d = Math.hypot(f.lat - field.lat, f.lon - field.lon);
            if (d < minDist) {
              minDist = d;
              closest = f;
            }
          }
          const profRes = await fetch(`/golden/${closest.id}/profile.json`);
          if (profRes.ok) {
            const prof = (await profRes.json()) as FieldProfile;
            const isSouthAsia = field.lat >= 5 && field.lat <= 38.5 && field.lon >= 66 && field.lon <= 99;
            return {
              ...prof,
              field: {
                lat: field.lat,
                lon: field.lon,
                name: field.name ?? `Field (${field.lat.toFixed(3)}°, ${field.lon.toFixed(3)}°)`,
              },
              currency: isSouthAsia ? "INR" : "USD",
              currency_symbol: isSouthAsia ? "₹" : "$",
            } as T;
          }
        }
      }
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
  geocode: (q: string) => request<import("@/types/api").GeocodeResult>(`/geocode?q=${encodeURIComponent(q)}`),
};
