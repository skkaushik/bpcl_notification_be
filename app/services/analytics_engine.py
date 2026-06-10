"""
Analytics Engine — the source of truth for all data analysis.

All functions accept a normalized Pandas DataFrame and return
structured Python dicts/lists. NO LLM involvement whatsoever.

These functions mirror and extend the logic in the existing frontend
dashboardHelpers.js to ensure consistency.
"""

from datetime import datetime
from typing import Optional, Any
from collections import Counter

import pandas as pd
import numpy as np

from app.utils.date_utils import parse_date, days_since, is_overdue


# ─── Helpers ───────────────────────────────────────────────────────────────────

def _safe_str(value: Any) -> str:
    """Safely convert a value to a stripped uppercase string."""
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return ""
    return str(value).strip().upper()


def _get_col(df: pd.DataFrame, name: str) -> Optional[str]:
    """Get column name if it exists in the DataFrame."""
    if name in df.columns:
        return name
    return None


VALID_DEPTS = ("MS", "MR", "MI", "ME", "MC", "FS")

def _extract_unit(work_center: str) -> tuple[str, str]:
    """
    Extract department prefix and unit name from work center value.
    If no prefix matches, returns 'OTHERS' as the prefix.
    """
    wc = _safe_str(work_center)
    for prefix in VALID_DEPTS:
        if wc.startswith(prefix):
            return prefix, wc[len(prefix):]
    return "OTHERS", wc


def _is_valid_dept(work_center: str) -> bool:
    """All work centers are now valid (mapped to specific department or OTHERS)."""
    return True


def _filter_valid_depts(df: pd.DataFrame) -> pd.DataFrame:
    """Filter DataFrame to only valid department work center rows."""
    wc_col = _get_col(df, "work_center")
    if wc_col is None:
        return df
    mask = df[wc_col].apply(lambda x: _is_valid_dept(x))
    return df[mask].copy()


# ─── Analytics Functions ───────────────────────────────────────────────────────

def get_summary_stats(df: pd.DataFrame) -> dict:
    """
    Calculate high-level summary statistics.
    
    Returns:
        Dict with total count, breakdowns by type/status/priority,
        overdue count, and units impacted.
    """
    filtered = _filter_valid_depts(df)
    total = len(filtered)

    result = {
        "total_notifications": total,
        "by_type": {},
        "by_status": {},
        "by_priority": {},
        "overdue_count": 0,
        "open_count": 0,
        "units_impacted": 0,
    }

    if total == 0:
        return result

    # By notification type
    type_col = _get_col(filtered, "notification_type")
    if type_col:
        type_counts = filtered[type_col].apply(_safe_str).value_counts()
        result["by_type"] = {k: int(v) for k, v in type_counts.items() if k}

    # By status
    status_col = _get_col(filtered, "status")
    if status_col:
        status_counts = filtered[status_col].apply(_safe_str).value_counts()
        result["by_status"] = {k: int(v) for k, v in status_counts.items() if k}

    # By priority
    priority_col = _get_col(filtered, "priority")
    if priority_col:
        priority_counts = filtered[priority_col].apply(
            lambda x: _safe_str(x) if _safe_str(x) else "UNSET"
        ).value_counts()
        result["by_priority"] = {k: int(v) for k, v in priority_counts.items()}

    # Overdue count
    due_col = _get_col(filtered, "due_date")
    if due_col:
        result["overdue_count"] = int(
            filtered[due_col].apply(lambda x: is_overdue(x)).sum()
        )

    # Open count (status not in closed/completed states)
    if status_col:
        closed_statuses = {"NOCO", "CLSD", "DLFL", "COMP", "COMPLETED", "CLOSED"}
        result["open_count"] = int(
            filtered[status_col].apply(
                lambda x: _safe_str(x) not in closed_statuses
            ).sum()
        )

    # Units impacted
    wc_col = _get_col(filtered, "work_center")
    if wc_col:
        units = set()
        for val in filtered[wc_col]:
            _, unit = _extract_unit(val)
            if unit:
                units.add(unit)
        result["units_impacted"] = len(units)

    return result


def get_open_notifications(
    df: pd.DataFrame,
    priority: Optional[str] = None,
    limit: int = 50,
) -> list[dict]:
    """
    Get open/active notifications, optionally filtered by priority.
    
    Returns:
        List of notification dicts.
    """
    filtered = _filter_valid_depts(df)
    status_col = _get_col(filtered, "status")

    if status_col:
        closed_statuses = {"NOCO", "CLSD", "DLFL", "COMP", "COMPLETED", "CLOSED"}
        filtered = filtered[
            filtered[status_col].apply(lambda x: _safe_str(x) not in closed_statuses)
        ]

    if priority:
        priority_col = _get_col(filtered, "priority")
        if priority_col:
            filtered = filtered[
                filtered[priority_col].apply(lambda x: _safe_str(x) == priority.upper())
            ]

    return _df_to_records(filtered.head(limit))


def get_overdue_notifications(df: pd.DataFrame, limit: int = 50) -> list[dict]:
    """
    Get notifications that are past their due date.
    
    Returns:
        List of overdue notification dicts with days_overdue field.
    """
    filtered = _filter_valid_depts(df)
    due_col = _get_col(filtered, "due_date")

    if due_col is None:
        return []

    now = datetime.now()
    records = []

    for _, row in filtered.iterrows():
        due_date = parse_date(row.get(due_col))
        if due_date and due_date < now:
            record = _row_to_dict(row)
            record["days_overdue"] = (now - due_date).days
            records.append(record)

    # Sort by most overdue first
    records.sort(key=lambda x: x.get("days_overdue", 0), reverse=True)
    return records[:limit]


def get_critical_notifications(df: pd.DataFrame, limit: int = 50) -> list[dict]:
    """
    Get high-priority open notifications (priority 1 or 2).
    
    Returns:
        List of critical notification dicts.
    """
    filtered = _filter_valid_depts(df)

    # Filter for open status
    status_col = _get_col(filtered, "status")
    if status_col:
        closed_statuses = {"NOCO", "CLSD", "DLFL", "COMP", "COMPLETED", "CLOSED"}
        filtered = filtered[
            filtered[status_col].apply(lambda x: _safe_str(x) not in closed_statuses)
        ]

    # Filter for high priority
    priority_col = _get_col(filtered, "priority")
    if priority_col:
        high_priorities = {"1", "2", "VERY HIGH", "HIGH"}
        filtered = filtered[
            filtered[priority_col].apply(lambda x: _safe_str(x) in high_priorities)
        ]

    return _df_to_records(filtered.head(limit))


def get_equipment_ranking(df: pd.DataFrame, top_n: int = 10) -> list[dict]:
    """
    Rank equipment by notification count.
    
    Returns:
        List of dicts with equipment_id, notification_count, types, statuses.
    """
    filtered = _filter_valid_depts(df)
    equip_col = _get_col(filtered, "equipment")

    if equip_col is None:
        return []

    type_col = _get_col(filtered, "notification_type")
    status_col = _get_col(filtered, "status")

    groups = {}
    for _, row in filtered.iterrows():
        equip_id = _safe_str(row.get(equip_col, ""))
        if not equip_id:
            continue

        if equip_id not in groups:
            groups[equip_id] = {
                "equipment_id": equip_id,
                "notification_count": 0,
                "types": [],
                "statuses": [],
            }

        groups[equip_id]["notification_count"] += 1
        if type_col:
            groups[equip_id]["types"].append(_safe_str(row.get(type_col, "")))
        if status_col:
            groups[equip_id]["statuses"].append(_safe_str(row.get(status_col, "")))

    # Deduplicate types and statuses
    for equip_data in groups.values():
        equip_data["types"] = list(set(t for t in equip_data["types"] if t))
        equip_data["statuses"] = list(set(s for s in equip_data["statuses"] if s))

    # Sort by count descending
    ranked = sorted(groups.values(), key=lambda x: x["notification_count"], reverse=True)
    return ranked[:top_n]


def get_recurring_failures(df: pd.DataFrame, min_count: int = 3) -> list[dict]:
    """
    Find equipment with recurring notifications (potential chronic failures).
    
    Returns:
        List of dicts with equipment_id, count, breakdown_count, type_distribution.
    """
    filtered = _filter_valid_depts(df)
    equip_col = _get_col(filtered, "equipment")
    type_col = _get_col(filtered, "notification_type")
    breakdown_col = _get_col(filtered, "breakdown_indicator")

    if equip_col is None:
        return []

    groups = {}
    for _, row in filtered.iterrows():
        equip_id = _safe_str(row.get(equip_col, ""))
        if not equip_id:
            continue

        if equip_id not in groups:
            groups[equip_id] = {
                "equipment_id": equip_id,
                "notification_count": 0,
                "breakdown_count": 0,
                "type_distribution": Counter(),
            }

        groups[equip_id]["notification_count"] += 1

        if breakdown_col:
            bd = _safe_str(row.get(breakdown_col, ""))
            if bd in ("X", "YES", "TRUE", "1"):
                groups[equip_id]["breakdown_count"] += 1

        if type_col:
            t = _safe_str(row.get(type_col, ""))
            if t:
                groups[equip_id]["type_distribution"][t] += 1

    # Filter by min_count and sort
    recurring = []
    for data in groups.values():
        if data["notification_count"] >= min_count:
            data["type_distribution"] = dict(data["type_distribution"])
            recurring.append(data)

    recurring.sort(key=lambda x: x["notification_count"], reverse=True)
    return recurring


def get_area_backlog(df: pd.DataFrame) -> list[dict]:
    """
    Calculate backlog (open + overdue) grouped by work center / area.
    
    Returns:
        List of dicts with unit, open_count, overdue_count, total_backlog.
    """
    filtered = _filter_valid_depts(df)
    wc_col = _get_col(filtered, "work_center")
    status_col = _get_col(filtered, "status")
    due_col = _get_col(filtered, "due_date")

    if wc_col is None:
        return []

    closed_statuses = {"NOCO", "CLSD", "DLFL", "COMP", "COMPLETED", "CLOSED"}
    now = datetime.now()
    groups = {}

    for _, row in filtered.iterrows():
        _, unit = _extract_unit(row.get(wc_col, ""))
        if not unit:
            continue

        if unit not in groups:
            groups[unit] = {
                "unit": unit,
                "total_count": 0,
                "open_count": 0,
                "overdue_count": 0,
            }

        groups[unit]["total_count"] += 1

        # Check if open
        if status_col:
            status = _safe_str(row.get(status_col, ""))
            if status not in closed_statuses:
                groups[unit]["open_count"] += 1

        # Check if overdue
        if due_col:
            due_date = parse_date(row.get(due_col))
            if due_date and due_date < now:
                groups[unit]["overdue_count"] += 1

    result = list(groups.values())
    for item in result:
        item["total_backlog"] = item["open_count"] + item["overdue_count"]

    result.sort(key=lambda x: x["total_backlog"], reverse=True)
    return result


def get_notification_trends(
    df: pd.DataFrame,
    period: str = "month",
) -> list[dict]:
    """
    Analyze notification creation trends over time.
    
    Args:
        df: Normalized DataFrame.
        period: Grouping period — 'day', 'week', 'month', or 'year'.
    
    Returns:
        List of dicts with period label and count.
    """
    filtered = _filter_valid_depts(df)
    date_col = _get_col(filtered, "created_date")

    if date_col is None:
        return []

    # Parse all dates
    dates = filtered[date_col].apply(parse_date).dropna()

    if dates.empty:
        return []

    date_series = pd.Series(dates.values, name="date")
    date_index = pd.DatetimeIndex(date_series)

    # Group by period
    freq_map = {
        "day": "D",
        "week": "W",
        "month": "ME",
        "year": "YE",
    }
    freq = freq_map.get(period, "ME")

    counts = date_index.to_series().groupby(pd.Grouper(freq=freq)).count()

    format_map = {
        "day": "%Y-%m-%d",
        "week": "%Y-W%U",
        "month": "%Y-%m",
        "year": "%Y",
    }
    fmt = format_map.get(period, "%Y-%m")

    return [
        {"name": idx.strftime(fmt), "value": int(count)}
        for idx, count in counts.items()
        if count > 0
    ]


def get_type_distribution(df: pd.DataFrame) -> list[dict]:
    """
    Get distribution of notification types.
    
    Returns:
        List of dicts with name (type) and value (count).
    """
    filtered = _filter_valid_depts(df)
    type_col = _get_col(filtered, "notification_type")

    if type_col is None:
        return []

    counts = filtered[type_col].apply(_safe_str).value_counts()
    return [
        {"name": name, "value": int(val)}
        for name, val in counts.items()
        if name
    ]


def get_status_distribution(df: pd.DataFrame) -> list[dict]:
    """
    Get distribution of notification statuses.
    
    Returns:
        List of dicts with name (status) and value (count).
    """
    filtered = _filter_valid_depts(df)
    status_col = _get_col(filtered, "status")

    if status_col is None:
        return []

    counts = filtered[status_col].apply(_safe_str).value_counts()
    return [
        {"name": name, "value": int(val)}
        for name, val in counts.items()
        if name
    ]


def get_priority_distribution(df: pd.DataFrame) -> list[dict]:
    """
    Get distribution of notification priorities.
    
    Returns:
        List of dicts with name (priority) and value (count).
    """
    filtered = _filter_valid_depts(df)
    priority_col = _get_col(filtered, "priority")

    if priority_col is None:
        return []

    counts = filtered[priority_col].apply(
        lambda x: _safe_str(x) if _safe_str(x) else "UNSET"
    ).value_counts()
    return [
        {"name": name, "value": int(val)}
        for name, val in counts.items()
    ]


def get_aging_analysis(df: pd.DataFrame) -> list[dict]:
    """
    Analyze notification aging in defined buckets.
    
    Returns:
        List of dicts with age_bucket and count.
    """
    filtered = _filter_valid_depts(df)
    date_col = _get_col(filtered, "created_date")

    if date_col is None:
        return []

    buckets = {
        "0-7 days": 0,
        "7-15 days": 0,
        "15-30 days": 0,
        "30-60 days": 0,
        "60+ days": 0,
    }

    for _, row in filtered.iterrows():
        age = days_since(row.get(date_col))
        if age <= 7:
            buckets["0-7 days"] += 1
        elif age <= 15:
            buckets["7-15 days"] += 1
        elif age <= 30:
            buckets["15-30 days"] += 1
        elif age <= 60:
            buckets["30-60 days"] += 1
        else:
            buckets["60+ days"] += 1

    return [
        {"name": bucket, "value": count}
        for bucket, count in buckets.items()
    ]


def get_unit_wise_breakdown(df: pd.DataFrame) -> list[dict]:
    """
    Get breakdown per unit for all departments.
    
    Returns:
        List of dicts with unit and counts per department.
    """
    filtered = _filter_valid_depts(df)
    wc_col = _get_col(filtered, "work_center")

    if wc_col is None:
        return []

    groups = {}
    for _, row in filtered.iterrows():
        prefix, unit = _extract_unit(row.get(wc_col, ""))
        if not unit or not prefix:
            continue

        if unit not in groups:
            groups[unit] = {"unit": unit, "MS": 0, "MR": 0, "MI": 0, "ME": 0, "MC": 0, "FS": 0, "OTHERS": 0}
        
        if prefix in groups[unit]:
            groups[unit][prefix] += 1
        else:
            groups[unit][prefix] = 1

    result = list(groups.values())
    result.sort(key=lambda x: sum(v for k, v in x.items() if k != "unit"), reverse=True)
    return result


def get_problematic_equipment(df: pd.DataFrame, top_n: int = 10) -> list[dict]:
    """
    Identify the most problematic equipment based on notification count,
    breakdown frequency, and type diversity.
    
    Returns:
        List of dicts with equipment details and a computed risk_score.
    """
    filtered = _filter_valid_depts(df)
    equip_col = _get_col(filtered, "equipment")
    type_col = _get_col(filtered, "notification_type")
    breakdown_col = _get_col(filtered, "breakdown_indicator")
    wc_col = _get_col(filtered, "work_center")

    if equip_col is None:
        return []

    groups = {}
    for _, row in filtered.iterrows():
        equip_id = _safe_str(row.get(equip_col, ""))
        if not equip_id:
            continue

        if equip_id not in groups:
            groups[equip_id] = {
                "equipment_id": equip_id,
                "notification_count": 0,
                "breakdown_count": 0,
                "types": Counter(),
                "units": set(),
            }

        groups[equip_id]["notification_count"] += 1

        if breakdown_col:
            bd = _safe_str(row.get(breakdown_col, ""))
            if bd in ("X", "YES", "TRUE", "1"):
                groups[equip_id]["breakdown_count"] += 1

        if type_col:
            t = _safe_str(row.get(type_col, ""))
            if t:
                groups[equip_id]["types"][t] += 1

        if wc_col:
            _, unit = _extract_unit(row.get(wc_col, ""))
            if unit:
                groups[equip_id]["units"].add(unit)

    # Calculate risk score
    result = []
    for data in groups.values():
        if data["notification_count"] < 2:
            continue

        # Risk score: weighted combination
        risk_score = (
            data["notification_count"] * 1.0
            + data["breakdown_count"] * 3.0
            + len(data["types"]) * 0.5
        )

        result.append({
            "equipment_id": data["equipment_id"],
            "notification_count": data["notification_count"],
            "breakdown_count": data["breakdown_count"],
            "type_distribution": dict(data["types"]),
            "units": list(data["units"]),
            "risk_score": round(risk_score, 1),
        })

    result.sort(key=lambda x: x["risk_score"], reverse=True)
    return result[:top_n]


def get_notifications_table(
    df: pd.DataFrame,
    filters: Optional[dict] = None,
    page: int = 1,
    page_size: int = 25,
) -> dict:
    """
    Get a paginated, filtered notification table.
    
    Args:
        df: Normalized DataFrame.
        filters: Optional dict with keys like notification_type, status, etc.
        page: Page number (1-indexed).
        page_size: Rows per page.
    
    Returns:
        Dict with 'data' (list of row dicts), 'total', 'page', 'page_size'.
    """
    filtered = _filter_valid_depts(df)

    if filters:
        type_col = _get_col(filtered, "notification_type")
        status_col = _get_col(filtered, "status")
        priority_col = _get_col(filtered, "priority")
        equip_col = _get_col(filtered, "equipment")

        if "notification_type" in filters and type_col:
            val = filters["notification_type"].upper()
            filtered = filtered[filtered[type_col].apply(lambda x: _safe_str(x) == val)]

        if "status" in filters and status_col:
            val = filters["status"].upper()
            filtered = filtered[filtered[status_col].apply(lambda x: _safe_str(x) == val)]

        if "priority" in filters and priority_col:
            val = str(filters["priority"]).upper()
            filtered = filtered[filtered[priority_col].apply(lambda x: _safe_str(x) == val)]

        if "equipment" in filters and equip_col:
            val = filters["equipment"].upper()
            filtered = filtered[filtered[equip_col].apply(lambda x: val in _safe_str(x))]

    total = len(filtered)
    start = (page - 1) * page_size
    end = start + page_size
    page_data = filtered.iloc[start:end]

    return {
        "data": _df_to_records(page_data),
        "total": total,
        "page": page,
        "page_size": page_size,
    }


# ─── Internal Helpers ──────────────────────────────────────────────────────────

def _row_to_dict(row: pd.Series) -> dict:
    """Convert a DataFrame row to a clean dict."""
    d = {}
    for key, value in row.items():
        if isinstance(value, (pd.Timestamp, datetime)):
            d[key] = value.isoformat()
        elif isinstance(value, float) and np.isnan(value):
            d[key] = None
        else:
            d[key] = value
    return d


def _df_to_records(df: pd.DataFrame) -> list[dict]:
    """Convert a DataFrame to a list of clean dicts."""
    records = []
    for _, row in df.iterrows():
        records.append(_row_to_dict(row))
    return records


# ─── Function Registry ─────────────────────────────────────────────────────────
# Maps function names (used by AI intent layer) to actual callables

ANALYTICS_FUNCTIONS: dict[str, dict] = {
    "get_summary_stats": {
        "fn": get_summary_stats,
        "description": "Overall statistics: total count, breakdowns by type/status/priority, overdue, open count",
        "params": [],
    },
    "get_open_notifications": {
        "fn": get_open_notifications,
        "description": "List of open/active notifications, optionally filtered by priority",
        "params": ["priority", "limit"],
    },
    "get_overdue_notifications": {
        "fn": get_overdue_notifications,
        "description": "Notifications past their due date, sorted by most overdue",
        "params": ["limit"],
    },
    "get_critical_notifications": {
        "fn": get_critical_notifications,
        "description": "High-priority (1 or 2) open notifications",
        "params": ["limit"],
    },
    "get_equipment_ranking": {
        "fn": get_equipment_ranking,
        "description": "Equipment ranked by notification count (most notifications first)",
        "params": ["top_n"],
    },
    "get_recurring_failures": {
        "fn": get_recurring_failures,
        "description": "Equipment with recurring/repeated notifications (chronic failures)",
        "params": ["min_count"],
    },
    "get_area_backlog": {
        "fn": get_area_backlog,
        "description": "Backlog (open + overdue) grouped by work center / unit / area",
        "params": [],
    },
    "get_notification_trends": {
        "fn": get_notification_trends,
        "description": "Notification creation trends over time (by day/week/month/year)",
        "params": ["period"],
    },
    "get_type_distribution": {
        "fn": get_type_distribution,
        "description": "Distribution of notification types (M1, M2, etc.)",
        "params": [],
    },
    "get_status_distribution": {
        "fn": get_status_distribution,
        "description": "Distribution of notification statuses",
        "params": [],
    },
    "get_priority_distribution": {
        "fn": get_priority_distribution,
        "description": "Distribution of notification priorities",
        "params": [],
    },
    "get_aging_analysis": {
        "fn": get_aging_analysis,
        "description": "Notification aging buckets (0-7d, 7-15d, 15-30d, 30-60d, 60+d)",
        "params": [],
    },
    "get_unit_wise_breakdown": {
        "fn": get_unit_wise_breakdown,
        "description": "Department count per unit (MS, MR, MI, ME, MC, FS, OTHERS)",
        "params": [],
    },
    "get_problematic_equipment": {
        "fn": get_problematic_equipment,
        "description": "Most problematic equipment by risk score (notification count + breakdowns)",
        "params": ["top_n"],
    },
    "get_notifications_table": {
        "fn": get_notifications_table,
        "description": "Paginated list of notifications, optionally filtered by notification_type, status, priority, or equipment.",
        "params": ["filters", "page", "page_size"],
    },
}
