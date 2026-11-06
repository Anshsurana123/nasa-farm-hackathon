"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import type {
  CropSpec,
  FarmConstraints,
  FieldProfile,
  GoldenField,
  Priorities,
  SoilHealthCardInput,
  StrategyRecommendation,
} from "@/types/api";
import { api } from "@/lib/api";
import { getFallbackStrategies } from "@/lib/fallbackStrategies";
import { type UnitSystem } from "@/lib/ui";
import { useI18n } from "@/i18n";

interface SelectedParcel {
  lat: number;
  lon: number;
  name: string;
}

interface FieldContextValue {
  goldenFields: GoldenField[];
  selectedField: SelectedParcel;
  selectedGoldenId: string | null;
  profile: FieldProfile | null;
  strategies: StrategyRecommendation[];
  crops: CropSpec[];
  priorities: Priorities;
  constraints: FarmConstraints;
  selectedRank: number;
  unitSystem: UnitSystem;
  soilHealthCard: SoilHealthCardInput | null;
  baselineOverride: string[] | null;
  loading: boolean;
  optimizing: boolean;
  error: string | null;
  selectGolden: (field: GoldenField) => void;
  selectLocation: (point: SelectedParcel) => void;
  setPriorities: (p: Priorities) => void;
  setConstraints: (c: FarmConstraints) => void;
  setSelectedRank: (rank: number) => void;
  setUnitSystem: (u: UnitSystem) => void;
  setSoilHealthCard: (shc: SoilHealthCardInput | null) => void;
  setBaselineOverride: (b: string[] | null) => void;
  setStrategies: (s: StrategyRecommendation[]) => void;
  runOptimization: (
    overrideP?: Priorities,
    overrideC?: FarmConstraints,
    overrideShc?: SoilHealthCardInput | null,
    overrideBase?: string[] | null
  ) => Promise<void>;
}

const DEFAULT_PARCEL: SelectedParcel = {
  lat: 30.19,
  lon: 75.78,
  name: "Sangrur, Punjab",
};

const DEFAULT_PRIORITIES: Priorities = {
  profit: 1.5,
  water_savings: 2.0,
  soil_health: 1.5,
  low_risk: 1.5,
  low_labour: 1.0,
  food_security: 1.0,
};

const DEFAULT_CONSTRAINTS: FarmConstraints = {
  area_ha: 2.0,
  irrigation: "full",
  irrigation_cap_mm: undefined,
  must_grow: [],
  exclude: [],
  has_livestock: false,
  rotation_years: 1,
};

const FieldContext = createContext<FieldContextValue | null>(null);

export function FieldProvider({ children }: { children: ReactNode }) {
  const { lang } = useI18n();
  const [goldenFields, setGoldenFields] = useState<GoldenField[]>([]);
  const [selectedField, setSelectedField] = useState<SelectedParcel>(DEFAULT_PARCEL);
  const [selectedGoldenId, setSelectedGoldenId] = useState<string | null>("sangrur");
  const [profile, setProfile] = useState<FieldProfile | null>(null);
  const [strategies, setStrategies] = useState<StrategyRecommendation[]>([]);
  const [crops, setCrops] = useState<CropSpec[]>([]);
  const [priorities, setPrioritiesState] = useState<Priorities>(DEFAULT_PRIORITIES);
  const [constraints, setConstraintsState] = useState<FarmConstraints>(DEFAULT_CONSTRAINTS);
  const [selectedRank, setSelectedRankState] = useState<number>(1);
  const [unitSystem, setUnitSystemState] = useState<UnitSystem>("acre");
  const [soilHealthCard, setSoilHealthCardState] = useState<SoilHealthCardInput | null>(null);
  const [baselineOverride, setBaselineOverrideState] = useState<string[] | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [optimizing, setOptimizing] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const hydratedRef = useRef(false);

  // Restore saved parcel & preferences on mount
  useEffect(() => {
    try {
      const savedParcel = localStorage.getItem("tl_selected_field");
      const savedGolden = localStorage.getItem("tl_selected_golden_id");
      const savedPrio = localStorage.getItem("tl_priorities");
      const savedConst = localStorage.getItem("tl_constraints");
      const savedRank = localStorage.getItem("tl_selected_rank");
      const savedUnit = localStorage.getItem("tl_unit_system");

      if (savedParcel) {
        const parsed = JSON.parse(savedParcel) as SelectedParcel;
        if (
          typeof parsed.lat === "number" &&
          typeof parsed.lon === "number" &&
          parsed.lat >= 5 &&
          parsed.lat <= 38.5 &&
          parsed.lon >= 66 &&
          parsed.lon <= 99
        ) {
          setSelectedField(parsed);
        }
      }
      if (savedGolden !== null) {
        setSelectedGoldenId(savedGolden === "" ? null : savedGolden);
      }
      if (savedPrio) {
        setPrioritiesState({ ...DEFAULT_PRIORITIES, ...JSON.parse(savedPrio) });
      }
      if (savedConst) {
        setConstraintsState({ ...DEFAULT_CONSTRAINTS, ...JSON.parse(savedConst) });
      }
      if (savedRank !== null) {
        setSelectedRankState(Number(savedRank));
      }
      if (savedUnit === "acre" || savedUnit === "hectare") {
        setUnitSystemState(savedUnit);
      }
    } catch {
      // Ignore storage errors
    }
    hydratedRef.current = true;
  }, []);

  // Load golden fields & crop catalog once
  useEffect(() => {
    api
      .goldenFields()
      .then((fields) => {
        setGoldenFields(fields);
        const validIds = new Set(fields.map((f) => f.id));
        const savedGolden = localStorage.getItem("tl_selected_golden_id");
        if (!localStorage.getItem("tl_selected_field") || (savedGolden && !validIds.has(savedGolden))) {
          const hero = fields.find((f) => f.id === "sangrur") ?? fields[0];
          if (hero) {
            setSelectedGoldenId(hero.id);
            setSelectedField({ lat: hero.lat, lon: hero.lon, name: hero.name });
          }
        }
      })
      .catch((err) => console.warn("Could not load golden fields list:", err));

    api
      .crops()
      .then((list) => setCrops(list))
      .catch((err) => console.warn("Could not load crops catalog:", err));
  }, []);

  // Fetch profile + recommendations whenever selectedField, lang, soilHealthCard, or baselineOverride changes
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
          if (soilHealthCard) {
            const nextSoil = { ...data.soil };
            if (soilHealthCard.ph !== undefined && soilHealthCard.ph !== null) {
              nextSoil.ph = soilHealthCard.ph;
            }
            if (soilHealthCard.soc_pct !== undefined && soilHealthCard.soc_pct !== null) {
              nextSoil.soc_g_per_kg = Number((soilHealthCard.soc_pct * 10).toFixed(2));
            }
            nextSoil.source = "farmer_test";
            setProfile({ ...data, soil: nextSoil });
          } else {
            setProfile(data);
          }
          setLoading(false);
        }
      })
      .catch((err) => {
        if (!isCancelled) {
          setError(err.message ?? "Failed to load field profile");
          setLoading(false);
        }
      });

    setOptimizing(true);
    api
      .recommend({
        field: { lat: selectedField.lat, lon: selectedField.lon, name: selectedField.name },
        priorities,
        constraints,
        language: (lang as "en" | "pa" | "hi") || "en",
        soil_health_card: soilHealthCard,
        baseline_override: baselineOverride,
      })
      .then((recs) => {
        if (!isCancelled && recs && recs.length > 0) {
          setStrategies(recs);
        }
      })
      .catch(() => {
        if (!isCancelled) {
          setStrategies(
            getFallbackStrategies(
              { lat: selectedField.lat, lon: selectedField.lon, name: selectedField.name },
              "₹"
            )
          );
        }
      })
      .finally(() => {
        if (!isCancelled) setOptimizing(false);
      });

    return () => {
      isCancelled = true;
    };
  }, [selectedField.lat, selectedField.lon, selectedGoldenId, lang, soilHealthCard, baselineOverride]);

  const selectGolden = useCallback((field: GoldenField) => {
    const next = { lat: field.lat, lon: field.lon, name: field.name };
    const defaultIrr: "none" | "limited" | "full" =
      field.id === "vidarbha" || field.id === "bundelkhand"
        ? "none"
        : field.id === "bathinda"
        ? "limited"
        : "full";
    setSelectedGoldenId(field.id);
    setSelectedField(next);
    setBaselineOverrideState(null);
    setConstraintsState((prev) => ({ ...prev, irrigation: defaultIrr }));
    try {
      localStorage.setItem("tl_selected_golden_id", field.id);
      localStorage.setItem("tl_selected_field", JSON.stringify(next));
    } catch {
      // Ignore
    }
  }, []);

  const selectLocation = useCallback((point: SelectedParcel) => {
    setSelectedGoldenId(null);
    setSelectedField(point);
    setBaselineOverrideState(null);
    try {
      localStorage.setItem("tl_selected_golden_id", "");
      localStorage.setItem("tl_selected_field", JSON.stringify(point));
    } catch {
      // Ignore
    }
  }, []);

  const setPriorities = useCallback((p: Priorities) => {
    setPrioritiesState(p);
    try {
      localStorage.setItem("tl_priorities", JSON.stringify(p));
    } catch {
      // Ignore
    }
  }, []);

  const setConstraints = useCallback((c: FarmConstraints) => {
    setConstraintsState(c);
    try {
      localStorage.setItem("tl_constraints", JSON.stringify(c));
    } catch {
      // Ignore
    }
  }, []);

  const setSelectedRank = useCallback((rank: number) => {
    setSelectedRankState(rank);
    try {
      localStorage.setItem("tl_selected_rank", String(rank));
    } catch {
      // Ignore
    }
  }, []);

  const setUnitSystem = useCallback((u: UnitSystem) => {
    setUnitSystemState(u);
    try {
      localStorage.setItem("tl_unit_system", u);
    } catch {
      // Ignore
    }
  }, []);

  const setSoilHealthCard = useCallback((shc: SoilHealthCardInput | null) => {
    setSoilHealthCardState(shc);
  }, []);

  const setBaselineOverride = useCallback((b: string[] | null) => {
    setBaselineOverrideState(b);
  }, []);

  const runOptimization = useCallback(
    async (
      overrideP?: Priorities,
      overrideC?: FarmConstraints,
      overrideShc?: SoilHealthCardInput | null,
      overrideBase?: string[] | null
    ) => {
      const pToUse = overrideP ?? priorities;
      const cToUse = overrideC ?? constraints;
      const shcToUse = overrideShc !== undefined ? overrideShc : soilHealthCard;
      const baseToUse = overrideBase !== undefined ? overrideBase : baselineOverride;
      setOptimizing(true);
      try {
        const recs = await api.recommend({
          field: { lat: selectedField.lat, lon: selectedField.lon, name: selectedField.name },
          priorities: pToUse,
          constraints: cToUse,
          language: (lang as "en" | "pa" | "hi") || "en",
          soil_health_card: shcToUse,
          baseline_override: baseToUse,
        });
        if (recs && recs.length > 0) {
          setStrategies(recs);
        }
      } catch {
        setStrategies(
          getFallbackStrategies(
            { lat: selectedField.lat, lon: selectedField.lon, name: selectedField.name },
            "₹"
          )
        );
      } finally {
        setOptimizing(false);
      }
    },
    [selectedField, priorities, constraints, lang, soilHealthCard, baselineOverride]
  );

  return (
    <FieldContext.Provider
      value={{
        goldenFields,
        selectedField,
        selectedGoldenId,
        profile,
        strategies,
        crops,
        priorities,
        constraints,
        selectedRank,
        unitSystem,
        soilHealthCard,
        baselineOverride,
        loading,
        optimizing,
        error,
        selectGolden,
        selectLocation,
        setPriorities,
        setConstraints,
        setSelectedRank,
        setUnitSystem,
        setSoilHealthCard,
        setBaselineOverride,
        setStrategies,
        runOptimization,
      }}
    >
      {children}
    </FieldContext.Provider>
  );
}

export function useField(): FieldContextValue {
  const ctx = useContext(FieldContext);
  if (!ctx) {
    throw new Error("useField must be used within <FieldProvider>");
  }
  return ctx;
}
