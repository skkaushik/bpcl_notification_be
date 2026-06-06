"""
File parser service.

Handles ingestion of .xlsx, .xls, and .csv files into Pandas DataFrames.
Applies basic cleaning and date parsing.
"""

import pandas as pd
from pathlib import Path
from io import BytesIO
from typing import BinaryIO

from app.utils.date_utils import parse_date


# Supported file extensions
SUPPORTED_EXTENSIONS = {".xlsx", ".xls", ".csv"}


class FileParseError(Exception):
    """Raised when a file cannot be parsed."""
    pass


def parse_file(file_content: bytes, filename: str) -> pd.DataFrame:
    """
    Parse an uploaded file into a Pandas DataFrame.
    
    Args:
        file_content: Raw bytes of the uploaded file.
        filename: Original filename (used to detect format).
        
    Returns:
        Cleaned Pandas DataFrame.
        
    Raises:
        FileParseError: If the file format is unsupported or parsing fails.
    """
    ext = Path(filename).suffix.lower()

    if ext not in SUPPORTED_EXTENSIONS:
        raise FileParseError(
            f"Unsupported file format: '{ext}'. "
            f"Supported formats: {', '.join(SUPPORTED_EXTENSIONS)}"
        )

    try:
        buffer = BytesIO(file_content)

        if ext == ".csv":
            df = _parse_csv(buffer)
        elif ext == ".xlsx":
            df = _parse_xlsx(buffer)
        elif ext == ".xls":
            df = _parse_xls(buffer)
        else:
            raise FileParseError(f"Unsupported file format: '{ext}'")

    except FileParseError:
        raise
    except Exception as e:
        raise FileParseError(f"Failed to parse file '{filename}': {str(e)}")

    # Basic cleaning
    df = _clean_dataframe(df)

    if df.empty:
        raise FileParseError("File appears to be empty after cleaning.")

    return df


def _parse_csv(buffer: BytesIO) -> pd.DataFrame:
    """Parse a CSV file, trying multiple encodings."""
    for encoding in ["utf-8", "latin-1", "cp1252"]:
        try:
            buffer.seek(0)
            return pd.read_csv(buffer, encoding=encoding)
        except UnicodeDecodeError:
            continue
    raise FileParseError("Could not decode CSV file with any supported encoding.")


def _parse_xlsx(buffer: BytesIO) -> pd.DataFrame:
    """Parse an .xlsx file using openpyxl."""
    return pd.read_excel(buffer, engine="openpyxl")


def _parse_xls(buffer: BytesIO) -> pd.DataFrame:
    """Parse a legacy .xls file using xlrd."""
    return pd.read_excel(buffer, engine="xlrd")


def _clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Apply basic cleaning to a DataFrame:
    - Drop completely empty rows
    - Strip whitespace from string columns
    - Drop columns that are entirely empty
    """
    # Drop rows where all values are NaN
    df = df.dropna(how="all")

    # Drop columns where all values are NaN
    df = df.dropna(axis=1, how="all")

    # Strip whitespace from string columns
    for col in df.select_dtypes(include=["object"]).columns:
        df[col] = df[col].astype(str).str.strip()
        # Replace "nan" strings back to actual NaN
        df[col] = df[col].replace("nan", pd.NA)

    # Reset index
    df = df.reset_index(drop=True)

    return df
