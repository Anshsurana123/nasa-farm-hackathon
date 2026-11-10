"""Human nutritional yield & food security assessment. (TASK-M08, PS Requirement 4)

Calculates metabolizable food energy (Mcal/ha) and dietary protein (kg/ha) produced
per hectare per year from simulated crop rotation grain yields, benchmarked against
ICMR-NIN (2020) Recommended Dietary Allowances (RDA) for Indian households.

Citations:
  - ICMR - National Institute of Nutrition (2020). "Nutritive Value of Indian Foods",
    Hyderabad, India. Tables of Food Composition (Cereals, Pulses, Oilseeds, Tubers).
  - ICMR - NIN Expert Group (2020). "Recommended Dietary Allowances and Estimated Average
    Requirements for Indians", Table 4.1 (Reference Adult Energy: ~2,200 kcal/day, Protein: 50 g/day).
  - FAO (2001). "Food Balance Sheets: A Handbook", Food and Agriculture Organization of the UN, Rome.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

# Nutritional composition per tonne of harvested crop yield (marketed/farmgate form).
# Mcal per tonne (1 Mcal = 1,000 kcal) and kg protein per tonne of harvested yield.
# Values account for edible fraction and standard processing/milling recovery.
CROP_NUTRITIVE_VALUE: dict[str, tuple[float, float]] = {
    # Cereals & millets (ICMR-NIN 2020 Table 1: Cereals and Millets)
    "wheat": (3460.0, 118.0),          # Whole wheat grain: 346 kcal/100g, 11.8% protein
    "rice_puddled": (2310.0, 45.6),    # Rough paddy: 67% milling recovery * (345 kcal/100g, 6.8% protein)
    "rice_short": (2310.0, 45.6),      # Rough paddy (PR-126)
    "rice_dsr": (2310.0, 45.6),        # Direct-seeded rough paddy
    "basmati": (2310.0, 45.6),         # Basmati rough paddy
    "maize": (3420.0, 111.0),          # Maize grain: 342 kcal/100g, 11.1% protein
    "sorghum": (3490.0, 104.0),        # Jowar: 349 kcal/100g, 10.4% protein
    "pearl_millet": (3610.0, 116.0),   # Bajra: 361 kcal/100g, 11.6% protein
    "barley": (3360.0, 115.0),         # Barley grain: 336 kcal/100g, 11.5% protein

    # Pulses & grain legumes (ICMR-NIN 2020 Table 2: Pulses and Legumes)
    "chickpea": (3600.0, 171.0),       # Bengal gram / Chana: 360 kcal/100g, 17.1% protein
    "moong": (3480.0, 240.0),          # Green gram: 348 kcal/100g, 24.0% protein
    "urad": (3470.0, 240.0),           # Black gram: 347 kcal/100g, 24.0% protein
    "pigeon_pea": (3430.0, 223.0),     # Red gram / Arhar / Tur: 343 kcal/100g, 22.3% protein
    "lentil": (3430.0, 251.0),         # Masoor: 343 kcal/100g, 25.1% protein
    "soybean": (4320.0, 432.0),        # Soybean: 432 kcal/100g, 43.2% protein
    "common_bean": (3400.0, 210.0),    # Rajma: 340 kcal/100g, 21.0% protein

    # Oilseeds & roots/tubers (ICMR-NIN 2020 Tables 3 & 4)
    "groundnut": (3970.0, 177.0),      # In-shell pod: ~70% kernel * (567 kcal/100g, 25.3% protein)
    "mustard": (5410.0, 200.0),        # Mustard seed: 541 kcal/100g, 20.0% protein
    "sunflower": (5840.0, 198.0),      # Sunflower seed: 584 kcal/100g, 19.8% protein
    "potato": (770.0, 20.0),           # Fresh tuber (78% moisture): 77 kcal/100g, 2.0% protein

    # Non-food / fodder / green-manure crops (0 direct human food calories/protein)
    "cotton": (0.0, 0.0),              # Non-food fibre crop
    "dhaincha": (0.0, 0.0),            # Green manure crop (soil incorporation)
    "berseem": (0.0, 0.0),             # Livestock fodder (secondary animal product not direct food)
    "fallow": (0.0, 0.0),              # Unplanted fallow
}

# Annual nutritional requirements for an average Indian rural household of 5 members
# (ICMR-NIN 2020 RDA: 2,200 kcal/person/day * 5 * 365 = 4,015 Mcal/yr; 50 g protein/person/day * 5 * 365 = 91.25 kg/yr)
HOUSEHOLD_ANNUAL_ENERGY_MCAL = 4015.0
HOUSEHOLD_ANNUAL_PROTEIN_KG = 91.25


def compute_nutrition_yield(
    crop_yields: Mapping[str, float] | Sequence[tuple[str, float]],
    rotation_years: int = 1,
) -> dict[str, float]:
    """Calculate annual food energy (Mcal/ha), protein (kg/ha), and food security index.

    Args:
        crop_yields: Mapping or sequence of (crop_id, yield_t_ha) across rotation steps.
        rotation_years: Number of calendar years in the multi-year rotation sequence.

    Returns:
        dict containing:
            - annual_energy_mcal_ha: annual metabolizable food energy in Mcal/ha/yr
            - annual_protein_kg_ha: annual dietary protein in kg/ha/yr
            - households_nourished: average households sustained in both energy and protein
            - food_security_score: normalized [0, 1] index
    """
    rot_yrs = max(1, rotation_years)
    total_energy_mcal = 0.0
    total_protein_kg = 0.0

    items = crop_yields.items() if isinstance(crop_yields, Mapping) else crop_yields
    for crop_id, yield_t_ha in items:
        if crop_id == "fallow" or yield_t_ha <= 0.0:
            continue
        mcal_per_t, kg_prot_per_t = CROP_NUTRITIVE_VALUE.get(crop_id, (3000.0, 100.0))
        total_energy_mcal += yield_t_ha * mcal_per_t
        total_protein_kg += yield_t_ha * kg_prot_per_t

    annual_mcal = total_energy_mcal / rot_yrs
    annual_protein = total_protein_kg / rot_yrs

    hh_energy = annual_mcal / HOUSEHOLD_ANNUAL_ENERGY_MCAL
    hh_protein = annual_protein / HOUSEHOLD_ANNUAL_PROTEIN_KG

    # Households nourished simultaneously meeting both caloric and protein thresholds
    # Limiting nutrient dictates true food security (von Liebig's Law of the Minimum)
    households_nourished = round(min(hh_energy, hh_protein), 2)

    # Food security score normalized to [0, 1]: 1.0 represents feeding >= 2.5 rural households/ha
    score = min(1.0, (0.50 * (hh_energy / 2.5) + 0.50 * (hh_protein / 2.5)))

    return {
        "annual_energy_mcal_ha": round(annual_mcal, 1),
        "annual_protein_kg_ha": round(annual_protein, 1),
        "households_nourished": households_nourished,
        "food_security_score": round(max(0.0, score), 3),
    }
