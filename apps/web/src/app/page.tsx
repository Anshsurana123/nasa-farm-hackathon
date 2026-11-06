"use client";

import { useState } from "react";
import Link from "next/link";
import { AppShell } from "@/components/AppShell";
import { FieldMap } from "@/components/FieldMap";
import { SoilColumn3D } from "@/components/SoilColumn3D";
import { ProgressRing } from "@/components/ProgressRing";
import { useField } from "@/context/FieldContext";
import { api } from "@/lib/api";
import {
  avgIrrigation,
  fmtDMS,
  fmtMoney,
  isSouthAsia,
  regionContext,
  regionFlag,
  waterSavedPct,
} from "@/lib/ui";
import {
  Activity,
  ArrowRight,
  Compass,
  Droplets,
  FileText,
  FlaskConical,
  Layers,
  MapPin,
  Search,
  Sparkles,
  Sprout,
  TrendingUp,
} from "lucide-react";

export default function MissionControlPage() {
  const {
    goldenFields,
    selectedField,
    selectedGoldenId,
    profile,
    strategies,
    crops,
    selectGolden,
    selectLocation,
  } = useField();

  const [locationInputMode, setLocationInputMode] = useState<"address" | "coords">("address");
  const [addressQuery, setAddressQuery] = useState<string>("");
  const [customLat, setCustomLat] = useState<string>(selectedField.lat.toFixed(4));
  const [customLon, setCustomLon] = useState<string>(selectedField.lon.toFixed(4));
  const [geocodingLoading, setGeocodingLoading] = useState<boolean>(false);
  const [geocodingError, setGeocodingError] = useState<string | null>(null);

  const regCtx = regionContext(selectedField.lat, selectedField.lon, selectedGoldenId);
  const isSA = isSouthAsia(selectedField.lat, selectedField.lon);
  const currencySymbol = profile?.currency_symbol ?? (isSA ? "₹" : "$");

  const baseline = strategies.find((s) => s.rank === 0) ?? strategies[0];
  const topRec = strategies.find((s) => s.rank === 1) ?? strategies[1] ?? baseline;
  const baseRes = baseline?.results?.[0];
  const topRes = topRec?.results?.[0];

  const savedWater = topRec ? (waterSavedPct(topRec) ?? 24) : 24;
  const baseIrr = avgIrrigation(baseRes) ?? 1450;
  const topIrr = avgIrrigation(topRes) ?? 1080;
  const profitMedian = topRes?.profit_p50 ?? (isSA ? 104000 : 1240);
  const soilScore = Math.round(topRes?.soil_health_score ?? 74);

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
        setGeocodingError("Location not found");
      }
    } catch (err: unknown) {
      setGeocodingError(
        err instanceof Error ? err.message : "Could not find address or parse Google Maps link"
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
      selectLocation({
        lat,
        lon,
        name: `Coordinate (${lat.toFixed(3)}°, ${lon.toFixed(3)}°)`,
      });
    }
  };

  // Regional narrative metadata
  let sectorTitle = "Global Agro-Climatic Intelligence & Subsurface Modeling";
  let sectorDesc =
    "Dynamic parcel diagnostics coupling NASA POWER daily agroclimatology, ISRIC SoilGrids 250m soil physics, NASA SMAP root-zone moisture, and FAO AquaCrop simulation.";
  let sectorBadge = "GLOBAL EO SWATH";
  let badgeTone = "border-cyan-500/45 bg-cyan-500/15 text-cyan-600 dark:text-cyan-300";

  if (regCtx.key === "punjab") {
    sectorTitle = "Indo-Gangetic Basin: Aquifer Depletion & Stubble Fire Mitigation";
    sectorDesc =
      "NASA GRACE-FO mascons track ~3.85 cm/yr groundwater drawdown across NW India driven by flooded paddy monoculture, followed by October residue burning observed by NASA FIRMS. TerraLoop evaluates DSR, pulse, and residue-retention rotations.";
    sectorBadge = "CRITICAL AQUIFER CORRIDOR";
    badgeTone = "border-amber-500/50 bg-amber-500/15 text-amber-600 dark:text-amber-300";
  } else if (regCtx.key === "california") {
    sectorTitle = "San Joaquin & Tulare Basin: Mediterranean Overdraft & Drought Adaptation";
    sectorDesc =
      "NASA GRACE mascons record chronic groundwater overdraft (~2.8 cm/yr) across the Central Valley. TerraLoop evaluates deep-rooting pulses, minimum tillage, and deficit-irrigated rotations to stabilize basin storage.";
    sectorBadge = "AQUIFER OVERDRAFT ZONE";
    badgeTone = "border-orange-500/50 bg-orange-500/15 text-orange-600 dark:text-orange-300";
  } else if (regCtx.key === "cornbelt") {
    sectorTitle = "Upper Midwest Corn Belt: Topsoil Carbon & Cover-Crop Integration";
    sectorDesc =
      "Continuous corn-soybean sequences leave winter soils bare and vulnerable to RUSLE sheet erosion. TerraLoop tests overwintering cover crops (cereal rye, red clover) and strip-till practices to rebuild RothC organic carbon.";
    sectorBadge = "SOIL CARBON RENEWAL";
    badgeTone = "border-emerald-500/50 bg-emerald-500/15 text-emerald-600 dark:text-emerald-300";
  } else if (regCtx.key === "eastafrica") {
    sectorTitle = "East African Highlands: Bimodal Monsoon & Biological N-Fixation";
    sectorDesc =
      "Smallholder parcels navigate variable Long Rains and Short Rains monitored by NASA GPM IMERG and SMAP. TerraLoop pairs cereals with drought-hardy legumes (pigeon pea, cowpea, green gram) to fix atmospheric nitrogen.";
    sectorBadge = "BIMODAL MONSOON ADAPTATION";
    badgeTone = "border-cyan-500/50 bg-cyan-500/15 text-cyan-600 dark:text-cyan-300";
  }

  return (
    <AppShell showTelemetry={true}>
      {/* Hero Mission Command Deck */}
      <section className="glass rounded-2xl p-5 sm:p-6 border border-line reticle-frame relative overflow-hidden">
        <div className="grid grid-cols-1 xl:grid-cols-12 gap-6 items-center">
          {/* Left: Regional Briefing & Mission Actions */}
          <div className="xl:col-span-7 space-y-3">
            <div className="flex items-center gap-2 flex-wrap font-mono text-[11px]">
              <span className="px-2.5 py-0.5 rounded-md bg-emerald-500/20 text-emerald-600 dark:text-emerald-300 border border-emerald-500/40 font-bold uppercase tracking-wider">
                MODULE 01 // MISSION CONTROL
              </span>
              <span className={`px-2.5 py-0.5 rounded-md font-bold uppercase tracking-wider border ${badgeTone}`}>
                {sectorBadge}
              </span>
              <span className="text-muted">
                {regCtx.icon} · {fmtDMS(selectedField.lat, true)} {fmtDMS(selectedField.lon, false)}
              </span>
            </div>

            <h1
              id="page-main-heading"
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
                className="px-4 py-2.5 rounded-xl bg-gradient-to-r from-emerald-500 to-cyan-500 hover:opacity-95 text-slate-950 font-mono text-xs font-bold flex items-center gap-2 shadow-md transition-opacity"
              >
                <Sparkles className="w-4 h-4" />
                <span>Launch Rotation Studio</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </Link>

              <Link
                href="/diagnostics"
                className="px-4 py-2.5 rounded-xl bg-surface hover:bg-foreground/10 border border-line-strong text-foreground font-mono text-xs font-semibold flex items-center gap-2 transition-colors"
              >
                <Activity className="w-4 h-4 text-cyan-400" />
                <span>Inspect Field Diagnostics</span>
              </Link>

              <Link
                href="/lab"
                className="px-4 py-2.5 rounded-xl bg-surface hover:bg-foreground/10 border border-line-strong text-foreground font-mono text-xs font-semibold flex items-center gap-2 transition-colors"
              >
                <FlaskConical className="w-4 h-4 text-violet-400" />
                <span>Open 3D Pareto &amp; Shock Lab</span>
              </Link>
            </div>
          </div>

          {/* Right: Live Prescriptive Transformation Preview Card */}
          <div className="xl:col-span-5 rounded-2xl p-4 sm:p-5 bg-gradient-to-br from-emerald-500/12 via-cyan-500/8 to-violet-500/12 border border-emerald-500/35 space-y-3.5">
            <div className="flex items-center justify-between font-mono text-[10px]">
              <span className="font-bold uppercase tracking-widest text-emerald-600 dark:text-emerald-300 flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                <span>TOP PRESCRIPTION FOR {selectedField.name.toUpperCase()}</span>
              </span>
              <span className="px-2 py-0.5 rounded bg-background/70 border border-line text-muted">
                NSGA-II RANK #1
              </span>
            </div>

            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-[11px] font-mono text-muted">
                  Replaces: <span className="line-through opacity-75">{baseline?.rotation.label ?? "Intensive Baseline"}</span>
                </p>
                <h2 className="font-display font-bold text-base sm:text-lg text-foreground mt-0.5">
                  {topRec?.rotation.label ?? "DSR Rice ➔ Wheat + Mulch ➔ Summer Moong"}
                </h2>
              </div>

              <ProgressRing
                value={soilScore}
                max={100}
                label="Recommended Strategy Soil Health Score"
                size="3.4rem"
                thickness="5px"
                color="var(--accent-canopy)"
              >
                <span className="text-xs font-mono font-bold text-emerald-500">{soilScore}</span>
                <span className="text-[8px] font-mono text-muted">SOIL</span>
              </ProgressRing>
            </div>

            <div className="grid grid-cols-3 gap-2 pt-2 border-t border-line font-mono text-xs">
              <div className="p-2.5 rounded-xl bg-background/60 border border-line">
                <span className="text-[9px] text-muted uppercase block">Water Saved</span>
                <span className="text-sm font-bold text-cyan-500 dark:text-cyan-300">
                  −{ Math.max(0, savedWater) }% H₂O
                </span>
                <span className="text-[9px] text-muted block">{baseIrr - topIrr} mm/yr cut</span>
              </div>

              <div className="p-2.5 rounded-xl bg-background/60 border border-line">
                <span className="text-[9px] text-muted uppercase block">Net Margin</span>
                <span className="text-sm font-bold text-emerald-600 dark:text-emerald-400">
                  {fmtMoney(profitMedian, currencySymbol)}
                </span>
                <span className="text-[9px] text-muted block">Median P50/ha</span>
              </div>

              <div className="p-2.5 rounded-xl bg-background/60 border border-line">
                <span className="text-[9px] text-muted uppercase block">10-Yr Carbon</span>
                <span className="text-sm font-bold text-amber-500 dark:text-amber-300">
                  +{(topRes?.soc_delta_t_ha_10yr ?? 2.1).toFixed(1)} t/ha
                </span>
                <span className="text-[9px] text-muted block">RothC-26.3</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Main Split Interactive Workspace: 3D Terrain Map + 3D Subsurface Monolith */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left Column: 3D Satellite Swath Map + Parcel Locator + Benchmark Cards */}
        <div className="lg:col-span-5 space-y-5">
          <FieldMap
            selectedField={selectedField}
            goldenFields={goldenFields}
            onSelect={(pt) => {
              selectLocation(pt);
              setCustomLat(pt.lat.toFixed(4));
              setCustomLon(pt.lon.toFixed(4));
            }}
          />

          {/* Interactive Coordinate / Geocode Panel */}
          <div className="glass rounded-2xl p-4 sm:p-5 border border-line text-xs space-y-3.5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 font-mono text-[11px] uppercase tracking-wider font-bold text-foreground">
                <MapPin className="w-4 h-4 text-cyan-400" />
                <span>Parcel Geocode &amp; Coordinate Sampler</span>
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
                  Address / URL
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
                  Lat / Lon
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
                    placeholder="Enter village, district, or paste Google Maps URL…"
                    className="flex-1 px-3 py-2 rounded-xl border border-line-strong bg-background text-foreground placeholder:text-muted text-xs font-mono focus:border-cyan-400 outline-none transition-colors"
                  />
                  <button
                    type="submit"
                    disabled={geocodingLoading || !addressQuery.trim()}
                    className="px-4 py-2 rounded-xl bg-gradient-to-r from-emerald-500 to-cyan-500 hover:opacity-95 text-slate-950 font-mono font-bold transition-opacity flex items-center gap-1.5 shrink-0 cursor-pointer disabled:opacity-50 text-xs"
                  >
                    <Search className="w-3.5 h-3.5" />
                    <span>{geocodingLoading ? "…" : "Sample"}</span>
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
                    <label className="text-[10px] font-mono text-muted block mb-1">LATITUDE [°N]</label>
                    <input
                      type="number"
                      step="0.0001"
                      min="-90"
                      max="90"
                      required
                      value={customLat}
                      onChange={(e) => setCustomLat(e.target.value)}
                      className="w-full px-3 py-1.5 rounded-xl border border-line-strong bg-background font-mono text-foreground text-xs outline-none"
                    />
                  </div>
                  <div className="flex-1">
                    <label className="text-[10px] font-mono text-muted block mb-1">LONGITUDE [°E]</label>
                    <input
                      type="number"
                      step="0.0001"
                      min="-180"
                      max="180"
                      required
                      value={customLon}
                      onChange={(e) => setCustomLon(e.target.value)}
                      className="w-full px-3 py-1.5 rounded-xl border border-line-strong bg-background font-mono text-foreground text-xs outline-none"
                    />
                  </div>
                  <div className="flex items-end">
                    <button
                      type="submit"
                      className="px-4 py-1.5 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-mono font-bold transition-colors cursor-pointer text-xs"
                    >
                      Go
                    </button>
                  </div>
                </div>
              </form>
            )}

            {/* Golden Benchmark Quick-Select Grid */}
            <div className="pt-2 border-t border-line space-y-2">
              <span className="text-[10px] font-mono uppercase tracking-wider text-muted block">
                Precomputed NASA Benchmark Stations (Instant Zero-Latency)
              </span>
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

        {/* Right Column: Interactive 3D Stratigraphic Pedon + Multi-Page Mission Launchpad */}
        <div className="lg:col-span-7 space-y-5">
          {profile && <SoilColumn3D profile={profile} strategies={strategies} />}

          {/* Multi-Page Mission Modules Grid */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="font-display font-bold text-xs uppercase tracking-wider text-foreground flex items-center gap-2">
                <Compass className="w-4 h-4 text-emerald-400" />
                <span>Explore Dedicated Mission Modules</span>
              </h2>
              <span className="text-[11px] font-mono text-muted">
                All modules stay synced to {selectedField.name}
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
                    MODULE 02
                  </span>
                </div>
                <div>
                  <h3 className="font-display font-bold text-base text-foreground group-hover:text-cyan-400 transition-colors">
                    Deep Field Diagnostics Atlas
                  </h3>
                  <p className="text-xs text-muted mt-1 leading-relaxed">
                    Interactive 12-month hyetograph, thermal envelope, USDA soil texture granulometry, SMAP root-zone percentiles, and HLS satellite crop history.
                  </p>
                </div>
                <div className="pt-2 border-t border-line flex items-center justify-between text-[11px] font-mono text-cyan-500 dark:text-cyan-300 font-semibold">
                  <span>Rain: {Math.round(profile?.climate.annual_precip_mm ?? 650)} mm/yr · SOC: {profile?.soil.soc_g_per_kg?.toFixed(1) ?? "8.5"} g/kg</span>
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
                    MODULE 03
                  </span>
                </div>
                <div>
                  <h3 className="font-display font-bold text-base text-foreground group-hover:text-amber-400 transition-colors">
                    Rotation Decision Studio &amp; Calendar
                  </h3>
                  <p className="text-xs text-muted mt-1 leading-relaxed">
                    Tune farmer priority weights, inspect the 12-month agronomic Gantt sowing calendar, and compare 5-axis USDA-NRCS soil health radar profiles.
                  </p>
                </div>
                <div className="pt-2 border-t border-line flex items-center justify-between text-[11px] font-mono text-amber-600 dark:text-amber-300 font-semibold">
                  <span>{strategies.length} Rotations Simulated · Top Saves {savedWater}% H₂O</span>
                  <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
                </div>
              </Link>

              {/* Module 04: 3D Pareto & Shock Lab */}
              <Link
                href="/lab"
                className="glass card-interactive rounded-2xl p-4.5 border border-line flex flex-col justify-between gap-3 group"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="w-10 h-10 rounded-xl bg-violet-500/15 border border-violet-500/40 flex items-center justify-center text-violet-400 shrink-0">
                    <TrendingUp className="w-5 h-5" />
                  </div>
                  <span className="text-[10px] font-mono font-bold uppercase px-2 py-0.5 rounded bg-violet-500/15 text-violet-600 dark:text-violet-300 border border-violet-500/30">
                    MODULE 04
                  </span>
                </div>
                <div>
                  <h3 className="font-display font-bold text-base text-foreground group-hover:text-violet-400 transition-colors">
                    3D Pareto Frontier &amp; Climate Shock Lab
                  </h3>
                  <p className="text-xs text-muted mt-1 leading-relaxed">
                    Orbit the 3D multi-objective trade-off cube and stress-test rotations against ET₀ droughts, MSP price drops, and urea fertilizer spikes.
                  </p>
                </div>
                <div className="pt-2 border-t border-line flex items-center justify-between text-[11px] font-mono text-violet-600 dark:text-violet-300 font-semibold">
                  <span>3D Cube + What-If Perturbation Matrix</span>
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
                        MODULE 05 // {crops.length || 21} CROPS
                      </span>
                      <h3 className="font-display font-bold text-sm text-foreground truncate">
                        Botanical Encyclopedia &amp; Suitability
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
                        MODULE 06 // PRINT PDF
                      </span>
                      <h3 className="font-display font-bold text-sm text-foreground truncate">
                        Executive Advisory Brief &amp; Farm Scaler
                      </h3>
                    </div>
                  </div>
                  <ArrowRight className="w-4 h-4 text-sky-400 shrink-0 group-hover:translate-x-1 transition-transform" />
                </Link>
              </div>
            </div>
          </div>
        </div>
      </div>
    </AppShell>
  );
}
