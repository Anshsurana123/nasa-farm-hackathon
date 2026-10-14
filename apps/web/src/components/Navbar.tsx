"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useI18n, DICTS } from "@/i18n";
import type { GoldenField } from "@/types/api";
import { regionFlag } from "@/lib/ui";
import { Globe, Moon, Sun, Sparkles, BookOpen, Satellite } from "lucide-react";

interface NavbarProps {
  goldenFields: GoldenField[];
  selectedId: string | null;
  onSelectGolden: (field: GoldenField) => void;
}

export function Navbar({ goldenFields, selectedId, onSelectGolden }: NavbarProps) {
  const { lang, setLang, t } = useI18n();
  const [isDark, setIsDark] = useState<boolean>(true);

  // Initialize theme on mount
  useEffect(() => {
    const saved = localStorage.getItem("theme");
    const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    const shouldBeDark = saved ? saved === "dark" : prefersDark;
    setIsDark(shouldBeDark);
    if (shouldBeDark) {
      document.documentElement.classList.add("dark");
    } else {
      document.documentElement.classList.remove("dark");
    }
  }, []);

  const toggleTheme = () => {
    const nextDark = !isDark;
    setIsDark(nextDark);
    localStorage.setItem("theme", nextDark ? "dark" : "light");
    if (nextDark) {
      document.documentElement.classList.add("dark");
    } else {
      document.documentElement.classList.remove("dark");
    }
  };

  return (
    <header className="sticky top-0 z-50 glass-strong border-b border-line transition-all duration-300">
      {/* Top Accent Line with subtle shimmer */}
      <div className="h-[2px] w-full bg-gradient-to-r from-emerald-500 via-cyan-400 to-indigo-500" />

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between gap-4">
        {/* Brand Section */}
        <Link href="/" className="flex items-center gap-3.5 group">
          <div className="relative">
            {/* Outer animated glow ring */}
            <div className="absolute -inset-1 rounded-2xl bg-gradient-to-tr from-emerald-500 via-teal-400 to-cyan-500 opacity-70 blur-xs group-hover:opacity-100 transition-opacity" />
            <div className="relative w-10 h-10 rounded-xl bg-gradient-to-tr from-emerald-600 via-teal-600 to-cyan-700 flex items-center justify-center text-white font-black text-xl shadow-lg border border-white/20 group-hover:scale-105 transition-transform duration-200">
              <span className="font-display">⟳</span>
            </div>
            {/* Pulsing satellite indicator dot */}
            <span className="absolute -top-0.5 -right-0.5 flex h-3 w-3">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
              <span className="relative inline-flex rounded-full h-3 w-3 bg-emerald-500 border-2 border-background" />
            </span>
          </div>

          <div>
            <div className="flex items-center gap-2">
              <span className="font-display font-extrabold text-xl tracking-tight text-foreground flex items-center gap-1.5">
                Terra<span className="text-emerald-500 dark:text-emerald-400">Loop</span>
              </span>
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20 shadow-2xs">
                <Satellite className="w-2.5 h-2.5" />
                NASA Space Apps
              </span>
            </div>
            <p className="text-[11px] text-muted hidden sm:block tracking-tight">
              {t("app.tagline")}
            </p>
          </div>
        </Link>

        {/* Right Action Tools */}
        <div className="flex items-center gap-2 sm:gap-3">
          {/* Methodology Link */}
          <Link
            href="/methodology"
            className="px-3 py-1.5 rounded-xl text-xs font-medium text-foreground/80 hover:text-foreground hover:bg-foreground/5 border border-transparent hover:border-line transition-all duration-200 hidden md:inline-flex items-center gap-1.5"
          >
            <BookOpen className="w-3.5 h-3.5 text-emerald-500" />
            <span>Methodology</span>
          </Link>

          {/* Theme Toggle Button */}
          <button
            type="button"
            onClick={toggleTheme}
            aria-label="Toggle dark/light theme"
            className="p-2 rounded-xl text-xs font-medium border border-line bg-surface hover:bg-foreground/5 text-foreground/80 hover:text-foreground transition-all duration-200 cursor-pointer shadow-2xs flex items-center justify-center"
            title={isDark ? "Switch to Light Mode" : "Switch to Dark Mode"}
          >
            {isDark ? (
              <Sun className="w-4 h-4 text-amber-400 transition-transform hover:rotate-45" />
            ) : (
              <Moon className="w-4 h-4 text-indigo-500 transition-transform hover:-rotate-12" />
            )}
          </button>

          {/* Language Switcher */}
          <div className="flex items-center rounded-xl border border-line p-0.5 bg-surface text-xs shadow-2xs">
            <span className="px-2 text-muted hidden lg:inline-flex">
              <Globe className="w-3.5 h-3.5" />
            </span>
            {Object.entries(DICTS).map(([code, meta]) => (
              <button
                key={code}
                onClick={() => setLang(code)}
                className={`px-2.5 py-1 rounded-lg font-medium transition-all duration-200 cursor-pointer ${
                  lang === code
                    ? "bg-emerald-600 text-white shadow-xs font-semibold"
                    : "text-muted hover:text-foreground"
                }`}
              >
                {meta.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Demo Benchmark Fields Navigation Strip */}
      <div className="bg-surface/60 border-t border-line px-4 sm:px-6 lg:px-8 py-2 overflow-x-auto scrollbar-none">
        <div className="max-w-7xl mx-auto flex items-center gap-2 text-xs">
          <span className="text-muted font-bold shrink-0 flex items-center gap-1.5 uppercase text-[10px] tracking-wider pr-1">
            <Sparkles className="w-3 h-3 text-amber-400" /> {t("nav.demoFields")}:
          </span>
          <div className="flex items-center gap-2 shrink-0">
            {goldenFields.map((gf) => {
              const isSelected = selectedId === gf.id;
              const flag = regionFlag(gf.id);
              const isHero = gf.id === "sangrur";

              return (
                <button
                  key={gf.id}
                  onClick={() => onSelectGolden(gf)}
                  className={`px-3 py-1 rounded-full text-xs font-medium transition-all duration-200 flex items-center gap-1.5 cursor-pointer whitespace-nowrap ${
                    isSelected
                      ? "bg-gradient-to-r from-emerald-600 to-teal-600 text-white shadow-sm font-semibold ring-2 ring-emerald-500/40 scale-102"
                      : "bg-surface text-foreground/80 border border-line hover:border-emerald-500/40 hover:text-foreground hover:bg-foreground/5"
                  }`}
                >
                  <span className="text-sm">{flag}</span>
                  <span>{gf.name}</span>
                  {isHero && (
                    <span className="px-1.5 py-0.2 rounded-full text-[9px] font-black uppercase tracking-wider bg-amber-400/20 text-amber-500 border border-amber-400/30">
                      Hero
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        </div>
      </div>
    </header>
  );
}
