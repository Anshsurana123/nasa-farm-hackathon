"use client";

import { useEffect, useState, useTransition } from "react";
import type { FieldProfile, GoldenField, StrategyRecommendation } from "@/types/api";
import { api } from "@/lib/api";
import { Navbar } from "@/components/Navbar";
import { TelemetryBar } from "@/components/TelemetryBar";
import { FieldMap } from "@/components/FieldMap";
import { ReportCard } from "@/components/ReportCard";
import { RotationExplorer } from "@/components/RotationExplorer";
import { AgronomicBrief } from "@/components/AgronomicBrief";
import { useI18n } from "@/i18n";
import { regionContext } from "@/lib/ui";
import {
  Satellite,
  Compass,
  TrendingUp,
  FlaskConical,
  FileText,
  Search,
  MapPin,
  Sparkles,
  AlertTriangle,
  Flame,
  Droplets,
  Layers,
  ArrowRight,
  ExternalLink,
} from "lucide-react";

type MainTab = "dashboard" | "rotations" | "pareto" | "whatif" | "brief";

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
  const [strategies, setStrategies] = useState<StrategyRecommendation[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Active workspace tab
  const [activeTab, setActiveTab] = useState<MainTab>("dashboard");
  const [, startTransition] = useTransition();

  // Manual inputs for lat/lon
  const [customLat, setCustomLat] = useState<string>("30.2000");
  const [customLon, setCustomLon] = useState<string>("75.9200");

  // Address & Google Maps link import state
  const [locationInputMode, setLocationInputMode] = useState<"address" | "coords">("address");
  const [addressQuery, setAddressQuery] = useState<string>("");
  const [geocodingLoading, setGeocodingLoading] = useState<boolean>(false);
  const [geocodingError, setGeocodingError] = useState<string | null>(null);

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

  const handleAddressSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    const q = addressQuery.trim();
    if (!q) return;
    setGeocodingLoading(true);
    setGeocodingError(null);
    try {
      const res = await api.geocode(q);
      if (res && !isNaN(res.lat) && !isNaN(res.lon)) {
        setSelectedGoldenId(null);
        setSelectedField({ lat: res.lat, lon: res.lon, name: res.name });
        setCustomLat(res.lat.toFixed(4));
        setCustomLon(res.lon.toFixed(4));
      } else {
        setGeocodingError("Location not found");
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Could not find address or parse Google Maps link";
      setGeocodingError(msg);
    } finally {
      setGeocodingLoading(false);
    }
  };

  const handleTabChange = (tab: MainTab) => {
    startTransition(() => {
      setActiveTab(tab);
    });
  };

  // Regional Crisis Context
  const regCtx = regionContext(selectedField.lat, selectedField.lon, selectedGoldenId);

  return (
    <div className="min-h-screen flex flex-col bg-background text-foreground transition-colors">
      <Navbar
        goldenFields={goldenFields}
        selectedId={selectedGoldenId}
        onSelectGolden={handleSelectGolden}
      />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
        {/* Mission Telemetry Readout Strip */}
        {profile && <TelemetryBar profile={profile} />}

        {/* Dynamic Regional Crisis Context Banner */}
        {(() => {
          let title = "Global Agro-Climatic Intelligence (NASA Earth Observations)";
          let desc =
            "TerraLoop evaluates this field dynamically using NASA POWER daily agroclimatology, ISRIC SoilGrids 250m soil physics, NASA SMAP root-zone moisture, and FAO AquaCrop simulation for any parcel on Earth.";
          let badge = "Global Monitoring";
          let alertColor = "border-cyan-500/30 bg-cyan-500/5 text-cyan-600 dark:text-cyan-400";

          if (regCtx.key === "punjab") {
            title = "Lead Demo: Punjab Groundwater Depletion & Stubble Burning Crisis";
            desc =
              "NASA GRACE-FO satellites observe ~4 cm/year groundwater depletion across NW India. Tube-well paddy monoculture drives depletion, followed by October residue burning detected by NASA FIRMS. TerraLoop tests crop rotation alternatives that stabilize aquifers and eliminate burning.";
            badge = "Critical Crisis Corridor";
            alertColor = "border-amber-500/30 bg-amber-500/5 text-amber-600 dark:text-amber-400";
          } else if (regCtx.key === "california") {
            title = "Regional Context: California Central Valley Aquifer Overdraft & Drought";
            desc =
              "NASA GRACE mascons track chronic groundwater overdraft (~2.8 cm/yr) across the San Joaquin and Tulare basins during Mediterranean summer drought. TerraLoop evaluates deep-rooting pulses, minimum tillage, and high-efficiency water conservation rotations to preserve groundwater reserves.";
            badge = "Severe Aquifer Overdraft";
            alertColor = "border-orange-500/30 bg-orange-500/5 text-orange-600 dark:text-orange-400";
          } else if (regCtx.key === "cornbelt") {
            title = "Regional Context: US Corn Belt Soil Health & Cover Cropping";
            desc =
              "Continuous corn-soybean rotations experience winter bare-ground vulnerability and long-term soil organic carbon decline. TerraLoop integrates overwintering cover crops (cereal rye, red clover) with strip-till practices to boost RothC SOC stocks and curb RUSLE water erosion.";
            badge = "Soil Carbon Renewal";
            alertColor = "border-emerald-500/30 bg-emerald-500/5 text-emerald-600 dark:text-emerald-400";
          } else if (regCtx.key === "eastafrica") {
            title = "Regional Context: East Africa Bimodal Rain Resilience";
            desc =
              "Smallholders navigate unpredictable bimodal rainfall seasons (Long Rains & Short Rains) monitored by NASA GPM IMERG and SMAP. TerraLoop designs resilient rotations with drought-hardy legumes (pigeon pea, cowpea, green gram) to secure food supply and fix biological nitrogen.";
            badge = "Bimodal Climate Adaptation";
            alertColor = "border-blue-500/30 bg-blue-500/5 text-blue-600 dark:text-blue-400";
          }

          return (
            <div className="glass rounded-3xl p-5 border border-line shadow-xs flex items-start gap-4 transition-all">
              <div className="w-10 h-10 rounded-2xl bg-foreground/5 flex items-center justify-center text-2xl shrink-0 border border-line">
                {regCtx.icon}
              </div>
              <div className="space-y-1 flex-1">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-display font-bold text-sm text-foreground">
                    {title}
                  </span>
                  <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider border ${alertColor}`}>
                    {badge}
                  </span>
                </div>
                <p className="text-xs text-muted leading-relaxed">
                  {desc}
                </p>
              </div>
            </div>
          );
        })()}

        {/* Workspace Stepper / Tab Switcher */}
        <div className="flex flex-wrap items-center justify-between gap-4 border-b border-line pb-4">
          <nav
            aria-label="Workflow Steps"
            className="inline-flex rounded-2xl bg-surface p-1.5 border border-line text-xs shadow-xs flex-wrap gap-1"
          >
            <button
              type="button"
              onClick={() => handleTabChange("dashboard")}
              className={`px-3.5 py-2 rounded-xl font-semibold transition-all duration-200 cursor-pointer flex items-center gap-2 ${
                activeTab === "dashboard"
                  ? "bg-gradient-to-r from-emerald-600 to-teal-600 text-white shadow-xs font-bold"
                  : "text-muted hover:text-foreground hover:bg-foreground/5"
              }`}
            >
              <Compass className="w-4 h-4" />
              <span>1. {t("nav.dashboard")}</span>
            </button>

            <button
              type="button"
              onClick={() => handleTabChange("rotations")}
              className={`px-3.5 py-2 rounded-xl font-semibold transition-all duration-200 cursor-pointer flex items-center gap-2 ${
                activeTab === "rotations"
                  ? "bg-gradient-to-r from-emerald-600 to-teal-600 text-white shadow-xs font-bold"
                  : "text-muted hover:text-foreground hover:bg-foreground/5"
              }`}
            >
              <Sparkles className="w-4 h-4" />
              <span>2. {t("nav.rotations")}</span>
            </button>

            <button
              type="button"
              onClick={() => handleTabChange("pareto")}
              className={`px-3.5 py-2 rounded-xl font-semibold transition-all duration-200 cursor-pointer flex items-center gap-2 ${
                activeTab === "pareto"
                  ? "bg-gradient-to-r from-emerald-600 to-teal-600 text-white shadow-xs font-bold"
                  : "text-muted hover:text-foreground hover:bg-foreground/5"
              }`}
            >
              <TrendingUp className="w-4 h-4" />
              <span>3. {t("nav.pareto")}</span>
            </button>

            <button
              type="button"
              onClick={() => handleTabChange("whatif")}
              className={`px-3.5 py-2 rounded-xl font-semibold transition-all duration-200 cursor-pointer flex items-center gap-2 ${
                activeTab === "whatif"
                  ? "bg-gradient-to-r from-emerald-600 to-teal-600 text-white shadow-xs font-bold"
                  : "text-muted hover:text-foreground hover:bg-foreground/5"
              }`}
            >
              <FlaskConical className="w-4 h-4" />
              <span>4. {t("nav.whatif")}</span>
            </button>

            <button
              type="button"
              onClick={() => handleTabChange("brief")}
              className={`px-3.5 py-2 rounded-xl font-semibold transition-all duration-200 cursor-pointer flex items-center gap-2 ${
                activeTab === "brief"
                  ? "bg-gradient-to-r from-emerald-600 to-teal-600 text-white shadow-xs font-bold"
                  : "text-muted hover:text-foreground hover:bg-foreground/5"
              }`}
            >
              <FileText className="w-4 h-4" />
              <span>5. {t("nav.brief")}</span>
            </button>
          </nav>

          <div className="flex items-center gap-2 text-xs font-mono text-muted bg-surface px-3 py-1.5 rounded-xl border border-line">
            <MapPin className="w-3.5 h-3.5 text-emerald-500" />
            <span className="font-bold text-foreground">
              {selectedField.lat.toFixed(4)}°, {selectedField.lon.toFixed(4)}°
            </span>
          </div>
        </div>

        {/* Loading / Error States with Radar Orbit Visuals */}
        {loading && (
          <div className="glass rounded-3xl p-16 border border-line text-center space-y-5 shadow-lg relative overflow-hidden">
            <div className="relative w-16 h-16 mx-auto">
              <div className="absolute inset-0 rounded-full border-4 border-emerald-500/20" />
              <div className="absolute inset-0 rounded-full border-4 border-emerald-500 border-t-transparent animate-spin" />
              <div className="absolute inset-3 rounded-full bg-emerald-500/10 flex items-center justify-center text-lg">
                🛰️
              </div>
            </div>

            <div>
              <p className="font-display text-base font-bold text-foreground">{t("profile.loading")}</p>
              <p className="text-xs text-muted mt-1.5 max-w-lg mx-auto">
                Aggregating NASA POWER daily series · ISRIC SoilGrids 250m · SMAP root-zone percentiles · GRACE-FO groundwater mascons
              </p>
            </div>
          </div>
        )}

        {error && (
          <div className="p-5 rounded-3xl bg-rose-500/10 border border-rose-500/30 text-rose-600 dark:text-rose-300 text-xs space-y-1.5 shadow-sm">
            <p className="font-bold flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-rose-500" />
              <span>{t("profile.error")}</span>
            </p>
            <p className="font-mono text-[11px] opacity-90">{error}</p>
          </div>
        )}

        {/* Active Tab Views */}
        {!loading && profile && (
          <div className="transition-all duration-300">
            {/* VIEW 1: Dashboard (Interactive Map + Geocoder + Dossier) */}
            {activeTab === "dashboard" && (
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
                {/* Left: Map + Location Geocoder */}
                <div className="lg:col-span-5 space-y-4">
                  <FieldMap
                    selectedField={selectedField}
                    goldenFields={goldenFields}
                    onSelect={handleMapSelect}
                  />

                  {/* Location Selector (Address / Google Maps or Lat/Lon) */}
                  <div className="glass rounded-3xl p-5 border border-line shadow-sm text-xs space-y-3.5">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2 font-display font-bold text-foreground">
                        <MapPin className="w-4 h-4 text-emerald-500" />
                        <span>Select or Search Field</span>
                      </div>
                      <div className="inline-flex rounded-xl bg-foreground/5 p-0.5 border border-line text-[11px]">
                        <button
                          type="button"
                          onClick={() => setLocationInputMode("address")}
                          className={`px-3 py-1 rounded-lg font-semibold transition-all duration-200 cursor-pointer ${
                            locationInputMode === "address"
                              ? "bg-emerald-600 text-white shadow-xs"
                              : "text-muted hover:text-foreground"
                          }`}
                        >
                          🗺️ Address / Maps Link
                        </button>
                        <button
                          type="button"
                          onClick={() => setLocationInputMode("coords")}
                          className={`px-3 py-1 rounded-lg font-semibold transition-all duration-200 cursor-pointer ${
                            locationInputMode === "coords"
                              ? "bg-emerald-600 text-white shadow-xs"
                              : "text-muted hover:text-foreground"
                          }`}
                        >
                          🌐 Coordinates
                        </button>
                      </div>
                    </div>

                    {locationInputMode === "address" ? (
                      <form onSubmit={handleAddressSearch} className="space-y-2.5">
                        <div className="flex gap-2">
                          <input
                            type="text"
                            value={addressQuery}
                            onChange={(e) => setAddressQuery(e.target.value)}
                            placeholder="Type city/address or paste Google Maps link..."
                            className="flex-1 px-3.5 py-2.5 rounded-2xl border border-line bg-surface text-foreground placeholder:text-muted text-xs focus:ring-2 focus:ring-emerald-500/30 focus:border-emerald-500 outline-none transition-all"
                          />
                          <button
                            type="submit"
                            disabled={geocodingLoading || !addressQuery.trim()}
                            className="px-4 py-2.5 rounded-2xl bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white font-bold transition-all flex items-center gap-1.5 shrink-0 cursor-pointer disabled:opacity-50 shadow-md text-xs"
                          >
                            {geocodingLoading ? (
                              <>
                                <span className="w-3.5 h-3.5 rounded-full border-2 border-white border-t-transparent animate-spin" />
                                <span>Locating...</span>
                              </>
                            ) : (
                              <>
                                <Search className="w-3.5 h-3.5" />
                                <span>Locate</span>
                              </>
                            )}
                          </button>
                        </div>
                        {geocodingError && (
                          <p className="text-[11px] text-rose-500 font-semibold">{geocodingError}</p>
                        )}
                        <div className="flex items-center justify-between text-[10px] text-muted pt-0.5">
                          <span>💡 Supports shortened Google Maps links (goo.gl, maps.app) and global addresses</span>
                          <span className="font-mono">{selectedField.lat.toFixed(3)}°, {selectedField.lon.toFixed(3)}°</span>
                        </div>
                      </form>
                    ) : (
                      <form onSubmit={handleManualSubmit} className="space-y-2.5">
                        <div className="flex gap-2.5">
                          <div className="flex-1">
                            <label className="text-[10px] text-muted block mb-1 font-medium">Latitude (-90 to 90)</label>
                            <input
                              type="number"
                              step="0.0001"
                              value={customLat}
                              onChange={(e) => setCustomLat(e.target.value)}
                              className="w-full px-3 py-2 rounded-xl border border-line bg-surface font-mono text-foreground text-xs outline-none"
                            />
                          </div>
                          <div className="flex-1">
                            <label className="text-[10px] text-muted block mb-1 font-medium">Longitude (-180 to 180)</label>
                            <input
                              type="number"
                              step="0.0001"
                              value={customLon}
                              onChange={(e) => setCustomLon(e.target.value)}
                              className="w-full px-3 py-2 rounded-xl border border-line bg-surface font-mono text-foreground text-xs outline-none"
                            />
                          </div>
                          <div className="flex items-end">
                            <button
                              type="submit"
                              className="px-4 py-2 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 text-white font-bold hover:brightness-110 transition-opacity cursor-pointer shadow-md text-xs"
                            >
                              Analyse
                            </button>
                          </div>
                        </div>
                      </form>
                    )}
                  </div>
                </div>

                {/* Right: Field Diagnostic Report Card Dossier */}
                <div className="lg:col-span-7">
                  <ReportCard profile={profile} />
                </div>
              </div>
            )}

            {/* VIEW 2: Rotation Decision Engine */}
            {activeTab === "rotations" && (
              <RotationExplorer
                field={{ lat: selectedField.lat, lon: selectedField.lon, name: selectedField.name }}
                profile={profile}
                initialTab="cards"
                onStrategiesLoaded={(s) => setStrategies(s)}
                strategies={strategies.length > 0 ? strategies : undefined}
              />
            )}

            {/* VIEW 3: Pareto Frontier */}
            {activeTab === "pareto" && (
              <RotationExplorer
                field={{ lat: selectedField.lat, lon: selectedField.lon, name: selectedField.name }}
                profile={profile}
                initialTab="pareto"
                onStrategiesLoaded={(s) => setStrategies(s)}
                strategies={strategies.length > 0 ? strategies : undefined}
              />
            )}

            {/* VIEW 4: What-If Climate Stress Lab */}
            {activeTab === "whatif" && (
              <RotationExplorer
                field={{ lat: selectedField.lat, lon: selectedField.lon, name: selectedField.name }}
                profile={profile}
                initialTab="whatif"
                onStrategiesLoaded={(s) => setStrategies(s)}
                strategies={strategies.length > 0 ? strategies : undefined}
              />
            )}

            {/* VIEW 5: Field Agronomic Brief */}
            {activeTab === "brief" && (
              <AgronomicBrief profile={profile} strategies={strategies} />
            )}
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-line bg-surface/70 py-8 text-xs text-muted mt-12 transition-colors">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-2.5">
            <span className="font-display font-black text-foreground">TerraLoop</span>
            <span>·</span>
            <span className="font-semibold text-emerald-500">NASA Space Apps Challenge 2026</span>
          </div>
          <div className="flex items-center gap-4 text-[11px] flex-wrap">
            <span>Data: NASA POWER · ISRIC SoilGrids · SMAP · GRACE-FO · FIRMS · FAO AquaCrop</span>
            <a
              href="/methodology"
              className="hover:text-foreground underline flex items-center gap-1 transition-colors"
            >
              <span>Methodology &amp; Documentation</span>
              <ExternalLink className="w-3 h-3" />
            </a>
          </div>
        </div>
      </footer>
    </div>
  );
}
