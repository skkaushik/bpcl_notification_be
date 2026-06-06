"""
Schema normalization layer.

Maps varying column names from uploaded SAP PM notification files
to a canonical internal schema. Handles common naming variations
across different SAP exports and user-modified files.
"""

import re
from typing import Optional
import pandas as pd


# ─── Canonical Field Definitions ───────────────────────────────────────────────
# Each canonical field maps to a list of known aliases (normalized form).
# Normalization: lowercase, strip all whitespace, dots, underscores, hyphens.

CANONICAL_FIELD_ALIASES: dict[str, list[str]] = {
    "notification_id": [
        "notification",
        "notificationno",
        "notificationnumber",
        "notificationid",
        "notification_id",
        "notifictn",
        "notifno",
    ],
    "equipment": [
        "equipment",
        "equipmentnumber",
        "equipmentid",
        "equip",
        "equipmentno",
    ],
    "functional_location": [
        "functionallocation",
        "functionalloc",
        "funclocation",
        "funcloc",
        "floc",
    ],
    "priority": [
        "priority",
        "prio",
    ],
    "status": [
        "userstatus",
        "status",
    ],
    "system_status": [
        "systemstatus",
        "sysstatus",
        "sysstat",
    ],
    "created_date": [
        "notifdate",
        "notificationdate",
        "createddate",
        "createdon",
        "date",
    ],
    "due_date": [
        "requiredend",
        "duedate",
        "requiredenddate",
        "reqend",
    ],
    "description": [
        "description",
        "desc",
        "notificationdescription",
    ],
    "description_2": [
        "description2",
        "desc2",
    ],
    "work_center": [
        "mainworkctr",
        "workcenter",
        "workctr",
        "mainworkcenter",
        "unit",
    ],
    "area": [
        "area",
        "plantsection",
        "section",
    ],
    "plant": [
        "plant",
        "plantcode",
    ],
    "breakdown_indicator": [
        "breakdown",
        "breakdownindicator",
        "brkdown",
        "breakdownind",
    ],
    "notification_type": [
        "notifictntype",
        "notificationtype",
        "notiftype",
        "type",
    ],
    "reported_by": [
        "reportedby",
        "reporter",
        "createdby",
    ],
}

# Build a reverse lookup: normalized_alias → canonical_field
_ALIAS_TO_CANONICAL: dict[str, str] = {}
for canonical, aliases in CANONICAL_FIELD_ALIASES.items():
    for alias in aliases:
        _ALIAS_TO_CANONICAL[alias] = canonical


def _normalize_column_name(name: str) -> str:
    """
    Normalize a column name by lowering case, removing
    whitespace, dots, underscores, and hyphens.
    """
    return re.sub(r"[\s._\-]+", "", str(name).strip().lower())


def detect_column_mapping(columns: list[str]) -> dict[str, str]:
    """
    Detect the mapping from original file columns to canonical fields.
    
    Args:
        columns: List of column names from the uploaded file.
        
    Returns:
        Dict mapping original_column_name → canonical_field_name.
        Only includes columns that could be matched.
    """
    mapping: dict[str, str] = {}
    used_canonical: set[str] = set()

    # Sort aliases by specificity (longer normalized names first)
    # This prevents "type" from matching before "notifictntype"
    sorted_columns = sorted(columns, key=lambda c: len(_normalize_column_name(c)), reverse=True)

    for original in sorted_columns:
        normalized = _normalize_column_name(original)
        if normalized in _ALIAS_TO_CANONICAL:
            canonical = _ALIAS_TO_CANONICAL[normalized]
            if canonical not in used_canonical:
                mapping[original] = canonical
                used_canonical.add(canonical)

    return mapping


def normalize_dataframe(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, str]]:
    """
    Normalize a DataFrame by renaming columns to canonical field names.
    
    Args:
        df: Raw DataFrame from file upload.
        
    Returns:
        Tuple of (normalized DataFrame, column mapping dict).
        Columns that don't match any alias are kept with their original names.
    """
    mapping = detect_column_mapping(df.columns.tolist())

    # Create rename dict: original → canonical
    rename_dict = {original: canonical for original, canonical in mapping.items()}

    normalized_df = df.rename(columns=rename_dict)

    return normalized_df, mapping


def get_canonical_field(
    df: pd.DataFrame,
    canonical_name: str,
) -> Optional[str]:
    """
    Get the actual column name in a DataFrame for a canonical field.
    Handles both normalized and non-normalized DataFrames.
    
    Returns the column name if found, None otherwise.
    """
    # Direct match (already normalized)
    if canonical_name in df.columns:
        return canonical_name

    # Try to find via aliases
    aliases = CANONICAL_FIELD_ALIASES.get(canonical_name, [])
    for col in df.columns:
        if _normalize_column_name(col) in aliases:
            return col

    return None
