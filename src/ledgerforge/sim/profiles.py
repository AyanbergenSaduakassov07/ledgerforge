"""Industry scenario profiles: vocabulary and transaction mix only, never accounting semantics."""

from __future__ import annotations

from ledgerforge.contracts.schemas import (
    ACC_EQUIPMENT,
    ACC_INVENTORY,
    ACC_MATERIALS,
    ACC_RENT,
    ACC_SUBCONTRACT,
    ACC_UTILITIES,
)

# (description, expense account, unit price range in major units of a USD-like currency)
CATALOG = {
    "industrial_procurement": [
        ("Centrifugal pump assembly", ACC_EQUIPMENT, (2_000, 18_000)),
        ("Pipeline valve set DN150", ACC_INVENTORY, (300, 2_500)),
        ("Compressor maintenance service", ACC_SUBCONTRACT, (800, 6_000)),
        ("Steel pipe 219x8 mm, tonne", ACC_MATERIALS, (700, 1_400)),
        ("Electrical cable VVG 3x95, km", ACC_MATERIALS, (900, 4_000)),
        ("Transformer substation inspection", ACC_SUBCONTRACT, (500, 3_500)),
        ("Industrial safety equipment kit", ACC_INVENTORY, (100, 900)),
        ("Diesel generator spare parts", ACC_INVENTORY, (200, 2_000)),
    ],
    "construction": [
        ("Concrete M300, m3", ACC_MATERIALS, (60, 120)),
        ("Rebar A500C, tonne", ACC_MATERIALS, (550, 900)),
        ("Earthworks subcontract milestone", ACC_SUBCONTRACT, (5_000, 40_000)),
        ("Formwork rental", ACC_RENT, (400, 3_000)),
        ("Site electrical installation", ACC_SUBCONTRACT, (1_500, 12_000)),
        ("Tower crane rental", ACC_RENT, (3_000, 9_000)),
        ("Facade panels", ACC_MATERIALS, (80, 300)),
    ],
    "manufacturing": [
        ("Aluminium sheet 2 mm, tonne", ACC_MATERIALS, (2_000, 3_200)),
        ("Polymer granules, tonne", ACC_MATERIALS, (1_100, 1_900)),
        ("CNC tooling set", ACC_EQUIPMENT, (1_500, 9_000)),
        ("Packaging materials", ACC_INVENTORY, (50, 600)),
        ("Line calibration service", ACC_SUBCONTRACT, (700, 4_000)),
        ("Industrial lubricants", ACC_INVENTORY, (80, 500)),
        ("Electricity supply", ACC_UTILITIES, (1_000, 6_000)),
    ],
    "retail_services": [
        ("Store fit-out works", ACC_SUBCONTRACT, (2_000, 15_000)),
        ("POS terminal lease", ACC_RENT, (100, 600)),
        ("Merchandise batch", ACC_INVENTORY, (500, 5_000)),
        ("Cleaning services", ACC_SUBCONTRACT, (300, 1_500)),
        ("Logistics and delivery", ACC_SUBCONTRACT, (200, 2_500)),
        ("Utilities", ACC_UTILITIES, (300, 2_000)),
    ],
}

# Monthly recurring services (same amount each month; legitimate near-duplicates).
RECURRING = {
    "industrial_procurement": ("Equipment lease", ACC_RENT),
    "construction": ("Site office rental", ACC_RENT),
    "manufacturing": ("Warehouse rental", ACC_RENT),
    "retail_services": ("Store premises rent", ACC_RENT),
}

VENDOR_WORDS = (
    "Steppe",
    "Altyn",
    "Caspian",
    "Irtysh",
    "Tengri",
    "Saryarka",
    "Baiterek",
    "Kökshe",
    "Ural",
    "Orda",
    "Zhetisu",
    "Turan",
    "Aral",
    "Shygys",
    "Batys",
    "Kazyna",
    "Nomad",
    "Silk",
)
VENDOR_SUFFIX = (
    "Engineering LLP",
    "Trade LLP",
    "Supply JSC",
    "Industrial Group",
    "Logistics LLP",
    "Technologies Ltd",
    "Services LLP",
    "GmbH",
    "Co. Ltd",
)

# Episode timezones: (IANA name for display, fixed UTC offset used for all computations).
TIMEZONES = (
    ("Asia/Almaty", "+05:00"),
    ("Asia/Tashkent", "+05:00"),
    ("Asia/Dubai", "+04:00"),
    ("Europe/Istanbul", "+03:00"),
    ("Asia/Baku", "+04:00"),
)
VENDOR_OFFSETS = ("+05:00", "+03:00", "+01:00", "+00:00", "+08:00", "+04:00", "-05:00")

# Units of base currency per 1 USD (anchors for the synthetic rate walk; fictional values).
USD_ANCHOR = {
    "USD": 1.0,
    "KZT": 505.0,
    "EUR": 0.93,
    "RUB": 96.0,
    "CNY": 7.2,
    "JPY": 151.0,
    "KWD": 0.307,
}

# Line items per invoice grow with difficulty (bigger ledgers); capped by the smallest catalog (6).
MAX_LINE_ITEMS = {"basic": 3, "intermediate": 4, "advanced": 5, "expert": 6}
# Bank-fee filler tops each ledger up to this size (gate maximum is 2000 rows).
TARGET_LEDGER_ROWS = {"basic": 200, "intermediate": 400, "advanced": 800, "expert": 1600}
