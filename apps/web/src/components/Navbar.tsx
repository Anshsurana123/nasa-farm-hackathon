"use client";

import { useI18n, DICTS } from "@/i18n";
import type { GoldenField } from "@/types/api";

interface NavbarProps {
  goldenFields: GoldenField[];
  selectedId: string | null;
  onSelectGolden: (field: GoldenField) => void;
}

export function Navbar({ goldenFields, selectedId, onSelectGolden }: NavbarProps) {
  const { lang, setLang, t } = useI18n();

  return (
    <header className="sticky top-0 z-40 bg-white/80 dark:bg-zinc-950/80 backdrop-blur-md border-b border-zinc-200 dark:border-zinc-800">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between gap-4">
        {/* Brand */}
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-emerald-600 to-teal-400 flex items-center justify-center text-white font-black text-lg shadow-sm">
            ⟳
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-extrabold text-lg tracking-tight text-zinc-900 dark:text-zinc-50">
                {t("app.title")}
              </span>
              <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-300">
                NASA Space Apps
              </span>
            </div>
            <p className="text-[11px] text-zinc-500 hidden sm:block">
              {t("app.tagline")}
            </p>
          </div>
        </div>

        {/* Golden Field Quick Switcher & Language */}
        <div className="flex items-center gap-3">
          {/* Language Switcher */}
          <div className="flex rounded-lg border border-zinc-200 dark:border-zinc-800 p-0.5 bg-zinc-50 dark:bg-zinc-900 text-xs">
            {Object.entries(DICTS).map(([code, meta]) => (
              <button
                key={code}
                onClick={() => setLang(code)}
                className={`px-2.5 py-1 rounded-md font-medium transition-all ${
                  lang === code
                    ? "bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 shadow-xs"
                    : "text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100"
                }`}
              >
                {meta.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Demo Fields Strip */}
      <div className="bg-zinc-50/80 dark:bg-zinc-900/60 border-t border-zinc-100 dark:border-zinc-800/80 px-4 sm:px-6 lg:px-8 py-2 overflow-x-auto">
        <div className="max-w-7xl mx-auto flex items-center gap-2 text-xs">
          <span className="text-zinc-400 font-medium shrink-0 flex items-center gap-1">
            <span>🎯</span> {t("nav.demoFields")}:
          </span>
          <div className="flex items-center gap-1.5 shrink-0">
            {goldenFields.map((gf) => {
              const isSelected = selectedId === gf.id;
              const isHero = gf.id === "sangrur";
              return (
                <button
                  key={gf.id}
                  onClick={() => onSelectGolden(gf)}
                  className={`px-3 py-1 rounded-full text-xs font-medium transition-all flex items-center gap-1.5 ${
                    isSelected
                      ? "bg-emerald-600 text-white shadow-xs font-semibold"
                      : "bg-white dark:bg-zinc-800/80 text-zinc-700 dark:text-zinc-300 border border-zinc-200/80 dark:border-zinc-700 hover:border-zinc-300"
                  }`}
                >
                  {isHero && <span>⭐</span>}
                  <span>{gf.name}</span>
                </button>
              );
            })}
          </div>
        </div>
      </div>
    </header>
  );
}
