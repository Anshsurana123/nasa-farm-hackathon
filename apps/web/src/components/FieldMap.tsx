"use client";

import { useEffect, useRef } from "react";
import type { GoldenField } from "@/types/api";

interface FieldMapProps {
  selectedField: { lat: number; lon: number; name?: string };
  goldenFields: GoldenField[];
  onSelect: (field: { lat: number; lon: number; name: string }) => void;
}

export function FieldMap({ selectedField, goldenFields, onSelect }: FieldMapProps) {
  const mapContainer = useRef<HTMLDivElement>(null);
  const mapInstance = useRef<any>(null);
  const markerInstance = useRef<any>(null);

  useEffect(() => {
    let isMounted = true;

    async function initMap() {
      if (!mapContainer.current || mapInstance.current) return;

      try {
        const maplibre = await import("maplibre-gl");
        if (!isMounted || !mapContainer.current) return;

        // Load stylesheet dynamically if not present
        if (!document.getElementById("maplibre-css")) {
          const link = document.createElement("link");
          link.id = "maplibre-css";
          link.rel = "stylesheet";
          link.href = "https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.css";
          document.head.appendChild(link);
        }

        const map = new maplibre.Map({
          container: mapContainer.current,
          style: {
            version: 8,
            sources: {
              osm: {
                type: "raster",
                tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
                tileSize: 256,
                attribution: "© OpenStreetMap contributors",
              },
            },
            layers: [
              {
                id: "osm-tiles",
                type: "raster",
                source: "osm",
                minzoom: 0,
                maxzoom: 19,
              },
            ],
          },
          center: [selectedField.lon, selectedField.lat],
          zoom: 7,
        });

        map.addControl(new maplibre.NavigationControl(), "top-right");

        // Click on map to select arbitrary location
        map.on("click", (e) => {
          onSelect({
            lat: Number(e.lngLat.lat.toFixed(4)),
            lon: Number(e.lngLat.lng.toFixed(4)),
            name: `Custom (${e.lngLat.lat.toFixed(3)}, ${e.lngLat.lng.toFixed(3)})`,
          });
        });

        // Add initial marker
        const marker = new maplibre.Marker({ color: "#10b981" })
          .setLngLat([selectedField.lon, selectedField.lat])
          .addTo(map);

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

  // Update center and marker when selectedField changes
  useEffect(() => {
    if (mapInstance.current) {
      mapInstance.current.flyTo({
        center: [selectedField.lon, selectedField.lat],
        zoom: 8,
        essential: true,
      });
      if (markerInstance.current) {
        markerInstance.current.setLngLat([selectedField.lon, selectedField.lat]);
      }
    }
  }, [selectedField.lat, selectedField.lon]);

  return (
    <div className="relative w-full h-[360px] md:h-[460px] rounded-2xl overflow-hidden border border-zinc-200 dark:border-zinc-800 shadow-sm">
      <div ref={mapContainer} className="w-full h-full bg-zinc-100 dark:bg-zinc-800" />
      <div className="absolute bottom-3 left-3 bg-white/90 dark:bg-zinc-900/90 backdrop-blur-md px-3 py-1.5 rounded-lg border border-zinc-200/80 dark:border-zinc-700/80 text-[11px] font-medium text-zinc-700 dark:text-zinc-300 pointer-events-none shadow-sm">
        📍 {selectedField.name ?? "Selected Point"}: {selectedField.lat.toFixed(4)}°N, {selectedField.lon.toFixed(4)}°E
      </div>
    </div>
  );
}
