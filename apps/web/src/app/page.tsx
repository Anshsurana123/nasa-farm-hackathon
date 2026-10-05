"use client";

import { useEffect, useState } from "react";
import type { FieldProfile, GoldenField } from "@/types/api";
import { api } from "@/lib/api";
import { Navbar } from "@/components/Navbar";
import { FieldMap } from "@/components/FieldMap";
import { ReportCard } from "@/components/ReportCard";
import { RotationExplorer } from "@/components/RotationExplorer";
import { useI18n } from "@/i18n";

export default function Home() {
  const { t } = useI18n();
  const [goldenFields, setGoldenFields] = useState<GoldenField[]>([]);
  const [selectedField, setSelectedField] = useState<{ lat: number; lon: number; name: string }>({
    lat: 30.2,
    lon: 75.92,
    name: "Sangrur, Punjab (hero field)",
  });
  const [selectedGoldenId, setSelectedGoldenId] = useState<string | null>("sangrur");
  const [profile, setProfile] = useState<FieldProfile | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Manual inputs for lat/lon
  const [customLat, setCustomLat] = useState<string>("30.2000");
  const [customLon, setCustomLon] = useState<string>("75.9200");

  // Load golden fields list on mount
  useEffect(() => {
    api
      .goldenFields()
      .then((fields) => {
        setGoldenFields(fields);
        const hero = fields.find((f) => f.id === "sangrur") ?? fields[0];
        if (hero) {
          setSelectedGoldenId(hero.id);
          setSelectedField({ lat: hero.lat, lon: hero.lon, name: hero.name });
        }
      })
      .catch((err) => {
        console.warn("Could not load golden fields list:", err);
      });
  }, []);

  // Fetch profile whenever selectedField changes
  useEffect(() => {
    let isCancelled = false;
    setLoading(true);
    setError(null);

    const fetchPromise = selectedGoldenId
      ? api.goldenProfile(selectedGoldenId)
      : api.profile({ lat: selectedField.lat, lon: selectedField.lon, name: selectedField.name });

    fetchPromise
      .then((data) => {
        if (!isCancelled) {
          setProfile(data);
          setLoading(false);
          setCustomLat(selectedField.lat.toFixed(4));
          setCustomLon(selectedField.lon.toFixed(4));
        }
      })
      .catch((err) => {
        if (!isCancelled) {
          console.error("Failed to load profile:", err);
          setError(err.message ?? "Failed to load field profile");
          setLoading(false);
        }
      });

    return () => {
      isCancelled = true;
    };
  }, [selectedField.lat, selectedField.lon, selectedGoldenId]);

  const handleSelectGolden = (field: GoldenField) => {
    setSelectedGoldenId(field.id);
    setSelectedField({ lat: field.lat, lon: field.lon, name: field.name });
  };

  const handleMapSelect = (point: { lat: number; lon: number; name: string }) => {
    setSelectedGoldenId(null);
    setSelectedField(point);
  };

  const handleManualSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const lat = parseFloat(customLat);
    const lon = parseFloat(customLon);
    if (!isNaN(lat) && !isNaN(lon)) {
      setSelectedGoldenId(null);
      setSelectedField({ lat, lon, name: `Coordinate (${lat.toFixed(3)}, ${lon.toFixed(3)})` });
    }
  };

  return (
    <div className="min-h-screen flex flex-col bg-zinc-50 dark:bg-zinc-950">
      <Navbar
        goldenFields={goldenFields}
        selectedId={selectedGoldenId}
        onSelectGolden={handleSelectGolden}
      />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
        {/* Top Grid: Interactive Map + Field Selector */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
          {/* Map Column (5 cols) */}
          <div className="lg:col-span-5 space-y-4">
            <FieldMap
              selectedField={selectedField}
              goldenFields={goldenFields}
              onSelect={handleMapSelect}
            />

            {/* Coordinate input & details form */}
            <div className="bg-white dark:bg-zinc-900 rounded-2xl p-4 border border-zinc-200 dark:border-zinc-800 shadow-sm text-xs space-y-3">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-zinc-900 dark:text-zinc-100 flex items-center gap-1.5">
                  <span>📍</span>
                  <span>Field Coordinates</span>
                </span>
                <span className="text-[10px] text-zinc-400">{t("map.hint")}</span>
              </div>

              <form onSubmit={handleManualSubmit} className="flex gap-2">
                <div className="flex-1">
                  <label className="text-[10px] text-zinc-400 block mb-0.5">Latitude</label>
                  <input
                    type="number"
                    step="0.0001"
                    value={customLat}
                    onChange={(e) => setCustomLat(e.target.value)}
                    className="w-full px-2.5 py-1.5 rounded-lg border border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-800 font-mono text-zinc-900 dark:text-zinc-100"
                  />
                </div>
                <div className="flex-1">
                  <label className="text-[10px] text-zinc-400 block mb-0.5">Longitude</label>
                  <input
                    type="number"
                    step="0.0001"
                    value={customLon}
                    onChange={(e) => setCustomLon(e.target.value)}
                    className="w-full px-2.5 py-1.5 rounded-lg border border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-800 font-mono text-zinc-900 dark:text-zinc-100"
                  />
                </div>
                <div className="flex items-end">
                  <button
                    type="submit"
                    className="px-3 py-1.5 rounded-lg bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900 font-semibold hover:opacity-90 transition-opacity"
                  >
                    Analyse
                  </button>
                </div>
              </form>
            </div>

            {/* Regional Context Banner */}
            {selectedGoldenId === "sangrur" && (
              <div className="rounded-2xl p-4 bg-gradient-to-br from-amber-50 to-orange-50 dark:from-amber-950/30 dark:to-orange-950/20 border border-amber-200/80 dark:border-amber-800/50 text-xs space-y-1.5">
                <span className="font-bold text-amber-900 dark:text-amber-200 flex items-center gap-1">
                  <span>🚨</span> Lead Demo: Punjab Groundwater & Stubble Crisis
                </span>
                <p className="text-amber-950/80 dark:text-amber-300/80 leading-relaxed text-[11px]">
                  NASA GRACE-FO satellites observe <strong>~4 cm/year</strong> groundwater depletion across NW India. Tube-well paddy monoculture drives depletion, followed by October residue burning detected by NASA FIRMS. TerraLoop tests crop rotation alternatives that stabilize aquifers.
                </p>
              </div>
            )}
          </div>

          {/* Report Card Column (7 cols) */}
          <div className="lg:col-span-7">
            {loading ? (
              <div className="bg-white dark:bg-zinc-900 rounded-2xl p-12 border border-zinc-200 dark:border-zinc-800 text-center space-y-3">
                <div className="w-8 h-8 rounded-full border-2 border-emerald-500 border-t-transparent animate-spin mx-auto" />
                <p className="text-xs text-zinc-500 font-medium">{t("profile.loading")}</p>
              </div>
            ) : error ? (
              <div className="bg-rose-50 dark:bg-rose-950/30 rounded-2xl p-6 border border-rose-200 dark:border-rose-900/50 text-rose-800 dark:text-rose-200 text-xs space-y-2">
                <p className="font-bold">{t("profile.error")}</p>
                <p className="font-mono text-[11px] opacity-80">{error}</p>
              </div>
            ) : profile ? (
              <div className="space-y-6">
                <ReportCard profile={profile} />
                <RotationExplorer region={selectedGoldenId ?? undefined} />
              </div>
            ) : null}
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 py-6 text-xs text-zinc-500">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <span className="font-bold text-zinc-900 dark:text-zinc-100">TerraLoop</span>
            <span>·</span>
            <span>NASA Space Apps Challenge 2026</span>
          </div>
          <div className="flex items-center gap-4 text-[11px]">
            <span>Data: NASA POWER · ISRIC SoilGrids · SMAP · GRACE · FIRMS</span>
            <a
              href="https://github.com"
              target="_blank"
              rel="noreferrer"
              className="hover:text-zinc-900 dark:hover:text-zinc-100 underline"
            >
              Methodology & Docs
            </a>
          </div>
        </div>
      </footer>
    </div>
  );
}
