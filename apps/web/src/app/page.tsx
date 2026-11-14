"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AppShell } from "@/components/AppShell";
import { FieldMap } from "@/components/FieldMap";
import { SoilColumn3D } from "@/components/SoilColumn3D";
import { ProgressRing } from "@/components/ProgressRing";
import { TelemetryBar } from "@/components/TelemetryBar";
import { useField } from "@/context/FieldContext";
import { useI18n } from "@/i18n";
import { api } from "@/lib/api";
import {
  avgIrrigation,
  buildSectorBriefing,
  fmtAreaMoney,
  fmtAreaUnit,
  fmtDMS,
  isSouthAsia,
  regionContext,
  regionFlag,
  waterSavedPct,
} from "@/lib/ui";
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  Compass,
  FileText,
  FlaskConical,
  Layers,
  MapPin,
  RefreshCw,
  Search,
  Sparkles,
  Sprout,
  TrendingUp,
} from "lucide-react";

export default function MissionControlPage() {
  const { t, lang } = useI18n();
  const {
    goldenFields,
    selectedField,
    selectedGoldenId,
    profile,
    strategies,
    crops,
    unitSystem,
    error,
    runOptimization,
    selectGolden,
    selectLocation,
  } = useField();

  const [locationInputMode, setLocationInputMode] = useState<"address" | "coords">("address");
  const [addressQuery, setAddressQuery] = useState<string>("");
  const [customLat, setCustomLat] = useState<string>(selectedField.lat.toFixed(4));
  const [customLon, setCustomLon] = useState<string>(selectedField.lon.toFixed(4));
  const [geocodingLoading, setGeocodingLoading] = useState<boolean>(false);
  const [geocodingError, setGeocodingError] = useState<string | null>(null);

  useEffect(() => {
    setCustomLat(selectedField.lat.toFixed(4));
    setCustomLon(selectedField.lon.toFixed(4));
  }, [selectedField.lat, selectedField.lon]);

  const regCtx = regionContext(selectedField.lat, selectedField.lon, selectedGoldenId);
  const isSA = isSouthAsia(selectedField.lat, selectedField.lon);
  const currencySymbol = profile?.currency_symbol ?? (isSA ? "₹" : "$");

  const baseline = strategies.find((s) => s.rank === 0) ?? strategies[0];
  const topRec = strategies.find((s) => s.rank === 1) ?? strategies[1] ?? null;
  const baseRes = baseline?.results?.[0];
  const topRes = topRec?.results?.[0];

  const savedWater = topRec ? (waterSavedPct(topRec) ?? null) : null;
  const baseIrr = baseRes ? avgIrrigation(baseRes) : null;
  const topIrr = topRes ? avgIrrigation(topRes) : null;
  const profitMedian = topRes?.profit_p50 ?? null;
  const soilScore = topRes ? Math.round(topRes.soil_health_score) : null;

  const handleAddressSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    const q = addressQuery.trim();
    if (!q) return;
    setGeocodingLoading(true);
    setGeocodingError(null);
    try {
      const res = await api.geocode(q);
      if (res && !Number.isNaN(res.lat) && !Number.isNaN(res.lon)) {
        selectLocation({ lat: res.lat, lon: res.lon, name: res.name });
        setCustomLat(res.lat.toFixed(4));
        setCustomLon(res.lon.toFixed(4));
      } else {
        setGeocodingError(t("nav.locationNotFound"));
      }
    } catch (err: unknown) {
      setGeocodingError(
        err instanceof Error ? err.message : t("home.geocodeErrorFallback")
      );
    } finally {
      setGeocodingLoading(false);
    }
  };

  const handleManualSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const lat = parseFloat(customLat);
    const lon = parseFloat(customLon);
    if (!Number.isNaN(lat) && !Number.isNaN(lon) && lat >= -90 && lat <= 90 && lon >= -180 && lon <= 180) {
      const reg = regionContext(lat, lon, null);
      selectLocation({
        lat,
        lon,
        name: `${reg.shortName} (${lat.toFixed(3)}°, ${lon.toFixed(3)}°)`,
      });
    }
  };

  // Dynamic regional + live NASA/SoilGrids profile briefing
  const {
    badge: sectorBadge,
    badgeTone,
    title: sectorTitle,
    description: sectorDesc,
  } = buildSectorBriefing(
    selectedField.lat,
    selectedField.lon,
    selectedGoldenId,
    profile,
    topRec ?? undefined,
    lang === "hi" || lang === "pa" ? lang : "en"
  );

  return (
    <AppShell showTelemetry={false} alwaysRenderChildren={true}>
      {/* ------------------------------------------------------------------- */}
      {/* SECTION 01: LOCATION SELECTION (Map Pin Drop + Address / Geocode)   */}
      {/* ------------------------------------------------------------------- */}
      <section aria-labelledby="location-selection-heading" className="space-y-3.5">
        {/* Step Header & Live Parcel Status */}
        <div className="glass rounded-2xl px-4 sm:px-6 py-3.5 border border-line reticle-frame flex flex-col md:flex-row md:items-center justify-between gap-3">
          <div className="flex items-center gap-2.5 flex-wrap">
            <span className="px-2.5 py-0.5 rounded-md bg-emerald-500/20 text-emerald-600 dark:text-emerald-300 border border-emerald-500/40 font-mono text-[11px] font-bold uppercase tracking-wider flex items-center gap-1.5">
              <MapPin className="w-3.5 h-3.5 text-emerald-500" />
              <span>{t("home.step01Badge")}</span>
            </span>
            <h2 id="location-selection-heading" className="font-display text-sm sm:text-base font-bold text-foreground">
              {t("home.step01Heading")}
            </h2>
            <span className="text-xs text-muted hidden lg:inline">
              {t("home.step01Subtext")}
            </span>
          </div>

          <div className="flex items-center gap-2 font-mono text-xs shrink-0">
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-xl bg-background/80 border border-line-strong text-foreground font-semibold">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              <span suppressHydrationWarning className="truncate max-w-[180px] sm:max-w-[240px]">{selectedField.name}</span>
            </span>
            <span suppressHydrationWarning className="px-2.5 py-1 rounded-xl bg-background/50 border border-line text-cyan-500 dark:text-cyan-300 font-bold whitespace-nowrap">
              {fmtDMS(selectedField.lat, true)} {fmtDMS(selectedField.lon, false)}
            </span>
          </div>
        </div>

        {/* 2-Column Location Command Deck: Map on Left (Pin Drop) + Address Sampler & Presets on Right */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-stretch">
          {/* Map Pin Drop Container */}
          <div className="lg:col-span-7 xl:col-span-7 flex flex-col">
            <FieldMap
              selectedField={selectedField}
              goldenFields={goldenFields}
              onSelect={(pt) => {
                const matched = pt.id ? goldenFields.find((g) => g.id === pt.id) : undefined;
                if (matched) selectGolden(matched);
                else selectLocation(pt);
                setCustomLat(pt.lat.toFixed(4));
                setCustomLon(pt.lon.toFixed(4));
              }}
            />
          </div>

          {/* Address, URL, Coordinates & Benchmark Presets Card */}
          <div className="lg:col-span-5 xl:col-span-5 flex flex-col">
            <div className="glass rounded-2xl p-4 sm:p-5 border border-line text-xs space-y-3.5 h-full flex flex-col justify-between">
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 font-mono text-[11px] uppercase tracking-wider font-bold text-foreground">
                    <Search className="w-3.5 h-3.5 text-cyan-400" />
                    <span>{t("home.addressSearchHeading")}</span>
                  </div>
                  <div className="inline-flex rounded-lg bg-background/80 p-0.5 border border-line text-[10px] font-mono">
                    <button
                      type="button"
                      onClick={() => setLocationInputMode("address")}
                      className={`px-2.5 py-1 rounded-md font-semibold transition-colors cursor-pointer ${
                        locationInputMode === "address"
                          ? "bg-emerald-500 text-slate-950 font-bold"
                          : "text-muted hover:text-foreground"
                      }`}
                    >
                      {t("home.addressTab")}
                    </button>
                    <button
                      type="button"
                      onClick={() => setLocationInputMode("coords")}
                      className={`px-2.5 py-1 rounded-md font-semibold transition-colors cursor-pointer ${
                        locationInputMode === "coords"
                          ? "bg-emerald-500 text-slate-950 font-bold"
                          : "text-muted hover:text-foreground"
                      }`}
                    >
                      {t("home.coordsTab")}
                    </button>
                  </div>
                </div>

                {locationInputMode === "address" ? (
                  <form onSubmit={handleAddressSearch} className="space-y-2">
                    <div className="flex gap-2">
                      <input
                        type="text"
                        required
                        value={addressQuery}
                        onChange={(e) => setAddressQuery(e.target.value)}
                        placeholder={t("home.addressPlaceholder")}
                        className="flex-1 px-3 py-2 rounded-xl border border-line-strong bg-background text-foreground placeholder:text-muted text-xs font-mono focus:border-cyan-400 outline-none transition-colors"
                      />
                      <button
                        type="submit"
                        disabled={geocodingLoading || !addressQuery.trim()}
                        className="px-4 py-2 rounded-xl bg-emerald-500 hover:opacity-95 text-slate-950 font-mono font-bold transition-opacity flex items-center gap-1.5 shrink-0 cursor-pointer disabled:opacity-50 text-xs shadow-xs"
                      >
                        <Search className="w-3.5 h-3.5" />
                        <span>{geocodingLoading ? "…" : t("home.locateBtn")}</span>
                      </button>
                    </div>
                    {geocodingError && (
                      <p className="text-[11px] font-mono text-rose-500 font-semibold">{geocodingError}</p>
                    )}
                  </form>
                ) : (
                  <form onSubmit={handleManualSubmit} className="space-y-2">
                    <div className="flex gap-2">
                      <div className="flex-1">
                        <label className="text-[10px] font-mono text-muted block mb-1">{t("home.latLabel")}</label>
                        <input
                          type="number"
                          step="0.0001"
                          min="-90"
                          max="90"
                          required
                          value={customLat}
                          onChange={(e) => setCustomLat(e.target.value)}
                          className="w-full px-3 py-1.5 rounded-xl border border-line-strong bg-background font-mono text-foreground text-xs outline-none focus:border-cyan-400"
                        />
                      </div>
                      <div className="flex-1">
                        <label className="text-[10px] font-mono text-muted block mb-1">{t("home.lonLabel")}</label>
                        <input
                          type="number"
                          step="0.0001"
                          min="-180"
                          max="180"
                          required
                          value={customLon}
                          onChange={(e) => setCustomLon(e.target.value)}
                          className="w-full px-3 py-1.5 rounded-xl border border-line-strong bg-background font-mono text-foreground text-xs outline-none focus:border-cyan-400"
                        />
                      </div>
                      <div className="flex items-end">
                        <button
                          type="submit"
                          className="px-4 py-1.5 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-mono font-bold transition-colors cursor-pointer text-xs"
                        >
                          {t("home.goBtn")}
                        </button>
                      </div>
                    </div>
                  </form>
                )}
              </div>

              {/* Golden Benchmark Quick-Select Grid */}
              <div className="pt-3 border-t border-line space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-mono uppercase tracking-wider text-muted font-bold block">
                    {t("home.benchmarkHeader")}
                  </span>
                  <span className="text-[9px] font-mono text-emerald-500">
                    {t("home.benchmarkCount", { count: String(goldenFields.length || 6) })}
                  </span>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  {goldenFields.map((gf) => {
                    const active = selectedGoldenId === gf.id;
                    return (
                      <button
                        key={gf.id}
                        type="button"
                        onClick={() => selectGolden(gf)}
                        className={`p-2.5 rounded-xl border text-left transition-all cursor-pointer flex flex-col justify-between gap-1 ${
                          active
                            ? "bg-emerald-500/15 border-emerald-500/60 shadow-xs"
                            : "bg-background/50 hover:bg-foreground/5 border-line"
                        }`}
                      >
                        <div className="flex items-center justify-between gap-1">
                          <span className="font-display font-bold text-xs text-foreground truncate">
                            {gf.name}
                          </span>
                          <span className="px-1.5 py-0.5 rounded text-[9px] font-mono font-bold bg-foreground/10 text-emerald-500 shrink-0">
                            {regionFlag(gf.id)}
                          </span>
                        </div>
                        <p className="text-[10px] text-muted line-clamp-1">{gf.story}</p>
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ------------------------------------------------------------------- */}
      {/* SECTION 02: INFORMATION PROVIDED FOR SELECTED LOCATION              */}
      {/* ------------------------------------------------------------------- */}
      <section aria-labelledby="information-provided-heading" className="space-y-6 pt-2">
        {/* Section Context Header */}
        <div className="flex items-center justify-between border-b border-line pb-3">
          <div className="flex items-center gap-2.5 flex-wrap">
            <span className="px-2.5 py-0.5 rounded-md bg-cyan-500/20 text-cyan-600 dark:text-cyan-300 border border-cyan-500/40 font-mono text-[11px] font-bold uppercase tracking-wider flex items-center gap-1.5">
              <Sparkles className="w-3.5 h-3.5 text-cyan-400" />
              <span>{t("home.step02Badge")}</span>
            </span>
            <span className="text-muted font-mono text-xs">
              {t("home.liveDataFor")} <strong suppressHydrationWarning className="text-foreground">{selectedField.name}</strong>
            </span>
          </div>
          <span className="text-[11px] font-mono text-muted hidden sm:inline">
            NASA POWER · ISRIC SoilGrids · SMAP · GRACE-FO · HLS
          </span>
        </div>

        {/* 1. NASA Observational Telemetry Strip */}
        {profile && <TelemetryBar profile={profile} />}

        {/* Error notice with explicit Retry button when optimization failed */}
        {error && (
          <div className="p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/35 flex flex-wrap items-center justify-between gap-3 text-xs font-mono text-rose-600 dark:text-rose-300">
            <div className="flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-rose-500 shrink-0" />
              <span>{error}</span>
            </div>
            <button
              type="button"
              onClick={() => runOptimization()}
              className="px-3 py-1 rounded-lg bg-rose-500/20 hover:bg-rose-500/30 border border-rose-500/40 font-bold cursor-pointer flex items-center gap-1.5"
            >
              <RefreshCw className="w-3 h-3" />
              <span>{t("common.retry")}</span>
            </button>
          </div>
        )}

        {/* 2. Hero Mission Command Deck: Regional Agro-Climatic Briefing & Top Prescription */}
        <section className="glass rounded-2xl p-5 sm:p-6 border border-line reticle-frame relative overflow-hidden">
          <div className="grid grid-cols-1 xl:grid-cols-12 gap-6 items-center">
            {/* Left: Regional Briefing & Mission Actions */}
            <div className="xl:col-span-7 space-y-3">
              <div className="flex items-center gap-2 flex-wrap font-mono text-[11px]">
                <span className="px-2.5 py-0.5 rounded-md bg-emerald-500/20 text-emerald-600 dark:text-emerald-300 border border-emerald-500/40 font-bold uppercase tracking-wider">
                  {t("home.agroClimaticZone")}
                </span>
                <span className={`px-2.5 py-0.5 rounded-md font-bold uppercase tracking-wider border ${badgeTone}`}>
                  {sectorBadge}
                </span>
                <span className="text-muted">
                  {regCtx.icon} · {fmtDMS(selectedField.lat, true)} {fmtDMS(selectedField.lon, false)}
                </span>
              </div>

              <h1
                id="information-provided-heading"
                tabIndex={-1}
                className="font-serif text-2xl sm:text-3xl font-bold text-foreground tracking-tight outline-none"
              >
                {sectorTitle}
              </h1>

              <p className="text-xs sm:text-sm text-muted leading-relaxed prose-measure">
                {sectorDesc}
              </p>

              <div className="pt-2 flex flex-wrap items-center gap-2.5">
                <Link
                  href="/rotations"
                  className="px-4 py-2.5 rounded-xl bg-emerald-500 hover:opacity-95 text-slate-950 font-mono text-xs font-bold flex items-center gap-2 shadow-md transition-opacity"
                >
                  <Sparkles className="w-4 h-4" />
                  <span>{t("home.launchRotations")}</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </Link>

                <Link
                  href="/diagnostics"
                  className="px-4 py-2.5 rounded-xl bg-surface hover:bg-foreground/10 border border-line-strong text-foreground font-mono text-xs font-semibold flex items-center gap-2 transition-colors"
                >
                  <Activity className="w-4 h-4 text-cyan-400" />
                  <span>{t("home.inspectDiagnostics")}</span>
                </Link>

                <Link
                  href="/lab"
                  className="px-4 py-2.5 rounded-xl bg-surface hover:bg-foreground/10 border border-line-strong text-foreground font-mono text-xs font-semibold flex items-center gap-2 transition-colors"
                >
                  <FlaskConical className="w-4 h-4 text-stone-400" />
                  <span>{t("home.openLab")}</span>
                </Link>
              </div>
            </div>

            {/* Right: Live Prescriptive Transformation Preview Card */}
            <div className="xl:col-span-5 rounded-2xl p-4 sm:p-5 bg-background/50 border border-line-strong space-y-3.5">
              <div className="flex items-center justify-between font-mono text-[10px]">
                <span className="font-bold uppercase tracking-widest text-emerald-600 dark:text-emerald-300 flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                  <span suppressHydrationWarning>
                    {t("home.topPrescriptionFor", { name: selectedField.name.toUpperCase() })}
                  </span>
                </span>
                <span className="px-2 py-0.5 rounded bg-background/70 border border-line text-muted">
                  NSGA-II RANK #1
                </span>
              </div>

              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-[11px] font-mono text-muted">
                    {t("home.replaces")}: <span className="line-through opacity-75">{baseline?.rotation.label ?? t("home.baselinePlaceholder")}</span>
                  </p>
                  <h2 className="font-display font-bold text-base sm:text-lg text-foreground mt-0.5">
                    {topRec?.rotation.label ?? t("home.awaitingStrategies")}
                  </h2>
                </div>

                <ProgressRing
                  value={soilScore ?? 0}
                  max={100}
                  label={t("strategy.soilHealthScore")}
                  size="3.4rem"
                  thickness="5px"
                  color="var(--accent-canopy)"
                >
                  <span className="text-xs font-mono font-bold text-emerald-500">
                    {soilScore != null ? soilScore : "—"}
                  </span>
                  <span className="text-[8px] font-mono text-muted">{t("home.soilRingTag")}</span>
                </ProgressRing>
              </div>

              <div className="grid grid-cols-3 gap-2 pt-2 border-t border-line font-mono text-xs">
                <div className="p-2.5 rounded-xl bg-background/60 border border-line">
                  <span className="text-[9px] text-muted uppercase block">{t("home.waterSavedCard")}</span>
                  <span className="text-sm font-bold text-cyan-500 dark:text-cyan-300">
                    {savedWater != null ? `−${Math.max(0, savedWater)}% H₂O` : "—"}
                  </span>
                  <span className="text-[9px] text-muted block">
                    {baseIrr != null && topIrr != null
                      ? `${Math.max(0, Math.round(baseIrr - topIrr))} mm/yr`
                      : "—"}
                  </span>
                </div>

                <div className="p-2.5 rounded-xl bg-background/60 border border-line">
                  <span className="text-[9px] text-muted uppercase block">{t("home.netMarginCard")}</span>
                  <span className="text-sm font-bold text-emerald-600 dark:text-emerald-400">
                    {profitMedian != null
                      ? fmtAreaMoney(profitMedian, currencySymbol, unitSystem)
                      : "—"}
                  </span>
                  <span className="text-[9px] text-muted block">
                    {t("home.medianP50")}{fmtAreaUnit(unitSystem)}
                  </span>
                </div>

                <div className="p-2.5 rounded-xl bg-background/60 border border-line">
                  <span className="text-[9px] text-muted uppercase block">{t("home.soc10YrCard")}</span>
                  <span className="text-sm font-bold text-amber-500 dark:text-amber-300">
                    {topRes?.soc_delta_t_ha_10yr != null
                      ? `${topRes.soc_delta_t_ha_10yr > 0 ? "+" : ""}${topRes.soc_delta_t_ha_10yr.toFixed(1)} t/ha`
                      : "—"}
                  </span>
                  <span className="text-[9px] text-muted block">RothC-26.3</span>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* 3. Deep Exploration Workspace: 3D Subsurface Monolith + Multi-Page Mission Launchpad */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
          {/* Left Column: Interactive 3D Stratigraphic Pedon */}
          <div className="lg:col-span-5 space-y-4">
            {profile && <SoilColumn3D profile={profile} strategies={strategies} />}
          </div>

          {/* Right Column: Multi-Page Dedicated Mission Modules */}
          <div className="lg:col-span-7 space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="font-display font-bold text-xs uppercase tracking-wider text-foreground flex items-center gap-2">
                <Compass className="w-4 h-4 text-emerald-400" />
                <span>{t("home.exploreModules")}</span>
              </h2>
              <span className="text-[11px] font-mono text-muted">
                {t("home.syncedTo", { name: selectedField.name })}
              </span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
              {/* Module 02: Field Diagnostics */}
              <Link
                href="/diagnostics"
                className="glass card-interactive rounded-2xl p-4.5 border border-line flex flex-col justify-between gap-3 group"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="w-10 h-10 rounded-xl bg-cyan-500/15 border border-cyan-500/40 flex items-center justify-center text-cyan-400 shrink-0">
                    <Activity className="w-5 h-5" />
                  </div>
                  <span className="text-[10px] font-mono font-bold uppercase px-2 py-0.5 rounded bg-cyan-500/15 text-cyan-500 dark:text-cyan-300 border border-cyan-500/30">
                    {t("app.module")} 02
                  </span>
                </div>
                <div>
                  <h3 className="font-display font-bold text-base text-foreground group-hover:text-cyan-400 transition-colors">
                    {t("home.mod02Title")}
                  </h3>
                  <p className="text-xs text-muted mt-1 leading-relaxed">
                    {t("home.mod02Desc")}
                  </p>
                </div>
                <div className="pt-2 border-t border-line flex items-center justify-between text-[11px] font-mono text-cyan-500 dark:text-cyan-300 font-semibold">
                  <span>
                    {profile
                      ? `${t("telemetry.rain")}: ${Math.round(profile.climate.annual_precip_mm)} mm/yr · SOC: ${profile.soil.soc_g_per_kg?.toFixed(1) ?? "—"} g/kg`
                      : "—"}
                  </span>
                  <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
                </div>
              </Link>

              {/* Module 03: Rotation Studio */}
              <Link
                href="/rotations"
                className="glass card-interactive rounded-2xl p-4.5 border border-line flex flex-col justify-between gap-3 group"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="w-10 h-10 rounded-xl bg-amber-500/15 border border-amber-500/40 flex items-center justify-center text-amber-400 shrink-0">
                    <Layers className="w-5 h-5" />
                  </div>
                  <span className="text-[10px] font-mono font-bold uppercase px-2 py-0.5 rounded bg-amber-500/15 text-amber-600 dark:text-amber-300 border border-amber-500/30">
                    {t("app.module")} 03
                  </span>
                </div>
                <div>
                  <h3 className="font-display font-bold text-base text-foreground group-hover:text-amber-400 transition-colors">
                    {t("home.mod03Title")}
                  </h3>
                  <p className="text-xs text-muted mt-1 leading-relaxed">
                    {t("home.mod03Desc")}
                  </p>
                </div>
                <div className="pt-2 border-t border-line flex items-center justify-between text-[11px] font-mono text-amber-600 dark:text-amber-300 font-semibold">
                  <span>
                    {strategies.length > 0 && savedWater != null
                      ? t("home.mod03Stat", {
                          count: String(strategies.length),
                          saved: String(Math.max(0, savedWater)),
                        })
                      : t("home.mod03Idle")}
                  </span>
                  <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
                </div>
              </Link>

              {/* Module 04: 3D Pareto & Shock Lab */}
              <Link
                href="/lab"
                className="glass card-interactive rounded-2xl p-4.5 border border-line flex flex-col justify-between gap-3 group"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="w-10 h-10 rounded-xl bg-stone-500/15 border border-stone-500/40 flex items-center justify-center text-stone-400 shrink-0">
                    <TrendingUp className="w-5 h-5" />
                  </div>
                  <span className="text-[10px] font-mono font-bold uppercase px-2 py-0.5 rounded bg-stone-500/15 text-stone-600 dark:text-stone-300 border border-stone-500/30">
                    {t("app.module")} 04
                  </span>
                </div>
                <div>
                  <h3 className="font-display font-bold text-base text-foreground group-hover:text-stone-400 transition-colors">
                    {t("home.mod04Title")}
                  </h3>
                  <p className="text-xs text-muted mt-1 leading-relaxed">
                    {t("home.mod04Desc")}
                  </p>
                </div>
                <div className="pt-2 border-t border-line flex items-center justify-between text-[11px] font-mono text-stone-600 dark:text-stone-300 font-semibold">
                  <span>{t("home.mod04Stat")}</span>
                  <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
                </div>
              </Link>

              {/* Module 05 & 06: Crop KB + Advisory Brief */}
              <div className="grid grid-cols-1 gap-3.5">
                <Link
                  href="/crops"
                  className="glass card-interactive rounded-2xl p-4 border border-line flex items-center justify-between gap-3 group"
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="w-10 h-10 rounded-xl bg-emerald-500/15 border border-emerald-500/40 flex items-center justify-center text-emerald-400 shrink-0">
                      <Sprout className="w-5 h-5" />
                    </div>
                    <div className="min-w-0">
                      <span className="text-[10px] font-mono font-bold text-emerald-500 uppercase block">
                        {t("home.mod05Tag", { count: String(crops.length || 23) })}
                      </span>
                      <h3 className="font-display font-bold text-sm text-foreground truncate">
                        {t("home.mod05Title")}
                      </h3>
                    </div>
                  </div>
                  <ArrowRight className="w-4 h-4 text-emerald-400 shrink-0 group-hover:translate-x-1 transition-transform" />
                </Link>

                <Link
                  href="/brief"
                  className="glass card-interactive rounded-2xl p-4 border border-line flex items-center justify-between gap-3 group"
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="w-10 h-10 rounded-xl bg-sky-500/15 border border-sky-500/40 flex items-center justify-center text-sky-400 shrink-0">
                      <FileText className="w-5 h-5" />
                    </div>
                    <div className="min-w-0">
                      <span className="text-[10px] font-mono font-bold text-sky-400 uppercase block">
                        {t("home.mod06Tag")}
                      </span>
                      <h3 className="font-display font-bold text-sm text-foreground truncate">
                        {t("home.mod06Title")}
                      </h3>
                    </div>
                  </div>
                  <ArrowRight className="w-4 h-4 text-sky-400 shrink-0 group-hover:translate-x-1 transition-transform" />
                </Link>
              </div>
            </div>
          </div>
        </div>
      </section>
    </AppShell>
  );
}
