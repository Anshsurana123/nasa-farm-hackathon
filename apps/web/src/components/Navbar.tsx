"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useI18n, DICTS } from "@/i18n";
import { useField } from "@/context/FieldContext";
import { api } from "@/lib/api";
import { fmtDMS, regionFlag } from "@/lib/ui";
import {
  Globe,
  Moon,
  Sun,
  BookOpen,
  Satellite,
  Compass,
  Activity,
  Layers,
  FlaskConical,
  Sprout,
  FileText,
  Search,
  MapPin,
  X,
  Crosshair,
} from "lucide-react";

export const WORKFLOW_ROUTES = [
  {
    href: "/",
    step: "01",
    key: "nav.home",
    navLabel: "Mission",
    shortLabel: "Mission Control",
    desc: "3D Earth & Subsurface Hub",
    icon: Compass,
    accent: "text-emerald-400",
    activeBg: "bg-emerald-500/15 border-emerald-500/50 text-emerald-600 dark:text-emerald-300",
  },
  {
    href: "/diagnostics",
    step: "02",
    key: "nav.diagnostics",
    navLabel: "Diagnostics",
    shortLabel: "Diagnostics",
    desc: "Climate, Soil & Aquifer Atlas",
    icon: Activity,
    accent: "text-cyan-400",
    activeBg: "bg-cyan-500/15 border-cyan-500/50 text-cyan-600 dark:text-cyan-300",
  },
  {
    href: "/rotations",
    step: "03",
    key: "nav.rotations",
    navLabel: "Rotations",
    shortLabel: "Rotation Studio",
    desc: "NSGA-II Optimizer & Calendar",
    icon: Layers,
    accent: "text-amber-400",
    activeBg: "bg-amber-500/15 border-amber-500/50 text-amber-600 dark:text-amber-300",
  },
  {
    href: "/lab",
    step: "04",
    key: "nav.lab",
    navLabel: "Pareto Lab",
    shortLabel: "3D Pareto & Lab",
    desc: "Frontier Cube & Shock Simulator",
    icon: FlaskConical,
    accent: "text-stone-400",
    activeBg: "bg-stone-500/15 border-stone-500/50 text-stone-600 dark:text-stone-300",
  },
  {
    href: "/crops",
    step: "05",
    key: "nav.crops",
    navLabel: "Crop KB",
    shortLabel: "Crop KB (23)",
    desc: "Botanical Specs & Suitability",
    icon: Sprout,
    accent: "text-emerald-400",
    activeBg: "bg-emerald-500/15 border-emerald-500/50 text-emerald-600 dark:text-emerald-300",
  },
  {
    href: "/brief",
    step: "06",
    key: "nav.brief",
    navLabel: "Brief",
    shortLabel: "Advisory Brief",
    desc: "Executive Dossier & Print PDF",
    icon: FileText,
    accent: "text-sky-400",
    activeBg: "bg-sky-500/15 border-sky-500/50 text-sky-600 dark:text-sky-300",
  },
] as const;

export function Navbar() {
  const pathname = usePathname();
  const router = useRouter();
  const { lang, setLang, t } = useI18n();
  const {
    goldenFields,
    selectedField,
    selectedGoldenId,
    unitSystem,
    setUnitSystem,
    selectGolden,
    selectLocation,
  } = useField();

  const [isDark, setIsDark] = useState<boolean>(true);
  const [showLocator, setShowLocator] = useState<boolean>(false);
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [searchLoading, setSearchLoading] = useState<boolean>(false);
  const [searchError, setSearchError] = useState<string | null>(null);

  useEffect(() => {
    const saved = localStorage.getItem("theme");
    const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    const dark = saved ? saved === "dark" : prefersDark;
    setIsDark(dark);
    document.documentElement.classList.toggle("dark", dark);
  }, []);

  const toggleTheme = () => {
    const nextDark = !isDark;
    setIsDark(nextDark);
    localStorage.setItem("theme", nextDark ? "dark" : "light");
    document.documentElement.classList.toggle("dark", nextDark);
  };

  const handleNavigate = (e: React.MouseEvent<HTMLAnchorElement>, href: string) => {
    if (pathname === href) return;
    e.preventDefault();
    const doc = document as Document & {
      startViewTransition?: (cb: () => void) => { finished: Promise<void> };
    };
    if (!doc.startViewTransition) {
      router.push(href);
      window.setTimeout(() => {
        document.getElementById("page-main-heading")?.focus();
      }, 60);
      return;
    }
    const transition = doc.startViewTransition(() => {
      router.push(href);
    });
    transition.finished.finally(() => {
      document.getElementById("page-main-heading")?.focus();
    });
  };

  const handleQuickSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    const q = searchQuery.trim();
    if (!q) return;
    setSearchLoading(true);
    setSearchError(null);
    try {
      const res = await api.geocode(q);
      if (res && !Number.isNaN(res.lat) && !Number.isNaN(res.lon)) {
        selectLocation({ lat: res.lat, lon: res.lon, name: res.name });
        setShowLocator(false);
        setSearchQuery("");
      } else {
        setSearchError("Location not found");
      }
    } catch (err: unknown) {
      setSearchError(err instanceof Error ? err.message : "Could not resolve location");
    } finally {
      setSearchLoading(false);
    }
  };

  return (
    <header className="sticky top-0 z-50 glass-strong border-b border-line transition-colors no-print">

      {/* Row 1: Brand + Primary Multi-Page Navigation + Utilities */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between gap-2 sm:gap-3">
        {/* Brand Emblem */}
        <Link
          href="/"
          onClick={(e) => handleNavigate(e, "/")}
          className="flex items-center gap-2.5 group shrink-0"
        >
          <div className="relative w-9 h-9 sm:w-10 sm:h-10 rounded-lg bg-foreground/[0.04] border border-line-strong flex items-center justify-center group-hover:border-emerald-500/60 transition-all shadow-sm shrink-0">
            <svg
              width="22"
              height="22"
              viewBox="0 0 24 24"
              fill="none"
              className="text-foreground"
              aria-hidden="true"
            >
              <ellipse
                cx="12"
                cy="12"
                rx="9.5"
                ry="4.2"
                transform="rotate(-24 12 12)"
                stroke="#34d399"
                strokeWidth="1.6"
              />
              <path
                d="M5 13.5L12 10L19 13.5L12 17L5 13.5Z"
                fill="currentColor"
                fillOpacity="0.16"
                stroke="#f59e0b"
                strokeWidth="1.5"
              />
              <path
                d="M5 16.8L12 20.2L19 16.8"
                stroke="#38bdf8"
                strokeWidth="1.5"
                strokeLinecap="round"
              />
              <circle cx="19.5" cy="8.5" r="2" fill="#34d399" />
            </svg>
          </div>

          <div className="flex flex-col justify-center">
            <span className="font-serif font-bold text-lg sm:text-xl leading-none tracking-tight text-foreground">
              TerraLoop
            </span>
            <span className="mt-1 inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] font-mono font-bold uppercase tracking-wider bg-emerald-500/15 text-emerald-600 dark:text-emerald-300 border border-emerald-500/35 w-fit">
              <Satellite className="w-2.5 h-2.5 text-emerald-400 shrink-0" />
              <span>NASA EO · v2.6</span>
            </span>
          </div>
        </Link>

        {/* Center: Multi-Page Route Links (Desktop) */}
        <nav
          aria-label="Primary Multi-Page Navigation"
          className="hidden lg:flex items-center gap-1 p-1 rounded-xl bg-background/60 border border-line overflow-x-auto max-w-full min-w-0"
        >
          {WORKFLOW_ROUTES.map((item) => {
            const Icon = item.icon;
            const isActive =
              item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);

            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={(e) => handleNavigate(e, item.href)}
                title={`${item.step} · ${t(item.key)} — ${item.desc}`}
                className={`px-2.5 py-1.5 rounded-lg text-xs font-mono font-semibold transition-all flex items-center gap-1.5 border whitespace-nowrap shrink-0 ${
                  isActive
                    ? `${item.activeBg} shadow-xs`
                    : "border-transparent text-muted hover:text-foreground hover:bg-foreground/5"
                }`}
              >
                <Icon className={`w-3.5 h-3.5 shrink-0 ${isActive ? "" : item.accent}`} />
                <span className="hidden xl:inline text-[10px] opacity-70">{item.step}</span>
                <span>{item.navLabel}</span>
              </Link>
            );
          })}
        </nav>

        {/* Right Controls: Methodology, Theme, Language */}
        <div className="flex items-center gap-1.5 sm:gap-2 shrink-0">
          <Link
            href="/methodology"
            onClick={(e) => handleNavigate(e, "/methodology")}
            title={t("nav.methodology")}
            className={`px-2.5 py-1.5 rounded-lg text-xs font-mono font-semibold border transition-colors hidden sm:inline-flex items-center gap-1.5 whitespace-nowrap ${
              pathname === "/methodology"
                ? "bg-stone-500/15 border-stone-500/50 text-stone-600 dark:text-stone-300"
                : "text-foreground/85 hover:text-foreground bg-foreground/[0.04] hover:bg-foreground/[0.08] border-line"
            }`}
          >
            <BookOpen className="w-3.5 h-3.5 text-stone-400 shrink-0" />
            <span className="hidden xl:inline">{t("nav.methodology")}</span>
          </Link>

          <button
            type="button"
            onClick={toggleTheme}
            aria-label="Toggle dark/light theme"
            className="p-2 rounded-lg text-xs font-medium border border-line bg-surface hover:bg-foreground/10 text-foreground transition-colors cursor-pointer flex items-center justify-center shrink-0"
            title={isDark ? "Switch to Botanical Alabaster Mode" : "Switch to Orbital Dark Mode"}
          >
            {isDark ? (
              <Sun className="w-4 h-4 text-amber-400" />
            ) : (
              <Moon className="w-4 h-4 text-slate-700" />
            )}
          </button>

          {/* Area Unit Switcher: Per Acre (Killa) vs Per Hectare */}
          <div
            className="flex items-center rounded-lg border border-line p-0.5 bg-surface text-xs font-mono shrink-0"
            title="Switch between Indian farm unit (Per Acre / Killa) and metric (Per Hectare)"
          >
            <button
              type="button"
              onClick={() => setUnitSystem("acre")}
              className={`px-2 py-1 rounded-md font-bold transition-colors cursor-pointer text-[11px] ${
                unitSystem === "acre"
                  ? "bg-amber-500 text-slate-950"
                  : "text-muted hover:text-foreground"
              }`}
            >
              /Acre
            </button>
            <button
              type="button"
              onClick={() => setUnitSystem("hectare")}
              className={`px-2 py-1 rounded-md font-bold transition-colors cursor-pointer text-[11px] ${
                unitSystem === "hectare"
                  ? "bg-amber-500 text-slate-950"
                  : "text-muted hover:text-foreground"
              }`}
            >
              /Ha
            </button>
          </div>

          {/* Language Switcher */}
          <div className="flex items-center rounded-lg border border-line p-0.5 bg-surface text-xs shrink-0">
            <span className="px-1.5 text-muted hidden xl:inline-flex">
              <Globe className="w-3.5 h-3.5" />
            </span>
            {Object.entries(DICTS).map(([code, meta]) => (
              <button
                key={code}
                type="button"
                onClick={() => setLang(code)}
                className={`px-2 py-1 rounded-md font-medium transition-colors cursor-pointer text-[11px] ${
                  lang === code
                    ? "bg-emerald-500 text-slate-950 font-bold"
                    : "text-muted hover:text-foreground"
                }`}
              >
                {meta.short}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Mobile / Tablet Multi-Page Route Strip */}
      <nav
        aria-label="Mobile Page Navigation"
        className="lg:hidden flex items-center gap-1.5 px-4 py-2 bg-background/70 border-t border-line overflow-x-auto"
      >
        {WORKFLOW_ROUTES.map((item) => {
          const Icon = item.icon;
          const isActive =
            item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              onClick={(e) => handleNavigate(e, item.href)}
              className={`px-2.5 py-1.5 rounded-lg text-xs font-mono font-semibold whitespace-nowrap flex items-center gap-1.5 border ${
                isActive
                  ? item.activeBg
                  : "border-line bg-surface/60 text-muted hover:text-foreground"
              }`}
            >
              <Icon className={`w-3.5 h-3.5 ${item.accent}`} />
              <span>
                {item.step} · {t(item.key)}
              </span>
            </Link>
          );
        })}
        <Link
          href="/methodology"
          onClick={(e) => handleNavigate(e, "/methodology")}
          className={`px-2.5 py-1.5 rounded-lg text-xs font-mono font-semibold whitespace-nowrap flex items-center gap-1.5 border ${
            pathname === "/methodology"
              ? "bg-stone-500/15 border-stone-500/50 text-stone-300"
              : "border-line bg-surface/60 text-muted hover:text-foreground"
          }`}
        >
          <BookOpen className="w-3.5 h-3.5 text-stone-400" />
          <span>{t("nav.methodology")}</span>
        </Link>
      </nav>

      {/* Row 2: Global Active Parcel Command Bar & Benchmark Switcher */}
      <div className="bg-surface-strong/80 border-t border-line px-4 sm:px-6 lg:px-8 py-2">
        <div className="max-w-7xl mx-auto flex items-center justify-between gap-3 text-xs">
          {/* Active Parcel Indicator + Benchmark Pills */}
          <div className="flex items-center gap-2 overflow-x-auto py-0.5 flex-1 min-w-0">
            <span className="text-muted font-mono font-bold shrink-0 flex items-center gap-1.5 uppercase text-[10px] tracking-widest pr-2 border-r border-line">
              <Compass className="w-3.5 h-3.5 text-emerald-400" />
              <span>{t("nav.demoFields")}</span>
            </span>

            <div className="flex items-center gap-1.5 shrink-0">
              {goldenFields.map((gf) => {
                const isSelected = selectedGoldenId === gf.id;
                const code = regionFlag(gf.id);
                const isHero = gf.id === "sangrur";

                return (
                  <button
                    key={gf.id}
                    type="button"
                    onClick={() => selectGolden(gf)}
                    className={`px-2.5 py-1 rounded-lg text-xs transition-all flex items-center gap-1.5 cursor-pointer whitespace-nowrap border ${
                      isSelected
                        ? "bg-emerald-500/20 text-foreground border-emerald-500/70 font-bold shadow-xs"
                        : "bg-surface/70 text-muted border-line hover:border-line-strong hover:text-foreground"
                    }`}
                  >
                    <span
                      className={`font-mono text-[10px] px-1.5 py-0.2 rounded font-bold ${
                        isSelected
                          ? "bg-emerald-400 text-slate-950"
                          : "bg-foreground/10 text-muted"
                      }`}
                    >
                      {code}
                    </span>
                    <span>{gf.name}</span>
                    {isHero && (
                      <span className="px-1.5 py-0.2 rounded text-[9px] font-mono font-bold uppercase tracking-wider bg-amber-500/20 text-amber-600 dark:text-amber-300 border border-amber-500/40">
                        Hero
                      </span>
                    )}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Right: Active Coordinates Readout + Global Quick-Locate Toggle */}
          <div className="flex items-center gap-2 shrink-0 ml-2">
            <div className="hidden md:flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-background/70 border border-line font-mono text-[11px]">
              <Crosshair className="w-3.5 h-3.5 text-cyan-400" />
              <span suppressHydrationWarning className="font-semibold text-foreground truncate max-w-[140px] xl:max-w-[180px]">
                {selectedField.name}
              </span>
              <span className="text-muted">·</span>
              <span suppressHydrationWarning className="text-cyan-600 dark:text-cyan-300 whitespace-nowrap">
                {fmtDMS(selectedField.lat, true)} {fmtDMS(selectedField.lon, false)}
              </span>
            </div>

            <button
              type="button"
              onClick={() => setShowLocator((v) => !v)}
              className={`px-2.5 py-1 rounded-lg font-mono text-[11px] font-bold border transition-all cursor-pointer flex items-center gap-1.5 whitespace-nowrap ${
                showLocator
                  ? "bg-cyan-500 text-slate-950 border-cyan-400"
                  : "bg-cyan-500/15 hover:bg-cyan-500/25 text-cyan-600 dark:text-cyan-300 border-cyan-500/40"
              }`}
            >
              {showLocator ? <X className="w-3.5 h-3.5" /> : <Search className="w-3.5 h-3.5" />}
              <span>{showLocator ? "Close Locator" : "Search Any Parcel"}</span>
            </button>
          </div>
        </div>

        {/* Expandable Global Parcel Search Bar */}
        {showLocator && (
          <div className="max-w-7xl mx-auto pt-2.5 mt-2 border-t border-line animate-fade-up">
            <form
              onSubmit={handleQuickSearch}
              className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2"
            >
              <div className="flex items-center gap-2 flex-1 bg-background border border-line-strong rounded-xl px-3 py-1.5 focus-within:border-cyan-400">
                <MapPin className="w-4 h-4 text-cyan-400 shrink-0" />
                <input
                  type="text"
                  required
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search any village, district, coordinates (30.2, 75.9), or paste a Google Maps URL…"
                  className="w-full bg-transparent text-xs font-mono text-foreground placeholder:text-muted outline-none"
                />
              </div>
              <button
                type="submit"
                disabled={searchLoading || !searchQuery.trim()}
                className="px-4 py-2 rounded-xl bg-emerald-500 hover:opacity-95 text-slate-950 font-mono text-xs font-bold cursor-pointer disabled:opacity-50 shrink-0"
              >
                {searchLoading ? "Locating Satellite Swath…" : "Lock Parcel Coordinates"}
              </button>
            </form>
            {searchError && (
              <p className="text-[11px] font-mono text-rose-400 mt-1.5">{searchError}</p>
            )}
          </div>
        )}
      </div>
    </header>
  );
}
