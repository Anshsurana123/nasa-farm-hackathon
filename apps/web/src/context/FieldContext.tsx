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
  StrategyRecommendation,
} from "@/types/api";
import { api } from "@/lib/api";
import { getFallbackStrategies } from "@/lib/fallbackStrategies";
import { isSouthAsia } from "@/lib/ui";

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
  loading: boolean;
  optimizing: boolean;
  error: string | null;
  selectGolden: (field: GoldenField) => void;
  selectLocation: (point: SelectedParcel) => void;
  setPriorities: (p: Priorities) => void;
  setConstraints: (c: FarmConstraints) => void;
  setSelectedRank: (rank: number) => void;
  setStrategies: (s: StrategyRecommendation[]) => void;
  runOptimization: (overrideP?: Priorities, overrideC?: FarmConstraints) => Promise<void>;
}

const DEFAULT_PARCEL: SelectedParcel = {
  lat: 30.2,
  lon: 75.92,
  name: "Sangrur, Punjab (hero field)",
};

const DEFAULT_PRIORITIES: Priorities = {
  profit: 1.0,
  water_savings: 1.5,
  soil_health: 1.2,
  low_risk: 1.0,
  low_labour: 0.0,
  food_security: 0.0,
};

const DEFAULT_CONSTRAINTS: FarmConstraints = {
  area_ha: 2.0,
  irrigation: "limited",
  irrigation_cap_mm: undefined,
  must_grow: [],
  exclude: [],
  has_livestock: false,
  rotation_years: 1,
};

const FieldContext = createContext<FieldContextValue | null>(null);

export function FieldProvider({ children }: { children: ReactNode }) {
  const [goldenFields, setGoldenFields] = useState<GoldenField[]>([]);
  const [selectedField, setSelectedField] = useState<SelectedParcel>(DEFAULT_PARCEL);
  const [selectedGoldenId, setSelectedGoldenId] = useState<string | null>("sangrur");
  const [profile, setProfile] = useState<FieldProfile | null>(null);
  const [strategies, setStrategies] = useState<StrategyRecommendation[]>([]);
  const [crops, setCrops] = useState<CropSpec[]>([]);
  const [priorities, setPrioritiesState] = useState<Priorities>(DEFAULT_PRIORITIES);
  const [constraints, setConstraintsState] = useState<FarmConstraints>(DEFAULT_CONSTRAINTS);
  const [selectedRank, setSelectedRankState] = useState<number>(1);
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

      if (savedParcel) {
        const parsed = JSON.parse(savedParcel) as SelectedParcel;
        if (typeof parsed.lat === "number" && typeof parsed.lon === "number") {
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
      if (savedRank) {
        setSelectedRankState(Number(savedRank) || 1);
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
        if (!localStorage.getItem("tl_selected_field")) {
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

  // Fetch profile + initial recommendations whenever selectedField changes
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
        }
      })
      .catch((err) => {
        if (!isCancelled) {
          setError(err.message ?? "Failed to load field profile");
          setLoading(false);
        }
      });

    const sym = isSouthAsia(selectedField.lat, selectedField.lon) ? "₹" : "$";
    setOptimizing(true);
    api
      .recommend({
        field: { lat: selectedField.lat, lon: selectedField.lon, name: selectedField.name },
        priorities,
        constraints,
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
              sym
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
  }, [selectedField.lat, selectedField.lon, selectedGoldenId]);

  const selectGolden = useCallback((field: GoldenField) => {
    const next = { lat: field.lat, lon: field.lon, name: field.name };
    setSelectedGoldenId(field.id);
    setSelectedField(next);
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

  const runOptimization = useCallback(
    async (overrideP?: Priorities, overrideC?: FarmConstraints) => {
      const pToUse = overrideP ?? priorities;
      const cToUse = overrideC ?? constraints;
      const sym = profile?.currency_symbol ?? (isSouthAsia(selectedField.lat, selectedField.lon) ? "₹" : "$");
      setOptimizing(true);
      try {
        const recs = await api.recommend({
          field: { lat: selectedField.lat, lon: selectedField.lon, name: selectedField.name },
          priorities: pToUse,
          constraints: cToUse,
        });
        if (recs && recs.length > 0) {
          setStrategies(recs);
        }
      } catch {
        setStrategies(
          getFallbackStrategies(
            { lat: selectedField.lat, lon: selectedField.lon, name: selectedField.name },
            sym
          )
        );
      } finally {
        setOptimizing(false);
      }
    },
    [selectedField, priorities, constraints, profile]
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
        loading,
        optimizing,
        error,
        selectGolden,
        selectLocation,
        setPriorities,
        setConstraints,
        setSelectedRank,
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
