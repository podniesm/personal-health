"""Sprawdza poprawność plików CSV w data/: nagłówki, daty, liczby, duplikaty.

Użycie:  python scripts/validate.py
Kod wyjścia 0 = OK, 1 = znaleziono błędy.
"""
from __future__ import annotations

import csv
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
DATA = ROOT / "data"

# plik -> (nagłówek, kolumny liczbowe, klucz duplikatu)
SCHEMAS: dict[str, tuple[list[str], list[str], list[str]]] = {
    "labs/results.csv": (
        ["date", "test", "value", "unit", "ref_low", "ref_high", "flag", "lab", "source_file", "notes"],
        ["ref_low", "ref_high"],
        ["date", "test", "lab"],
    ),
    "training/activities.csv": (
        ["date", "type", "duration_min", "distance_km", "avg_hr", "max_hr", "elevation_m",
         "calories", "training_load", "rpe", "gear", "notes", "source"],
        ["duration_min", "distance_km", "avg_hr", "max_hr", "elevation_m", "calories", "training_load", "rpe"],
        ["date", "type", "duration_min"],
    ),
    "body/measurements.csv": (
        ["date", "time", "weight_kg", "body_fat_pct", "muscle_kg", "waist_cm", "bp_sys", "bp_dia",
         "resting_hr", "hrv_ms", "stress_avg", "vo2max", "kcal_total", "kcal_active", "notes", "source"],
        ["weight_kg", "body_fat_pct", "muscle_kg", "waist_cm", "bp_sys", "bp_dia", "resting_hr", "hrv_ms",
         "stress_avg", "vo2max", "kcal_total", "kcal_active"],
        [],
    ),
    "body/sleep.csv": (
        ["date", "bedtime", "wake_time", "duration_h", "deep_h", "rem_h", "light_h", "awake_h",
         "score", "notes", "source"],
        ["duration_h", "deep_h", "rem_h", "light_h", "awake_h", "score"],
        ["date"],
    ),
    "nutrition/log.csv": (
        ["date", "time", "meal", "description", "kcal", "protein_g", "carbs_g", "fat_g", "notes"],
        ["kcal", "protein_g", "carbs_g", "fat_g"],
        [],
    ),
}

ACTIVITY_TYPES = {"bieg", "rower", "pływanie", "siłownia", "spacer", "wędrówka", "narty", "inne"}
FLAGS = {"", "L", "H"}
TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def is_number(s: str) -> bool:
    try:
        float(s)
        return True
    except ValueError:
        return False


def validate(rel: str, header: list[str], numeric: list[str], dup_key: list[str]) -> list[str]:
    path = DATA / rel
    errors: list[str] = []
    if not path.exists():
        return [f"{rel}: brak pliku"]

    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != header:
            errors.append(f"{rel}: zły nagłówek\n   jest:  {reader.fieldnames}\n   ma być: {header}")
            return errors
        seen: dict[tuple, int] = {}
        for lineno, row in enumerate(reader, start=2):
            d = row["date"]
            try:
                parsed = date.fromisoformat(d)
                if parsed > date.today():
                    errors.append(f"{rel}:{lineno}: data z przyszłości: {d}")
            except ValueError:
                errors.append(f"{rel}:{lineno}: zła data '{d}' (oczekiwane YYYY-MM-DD)")
            if "time" in row and row["time"].strip() and not TIME_RE.match(row["time"].strip()):
                errors.append(f"{rel}:{lineno}: zła godzina '{row['time']}' (oczekiwane HH:MM)")
            for col in numeric:
                v = row[col].strip()
                if v and not is_number(v):
                    errors.append(f"{rel}:{lineno}: kolumna {col} nie jest liczbą: '{v}'")
            if rel.startswith("labs"):
                if row["flag"] not in FLAGS:
                    errors.append(f"{rel}:{lineno}: flag musi być '', 'L' lub 'H' (jest '{row['flag']}')")
                if not row["test"].strip():
                    errors.append(f"{rel}:{lineno}: puste pole test")
                v, lo, hi = row["value"].strip(), row["ref_low"].strip(), row["ref_high"].strip()
                if is_number(v) and (lo or hi) and all(is_number(x) for x in (lo, hi) if x):
                    fv = float(v)
                    expected = ""
                    if lo and fv < float(lo):
                        expected = "L"
                    elif hi and fv > float(hi):
                        expected = "H"
                    if row["flag"] != expected:
                        errors.append(f"{rel}:{lineno}: {row['test']}={v} przy normie {lo}-{hi} → flag powinno być '{expected}', jest '{row['flag']}'")
            if rel.startswith("training") and row["type"] not in ACTIVITY_TYPES:
                errors.append(f"{rel}:{lineno}: nieznany type '{row['type']}' (dozwolone: {sorted(ACTIVITY_TYPES)})")
            if dup_key:
                key = tuple(row[k].strip() for k in dup_key)
                if key in seen:
                    errors.append(f"{rel}:{lineno}: duplikat {dict(zip(dup_key, key))} (pierwszy raz w linii {seen[key]})")
                else:
                    seen[key] = lineno
    return errors


def main() -> int:
    all_errors: list[str] = []
    for rel, (header, numeric, dup_key) in SCHEMAS.items():
        all_errors.extend(validate(rel, header, numeric, dup_key))
    if all_errors:
        print(f"Znaleziono {len(all_errors)} problem(ów):")
        for e in all_errors:
            print(" -", e)
        return 1
    print("OK – wszystkie pliki CSV poprawne.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
