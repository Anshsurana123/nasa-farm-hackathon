"""Global Agro-Climatic Region Registry & Validation Policy. (TASK-D01, PS Requirement 8)

Enforces scope honesty: the biophysical engine (FAO-56, Saxton-Rawls, RothC) is globally
applicable via NASA Earth observations, but agronomic crop calendars, MSP procurement
economics, and CACP A2+FL cost structures are calibrated and validated strictly for India.

Fields outside calibrated Indian agro-climatic zones must be transparently labeled
with validation_status="unvalidated_global", carrying an explicit disclaimer banner
rather than silently masquerading as Punjab conditions (Rule 8).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class RegionConfig:
    region_id: str
    name: str
    country: str
    currency: str
    currency_symbol: str
    is_validated: bool
    validation_status: Literal["validated_india", "unvalidated_global"]
    validation_message: str | None
    allow_economic_ranking: bool
    agro_zone: str
    hemisphere: Literal["NH", "SH"]
    economics_table: str | None = None
    state: str | None = None


# India national boundary polygon approximate envelope (lat 6.5 to 37.5 N, lon 68.0 to 97.5 E)
def is_in_india(lat: float, lon: float) -> bool:
    """Return True if coordinates fall within the sovereign territory/economic envelope of India."""
    return 6.5 <= lat <= 37.5 and 68.0 <= lon <= 97.5


def detect_region_config(lat: float, lon: float) -> RegionConfig:
    """Classify coordinates into calibrated Indian agro-climatic zones or transparent global fallbacks."""
    hemisphere: Literal["NH", "SH"] = "NH" if lat >= 0.0 else "SH"

    if not is_in_india(lat, lon):
        return RegionConfig(
            region_id="unvalidated_global",
            name="Global Climatology Region",
            country="International",
            currency="USD",
            currency_symbol="$",
            is_validated=False,
            validation_status="unvalidated_global",
            validation_message=(
                "This field is located outside TerraLoop's calibrated Indian agro-climatic zones. "
                "Biophysical soil-water models are simulated using global NASA Earth observations, "
                "but regional crop calendars and CACP MSP economic data are unvalidated for this region."
            ),
            allow_economic_ranking=False,
            agro_zone="International Global Climatology (Unvalidated)",
            hemisphere=hemisphere,
            economics_table=None,
        )

    # Coordinates are within India: determine agro-climatic zone & administrative state
    # 1. Trans-Gangetic Semi-Arid Belt (Bathinda / Mansa / Fazilka, SW Punjab)
    if (29.2 <= lat <= 30.6) and (73.5 <= lon < 75.3):
        zone = "Trans-Gangetic Semi-Arid Belt (South-West Punjab / Haryana)"
        reg_id = "punjab_southwest"
        state = "Punjab"
    # 2. Trans-Gangetic Plains Alluvial Rice-Wheat Belt (Sangrur / Ludhiana / Karnal)
    elif (29.2 <= lat <= 32.5) and (73.5 <= lon <= 77.2):
        zone = "Trans-Gangetic Plains (Alluvial Rice–Wheat Belt)"
        if lat < 30.0 and lon >= 75.8:
            reg_id = "haryana"
            state = "Haryana"
        else:
            reg_id = "punjab_central"
            state = "Punjab"
    # 3. Western Himalayan Region
    elif (lat > 32.5 and 72.0 <= lon <= 81.5) or (29.5 <= lat <= 32.5 and 77.5 < lon <= 81.5):
        zone = "Western Himalayan Region (Hill & Sub-Montane Zone)"
        reg_id = "himalayan"
        state = "Himachal Pradesh"
    # 4. Thar Arid & Marwar Belt (Rajasthan)
    elif (24.0 <= lat < 29.2) and (69.0 <= lon < 76.5):
        zone = "Western Dry Region (Thar Arid & Marwar Belt, Rajasthan)"
        reg_id = "rajasthan_arid"
        state = "Rajasthan"
    # 5. Gujarat Plains & Hills
    elif (20.0 <= lat < 24.5) and (68.0 <= lon < 74.5):
        zone = "Gujarat Plains & Hills (Semi-Arid Cotton–Groundnut Zone)"
        reg_id = "gujarat"
        state = "Gujarat"
    # 6. Central Plateau - Bundelkhand (Jhansi, Lalitpur, Banda, Mahoba)
    elif (23.5 <= lat < 26.5) and (77.5 <= lon <= 81.5):
        zone = "Central Plateau & Hills (Bundelkhand Semi-Arid Zone)"
        reg_id = "bundelkhand"
        state = "Uttar Pradesh"
    # 7. Central Plateau - Malwa / Vindhyan
    elif (21.0 <= lat < 26.5) and (74.5 <= lon < 78.5):
        zone = "Central Plateau & Hills (Malwa / Vindhyan Soybean–Wheat Zone)"
        reg_id = "malwa"
        state = "Madhya Pradesh"
    # 8. Western / Central Deccan Plateau (Vidarbha Black Cotton Vertisol Belt: Yavatmal, Akola, Wardha)
    elif (17.5 <= lat < 22.5) and (75.5 <= lon <= 80.5):
        zone = "Western / Central Deccan Plateau (Vidarbha Black Cotton Vertisol Belt)"
        reg_id = "vidarbha"
        state = "Maharashtra"
    # 9. East Coast Plains & Deltas (Cauvery Delta: Thanjavur, Tiruvarur, Nagapattinam)
    elif (lat < 14.0) and (lon >= 78.5):
        zone = "East Coast Plains & Deltas (Cauvery / Coastal Alluvial Zone)"
        reg_id = "cauvery"
        state = "Tamil Nadu"
    # 10. Southern Plateau & Hills
    elif (lat < 17.5) and (lon < 78.5):
        zone = "Southern Plateau & Hills (Peninsular Semi-Arid Zone)"
        reg_id = "southern_hills"
        state = "Karnataka"
    # 11. Eastern Plains & Delta (Lower Gangetic)
    elif lon > 83.0 and lat >= 20.0:
        zone = "Eastern Plateau, Lower Gangetic & Brahmaputra Monsoon Zone"
        reg_id = "eastern_gangetic"
        state = "West Bengal"
    else:
        zone = "Indian Subtropical Agro-Climatic Zone"
        reg_id = "india_general"
        state = "India"

    return RegionConfig(
        region_id=reg_id,
        name=zone,
        country="India",
        currency="INR",
        currency_symbol="₹",
        is_validated=True,
        validation_status="validated_india",
        validation_message=None,
        allow_economic_ranking=True,
        agro_zone=zone,
        hemisphere="NH",
        economics_table="punjab",  # CACP national MSP reference table
        state=state,
    )
