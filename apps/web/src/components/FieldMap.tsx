"use client";

import { useEffect, useRef, useState } from "react";
import type { GeoJSONSource, Map as MapLibreMap, Marker as MapLibreMarker } from "maplibre-gl";
import type { GoldenField } from "@/types/api";
import { Layers, MapPin, Compass, Globe2, Box, RotateCw } from "lucide-react";
import { fmtDMS, regionContext, regionFlag } from "@/lib/ui";

interface FieldMapProps {
  selectedField: { lat: number; lon: number; name?: string };
  goldenFields: GoldenField[];
  onSelect: (field: { lat: number; lon: number; name: string }) => void;
}

function buildParcelGeoJSON(lat: number, lon: number) {
  const dLat = 0.0042;
  const dLon = 0.0052;
  const outerLat = 0.0095;
  const outerLon = 0.0115;

  return {
    type: "FeatureCollection" as const,
    features: [
      {
        type: "Feature" as const,
        properties: { kind: "perimeter", height: 18, base: 0, color: "#3898c8" },
        geometry: {
          type: "Polygon" as const,
          coordinates: [
            [
              [lon - outerLon, lat - outerLat],
              [lon + outerLon, lat - outerLat],
              [lon + outerLon, lat + outerLat],
              [lon - outerLon, lat + outerLat],
              [lon - outerLon, lat - outerLat],
            ],
          ],
        },
      },
      {
        type: "Feature" as const,
        properties: { kind: "parcel", height: 85, base: 0, color: "#52b778" },
        geometry: {
          type: "Polygon" as const,
          coordinates: [
            [
              [lon - dLon, lat - dLat],
              [lon + dLon, lat - dLat],
              [lon + dLon, lat + dLat],
              [lon - dLon, lat + dLat],
              [lon - dLon, lat - dLat],
            ],
          ],
        },
      },
    ],
  };
}

export function FieldMap({ selectedField, goldenFields, onSelect }: FieldMapProps) {
  const mapContainer = useRef<HTMLDivElement>(null);
  const mapInstance = useRef<MapLibreMap | null>(null);
  const markerInstance = useRef<MapLibreMarker | null>(null);
  const goldenMarkersRef = useRef<MapLibreMarker[]>([]);
  const orbitRafRef = useRef<number | null>(null);

  const [mapMode, setMapMode] = useState<"satellite" | "osm">("satellite");
  const [is3D, setIs3D] = useState<boolean>(true);
  const [isOrbiting, setIsOrbiting] = useState<boolean>(false);
  const [cameraHud, setCameraHud] = useState<{ pitch: number; bearing: number; zoom: number }>({
    pitch: 52,
    bearing: -18,
    zoom: 11.5,
  });

  useEffect(() => {
    let isMounted = true;

    async function initMap() {
      if (!mapContainer.current || mapInstance.current) return;

      try {
        const maplibre = await import("maplibre-gl");
        if (typeof window !== "undefined" && maplibre.config) {
          maplibre.config.WORKER_URL = "/maplibre/maplibre-gl-worker.mjs";
        }
        if (!isMounted || !mapContainer.current) return;

        const map = new maplibre.Map({
          container: mapContainer.current,
          style: {
            version: 8,
            sources: {
              satellite: {
                type: "raster",
                tiles: [
                  "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
                ],
                tileSize: 256,
                attribution: "Esri World Imagery · NASA EO",
              },
              osm: {
                type: "raster",
                tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
                tileSize: 256,
                attribution: "© OpenStreetMap contributors",
              },
              "terrain-dem": {
                type: "raster-dem",
                tiles: ["https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"],
                tileSize: 256,
                encoding: "terrarium",
                maxzoom: 14,
              },
              "parcel-swath": {
                type: "geojson",
                data: buildParcelGeoJSON(selectedField.lat, selectedField.lon),
              },
            },
            layers: [
              {
                id: "satellite-tiles",
                type: "raster",
                source: "satellite",
                minzoom: 0,
                maxzoom: 19,
                layout: { visibility: "visible" },
              },
              {
                id: "osm-tiles",
                type: "raster",
                source: "osm",
                minzoom: 0,
                maxzoom: 19,
                layout: { visibility: "none" },
              },
              {
                id: "parcel-perimeter-line",
                type: "line",
                source: "parcel-swath",
                paint: {
                  "line-color": ["get", "color"],
                  "line-width": 1.75,
                  "line-dasharray": [3, 2],
                  "line-opacity": 0.85,
                },
              },
              {
                id: "parcel-3d-extrusion",
                type: "fill-extrusion",
                source: "parcel-swath",
                paint: {
                  "fill-extrusion-color": ["get", "color"],
                  "fill-extrusion-height": ["get", "height"],
                  "fill-extrusion-base": ["get", "base"],
                  "fill-extrusion-opacity": 0.28,
                },
              },
            ],
          },
          center: [selectedField.lon, selectedField.lat],
          zoom: 11.5,
          pitch: 52,
          bearing: -18,
          maxPitch: 72,
          maxBounds: [
            [66.0, 5.0],
            [99.0, 38.5],
          ],
        });

        map.addControl(new maplibre.NavigationControl({ visualizePitch: true }), "top-right");

        map.on("load", () => {
          if (!isMounted) return;
          try {
            map.setTerrain({ source: "terrain-dem", exaggeration: 1.6 });
          } catch {
            // Ignore if DEM tiles are unreachable offline
          }
        });

        map.on("move", () => {
          if (!isMounted) return;
          setCameraHud({
            pitch: Math.round(map.getPitch()),
            bearing: Math.round((map.getBearing() + 360) % 360),
            zoom: Number(map.getZoom().toFixed(1)),
          });
        });

        // Click anywhere to drop a pin on a field
        map.on("click", (e) => {
          setIsOrbiting(false);
          const lat = Number(e.lngLat.lat.toFixed(4));
          const lon = Number(e.lngLat.lng.toFixed(4));
          const latStr = `${Math.abs(lat).toFixed(3)}°${lat >= 0 ? "N" : "S"}`;
          const lonStr = `${Math.abs(lon).toFixed(3)}°${lon >= 0 ? "E" : "W"}`;
          const reg = regionContext(lat, lon, null);
          onSelect({
            lat,
            lon,
            name: `${reg.shortName} (${latStr}, ${lonStr})`,
          });
        });

        // Precision SVG target reticle marker (no cartoon emoji)
        const customPinEl = document.createElement("div");
        customPinEl.className = "relative flex items-center justify-center cursor-grab active:cursor-grabbing";
        customPinEl.innerHTML = `
          <div class="absolute -inset-4 rounded-full border border-emerald-400/50 animate-ping"></div>
          <div class="relative w-9 h-9 rounded-full bg-stone-950/90 border-2 border-emerald-400 shadow-xl flex items-center justify-center text-emerald-400">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="4" />
              <line x1="12" y1="2" x2="12" y2="6" />
              <line x1="12" y1="18" x2="12" y2="22" />
              <line x1="2" y1="12" x2="6" y2="12" />
              <line x1="18" y1="12" x2="22" y2="12" />
            </svg>
          </div>
        `;

        const marker = new maplibre.Marker({ element: customPinEl, draggable: true })
          .setLngLat([selectedField.lon, selectedField.lat])
          .addTo(map);

        marker.on("dragend", () => {
          setIsOrbiting(false);
          const lngLat = marker.getLngLat();
          const lat = Number(lngLat.lat.toFixed(4));
          const lon = Number(lngLat.lng.toFixed(4));
          const latStr = `${Math.abs(lat).toFixed(3)}°${lat >= 0 ? "N" : "S"}`;
          const lonStr = `${Math.abs(lon).toFixed(3)}°${lon >= 0 ? "E" : "W"}`;
          const reg = regionContext(lat, lon, null);
          onSelect({
            lat,
            lon,
            name: `${reg.shortName} (${latStr}, ${lonStr})`,
          });
        });

        // Secondary benchmark field beacons
        goldenMarkersRef.current = goldenFields.map((gf) => {
          const el = document.createElement("div");
          el.className =
            "px-2 py-0.5 rounded bg-stone-950/90 border border-amber-400/80 text-amber-300 shadow-lg flex items-center justify-center text-[10px] font-mono font-bold cursor-pointer hover:scale-110 transition-transform hover:z-20";
          el.textContent = regionFlag(gf.id);
          el.title = `${gf.name} — Click to load benchmark profile`;
          el.addEventListener("click", (ev) => {
            ev.stopPropagation();
            setIsOrbiting(false);
            onSelect({ lat: gf.lat, lon: gf.lon, name: gf.name });
          });

          return new maplibre.Marker({ element: el })
            .setLngLat([gf.lon, gf.lat])
            .addTo(map);
        });

        markerInstance.current = marker;
        mapInstance.current = map;
      } catch (err) {
        console.warn("MapLibre initialization fallback:", err);
      }
    }

    initMap();

    return () => {
      isMounted = false;
      if (orbitRafRef.current) {
        window.cancelAnimationFrame(orbitRafRef.current);
      }
      if (mapInstance.current) {
        mapInstance.current.remove();
        mapInstance.current = null;
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Re-sync golden benchmark field beacons whenever goldenFields loads asynchronously
  useEffect(() => {
    let isMounted = true;
    async function syncGoldenBeacons() {
      const map = mapInstance.current;
      if (!map || !goldenFields.length) return;
      try {
        const maplibre = await import("maplibre-gl");
        if (!isMounted || !mapInstance.current) return;
        for (const m of goldenMarkersRef.current) {
          try {
            m.remove();
          } catch {
            // Ignore
          }
        }
        goldenMarkersRef.current = goldenFields.map((gf) => {
          const el = document.createElement("div");
          el.className =
            "px-2 py-0.5 rounded bg-stone-950/90 border border-amber-400/80 text-amber-300 shadow-lg flex items-center justify-center text-[10px] font-mono font-bold cursor-pointer hover:scale-110 transition-transform hover:z-20";
          el.textContent = regionFlag(gf.id);
          el.title = `${gf.name} — Click to load benchmark profile`;
          el.addEventListener("click", (ev) => {
            ev.stopPropagation();
            setIsOrbiting(false);
            onSelect({ lat: gf.lat, lon: gf.lon, name: gf.name });
          });

          return new maplibre.Marker({ element: el }).setLngLat([gf.lon, gf.lat]).addTo(map);
        });
      } catch {
        // Ignore
      }
    }
    syncGoldenBeacons();
    return () => {
      isMounted = false;
    };
  }, [goldenFields, onSelect]);

  // Toggle map layers (Satellite vs Street Map)
  useEffect(() => {
    if (mapInstance.current && mapInstance.current.isStyleLoaded()) {
      mapInstance.current.setLayoutProperty(
        "satellite-tiles",
        "visibility",
        mapMode === "satellite" ? "visible" : "none"
      );
      mapInstance.current.setLayoutProperty(
        "osm-tiles",
        "visibility",
        mapMode === "osm" ? "visible" : "none"
      );
    }
  }, [mapMode]);

  // Toggle 3D pitch vs 2D nadir
  useEffect(() => {
    const map = mapInstance.current;
    if (!map) return;
    map.easeTo({
      pitch: is3D ? 55 : 0,
      bearing: is3D ? -18 : 0,
      duration: 850,
    });
  }, [is3D]);

  // Continuous 3D camera orbit animation when enabled
  useEffect(() => {
    if (!isOrbiting || !mapInstance.current) {
      if (orbitRafRef.current) {
        window.cancelAnimationFrame(orbitRafRef.current);
        orbitRafRef.current = null;
      }
      return;
    }

    const map = mapInstance.current;
    if (map.getPitch() < 35) {
      map.easeTo({ pitch: 56, duration: 500 });
    }

    const step = () => {
      if (!mapInstance.current) return;
      mapInstance.current.rotateTo((mapInstance.current.getBearing() + 0.18) % 360, { duration: 0 });
      orbitRafRef.current = window.requestAnimationFrame(step);
    };
    orbitRafRef.current = window.requestAnimationFrame(step);

    return () => {
      if (orbitRafRef.current) {
        window.cancelAnimationFrame(orbitRafRef.current);
        orbitRafRef.current = null;
      }
    };
  }, [isOrbiting]);

  // Update center, marker, and 3D extruded parcel polygon when selectedField changes
  useEffect(() => {
    const map = mapInstance.current;
    if (!map) return;

    map.flyTo({
      center: [selectedField.lon, selectedField.lat],
      zoom: 11.5,
      pitch: is3D ? 55 : 0,
      essential: true,
      speed: 1.25,
    });
    if (markerInstance.current) {
      markerInstance.current.setLngLat([selectedField.lon, selectedField.lat]);
    }
    const src = map.getSource("parcel-swath") as GeoJSONSource | undefined;
    if (src && typeof src.setData === "function") {
      src.setData(buildParcelGeoJSON(selectedField.lat, selectedField.lon));
    }
  }, [selectedField.lat, selectedField.lon, is3D]);

  const resetView = () => {
    setIsOrbiting(false);
    if (mapInstance.current) {
      mapInstance.current.flyTo({
        center: [selectedField.lon, selectedField.lat],
        zoom: 11.5,
        pitch: is3D ? 52 : 0,
        bearing: -18,
        essential: true,
      });
    }
  };

  return (
    <div className="relative w-full h-[390px] md:h-[470px] rounded-2xl overflow-hidden border border-line shadow-lg reticle-frame group">
      <div ref={mapContainer} className="w-full h-full bg-stone-950 cursor-crosshair" />

      {/* Top Left: Cartographic & 3D Swath Controls */}
      <div className="absolute top-3 left-3 glass-strong p-1 rounded-xl border border-line shadow-md flex flex-wrap items-center gap-1 z-10 text-[11px] font-mono">
        <button
          type="button"
          onClick={() => setMapMode("satellite")}
          className={`px-2.5 py-1.5 rounded-lg font-semibold transition-all cursor-pointer flex items-center gap-1.5 ${
            mapMode === "satellite"
              ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/40"
              : "text-muted hover:text-foreground hover:bg-foreground/5"
          }`}
        >
          <Globe2 className="w-3.5 h-3.5" />
          <span>EO Optical</span>
        </button>
        <button
          type="button"
          onClick={() => setMapMode("osm")}
          className={`px-2.5 py-1.5 rounded-lg font-semibold transition-all cursor-pointer flex items-center gap-1.5 ${
            mapMode === "osm"
              ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/40"
              : "text-muted hover:text-foreground hover:bg-foreground/5"
          }`}
        >
          <Layers className="w-3.5 h-3.5" />
          <span>Topo / Street</span>
        </button>

        <span className="h-4 w-[1px] bg-line mx-0.5" />

        <button
          type="button"
          onClick={() => setIs3D((v) => !v)}
          className={`px-2.5 py-1.5 rounded-lg font-semibold transition-all cursor-pointer flex items-center gap-1.5 ${
            is3D
              ? "bg-sky-500/20 text-sky-400 border border-sky-500/40"
              : "text-muted hover:text-foreground hover:bg-foreground/5"
          }`}
          title="Toggle 3D DEM Terrain & Parcel Extrusion"
        >
          <Box className="w-3.5 h-3.5" />
          <span>{is3D ? "3D Swath" : "2D Nadir"}</span>
        </button>

        <button
          type="button"
          onClick={() => {
            setIsOrbiting((v) => {
              if (!v) setIs3D(true);
              return !v;
            });
          }}
          className={`px-2.5 py-1.5 rounded-lg font-semibold transition-all cursor-pointer flex items-center gap-1.5 ${
            isOrbiting
              ? "bg-amber-500/20 text-amber-400 border border-amber-500/40"
              : "text-muted hover:text-foreground hover:bg-foreground/5"
          }`}
          title="Orbit 360° around parcel"
        >
          <RotateCw className={`w-3.5 h-3.5 ${isOrbiting ? "animate-spin" : ""}`} />
          <span>Orbit</span>
        </button>

        <button
          type="button"
          onClick={resetView}
          title="Reset Orientation & Center"
          className="p-1.5 rounded-lg text-muted hover:text-foreground hover:bg-foreground/5 transition-colors cursor-pointer"
        >
          <Compass className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* Top Right below NavigationControl: Camera Telemetry Readout */}
      <div className="absolute top-28 right-3 glass-strong px-2.5 py-1.5 rounded-lg border border-line text-[10px] font-mono text-muted pointer-events-none hidden sm:flex flex-col items-end gap-0.5 z-10">
        <span>PITCH {cameraHud.pitch}° · BRG {cameraHud.bearing}°</span>
        <span className="text-emerald-400">NASADEM 30m + 3D PARCEL</span>
      </div>

      {/* Bottom Floating Telemetry Bar */}
      <div className="absolute bottom-3 left-3 right-3 flex flex-wrap items-center justify-between gap-2 pointer-events-none z-10">
        <div className="glass-strong text-foreground pointer-events-auto px-3 py-1.5 rounded-xl border border-line text-[11px] font-mono flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
          <span className="text-foreground/90">Click terrain or drag reticle to sample parcel</span>
        </div>

        <div className="glass-strong text-foreground pointer-events-auto px-3 py-1.5 rounded-xl border border-line text-[11px] font-mono font-bold shadow-md flex items-center gap-2">
          <MapPin className="w-3.5 h-3.5 text-emerald-400" />
          <span>
            {fmtDMS(selectedField.lat, true)} · {fmtDMS(selectedField.lon, false)}
          </span>
        </div>
      </div>
    </div>
  );
}
