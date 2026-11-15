"""Phenology & crop-history inference from NDVI time series. (TASK-E01, E02, E03)

Pipeline:
    raw NDVI (gee.ndvi_timeseries or regional HLS phenology)
      -> smooth()            : resample to 5-day, interpolate gaps, Savitzky-Golay
      -> detect_seasons()    : peaks with prominence >= 0.15 NDVI, start/end at 20% amplitude
      -> classify_season()   : rule-based Indian agro-climatic crop group inference
      -> list[InferredSeason]  (terraloop_schemas)

Indian agro-climatic rules of thumb for E02:
    * Kharif peak Aug-Oct, start Jun-Jul           -> rice (high peak >= 0.65) / cotton / maize / sorghum
    * Rabi peak Jan-Mar, start Nov-Dec             -> wheat / chickpea / mustard / rice-fallow urad
    * Zaid peak May, start Apr                     -> summer moong / urad
"""

from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
import pandas as pd
from terraloop_schemas import InferredSeason

from terraloop_engine import region_registry
from terraloop_engine.eo import classifier as clf_mod


def _savgol_smooth(y: np.ndarray, window_length: int = 9) -> np.ndarray:
    """Pure NumPy Savitzky-Golay smoothing (order 2 polynomial) without scipy."""
    if len(y) < window_length:
        return y.copy()

    # Precomputed Savitzky-Golay coefficients for window=9, poly=2
    coeffs = np.array([-21, 14, 39, 54, 59, 54, 39, 14, -21], dtype=float) / 231.0

    pad_width = window_length // 2
    padded = np.pad(y, pad_width, mode="edge")
    smoothed = np.convolve(padded, coeffs, mode="valid")
    return smoothed


def smooth(ndvi: pd.Series) -> pd.Series:
    """TASK-E01: Regularise and smooth an irregular NDVI series.

    Resamples to regular 5-day intervals, linearly interpolates gaps,
    and applies Savitzky-Golay polynomial smoothing.
    """
    if ndvi.empty:
        return pd.Series(dtype=float)

    s = ndvi.copy()
    if not isinstance(s.index, pd.DatetimeIndex):
        s.index = pd.to_datetime(s.index)
    s = s.sort_index()

    resampled = s.resample("5D").max()
    interpolated = resampled.interpolate(method="time").bfill().ffill()

    vals = np.clip(interpolated.to_numpy(dtype=float), -0.2, 1.0)
    smoothed_vals = _savgol_smooth(vals, window_length=9)

    return pd.Series(smoothed_vals, index=interpolated.index)


def detect_seasons(smoothed: pd.Series, prominence_threshold: float = 0.15) -> list[dict[str, Any]]:
    """TASK-E01: Detect growing seasons from smoothed NDVI time series.

    Finds local peaks with prominence >= prominence_threshold,
    and determines season start/end at 20% amplitude above baseline.

    Returns:
        list of dict: [{"start": date, "peak": date, "end": date, "peak_value": float, "amplitude": float}]
    """
    if len(smoothed) < 5:
        return []

    y = smoothed.to_numpy()
    dates = smoothed.index

    # Adaptive peak & prominence threshold for sparse-canopy dryland row crops (e.g. rainfed cotton on dark Vertisols)
    p95 = float(np.percentile(y, 95))
    if p95 < 0.40:
        min_peak_ndvi = max(0.22, float(np.percentile(y, 70)))
        eff_prominence = min(prominence_threshold, max(0.07, 0.38 * float(np.max(y) - np.min(y))))
    else:
        min_peak_ndvi = 0.30
        eff_prominence = prominence_threshold

    peaks: list[int] = []
    for i in range(1, len(y) - 1):
        if y[i] > y[i - 1] and y[i] >= y[i + 1] and y[i] >= min_peak_ndvi:
            peaks.append(i)

    seasons: list[dict[str, Any]] = []

    for p_idx in peaks:
        p_val = float(y[p_idx])

        left_window = max(0, p_idx - 30)
        left_base = float(np.min(y[left_window:p_idx])) if p_idx > left_window else 0.2

        right_window = min(len(y), p_idx + 31)
        right_base = float(np.min(y[p_idx:right_window])) if right_window > p_idx else 0.2

        base_val = max(0.1, min(left_base, right_base))
        prominence = p_val - base_val

        if prominence < eff_prominence:
            continue

        amplitude = prominence
        threshold_20 = base_val + 0.20 * amplitude

        start_idx = p_idx
        for j in range(p_idx, left_window - 1, -1):
            if y[j] <= threshold_20:
                start_idx = j
                break

        end_idx = p_idx
        for j in range(p_idx, right_window):
            if y[j] <= threshold_20:
                end_idx = j
                break

        if seasons and seasons[-1]["peak"] == dates[p_idx].date():
            continue

        seasons.append(
            {
                "start": dates[start_idx].date(),
                "peak": dates[p_idx].date(),
                "end": dates[end_idx].date(),
                "peak_value": round(p_val, 3),
                "amplitude": round(amplitude, 3),
            }
        )

    return seasons


def _cyclic_month_distance(m1: int, m2: int) -> int:
    diff = abs(int(m1) - int(m2)) % 12
    return min(diff, 12 - diff)


def _classify_global_season(
    season: dict[str, Any],
    lat: float,
    lon: float,
    reg: region_registry.RegionConfig,
) -> tuple[int, str, str]:
    """Calendar-slot & WorldCereal priority-crop classification outside India."""
    p_date: date = season["peak"]
    s_date: date = season["start"]
    e_date: date = season["end"]
    p_month = p_date.month
    p_val = float(season.get("peak_value", 0.6))
    dur_days = max(30, (e_date - s_date).days)

    slots = region_registry.get_calendar_slots(lat, lon)
    best_idx = 0
    best_slot: dict[str, Any] = slots[0] if slots else {"season_type": "warm", "optional": False}
    best_dist = 999
    for idx, sl in enumerate(slots):
        h_months = sl.get("typical_harvest_months") or [p_month]
        # Peak canopy NDVI generally precedes harvest by ~1 month
        peak_targets = [((int(hm) - 2) % 12) + 1 for hm in h_months]
        dist = min(_cyclic_month_distance(p_month, pt) for pt in peak_targets)
        # Prefer primary agronomic slots unless duration clearly reflects a brief catch/cover crop
        if sl.get("optional") and dur_days >= 85:
            dist += 2
        if dist < best_dist:
            best_dist = dist
            best_idx = int(sl.get("slot_index", idx))
            best_slot = sl

    prio = list(reg.priority_crops)
    s_type = str(best_slot.get("season_type", "warm"))
    overwinter = bool(best_slot.get("overwintering", False))
    slot_id = str(best_slot.get("slot_id", ""))
    catch_cover_slots = {
        "zaid",
        "summer_navarai",
        "autumn_catch",
        "offseason_cover",
        "autumn_cover",
        "spring_early",
        "dry_relay_forage",
    }

    if best_idx == 2 or slot_id in catch_cover_slots or dur_days < 80:
        for cid in ("rye_winter", "crimson_clover_vetch", "brachiaria_cover", "field_pea", "moong", "common_bean"):
            if cid in prio:
                return best_idx, cid.split("_")[0] if cid != "moong" else "moong", cid
        return best_idx, "pulse_cover", "crimson_clover_vetch"

    if (overwinter and s_type == "cool") or (s_type == "cool" and dur_days >= 165):
        if p_val < 0.56 and ("rapeseed_canola" in prio or "mustard" in prio):
            cid = "rapeseed_canola" if "rapeseed_canola" in prio else "mustard"
            return best_idx, "rapeseed_canola", cid
        for cid in ("wheat_winter", "triticale", "rye_winter", "barley", "wheat"):
            if cid in prio:
                return best_idx, "wheat_winter" if cid == "wheat_winter" else "wheat", cid
        return best_idx, "wheat_winter", "wheat_winter"

    if s_type == "cool":
        if p_val < 0.50:
            for cid in ("rapeseed_canola", "lupin", "field_pea", "faba_bean", "chickpea", "mustard"):
                if cid in prio:
                    return best_idx, "rapeseed_canola" if "rapeseed" in cid else "pulse_cover", cid
        for cid in ("wheat_spring", "barley", "oats", "wheat"):
            if cid in prio:
                return best_idx, "wheat", cid
        return best_idx, "wheat", "wheat_spring"

    # Warm main season
    if p_val >= 0.72 and ("rice_japonica_temperate" in prio or "rice_upland" in prio or "rice_puddled" in prio):
        cid = next(c for c in ("rice_japonica_temperate", "rice_upland", "rice_puddled") if c in prio)
        return best_idx, "rice", cid
    if best_idx == 0 and prio and prio[0] == "soybean":
        return best_idx, "soybean", "soybean"
    if best_idx == 1 and "maize" in prio and prio and prio[0] == "soybean":
        return best_idx, "maize", "maize"
    if "soybean" in prio and (best_idx == 1 or p_val < 0.74 or "maize" not in prio):
        return best_idx, "soybean", "soybean"
    if "cotton" in prio and "maize" not in prio:
        return best_idx, "cotton", "cotton"
    for cid in ("maize", "sorghum", "sunflower", "soybean", "common_bean", "cassava"):
        if cid in prio:
            return best_idx, cid if cid in ("maize", "soybean") else "maize", cid
    return best_idx, "maize", "maize"


def classify_season(season: dict[str, Any], lat: float, lon: float) -> InferredSeason:
    """TASK-E02: Rule-based classification of Indian crop group and season index.

    Rules across Indian agro-climatic zones:
      - Kharif (season_index 0): Peak in Jul-Nov (months 7-11).
        * High NDVI peak (>= 0.65): 'rice' ('rice_puddled')
        * SW Punjab Cotton Belt / Vidarbha Deccan: 'cotton'
        * Bundelkhand Semi-Arid: 'sorghum'
        * Default moderate Kharif peak: 'maize'
      - Rabi (season_index 1): Peak in Dec-Apr (months 12, 1-4).
        * Cauvery Delta: 'urad' (rice-fallow blackgram)
        * Vidarbha Rainfed Vertisol: 'chickpea'
        * Early Jan peak with moderate NDVI (< 0.60): 'mustard'
        * Default irrigated Rabi cereal: 'wheat'
      - Zaid (season_index 2): Peak in May-Jun (months 5-6).
        * Summer pulse: 'moong'
    """
    p_date: date = season["peak"]
    s_date: date = season["start"]
    e_date: date = season["end"]
    p_val: float = season.get("peak_value", 0.6)

    p_month = p_date.month

    reg = region_registry.detect_region_config(lat, lon)
    if reg.validation_status == "validated_india":
        is_sw_punjab = reg.region_id == "punjab_southwest"
        is_vidarbha = reg.region_id == "vidarbha"
        is_bundelkhand = reg.region_id == "bundelkhand"
        is_cauvery_delta = reg.region_id == "cauvery"

        if p_month in (7, 8, 9, 10, 11) or (p_month == 6 and (is_vidarbha or is_bundelkhand)):
            season_index = 0
            if is_cauvery_delta:
                crop_group = "rice"
                crop_id = "rice_puddled"
            elif is_sw_punjab or is_vidarbha:
                crop_group = "cotton"
                crop_id = "cotton"
            elif is_bundelkhand:
                crop_group = "sorghum"
                crop_id = "sorghum"
            elif p_val >= 0.65:
                crop_group = "rice"
                crop_id = "rice_puddled"
            else:
                crop_group = "maize"
                crop_id = "maize"
        elif p_month in (12, 1, 2, 3, 4):
            season_index = 1
            if is_cauvery_delta:
                crop_group = "rice"
                crop_id = "rice_puddled"
            elif is_vidarbha:
                crop_group = "chickpea"
                crop_id = "chickpea"
            elif p_month == 1 and p_val < 0.60 and not is_bundelkhand and not is_sw_punjab:
                crop_group = "mustard"
                crop_id = "mustard"
            else:
                crop_group = "wheat"
                crop_id = "wheat"
        else:
            season_index = 2
            if is_cauvery_delta:
                crop_group = "urad"
                crop_id = "urad"
            else:
                crop_group = "moong"
                crop_id = "moong"
        clf = clf_mod.build_calibrated_phenology_classifier()
    else:
        season_index, crop_group, crop_id = _classify_global_season(season, lat, lon, reg)
        clf = clf_mod.build_global_phenology_classifier()

    amplitude = float(season.get("amplitude", 0.35))
    dur_days = max(30, (e_date - s_date).days)
    feat = np.array(
        [[p_date.timetuple().tm_yday, s_date.timetuple().tm_yday, dur_days, p_val, p_val * dur_days * 0.65]],
        dtype=float,
    )
    ml_pred = clf.predict(feat)[0]
    ml_match = (ml_pred == crop_group) or (ml_pred == "mungbean" and crop_group in ("moong", "urad"))
    base_conf = 0.57 + 0.65 * amplitude + (0.04 if ml_match else 0.0)
    confidence = round(float(np.clip(base_conf, 0.60, 0.96)), 2)

    return InferredSeason(
        year=p_date.year,
        season_index=season_index,
        start=s_date,
        peak=p_date,
        end=e_date,
        crop_group=crop_group,
        crop_id=crop_id,
        confidence=confidence,
    )


def _merge_overwintering_peaks(seasons: list[dict[str, Any]], lat: float, lon: float) -> list[dict[str, Any]]:
    """Collapse bimodal autumn tillering + spring heading peaks for overwintering cereal/rapeseed crops."""
    slots = region_registry.get_calendar_slots(lat, lon)
    overwinter_slots = [s for s in slots if s.get("overwintering")]
    if not overwinter_slots or len(seasons) < 2:
        return seasons
    sow_months = {int(m) for s in overwinter_slots for m in s.get("sowing_months", [])}
    merged: list[dict[str, Any]] = []
    i = 0
    while i < len(seasons):
        cur = seasons[i]
        if i + 1 < len(seasons):
            nxt = seasons[i + 1]
            gap_days = (nxt["peak"] - cur["peak"]).days
            if (
                90 <= gap_days <= 225
                and cur["peak"].month in sow_months
                and cur["peak_value"] < 0.56
                and nxt["peak_value"] >= cur["peak_value"] + 0.14
            ):
                merged.append(
                    {
                        "start": cur["start"],
                        "peak": nxt["peak"],
                        "end": nxt["end"],
                        "peak_value": nxt["peak_value"],
                        "amplitude": max(cur["amplitude"], nxt["amplitude"]),
                    }
                )
                i += 2
                continue
        merged.append(cur)
        i += 1
    return merged


def infer_history(ndvi: pd.Series, lat: float, lon: float) -> list[InferredSeason]:
    """Full pipeline: irregular NDVI -> smoothed -> detected seasons -> classified crop history.

    Orders seasons within each year by (year, season_index) so Kharif (0) precedes Rabi (1) and Zaid (2),
    keeping the highest-confidence peak per (year, season_index) slot.
    """
    if ndvi.empty:
        return []
    smoothed = smooth(ndvi)
    seasons = _merge_overwintering_peaks(detect_seasons(smoothed), lat, lon)
    by_slot: dict[tuple[int, int], InferredSeason] = {}
    for s in seasons:
        inf = classify_season(s, lat, lon)
        key = (inf.year, inf.season_index)
        if key not in by_slot or inf.confidence > by_slot[key].confidence:
            by_slot[key] = inf
    inferred = list(by_slot.values())
    inferred.sort(key=lambda s: (s.year, s.season_index))
    return inferred
