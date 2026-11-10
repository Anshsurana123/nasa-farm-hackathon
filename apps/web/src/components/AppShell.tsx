"use client";

import type { ReactNode } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Navbar, WORKFLOW_ROUTES } from "./Navbar";
import { TelemetryBar } from "./TelemetryBar";
import { useField } from "@/context/FieldContext";
import { useI18n } from "@/i18n";
import {
  ArrowLeft,
  ArrowRight,
  AlertTriangle,
  ExternalLink,
  Satellite,
  Sparkles,
} from "lucide-react";

interface AppShellProps {
  children: ReactNode;
  showTelemetry?: boolean;
  alwaysRenderChildren?: boolean;
  pageStep?: string;
  pageBadge?: string;
  pageTitle?: string;
  pageDescription?: string;
  headerActions?: ReactNode;
}

export function AppShell({
  children,
  showTelemetry = true,
  alwaysRenderChildren = false,
  pageStep,
  pageBadge,
  pageTitle,
  pageDescription,
  headerActions,
}: AppShellProps) {
  const pathname = usePathname();
  const router = useRouter();
  const { t } = useI18n();
  const { profile, strategies, loading, error } = useField();

  const isFallbackData =
    Boolean(profile?.is_fallback) ||
    profile?.data_mode === "fallback_synthetic" ||
    strategies.some((s) => s.is_fallback || s.data_mode === "fallback_synthetic");
  const isHybridRegional =
    !isFallbackData &&
    (profile?.data_mode === "hybrid_regional" ||
      strategies.some((s) => s.data_mode === "hybrid_regional"));

  const currentIdx = WORKFLOW_ROUTES.findIndex((r) =>
    r.href === "/" ? pathname === "/" : pathname.startsWith(r.href)
  );
  const prevRoute = currentIdx > 0 ? WORKFLOW_ROUTES[currentIdx - 1] : null;
  const nextRoute =
    currentIdx >= 0 && currentIdx < WORKFLOW_ROUTES.length - 1
      ? WORKFLOW_ROUTES[currentIdx + 1]
      : null;

  const navigateWithTransition = (e: React.MouseEvent<HTMLAnchorElement>, href: string) => {
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

  return (
    <div className="min-h-screen flex flex-col bg-background text-foreground transition-colors">
      <Navbar />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
        {/* Page Header Banner (when provided) */}
        {pageTitle && (
          <div className="glass rounded-2xl p-5 sm:p-6 border border-line reticle-frame flex flex-col lg:flex-row lg:items-center justify-between gap-4 no-print">
            <div className="space-y-1.5">
              <div className="flex items-center gap-2 flex-wrap font-mono text-[11px]">
                {pageStep && (
                  <span className="px-2 py-0.5 rounded-md bg-emerald-500/20 text-emerald-600 dark:text-emerald-300 border border-emerald-500/40 font-bold uppercase tracking-wider">
                    MODULE {pageStep}
                  </span>
                )}
                {pageBadge && (
                  <span className="px-2.5 py-0.5 rounded-md bg-cyan-500/15 text-cyan-600 dark:text-cyan-300 border border-cyan-500/35 font-semibold uppercase tracking-wider flex items-center gap-1.5">
                    <Sparkles className="w-3 h-3" />
                    <span>{pageBadge}</span>
                  </span>
                )}
              </div>

              <h1
                id="page-main-heading"
                tabIndex={-1}
                className="font-serif text-2xl sm:text-3xl font-bold text-foreground tracking-tight outline-none"
              >
                {pageTitle}
              </h1>

              {pageDescription && (
                <p className="text-xs sm:text-sm text-muted leading-relaxed prose-measure">
                  {pageDescription}
                </p>
              )}
            </div>

            {headerActions && <div className="flex items-center gap-2.5 shrink-0">{headerActions}</div>}
          </div>
        )}

        {/* Persistent NASA Telemetry Strip */}
        {showTelemetry && profile && (
          <div className="no-print">
            <TelemetryBar profile={profile} />
          </div>
        )}

        {/* Data Mode / Fallback Transparency Banner */}
        {profile && (isFallbackData || isHybridRegional) && (
          <div
            role="status"
            className={`p-3.5 rounded-xl border text-xs font-mono flex items-start gap-2.5 no-print ${
              isFallbackData
                ? "bg-amber-500/15 border-amber-500/45 text-amber-600 dark:text-amber-300"
                : "bg-cyan-500/10 border-cyan-500/35 text-cyan-600 dark:text-cyan-300"
            }`}
          >
            <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
            <div>
              {isFallbackData ? (
                <>
                  <span className="font-bold uppercase">FALLBACK DATA MODE (SYNTHETIC / REGIONAL CLIMATOLOGY): </span>
                  <span>
                    Live NASA POWER / SoilGrids APIs were unreachable for this coordinate. Showing regional
                    climatology estimates rather than observed field telemetry.
                  </span>
                </>
              ) : (
                <>
                  <span className="font-bold uppercase">HYBRID REGIONAL DATA MODE: </span>
                  <span>
                    NASA POWER and SoilGrids are observed, while GEE satellite layers (GRACE, SMAP, NASADEM) use
                    regional climatology and FIRMS/HLS are marked unknown unless Earth Engine is active.
                  </span>
                </>
              )}
            </div>
          </div>
        )}

        {/* Loading / Error States */}
        {loading && !alwaysRenderChildren && (
          <div className="glass rounded-2xl p-16 border border-line text-center space-y-4 reticle-frame">
            <div className="relative w-12 h-12 mx-auto">
              <div className="absolute inset-0 rounded-full border-2 border-line-strong" />
              <div className="absolute inset-0 rounded-full border-2 border-emerald-400 border-t-transparent animate-spin" />
            </div>
            <div>
              <p className="font-mono text-sm font-bold text-foreground uppercase tracking-wider">
                {t("profile.loading")}
              </p>
              <p className="text-xs font-mono text-muted mt-1.5 max-w-lg mx-auto">
                SYNCHRONIZING: NASA POWER AG · ISRIC SOILGRIDS 250M · SMAP L4 · GRACE-FO TELLUS · HLS 30M
              </p>
            </div>
          </div>
        )}

        {/* Global Loading Banner when children stay mounted (e.g., Mission Control with live map) */}
        {loading && alwaysRenderChildren && (
          <div className="p-3 rounded-xl bg-emerald-500/15 border border-emerald-500/35 text-emerald-400 text-xs font-mono flex items-center justify-between no-print animate-pulse shadow-sm">
            <span className="flex items-center gap-2 font-bold uppercase tracking-wider text-[11px]">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
              <span>SYNCHRONIZING NASA TELEMETRY FOR NEW PARCEL COORDINATES…</span>
            </span>
            <span className="text-[10px] text-muted hidden sm:inline font-mono">
              POWER AG · SoilGrids 250m · SMAP L4 · GRACE-FO
            </span>
          </div>
        )}

        {error && (
          <div className="p-5 rounded-2xl bg-rose-500/10 border border-rose-500/35 text-rose-600 dark:text-rose-300 text-xs space-y-1.5">
            <p className="font-bold font-mono flex items-center gap-2 uppercase">
              <AlertTriangle className="w-4 h-4 text-rose-500" />
              <span>{t("profile.error")}</span>
            </p>
            <p className="font-mono text-[11px] opacity-90">{error}</p>
          </div>
        )}

        {/* Page Body */}
        {(alwaysRenderChildren || (!loading && profile)) && (
          <div className="animate-fade-up space-y-6">{children}</div>
        )}

        {/* Multi-Page Mission Progression Stepper */}
        {(prevRoute || nextRoute) && (
          <div className="pt-4 no-print">
            <div className="glass rounded-2xl p-4 sm:p-5 border border-line flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-4">
              {prevRoute ? (
                <Link
                  href={prevRoute.href}
                  onClick={(e) => navigateWithTransition(e, prevRoute.href)}
                  className="group flex items-center gap-3 p-3 rounded-xl bg-surface hover:bg-foreground/5 border border-line transition-all"
                >
                  <div className="w-9 h-9 rounded-lg bg-foreground/5 border border-line flex items-center justify-center group-hover:-translate-x-0.5 transition-transform">
                    <ArrowLeft className="w-4 h-4 text-muted group-hover:text-foreground" />
                  </div>
                  <div>
                    <span className="block text-[10px] font-mono uppercase tracking-wider text-muted">
                      Previous Step ({prevRoute.step})
                    </span>
                    <span className="font-display font-bold text-sm text-foreground">
                      {t(prevRoute.key)}
                    </span>
                  </div>
                </Link>
              ) : (
                <div className="hidden sm:block" />
              )}

              <div className="hidden md:flex items-center gap-1.5">
                {WORKFLOW_ROUTES.map((r, idx) => (
                  <Link
                    key={r.href}
                    href={r.href}
                    onClick={(e) => navigateWithTransition(e, r.href)}
                    title={`${r.step} · ${r.shortLabel}`}
                    className={`h-2 rounded-full transition-all ${
                      idx === currentIdx
                        ? "w-8 bg-emerald-400"
                        : idx < currentIdx
                        ? "w-3 bg-emerald-500/45"
                        : "w-3 bg-foreground/15 hover:bg-foreground/30"
                    }`}
                  />
                ))}
              </div>

              {nextRoute && (
                <Link
                  href={nextRoute.href}
                  onClick={(e) => navigateWithTransition(e, nextRoute.href)}
                  className="group flex items-center justify-between sm:justify-end gap-3 p-3 px-4 rounded-xl bg-emerald-500/20 border border-emerald-500/45 transition-all"
                >
                  <div className="text-left sm:text-right">
                    <span className="block text-[10px] font-mono font-bold uppercase tracking-wider text-emerald-600 dark:text-emerald-300">
                      Next Mission Module ({nextRoute.step})
                    </span>
                    <span className="font-display font-bold text-sm text-foreground">
                      {t(nextRoute.key)} — {nextRoute.desc}
                    </span>
                  </div>
                  <div className="w-9 h-9 rounded-lg bg-emerald-500 text-slate-950 flex items-center justify-center group-hover:translate-x-0.5 transition-transform shrink-0">
                    <ArrowRight className="w-4 h-4" />
                  </div>
                </Link>
              )}
            </div>
          </div>
        )}
      </main>

      {/* Multi-Page Footer */}
      <footer className="border-t border-line bg-surface-strong/80 py-8 text-xs font-mono text-muted mt-12 transition-colors no-print">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-12 gap-6 items-start">
            <div className="md:col-span-5 space-y-2">
              <div className="flex items-center gap-2.5">
                <Satellite className="w-4 h-4 text-emerald-400" />
                <span className="font-serif font-bold text-base text-foreground">TerraLoop</span>
                <span className="px-2 py-0.5 rounded bg-emerald-500/15 text-emerald-600 dark:text-emerald-300 border border-emerald-500/30 text-[10px] font-bold">
                  NASA Space Apps 2026
                </span>
              </div>
              <p className="text-xs font-sans text-muted leading-relaxed max-w-md">
                Multi-objective crop rotation decision-support platform coupling NASA satellite
                Earth observations with process-based soil carbon, hydrological, and economic models.
              </p>
            </div>

            <div className="md:col-span-7 grid grid-cols-2 sm:grid-cols-3 gap-3 text-[11px]">
              {WORKFLOW_ROUTES.map((r) => (
                <Link
                  key={r.href}
                  href={r.href}
                  onClick={(e) => navigateWithTransition(e, r.href)}
                  className="p-2.5 rounded-xl bg-background/50 hover:bg-foreground/5 border border-line transition-colors flex flex-col gap-0.5"
                >
                  <span className="text-[10px] text-emerald-500 font-bold">MODULE {r.step}</span>
                  <span className="font-sans font-semibold text-foreground">{r.shortLabel}</span>
                  <span className="text-[10px] text-muted truncate font-sans">{r.desc}</span>
                </Link>
              ))}
            </div>
          </div>

          <div className="pt-4 border-t border-line flex flex-wrap items-center justify-between gap-4 text-[11px]">
            <span>
              SENSORS: NASA POWER · GPM IMERG · SMAP L4 · GRACE-FO · NASADEM · FIRMS · HLS 30M · ISRIC SOILGRIDS
            </span>
            <Link
              href="/methodology"
              onClick={(e) => navigateWithTransition(e, "/methodology")}
              className="text-cyan-600 dark:text-cyan-300 hover:underline flex items-center gap-1 font-semibold"
            >
              <span>Scientific Methodology, Equations &amp; DOIs</span>
              <ExternalLink className="w-3 h-3" />
            </Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
