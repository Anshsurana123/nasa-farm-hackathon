"use client";

// Minimal i18n: JSON dictionaries + React context. Keys missing in a language fall back to English.
// To add a language: create <code>.json with the same keys and register it in DICTS.
// Punjabi strings are a first draft: get them reviewed by a native speaker (TASK-F07).

import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import en from "./en.json";
import es from "./es.json";
import fr from "./fr.json";
import hi from "./hi.json";
import pa from "./pa.json";
import pt from "./pt.json";

type Dict = Record<string, string>;
export const DICTS: Record<string, { label: string; short: string; dict: Dict }> = {
  en: { label: "English", short: "EN", dict: en },
  es: { label: "Español", short: "ES", dict: es },
  pt: { label: "Português", short: "PT", dict: pt },
  fr: { label: "Français", short: "FR", dict: fr },
  hi: { label: "हिन्दी", short: "हि", dict: hi },
  pa: { label: "ਪੰਜਾਬੀ", short: "ਪੰ", dict: pa },
};

type Vars = Record<string, string | number>;
type Ctx = { lang: string; setLang: (l: string) => void; t: (key: string, vars?: Vars) => string };
const I18nContext = createContext<Ctx | null>(null);

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<string>("en");

  useEffect(() => {
    try {
      const saved = localStorage.getItem("lang");
      if (saved && DICTS[saved]) setLangState(saved);
    } catch {
      // Ignore storage errors
    }
  }, []);

  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);

  const setLang = useCallback((l: string) => {
    setLangState(l);
    localStorage.setItem("lang", l);
  }, []);

  const t = useCallback(
    (key: string, vars?: Vars) => {
      let s = DICTS[lang]?.dict[key] ?? (en as Dict)[key] ?? key;
      if (vars) for (const [k, v] of Object.entries(vars)) s = s.replaceAll(`{${k}}`, String(v));
      return s;
    },
    [lang],
  );

  return <I18nContext.Provider value={{ lang, setLang, t }}>{children}</I18nContext.Provider>;
}

export function useI18n(): Ctx {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error("useI18n must be used inside <I18nProvider>");
  return ctx;
}
