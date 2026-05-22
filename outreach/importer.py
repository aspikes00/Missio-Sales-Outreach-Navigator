from __future__ import annotations
import csv
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from database.db import Database
from database.models import Lead
from database.queries import insert_lead, url_exists

logger = logging.getLogger(__name__)

COLUMN_MAP = {
    "linkedin_url": ["linkedin_url", "linkedin url", "profile url", "url", "linkedin"],
    "first_name": ["first_name", "first name", "firstname"],
    "last_name": ["last_name", "last name", "lastname"],
    "full_name": ["full_name", "full name", "name"],
    "title": ["title", "job title", "position", "role"],
    "company_name": ["company_name", "company", "company name", "organization"],
    "industry": ["industry", "sector"],
    "location": ["location", "city", "region"],
}


@dataclass
class ImportResult:
    added: int = 0
    skipped: int = 0
    errors: list[str] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []


def import_from_csv(
    filepath: str, db: Database, brand: str, source_list: Optional[str] = None
) -> ImportResult:
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"CSV file not found: {filepath}")

    result = ImportResult()

    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        headers = [h.lower().strip() for h in (reader.fieldnames or [])]
        col_index = _build_column_index(headers)

        if "linkedin_url" not in col_index:
            raise ValueError(
                "CSV must have a LinkedIn URL column. "
                "Accepted names: linkedin_url, linkedin url, profile url, url, linkedin"
            )
        if "first_name" not in col_index and "full_name" not in col_index:
            raise ValueError("CSV must have a first_name or full_name column.")

        for row_num, row in enumerate(reader, start=2):
            norm = {k.lower().strip(): v.strip() for k, v in row.items()}
            try:
                lead = _row_to_lead(norm, col_index, brand, source_list)
                if not lead.linkedin_url:
                    result.errors.append(f"Row {row_num}: missing LinkedIn URL — skipped")
                    result.skipped += 1
                    continue

                with db.transaction() as conn:
                    if url_exists(conn, lead.linkedin_url):
                        result.skipped += 1
                        continue
                    insert_lead(conn, lead)
                    result.added += 1

            except Exception as e:
                result.errors.append(f"Row {row_num}: {e}")
                result.skipped += 1

    logger.info(
        "Import complete [%s] — added: %d, skipped: %d, errors: %d",
        brand, result.added, result.skipped, len(result.errors),
    )
    return result


def _row_to_lead(norm: dict, col_index: dict, brand: str, source_list: Optional[str]) -> Lead:
    def get(field):
        key = col_index.get(field)
        return norm.get(key, "").strip() if key else ""

    linkedin_url = get("linkedin_url")
    full_name = get("full_name")
    first_name = get("first_name")
    last_name = get("last_name")

    if not first_name and full_name:
        parts = full_name.strip().split(" ", 1)
        first_name = parts[0]
        last_name = parts[1] if len(parts) > 1 else ""

    return Lead(
        id=None,
        linkedin_url=linkedin_url,
        brand=brand,
        first_name=first_name,
        last_name=last_name,
        full_name=full_name or f"{first_name} {last_name}".strip(),
        title=get("title"),
        company_name=get("company_name"),
        industry=get("industry"),
        location=get("location"),
        source_list=source_list,
    )


def _build_column_index(headers: list[str]) -> dict[str, str]:
    index = {}
    for field, aliases in COLUMN_MAP.items():
        for alias in aliases:
            if alias in headers:
                index[field] = alias
                break
    return index
