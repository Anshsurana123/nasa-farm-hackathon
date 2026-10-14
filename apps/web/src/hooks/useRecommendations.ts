"use client";

// Shared recommendation state for all workspace steps (rotations, trade-offs, stress test, brief).
// Previously each tab mounted its own RotationExplorer, which re-fetched and reset priorities on
// every tab switch. Lifting it here keeps one source of truth.

import { useCallback, useEffect, useRef, useState } from "react";
import type { FarmConstraints, FieldGeometry, Priorities, StrategyRecommendation } from "@/types/api";
import { api } from "@/lib/api";
import { getFallbackStrategies } from "@/lib/fallbackStrategies";

export const DEFAULT_PRIORITIES: Priorities = {
  profit: 1.0,
  water_savings: 1.5,
  soil_health: 1.2,
  low_risk: 1.0,
  low_labour: 0.0,
  food_security: 0.0,
};

export const PRIORITY_PRESETS: Record<string, Partial<Priorities>> = {
  balanced: { profit: 1.5, water_savings: 1.5, soil_health: 1.5, low_risk: 1.5 },
  water: { profit: 0.5, water_savings: 3, soil_health: 1, low_risk: 1 },
  profit: { profit: 3, water_savings: 0.5, soil_health: 0.5, low_risk: 1 },
  soil: { profit: 0.5, water_savings: 1, soil_health: 3, low_risk: 1 },
  risk: { profit: 1, water_savings: 1, soil_health: 1, low_risk: 3 },
};

export const DEFAULT_CONSTRAINTS: FarmConstraints = {
  area_ha: 2.0,
  irrigation: "limited",
  irrigation_cap_mm: undefined,
  must_grow: [],
  exclude: [],
  has_livestock: false,
  rotation_years: 1,
};

export function useRecommendations(field: FieldGeometry | null, currencySymbol: string) {
  const [priorities, setPriorities] = useState<Priorities>(DEFAULT_PRIORITIES);
  const [constraints, setConstraints] = useState<FarmConstraints>(DEFAULT_CONSTRAINTS);
  const [strategies, setStrategies] = useState<StrategyRecommendation[]>([]);
  const [loading, setLoading] = useState(false);
  const [isFallback, setIsFallback] = useState(false);
  const [dirty, setDirty] = useState(false);
  const reqId = useRef(0);

  const run = useCallback(
    async (p: Priorities = priorities, c: FarmConstraints = constraints) => {
      if (!field) return;
      const id = ++reqId.current;
      setLoading(true);
      try {
        const recs = await api.recommend({ field, priorities: p, constraints: c });
        if (id !== reqId.current) return;
        if (recs && recs.length > 0) {
          setStrategies(recs);
          setIsFallback(false);
        }
      } catch (err) {
        if (id !== reqId.current) return;
        console.warn("Backend /recommend failed, falling back to illustrative strategies", err);
        setStrategies(getFallbackStrategies(field, currencySymbol));
        setIsFallback(true);
      } finally {
        if (id === reqId.current) {
          setLoading(false);
          setDirty(false);
        }
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [field?.lat, field?.lon, field?.name, priorities, constraints, currencySymbol],
  );

  // Auto-run when the field changes.
  useEffect(() => {
    if (field) run();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [field?.lat, field?.lon]);

  const updatePriorities = (p: Priorities) => {
    setPriorities(p);
    setDirty(true);
  };
  const updateConstraints = (c: FarmConstraints) => {
    setConstraints(c);
    setDirty(true);
  };
  const applyPreset = (key: string) => {
    const next = { ...priorities, ...PRIORITY_PRESETS[key] };
    setPriorities(next);
    run(next, constraints);
  };

  return {
    priorities,
    constraints,
    strategies,
    loading,
    isFallback,
    dirty,
    run: () => run(),
    updatePriorities,
    updateConstraints,
    applyPreset,
  };
}

export type RecommendationsState = ReturnType<typeof useRecommendations>;
