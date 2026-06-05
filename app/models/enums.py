"""
Enumerations for the notification domain.
"""

from enum import Enum


class AIProvider(str, Enum):
    GEMINI = "gemini"
    OPENAI = "openai"


class NotificationType(str, Enum):
    """SAP PM notification types."""
    M1 = "M1"  # Breakdown
    M2 = "M2"  # Preventive Maintenance
    M3 = "M3"
    M4 = "M4"
    M5 = "M5"
    M6 = "M6"
    M7 = "M7"
    M8 = "M8"
    M9 = "M9"


class Priority(str, Enum):
    VERY_HIGH = "1"
    HIGH = "2"
    MEDIUM = "3"
    LOW = "4"


class ResponseType(str, Enum):
    """Types of responses the AI can generate."""
    SUMMARY = "summary"
    TABLE = "table"
    CHART = "chart"
    INSIGHT = "insight"


class ChartType(str, Enum):
    BAR = "bar"
    PIE = "pie"
    LINE = "line"
