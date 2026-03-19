"""Parse and validate hill ascent CSV import data."""
from __future__ import annotations

import csv
import io
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ParsedAscent:
    hill_name: str
    hill_id: int
    date: str  # YYYY-MM-DD


@dataclass
class ImportResult:
    ascents: list[ParsedAscent] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def _parse_date(s: str) -> str | None:
    """Try YYYY-MM-DD and DD/MM/YYYY. Return YYYY-MM-DD or None."""
    s = s.strip()
    for fmt in ('%Y-%m-%d', '%d/%m/%Y'):
        try:
            return datetime.strptime(s, fmt).strftime('%Y-%m-%d')
        except ValueError:
            pass
    return None


def parse_ascent_csv(text: str, hills_by_name: dict[str, int]) -> ImportResult:
    """Parse CSV with columns: hill_name, ascent_dates.

    ascent_dates is semicolon-separated (e.g. 2023-07-15;2024-08-20).
    hills_by_name maps lowercase hill name -> hill_id.
    A header row (hill_name, ascent_dates) is accepted and skipped.
    Existing ascents for any hill present in the CSV are replaced on import.
    Errors do not stop processing — all rows are checked.
    """
    result = ImportResult()
    reader = csv.reader(io.StringIO(text.strip()))

    for line_num, row in enumerate(reader, start=1):
        # Skip blank lines
        if not row or all(c.strip() == '' for c in row):
            continue

        # Skip header
        if line_num == 1 and row[0].strip().lower() in ('hill_name', 'hill name', 'name'):
            continue

        if len(row) < 2:
            result.errors.append(
                f'Row {line_num}: expected 2 columns (hill_name, ascent_dates), got {len(row)}'
            )
            continue

        hill_name = row[0].strip()
        dates_str = row[1].strip()

        if not hill_name:
            result.errors.append(f'Row {line_num}: hill name is empty')
            continue

        hill_id = hills_by_name.get(unicodedata.normalize('NFC', hill_name.lower()))
        if hill_id is None:
            result.errors.append(f'Row {line_num}: hill not found: "{hill_name}"')
            continue

        if not dates_str:
            result.errors.append(f'Row {line_num}: no dates provided for "{hill_name}"')
            continue

        date_parts = [d.strip() for d in dates_str.split(';') if d.strip()]
        if not date_parts:
            result.errors.append(f'Row {line_num}: no dates provided for "{hill_name}"')
            continue

        for date_str in date_parts:
            parsed = _parse_date(date_str)
            if parsed is None:
                result.errors.append(
                    f'Row {line_num}: invalid date "{date_str}" for "{hill_name}"'
                    f' — use YYYY-MM-DD or DD/MM/YYYY'
                )
            else:
                result.ascents.append(ParsedAscent(
                    hill_name=hill_name,
                    hill_id=hill_id,
                    date=parsed,
                ))

    return result
