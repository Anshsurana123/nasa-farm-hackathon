"use client";

// Minimal i18n: JSON dictionaries + React context. Keys missing in a language fall back to English.
// To add a language: create <code>.json with the same keys and register it in DICTS.
// Punjabi strings are a first draft: get them reviewed by a native speaker (TASK-F07).

import { createContext, useContext, useState, type ReactNode } from "react";
import en from "./en.json";
import pa from "./pa.json";

type Dict = Record<string, string>;
export const DICTS: Record<string, { label: string; dict: Dict }> = {
  en: { label: "English", dict: en },
  pa: { label: "ਪੰਜਾਬੀ", dict: pa },
  // hi: { label: "हिन्दी", dict: hi },  TODO(TASK-X02)
};

type Ctx = { lang: string; setLang: (l: string) => void; t: (key: string) => string };
const I18nContext = createContext<Ctx | null>(null);

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLang] = useState("en");
  const t = (key: string) => DICTS[lang]?.dict[key] ?? (en as Dict)[key] ?? key;
  return <I18nContext.Provider value={{ lang, setLang, t }}>{children}</I18nContext.Provider>;
}

export function useI18n(): Ctx {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error("useI18n must be used inside <I18nProvider>");
  return ctx;
}
