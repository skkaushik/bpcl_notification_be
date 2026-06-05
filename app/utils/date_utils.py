"""
Date parsing utilities for handling Excel serial numbers,
ISO strings, and common date formats from SAP PM data.
"""

from datetime import datetime, date
from typing import Optional, Union
import math


# Excel epoch: January 1, 1900 (with the Lotus 1-2-3 leap year bug)
_EXCEL_EPOCH_OFFSET = 25569  # days between 1900-01-01 and 1970-01-01


def parse_date(value: any) -> Optional[datetime]:
    """
    Parse a date value that may come in various formats:
    - Python datetime/date objects
    - Excel serial number (float/int)
    - ISO format strings
    - Common date format strings (DD-MM-YYYY, DD/MM/YYYY, etc.)
    
    Returns None if parsing fails.
    """
    if value is None:
        return None

    # Already a datetime
    if isinstance(value, datetime):
        return value

    # Python date object
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())

    # Excel serial number
    if isinstance(value, (int, float)):
        if math.isnan(value) or value <= 0:
            return None
        try:
            return datetime.utcfromtimestamp((value - _EXCEL_EPOCH_OFFSET) * 86400)
        except (ValueError, OSError, OverflowError):
            return None

    # String parsing
    if isinstance(value, str):
        value = value.strip()
        if not value or value.upper() in ("N/A", "NA", "NULL", "NONE", ""):
            return None

        # Try multiple common formats
        formats = [
            "%Y-%m-%d",           # 2024-01-15
            "%Y-%m-%dT%H:%M:%S",  # 2024-01-15T10:30:00
            "%d-%m-%Y",           # 15-01-2024
            "%d/%m/%Y",           # 15/01/2024
            "%m/%d/%Y",           # 01/15/2024
            "%d.%m.%Y",           # 15.01.2024
            "%Y/%m/%d",           # 2024/01/15
            "%d-%b-%Y",           # 15-Jan-2024
            "%d %b %Y",           # 15 Jan 2024
            "%b %d, %Y",          # Jan 15, 2024
        ]

        for fmt in formats:
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue

        # Try Python's flexible parser as last resort
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            pass

    return None


def days_since(value: any) -> int:
    """
    Calculate the number of days between a date value and today.
    Returns 0 if the date cannot be parsed.
    """
    parsed = parse_date(value)
    if parsed is None:
        return 0
    delta = datetime.now() - parsed
    return max(0, delta.days)


def is_overdue(due_date_value: any) -> bool:
    """
    Check if a notification is overdue (due date is in the past).
    Returns False if the date cannot be parsed or is empty.
    """
    parsed = parse_date(due_date_value)
    if parsed is None:
        return False
    return parsed < datetime.now()


def format_date(value: any, fmt: str = "%Y-%m-%d") -> str:
    """
    Format a date value to a string. Returns 'N/A' if parsing fails.
    """
    parsed = parse_date(value)
    if parsed is None:
        return "N/A"
    return parsed.strftime(fmt)
