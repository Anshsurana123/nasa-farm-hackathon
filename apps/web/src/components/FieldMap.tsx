"use client";

import { useEffect, useRef, useState } from "react";
import type { GoldenField } from "@/types/api";
import { Layers, MapPin, Navigation, Compass, Globe2 } from "lucide-react";
import { regionFlag } from "@/lib/ui";

interface FieldMapProps {
  selectedField: { lat: number; lon: number; name?: string };
  goldenFields: GoldenField[];
  onSelect: (field: { lat: number; lon: number; name: string }) => void;
}

export function FieldMap({ selectedField, goldenFields, onSelect }: FieldMapProps) {
  const mapContainer = useRef<HTMLDivElement>(null);
  const mapInstance = useRef<any>(null);
  const markerInstance = useRef<any>(null);
  const goldenMarkersRef = useRef<any[]>([]);
  const [mapMode, setMapMode] = useState<"satellite" | "osm">("satellite");
  const [isLoaded, setIsLoaded] = useState(false);

  useEffect(() => {
    let isMounted = true;

    async function initMap() {
      if (!mapContainer.current || mapInstance.current) return;

      try {
        const maplibre = await import("maplibre-gl");
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
                attribution: "Esri World Imagery",
              },
              osm: {
                type: "raster",
                tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
                tileSize: 256,
                attribution: "© OpenStreetMap contributors",
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
            ],
          },
          center: [selectedField.lon, selectedField.lat],
          zoom: 8.5,
          pitch: 15,
        });

        map.addControl(new maplibre.NavigationControl({ visualizePitch: true }), "top-right");

        map.on("load", () => {
          if (!isMounted) return;
          setIsLoaded(true);
        });

        // Click anywhere to drop a pin on a field
        map.on("click", (e) => {
          const lat = Number(e.lngLat.lat.toFixed(4));
          const lon = Number(e.lngLat.lng.toFixed(4));
          const latStr = `${Math.abs(lat).toFixed(3)}°${lat >= 0 ? "N" : "S"}`;
          const lonStr = `${Math.abs(lon).toFixed(3)}°${lon >= 0 ? "E" : "W"}`;
          onSelect({
            lat,
            lon,
            name: `Field (${latStr}, ${lonStr})`,
          });
        });

        // Add custom primary draggable pin with radar pulse
        const customPinEl = document.createElement("div");
        customPinEl.className = "relative flex items-center justify-center cursor-grab active:cursor-grabbing";
        customPinEl.innerHTML = `
          <div class="absolute -inset-3 rounded-full bg-emerald-500/25 animate-ping"></div>
          <div class="absolute -inset-1 rounded-full bg-emerald-500/40"></div>
          <div class="relative w-8 h-8 rounded-full bg-emerald-600 border-2 border-white shadow-xl flex items-center justify-center text-white text-xs font-black">
            🎯
          </div>
        `;

        const marker = new maplibre.Marker({ element: customPinEl, draggable: true })
          .setLngLat([selectedField.lon, selectedField.lat])
          .addTo(map);

        marker.on("dragend", () => {
          const lngLat = marker.getLngLat();
          const lat = Number(lngLat.lat.toFixed(4));
          const lon = Number(lngLat.lng.toFixed(4));
          const latStr = `${Math.abs(lat).toFixed(3)}°${lat >= 0 ? "N" : "S"}`;
          const lonStr = `${Math.abs(lon).toFixed(3)}°${lon >= 0 ? "E" : "W"}`;
          onSelect({
            lat,
            lon,
            name: `Field (${latStr}, ${lonStr})`,
          });
        });

        // Add secondary golden fields markers with flag and tooltip
        goldenMarkersRef.current = goldenFields.map((gf) => {
          const el = document.createElement("div");
          el.className =
            "w-7 h-7 rounded-full bg-amber-400 border-2 border-white shadow-lg flex items-center justify-center text-xs cursor-pointer hover:scale-125 transition-transform hover:z-20";
          el.innerHTML = gf.id === "sangrur" ? "⭐" : regionFlag(gf.id);
          el.title = `${gf.name} (Click to load profile)`;
          el.addEventListener("click", (ev) => {
            ev.stopPropagation();
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
      if (mapInstance.current) {
        mapInstance.current.remove();
        mapInstance.current = null;
      }
    };
  }, []);

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

  // Update center and marker when selectedField changes
  useEffect(() => {
    if (mapInstance.current) {
      mapInstance.current.flyTo({
        center: [selectedField.lon, selectedField.lat],
        zoom: 9.5,
        essential: true,
        speed: 1.2,
      });
      if (markerInstance.current) {
        markerInstance.current.setLngLat([selectedField.lon, selectedField.lat]);
      }
    }
  }, [selectedField.lat, selectedField.lon]);

  const resetView = () => {
    if (mapInstance.current) {
      mapInstance.current.flyTo({
        center: [selectedField.lon, selectedField.lat],
        zoom: 9.5,
        pitch: 0,
        bearing: 0,
        essential: true,
      });
    }
  };

  return (
    <div className="relative w-full h-[380px] md:h-[490px] rounded-3xl overflow-hidden border border-line shadow-lg group">
      <div ref={mapContainer} className="w-full h-full bg-slate-900 cursor-crosshair" />

      {/* Top Left: Map Layer Controls */}
      <div className="absolute top-3.5 left-3.5 glass-strong p-1 rounded-2xl border border-line shadow-md flex items-center gap-1 z-10 text-xs">
        <button
          type="button"
          onClick={() => setMapMode("satellite")}
          className={`px-3 py-1.5 rounded-xl font-semibold transition-all duration-200 cursor-pointer flex items-center gap-1.5 ${
            mapMode === "satellite"
              ? "bg-gradient-to-r from-emerald-600 to-teal-600 text-white shadow-xs"
              : "text-muted hover:text-foreground hover:bg-foreground/5"
          }`}
        >
          <Globe2 className="w-3.5 h-3.5" />
          <span>Satellite</span>
        </button>
        <button
          type="button"
          onClick={() => setMapMode("osm")}
          className={`px-3 py-1.5 rounded-xl font-semibold transition-all duration-200 cursor-pointer flex items-center gap-1.5 ${
            mapMode === "osm"
              ? "bg-gradient-to-r from-emerald-600 to-teal-600 text-white shadow-xs"
              : "text-muted hover:text-foreground hover:bg-foreground/5"
          }`}
        >
          <Layers className="w-3.5 h-3.5" />
          <span>Street Map</span>
        </button>
        <button
          type="button"
          onClick={resetView}
          title="Reset Orientation & Center"
          className="p-1.5 rounded-xl text-muted hover:text-foreground hover:bg-foreground/5 border-l border-line transition-colors cursor-pointer"
        >
          <Compass className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* Bottom Floating Telemetry Bar */}
      <div className="absolute bottom-3.5 left-3.5 right-3.5 flex flex-wrap items-center justify-between gap-2 pointer-events-none z-10">
        <div className="glass-strong text-foreground pointer-events-auto px-3.5 py-2 rounded-2xl border border-line text-[11px] font-medium shadow-md flex items-center gap-2.5">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
            <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500" />
          </span>
          <span className="text-foreground/90 font-medium">Click map or drag green pin to select parcel</span>
        </div>

        <div className="glass-strong text-foreground pointer-events-auto px-3.5 py-2 rounded-2xl border border-line text-[11px] font-mono font-bold text-foreground shadow-md flex items-center gap-2">
          <MapPin className="w-3.5 h-3.5 text-emerald-400" />
          <span>
            {Math.abs(selectedField.lat).toFixed(4)}°{selectedField.lat >= 0 ? "N" : "S"},{" "}
            {Math.abs(selectedField.lon).toFixed(4)}°{selectedField.lon >= 0 ? "E" : "W"}
          </span>
        </div>
      </div>
    </div>
  );
}
