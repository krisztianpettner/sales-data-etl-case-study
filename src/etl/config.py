"""
ETL Configuration — file paths, column mappings, status normalization, country rules.

FILE_CONFIG is the central registry. Each key (e.g. "TG1_2024") defines
everything needed to import that file: Excel path, sheet name, start row,
column mapping, and optional partner/contact sheet config.
"""
from pathlib import Path

# ── Project root ──────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ── Output database ──────────────────────────────────────────────────────────
DB_PATH = PROJECT_ROOT / "etl" / "dashboard.db"

# ── Admin database (persistent, survives ETL rebuilds) ──────────────────────
ADMIN_DB_PATH = PROJECT_ROOT / "admin" / "admin.db"

# ── SQL views & JSON data output ────────────────────────────────────────────
SQL_DIR = PROJECT_ROOT / "sql" / "views"
DATA_DIR = PROJECT_ROOT / "data"


# ══════════════════════════════════════════════════════════════════════════════
#  Column mappings — reusable building blocks
# ══════════════════════════════════════════════════════════════════════════════

# TG1 quotes: 2022 and earlier (different layout, bitmask status, no revision)
_TG1_COLS_2022 = {
    "quote_id": 3,           # first field — used by stop_on_empty detection
    "partner_name": 4,
    "country_domestic": 1,   # M=Magyar(domestic), W=Western(foreign)
    "industry": 2,           # single-letter industry codes
    "subject": 5,
    "handler_name": 6,
    "handler_phone": 7,
    "handler_email": 8,
    "request_date": 9,
    "deadline_date": 11,
    "registry_number": 21,
    "sent_date": 22,
    "total_value_eur": 24,
    "_status_won": 25,
    "_status_rejected": 26,
    "_status_postponed": 27,
    "_status_lost": 28,
    "_status_open": 29,
}

# TG1 quotes: 2023 (no revision, no country/industry/partner-type)
_TG1_COLS_2023 = {
    "quote_id": 2,
    "partner_name": 3,
    "subject": 4,
    "handler_name": 5,
    "handler_phone": 6,
    "handler_email": 7,
    "request_date": 8,
    "deadline_date": 9,
    "days_remaining": 10,
    "sent_date": 11,
    "status": 12,
    "registry_number": 13,
    "total_value_eur": 14,
    "work_number": 15,
}

# TG1 quotes: 2024 (has revision col 3, no country/industry/partner-type)
_TG1_COLS_LEGACY = {
    "quote_id": 2,
    "revision": 3,
    "partner_name": 4,
    "subject": 5,
    "handler_name": 6,
    "handler_phone": 7,
    "handler_email": 8,
    "request_date": 9,
    "deadline_date": 10,
    "days_remaining": 11,
    "sent_date": 12,
    "status": 13,
    "registry_number": 14,
    "total_value_eur": 15,
    "work_number": 16,
}

# TG1 quotes: 2025+ (extended with partner/country/industry cols 17-25)
_TG1_COLS_2025 = {
    **_TG1_COLS_LEGACY,
    "new_partner_date": 17,
    "partner_year": 18,
    "partner_month_num": 19,
    "partner_month_name": 20,
    "country_domestic": 21,
    "country_name": 22,
    "partner_type": 23,
    "industry": 24,
    "interest": 25,
}

# TG2 quotes: 2022 (different layout, no status col, feedback col 30, no revision)
_TG2_COLS_2022 = {
    "row_number": 1,
    "quote_id": 2,
    "partner_name": 4,
    "industry": 5,
    "country": 6,
    "handler_name": 7,
    "handler_phone": 8,
    "handler_email": 9,
    "request_date": 10,
    "sent_date": 13,
    "registry_number": 14,
    "line_value_eur": 15,
    "product_type": 18,
    "material": 19,
    "size_param": 20,
    "quantity": 29,
    "_feedback": 30,
}

# TG2 quotes: 2023 (has incoming_ref col 3, SKA col 5, no subject, no revision)
_TG2_COLS_2023 = {
    "row_number": 1,
    "quote_id": 2,
    "partner_name": 4,
    "ska": 5,
    "aszf": 6,
    "country": 7,
    "handler_name": 8,
    "handler_phone": 9,
    "handler_email": 10,
    "request_date": 11,
    "sent_date": 12,
    "status": 13,
    "registry_number": 14,
    "work_number": 15,
    "position": 16,
    "quantity": 17,
    "unit_price_eur": 18,
    "line_value_eur": 19,
    "product_type": 20,
    "material": 21,
    "size_param": 22,
}

# TG2 quotes: 2024 (has SKA col 4, subject col 6, revision col 15)
_TG2_COLS_2024 = {
    "row_number": 1,
    "quote_id": 2,
    "partner_name": 3,
    "ska": 4,
    "aszf": 5,
    "subject": 6,
    "country": 7,
    "handler_name": 8,
    "handler_phone": 9,
    "handler_email": 10,
    "request_date": 11,
    "sent_date": 12,
    "status": 13,
    "registry_number": 14,
    "revision": 15,
    "work_number": 16,
    "position": 17,
    "quantity": 18,
    "unit_price_eur": 19,
    "line_value_eur": 20,
    "product_type": 21,
    "material": 22,
    "size_param": 23,
}

# TG2 quotes: 2025+ (no SKA column)
_TG2_COLS_2025 = {
    "row_number": 1,
    "quote_id": 2,
    "partner_name": 3,
    "aszf": 4,
    "subject": 5,
    "country": 6,
    "handler_name": 7,
    "handler_phone": 8,
    "handler_email": 9,
    "request_date": 10,
    "sent_date": 11,
    "status": 12,
    "registry_number": 13,
    "revision": 14,
    "work_number": 15,
    "position": 16,
    "quantity": 17,
    "unit_price_eur": 18,
    "line_value_eur": 19,
    "product_type": 20,
    "material": 21,
    "size_param": 22,
}

# Partner list column mappings
_TG1_PARTNER_COLS_RICH = {
    "name": 1, "first_contact_date": 2, "tax_id": 3,
    "revenue_2023": 4, "currency": 5, "revenue_2023_eur": 6,
    "country": 7, "address_full": 8, "postal_code": 9,
    "county": 10, "city": 11, "street": 12,
    "partner_type": 13, "teaor_code": 14, "teaor_name": 15,
    "official_name": 16, "short_name": 17, "employee_count": 18,
    "founding_year": 19, "website": 20, "vat_status": 21,
}

_TG1_PARTNER_COLS_SIMPLE = {"name": 1, "ska": 2}

_TG2_PARTNER_COLS_2024 = {"name": 1, "aszf": 2, "ska": 3, "first_contact_date": 4}
_TG2_PARTNER_COLS_2025 = {"name": 1, "aszf": 2, "country": 3, "ska": 4, "first_contact_date": 5}
_TG2_PARTNER_COLS_2026 = {"name": 1, "aszf": 2, "country": 3, "first_contact_date": 4}

# Contact list column mappings
_TG1_CONTACT_COLS = {
    "tax_id": 1, "salutation": 2, "last_name": 3, "first_name": 4,
    "position": 5, "email": 6, "mobile": 7, "domain": 8,
}


# ══════════════════════════════════════════════════════════════════════════════
#  FILE_CONFIG — central registry, one entry per importable file
# ══════════════════════════════════════════════════════════════════════════════

FILE_CONFIG = {
    # 2020–2022 entries removed from the load on 2026-10-12 (user decision): CRM-only years,
    # HUF-looking values inflated the live pipeline. Mappings kept below; re-enable by uncommenting.
    # ── TG1 ────────────────────────────────────────────────────────────────
    # "TG1_2020": {
    #     "file": PROJECT_ROOT / "ajanlatkovetes_TG1_2020.xlsx",
    #     "sheet": ["Elsőfélév", "Másodikfélév"],
    #     "start_row": 4,
    #     "cols": _TG1_COLS_2022,
    #     # No partner sheet — partners extracted from quotes
    # },
    # "TG1_2021": {
    #     "file": PROJECT_ROOT / "ajanlatkovetes_TG1_2021.xlsx",
    #     "sheet": ["Elsőfélév", "Másodikfélév"],
    #     "start_row": 4,
    #     "cols": _TG1_COLS_2022,
    #     # No partner sheet — partners extracted from quotes
    # },
    # "TG1_2022": {
    #     "file": PROJECT_ROOT / "ajanlatkovetes_TG1_2022.xlsx",
    #     "sheet": "Elsőfélév",
    #     "start_row": 4,
    #     "cols": _TG1_COLS_2022,
    #     # No partner sheet in 2022
    # },
    "TG1_2023": {
        "file": PROJECT_ROOT / "ajanlatkovetes_TG1_2023.xlsx",
        "sheet": "Elsőfélév",
        "start_row": 2,
        "cols": _TG1_COLS_2023,
        "partner_sheet": "partnerek (A)",
        "partner_cols": _TG1_PARTNER_COLS_SIMPLE,
        "partner_start": 4,
    },
    "TG1_2024": {
        "file": PROJECT_ROOT / "ajanlatkovetes_TG1_2024.xlsx",
        "sheet": "teljes év",
        "start_row": 2,
        "cols": _TG1_COLS_LEGACY,
        "partner_sheet": "partnerek (A)",
        "partner_cols": _TG1_PARTNER_COLS_SIMPLE,
        "partner_start": 4,
    },
    "TG1_2025": {
        "file": PROJECT_ROOT / "ajanlatkovetes_TG1 2025.xlsx",
        "sheet": "2025",
        "start_row": 3,
        "cols": _TG1_COLS_2025,
        "partner_sheet": "partnerek",
        "partner_cols": _TG1_PARTNER_COLS_RICH,
        "partner_start": 4,
        "contact_sheet": "kontaktok",
        "contact_cols": _TG1_CONTACT_COLS,
        "contact_start": 3,
    },
    "TG1_2026": {
        "file": PROJECT_ROOT / "ajanlatkovetes_TG1 2026.xlsx",
        "sheet": "2026",
        "start_row": 3,
        "cols": _TG1_COLS_2025,
        # No partner/contact sheets in 2026
    },

    # ── TG2 ────────────────────────────────────────────────────────────────
    # "TG2_2022": {
    #     "file": PROJECT_ROOT / "ajanlatkovetes_TG2 2022.xlsx",
    #     "sheet": "2022",
    #     "start_row": 3,
    #     "cols": _TG2_COLS_2022,
    #     # No partner sheet in 2022
    # },
    "TG2_2023": {
        "file": PROJECT_ROOT / "ajanlatkovetes_TG2 2023.xlsx",
        "sheet": "2023",
        "start_row": 3,
        "cols": _TG2_COLS_2023,
        "partner_sheet": "partnerek (A)",
        "partner_cols": _TG2_PARTNER_COLS_2024,
        "partner_start": 4,
    },
    "TG2_2024": {
        "file": PROJECT_ROOT / "ajanlatkovetes_TG2 2024.xlsx",
        "sheet": "2024",
        "start_row": 3,
        "cols": _TG2_COLS_2024,
        "partner_sheet": "partnerek (A)",
        "partner_cols": _TG2_PARTNER_COLS_2024,
        "partner_start": 4,
    },
    "TG2_2025": {
        "file": PROJECT_ROOT / "ajanlatkovetes_TG2 2025.xlsx",
        "sheet": "2025",
        "start_row": 3,
        "cols": _TG2_COLS_2025,
        "partner_sheet": "partnerek",
        "partner_cols": _TG2_PARTNER_COLS_2025,
        "partner_start": 4,
    },
    "TG2_2026": {
        "file": PROJECT_ROOT / "ajanlatkovetes_TG2 2026.xlsx",
        "sheet": "2026",
        "start_row": 3,
        "cols": _TG2_COLS_2025,
        "partner_sheet": "partnerek",
        "partner_cols": _TG2_PARTNER_COLS_2026,
        "partner_start": 4,
    },
}


# ══════════════════════════════════════════════════════════════════════════════
#  File path resolution — fallback to data/ subdirectory
# ══════════════════════════════════════════════════════════════════════════════

def _resolve_file(path):
    """Resolve Excel file path: prefer data/ subdirectory, fall back to root.

    The data/ subfolder holds the real production files.
    The project root may hold mock/test copies — data/ takes priority.
    """
    alt = path.parent / "data" / path.name
    if alt.exists():
        return alt
    if path.exists():
        return path
    return path  # return original (will fail later with clear message)

# Resolve file paths in FILE_CONFIG (supports both root and data/ layouts)
for _key in FILE_CONFIG:
    FILE_CONFIG[_key]["file"] = _resolve_file(FILE_CONFIG[_key]["file"])


# ══════════════════════════════════════════════════════════════════════════════
#  Backward-compatible accessors (used by etl_bridge dynamic registration)
# ══════════════════════════════════════════════════════════════════════════════

def _build_compat():
    """Build EXCEL_FILES, SHEETS, DATA_START_ROW from FILE_CONFIG."""
    excel_files = {}
    sheets = {}
    data_start_row = {}
    for key, cfg in FILE_CONFIG.items():
        excel_files[key] = cfg["file"]
        sheet = cfg["sheet"]
        s = {"quotes": sheet if isinstance(sheet, str) else sheet[0]}
        if "partner_sheet" in cfg:
            s["partners"] = cfg["partner_sheet"]
        if "contact_sheet" in cfg:
            s["contacts"] = cfg["contact_sheet"]
        sheets[key] = s
        data_start_row[key] = cfg["start_row"]
        if "partner_start" in cfg:
            pline = key.split("_")[0]
            year = key.split("_")[1]
            data_start_row[f"{pline}_{year}_partner"] = cfg["partner_start"]
            data_start_row[f"{pline}_partner"] = cfg["partner_start"]
        if "contact_start" in cfg:
            data_start_row["TG1_contact"] = cfg["contact_start"]
    return excel_files, sheets, data_start_row

EXCEL_FILES, SHEETS, DATA_START_ROW = _build_compat()


# ══════════════════════════════════════════════════════════════════════════════
#  Status normalization mapping
# ══════════════════════════════════════════════════════════════════════════════

# raw_status (lowercased, stripped) → (normalized, is_open, is_won, is_lost)
STATUS_MAP = {
    "árajánlatra vár":                          ("PREPARATION",       1, 0, 0),
    "arajanlatra var":                           ("PREPARATION",       1, 0, 0),
    ">kiküldésre vár<":                          ("PREPARATION",       1, 0, 0),
    ">kikulddesre var<":                         ("PREPARATION",       1, 0, 0),
    ">kiküldesre vár<":                          ("PREPARATION",       1, 0, 0),
    ">>>kiküldésre vár<<<":                      ("PREPARATION",       1, 0, 0),
    ">>>kikulddesre var<<<":                      ("PREPARATION",       1, 0, 0),
    "várunk (infó)":                             ("PREPARATION",       1, 0, 0),
    "várunk (info)":                             ("PREPARATION",       1, 0, 0),
    "varunk (info)":                             ("PREPARATION",       1, 0, 0),
    "kiajánlott (élő)":                          ("QUOTED",            1, 0, 0),
    "kiajanlott (elo)":                          ("QUOTED",            1, 0, 0),
    "kiajánlott":                                ("QUOTED",            1, 0, 0),
    "kiajanlott":                                ("QUOTED",            1, 0, 0),
    "vélhetően élő":                             ("QUOTED",            1, 0, 0),
    "velhetoen elo":                             ("QUOTED",            1, 0, 0),
    "megnyertük":                                ("WON",               0, 1, 0),
    "megnyertuk":                                ("WON",               0, 1, 0),
    "megnyertük [reá]":                          ("WON",               0, 1, 0),
    "megnyertuk [rea]":                          ("WON",               0, 1, 0),
    "nem mi nyertük (elveszített)":              ("LOST_COMPETITOR",   0, 0, 1),
    "nem mi nyertuk (elveszitett)":              ("LOST_COMPETITOR",   0, 0, 1),
    "nem mi nyertük":                            ("LOST_COMPETITOR",   0, 0, 1),
    "nem mi nyertuk":                            ("LOST_COMPETITOR",   0, 0, 1),
    "vevő, nem nyerte el":                       ("LOST_CUSTOMER",     0, 0, 1),
    "vevo, nem nyerte el":                       ("LOST_CUSTOMER",     0, 0, 1),
    "vevő nem nyerte el":                        ("LOST_CUSTOMER",     0, 0, 1),
    "vevo nem nyerte el":                        ("LOST_CUSTOMER",     0, 0, 1),
    "vevő, elhalasztotta":                       ("POSTPONED",         0, 0, 0),
    "vevo, elhalasztotta":                        ("POSTPONED",         0, 0, 0),
    "vevő elhalasztotta":                        ("POSTPONED",         0, 0, 0),
    "vevo elhalasztotta":                        ("POSTPONED",         0, 0, 0),
    "visszajelzés nélküli így utólag lezártuk":  ("CLOSED_NO_RESPONSE", 0, 0, 0),
    "visszajelzes nelkuli igy utolag lezartuk":  ("CLOSED_NO_RESPONSE", 0, 0, 0),
    "visszajelzés nélküli, így utólag lezártuk": ("CLOSED_NO_RESPONSE", 0, 0, 0),
    "visszajelzes nelkuli, igy utolag lezartuk": ("CLOSED_NO_RESPONSE", 0, 0, 0),
    "nem készült árajánlat":                     ("NO_QUOTE",          0, 0, 0),
    "nem keszult arajanlat":                     ("NO_QUOTE",          0, 0, 0),
    "nem ide való":                              ("NOT_RELEVANT",      0, 0, 0),
    "nem ide valo":                              ("NOT_RELEVANT",      0, 0, 0),
    "[rendelés tételsora]":                      ("ORDER_LINE",        0, 0, 0),
    "[rendeles tetelsora]":                      ("ORDER_LINE",        0, 0, 0),
}

# ── Invalid / missing value markers ──────────────────────────────────────────
MISSING_MARKERS = {"-", "#N/A", "#REF!", "Hiányzik, add meg!", "hiányzik, add meg!",
                   "Hianyzik, add meg!", "nincs cim", "", None}

# ── Company suffix patterns to strip for name normalization ───────────────────
COMPANY_SUFFIXES = [
    r"\bkft\.?$", r"\bbt\.?$", r"\bzrt\.?$", r"\bnyrt\.?$", r"\brt\.?$",
    r"\bgmbh$", r"\bag$", r"\bs\.?r\.?l\.?$", r"\bsrl$", r"\bltd\.?$",
    r"\bllc$", r"\binc\.?$", r"\bcorp\.?$", r"\bsa$", r"\bsas$",
    r"\bsp\.?\s*z\.?\s*o\.?\s*o\.?$", r"\bb\.?v\.?$", r"\bn\.?v\.?$",
    r"\bse$", r"\bkg$", r"\bco\.?$", r"\bplc$", r"\bkg$",
    r"\boyj$", r"\bas$", r"\bab$", r"\baps$", r"\bgesmbh$",
    r"\bkga$", r"\bohg$",
    r"\bspol\.?\s*s\s*r\.?\s*o\.?$",
]


# ══════════════════════════════════════════════════════════════════════════════
#  Country → ISO code → Region mapping
# ══════════════════════════════════════════════════════════════════════════════

# Hungarian country name → ISO 3166-1 alpha-2 code
COUNTRY_NAME_MAP = {
    "Magyarország": "HU",
    "Németország": "DE",
    "Ausztria": "AT",
    "Svájc": "CH",
    "Csehország": "CZ",
    "Szlovákia": "SK",
    "Szlovénia": "SI",
    "Horvátország": "HR",
    "Lengyelország": "PL",
    "Románia": "RO",
    "Bulgária": "BG",
    "Szerbia": "RS",
    "Olaszország": "IT",
    "Franciaország": "FR",
    "Spanyolország": "ES",
    "Portugália": "PT",
    "Hollandia": "NL",
    "Belgium": "BE",
    "Dánia": "DK",
    "Svédország": "SE",
    "Norvégia": "NO",
    "Finnország": "FI",
    "Görögország": "GR",
    "Törökország": "TR",
    "Oroszország": "RU",
    "Írország": "IE",
    "Liechtenstein": "LI",
    "Izrael": "IL",
    "Kína": "CN",
    "Dél-Korea": "KR",
    "Egyiptom": "EG",
    "Tunézia": "TN",
    "Amerikai Egyesült Államok": "US",
    # Edge cases found in DB
    "Anglia": "GB",
    "Lengyel": "PL",
    "Jordan": "JO",
    "Jordánia": "JO",
    "Cseh Köztársaság": "CZ",
    "Slovénia": "SI",
    "Bosna i Hercegovina": "BA",
    "Bosznia-Hercegovina": "BA",
    "Spanyolország": "ES",
    "Ukrajna": "UA",
}

# Region groups: ISO code → region name
REGION_GROUPS = {
    "Nyugat-Európa": {"DE", "AT", "IT", "FR", "CH", "ES", "PT", "AD", "MC",
                       "BE", "NL", "LU", "IE", "GB", "LI", "SM", "VA"},
    "Észak-Európa": {"DK", "SE", "NO", "FI", "IS", "EE", "LV", "LT"},
    "Közép-Kelet-Európa": {"PL", "CZ", "SK", "HU", "SI", "HR"},
    "Balkán/Délkelet": {"RO", "BG", "RS", "BA", "ME", "XK", "AL", "MK", "GR", "TR"},
    "Kelet-Európa": {"UA", "BY", "MD", "RU"},
}

# German-speaking target countries
GERMAN_SPEAKING = {"DE", "AT", "CH"}

# EU 27 member states
EU_MEMBERS = {
    "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR",
    "HU", "IE", "IT", "LV", "LT", "LU", "MT", "NL", "PL", "PT", "RO", "SK",
    "SI", "ES", "SE",
}


def get_country_code(country_hu):
    """Hungarian country name → ISO 3166-1 alpha-2 code, or None."""
    if not country_hu:
        return None
    return COUNTRY_NAME_MAP.get(country_hu.strip())


def get_country_region(country_hu):
    """Hungarian country name → region string."""
    code = get_country_code(country_hu)
    if not code:
        return "Ismeretlen"
    if code == "HU":
        return "Magyarország"
    for region, codes in REGION_GROUPS.items():
        if code in codes:
            return region
    return "Egyéb"


def is_eu(country_hu):
    """Return True if country is an EU member state."""
    code = get_country_code(country_hu)
    return code in EU_MEMBERS if code else False


def is_german_speaking(country_hu):
    """Return True if country is DE/AT/CH."""
    code = get_country_code(country_hu)
    return code in GERMAN_SPEAKING if code else False
