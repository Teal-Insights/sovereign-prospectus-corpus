"""Country lookup from storage key patterns."""

from __future__ import annotations

# ISO-3 prefixes found in PDIP storage keys (pdip__ARG1 -> Argentina)
_COUNTRY_FROM_PREFIX: dict[str, str] = {
    "AGO": "Angola",
    "ARG": "Argentina",
    "AUT": "Austria",
    "BHR": "Bahrain",
    "BIH": "Bosnia and Herzegovina",
    "BRA": "Brazil",
    "BRB": "Barbados",
    "CAN": "Canada",
    "CHN": "China",
    "CMR": "Cameroon",
    "COL": "Colombia",
    "CYP": "Cyprus",
    "ECU": "Ecuador",
    "EGY": "Egypt",
    "ETH": "Ethiopia",
    "GHA": "Ghana",
    "GIN": "Guinea",
    "GUY": "Guyana",
    "HUN": "Hungary",
    "IDN": "Indonesia",
    "ISL": "Iceland",
    "ISR": "Israel",
    "ITA": "Italy",
    "JAM": "Jamaica",
    "JOR": "Jordan",
    "JPN": "Japan",
    "KAZ": "Kazakhstan",
    "KEN": "Kenya",
    "KGZ": "Kyrgyzstan",
    "KWT": "Kuwait",
    "LVA": "Latvia",
    "LKA": "Sri Lanka",
    "MAR": "Morocco",
    "MDA": "Moldova",
    "MNE": "Montenegro",
    "NGA": "Nigeria",
    "NLD": "Netherlands",
    "PAN": "Panama",
    "PER": "Peru",
    "PHL": "Philippines",
    "RWA": "Rwanda",
    "SAU": "Saudi Arabia",
    "SEN": "Senegal",
    "SLE": "Sierra Leone",
    "SRB": "Serbia",
    "SWE": "Sweden",
    "TUR": "Turkey",
    "UGA": "Uganda",
    "UZB": "Uzbekistan",
    "VEN": "Venezuela",
    "ZAF": "South Africa",
    "ZMB": "Zambia",
}


def guess_country(storage_key: str) -> str:
    """Best-effort country from storage key prefix."""
    if storage_key.startswith("pdip__"):
        suffix = storage_key[6:]
        for code, country in _COUNTRY_FROM_PREFIX.items():
            if suffix.startswith(code):
                return country
    return ""
