"""
Email Routing Service — handles filtering, routing, grouping, and sending.

The frontend sends only session_id + filters.
This service:
  1. Loads the normalized DataFrame from the session
  2. Applies the dashboard filters (unit, type, dept, status, date, age)
  3. Extracts notification fields from the filtered data
  4. Determines target emails via routing rules
  5. Groups notifications by target email
  6. Generates email body text
  7. Sends via SMTP (or logs in dry-run mode)
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging
from datetime import datetime
from typing import Optional
import math

import pandas as pd
import numpy as np

from app.config import settings
from app.utils.email_config import EMAIL_CONFIG

logger = logging.getLogger(__name__)

# ─── Helpers ───────────────────────────────────────────────────────────────────

VALID_DEPTS = ("MR", "MS", "MI", "ME", "MC", "FS")


def _safe_str(value) -> str:
    """Safely convert a value to a stripped uppercase string."""
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return ""
    return str(value).strip().upper()


def _get_col(df: pd.DataFrame, name: str) -> Optional[str]:
    """Get column name if it exists in the DataFrame."""
    if name in df.columns:
        return name
    return None


def _parse_date(value) -> Optional[datetime]:
    """Parse a date value from the DataFrame."""
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime()
    s = str(value).strip()
    if not s:
        return None
    # Try common formats
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%m/%d/%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    # Try Excel serial number
    try:
        serial = float(s)
        return datetime(1899, 12, 30) + pd.Timedelta(days=serial)
    except (ValueError, OverflowError):
        pass
    return None


# ─── Step 1: Apply Filters ─────────────────────────────────────────────────────

def apply_filters(
    df: pd.DataFrame,
    unit_filter: list[str],
    type_filter: list[str],
    dept_filter: list[str],
    user_status_filter: list[str],
    system_status_filter: list[str],
    start_date: Optional[str],
    end_date: Optional[str],
    age_filter: int,
    id_filter: list[str] = None,
) -> pd.DataFrame:
    """Apply all dashboard filters to the normalized DataFrame."""
    result = df.copy()

    wc_col = _get_col(result, "work_center")
    type_col = _get_col(result, "notification_type")
    status_col = _get_col(result, "status")
    sys_status_col = _get_col(result, "system_status")
    date_col = _get_col(result, "created_date")

    # Unit filter
    if unit_filter and wc_col:
        upper_units = [u.upper() for u in unit_filter]

        def match_unit(wc):
            wc_str = _safe_str(wc)
            for prefix in VALID_DEPTS:
                if wc_str.startswith(prefix):
                    plant = wc_str[len(prefix):]
                    return plant in upper_units
            return False

        result = result[result[wc_col].apply(match_unit)]

    # ID filter
    id_col = _get_col(result, "notification_id")
    if id_filter and id_col:
        result = result[result[id_col].astype(str).isin(id_filter)]

    # Type filter
    if type_filter and type_col:
        upper_types = [t.upper().replace(" ", "") for t in type_filter]
        result = result[
            result[type_col].apply(
                lambda x: _safe_str(x).replace(" ", "") in upper_types
            )
        ]

    # Department filter
    if dept_filter and wc_col:
        upper_depts = [d.upper() for d in dept_filter]

        def match_dept(wc):
            wc_str = _safe_str(wc)
            prefix = wc_str[:2]
            return prefix in upper_depts

        result = result[result[wc_col].apply(match_dept)]

    # User status filter
    if user_status_filter and status_col:
        def match_user_status(status_val):
            raw = _safe_str(status_val)
            for f_status in user_status_filter:
                f_upper = f_status.upper()
                if f_upper == "(BLANKS)" and not raw:
                    return True
                if f_upper in raw:
                    return True
            return False

        result = result[result[status_col].apply(match_user_status)]

    # System status filter
    if system_status_filter and sys_status_col:
        def match_sys_status(status_val):
            raw = _safe_str(status_val)
            for f_status in system_status_filter:
                f_upper = f_status.upper()
                if f_upper == "NOPR" and "NOPR ORAS" in raw:
                    continue
                if f_upper in raw:
                    return True
            return False

        result = result[result[sys_status_col].apply(match_sys_status)]

    # Date range filter
    if start_date and end_date and date_col:
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            start_dt = start_dt.replace(hour=0, minute=0, second=0)
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            end_dt = end_dt.replace(hour=23, minute=59, second=59)

            def in_date_range(val):
                d = _parse_date(val)
                if d is None:
                    return False
                return start_dt <= d <= end_dt

            result = result[result[date_col].apply(in_date_range)]
        except ValueError:
            logger.warning(f"Invalid date range: {start_date} to {end_date}")

    # Age filter (notifications from the last N days)
    if age_filter and age_filter > 0 and date_col:
        threshold = datetime.now()
        threshold = threshold.replace(hour=0, minute=0, second=0, microsecond=0)
        threshold = threshold - pd.Timedelta(days=age_filter)

        def passes_age(val):
            d = _parse_date(val)
            if d is None:
                return False
            return d >= threshold

        result = result[result[date_col].apply(passes_age)]

    return result


# ─── Step 2: Extract notification records from filtered DataFrame ──────────────

def extract_notifications(df: pd.DataFrame) -> list[dict]:
    """Convert filtered DataFrame rows into notification dicts."""
    wc_col = _get_col(df, "work_center")
    type_col = _get_col(df, "notification_type")
    status_col = _get_col(df, "status")
    sys_status_col = _get_col(df, "system_status")
    date_col = _get_col(df, "created_date")
    notif_id_col = _get_col(df, "notification_id")
    desc_col = _get_col(df, "description")
    desc2_col = _get_col(df, "description_2")

    notifications = []
    for _, row in df.iterrows():
        notif_id = _safe_str(row.get(notif_id_col, "")) if notif_id_col else ""
        if not notif_id:
            continue

        work_ctr = _safe_str(row.get(wc_col, "")) if wc_col else ""
        notif_type = _safe_str(row.get(type_col, "")) if type_col else ""
        status = _safe_str(row.get(status_col, "")) if status_col else ""
        sys_status = _safe_str(row.get(sys_status_col, "")) if sys_status_col else ""

        desc1 = str(row.get(desc_col, "") or "").strip() if desc_col else ""
        desc2 = str(row.get(desc2_col, "") or "").strip() if desc2_col else ""
        description = (desc1 + " " + desc2).strip() if desc2 else desc1

        notif_date_raw = row.get(date_col) if date_col else None
        notif_date = _parse_date(notif_date_raw)
        notif_date_str = notif_date.strftime("%Y-%m-%d") if notif_date else "N/A"

        notifications.append({
            "id": notif_id,
            "workCtr": work_ctr,
            "type": notif_type,
            "status": status,
            "sysStatus": sys_status,
            "description": description,
            "notifDate": notif_date_str,
        })

    return notifications


# ─── Step 3: Routing Rules ─────────────────────────────────────────────────────

def get_plant_config(plant_name: str) -> dict | None:
    """Look up the email configuration for a given plant name."""
    for config in EMAIL_CONFIG:
        if config["plantName"].upper() == plant_name.upper():
            return config
    return None


def determine_target_email(notification: dict) -> str:
    """
    Routing Rules:
      1. Prefix Extraction: MR (Rotary) or MS (Static)
      2. Process Team Override: type M1/M2/M6 AND status PENDING/APRE/JBCO/JBPR
      3. Departmental Routing: MR -> rotaryMail, MS -> staticMail
      4. Fallback: processEmail -> rotaryMail -> staticMail
    """
    raw_unit = notification["workCtr"].strip().upper()
    prefix = ""
    plant_name = raw_unit

    if raw_unit.startswith("MR") or raw_unit.startswith("MS"):
        prefix = raw_unit[:2]
        plant_name = raw_unit[2:].strip()

    config = get_plant_config(plant_name)
    if not config:
        return ""

    type_code = notification["type"].strip().upper()
    status = notification["status"].strip().upper()

    # Rule 2: Process Team Override
    is_process_type = type_code in ("M1", "M2", "M6")
    is_process_status = (
        status == "PENDING"
        or "APRE" in status
        or "JBCO" in status
        or "JBPR" in status
    )

    if is_process_type and is_process_status:
        if config.get("processEmail"):
            return config["processEmail"]

    # Rule 3: Departmental Routing
    if prefix == "MR" and config.get("rotaryMail"):
        return config["rotaryMail"]
    elif prefix == "MS" and config.get("staticMail"):
        return config["staticMail"]

    # Rule 4: Fallback
    for mail_key in ("processEmail", "rotaryMail", "staticMail"):
        if config.get(mail_key):
            return config[mail_key]

    return ""


# ─── Step 4: Grouping & Email Generation ───────────────────────────────────────

def generate_email_body(notifications: list[dict], age_filter: int) -> tuple[str, str]:
    """Generate email subject and HTML body for a group of notifications."""
    sample = notifications[0]
    raw_unit = sample["workCtr"].strip().upper()
    plant_name = raw_unit
    if raw_unit.startswith("MR") or raw_unit.startswith("MS"):
        plant_name = raw_unit[2:].strip()

    if age_filter > 0:
        age_label = "day" if age_filter == 1 else "days"
        subject = f"Pending Notifications - {plant_name} (Last {age_filter} {age_label})"
        age_text = f"for the last <strong>{age_filter} {age_label}</strong>"
    else:
        subject = f"Pending Notifications - {plant_name}"
        age_text = ""

    now = datetime.now()

    # Build table rows
    headers = [
        "S.No.", "Plant Name", "Notification No", "Notification Date",
        "Type", "Description", "Days", "User Status", "System Status",
    ]

    header_cells = "".join(
        f'<th style="background-color:#003865; color:#ffffff; padding:10px 12px; '
        f'border:1px solid #002a4e; font-size:13px; font-weight:600; '
        f'text-align:left; white-space:nowrap;">{h}</th>'
        for h in headers
    )

    data_rows = []
    for i, n in enumerate(notifications):
        days_pending = "0"
        if n["notifDate"] and n["notifDate"] != "N/A":
            try:
                notif_d = datetime.strptime(n["notifDate"], "%Y-%m-%d")
                diff_time = abs((now - notif_d).total_seconds())
                days_pending = str(math.ceil(diff_time / (60 * 60 * 24)))
            except ValueError:
                pass

        raw_desc = n["description"].replace("\r", " ").replace("\n", " ")
        date_str = n["notifDate"] if n["notifDate"] != "N/A" else ""

        bg = "#f8f9fa" if i % 2 == 0 else "#ffffff"
        cell_style = (
            f'style="padding:8px 12px; border:1px solid #dee2e6; '
            f'font-size:13px; background-color:{bg}; white-space:nowrap;"'
        )
        desc_style = (
            f'style="padding:8px 12px; border:1px solid #dee2e6; '
            f'font-size:13px; background-color:{bg}; '
            f'max-width:280px; word-wrap:break-word; white-space:normal;"'
        )

        row_html = (
            f"<td {cell_style}>{i + 1}</td>"
            f"<td {cell_style}>{n['workCtr']}</td>"
            f"<td {cell_style}>{n['id']}</td>"
            f"<td {cell_style}>{date_str}</td>"
            f"<td {cell_style}>{n['type']}</td>"
            f"<td {desc_style}>{raw_desc}</td>"
            f"<td {cell_style}>{days_pending}</td>"
            f"<td {cell_style}>{n['status']}</td>"
            f"<td {cell_style}>{n['sysStatus']}</td>"
        )
        data_rows.append(f"<tr>{row_html}</tr>")

    pending_msg = f"Please find below the notifications pending {age_text}:" if age_text else "Please find below all pending notifications:"

    html_body = f"""\
<html>
<body style="font-family: Arial, sans-serif; color: #333; margin: 0; padding: 20px;">
    <p style="font-size: 14px;">Dear Sir,</p>
    <p style="font-size: 14px;">{pending_msg}</p>

    <table style="border-collapse: collapse; width: 100%; margin: 20px 0; font-family: Arial, sans-serif;">
        <thead>
            <tr>{header_cells}</tr>
        </thead>
        <tbody>
            {''.join(data_rows)}
        </tbody>
    </table>

    <p style="font-size: 14px;">Kindly take necessary action.</p>
    <br/>
    <p style="font-size: 14px; margin: 0;">Regards,</p>
    <p style="font-size: 14px; font-weight: bold; margin: 4px 0 0 0;">Mechanical Maintenance Team</p>
</body>
</html>"""

    return subject, html_body


# ─── Step 5: Main orchestrator ─────────────────────────────────────────────────

def send_group_emails(
    df: pd.DataFrame,
    unit_filter: list[str],
    type_filter: list[str],
    dept_filter: list[str],
    user_status_filter: list[str],
    system_status_filter: list[str],
    start_date: Optional[str],
    end_date: Optional[str],
    age_filter: int,
    id_filter: list[str] = None,
) -> dict:
    """
    Full pipeline: filter → extract → route → group → generate body → send.
    """
    # Step 1: Apply filters
    filtered_df = apply_filters(
        df,
        unit_filter=unit_filter,
        type_filter=type_filter,
        dept_filter=dept_filter,
        user_status_filter=user_status_filter,
        system_status_filter=system_status_filter,
        start_date=start_date,
        end_date=end_date,
        age_filter=age_filter,
        id_filter=id_filter,
    )

    logger.info(f"Filtered DataFrame: {len(filtered_df)} rows (from {len(df)} total)")

    if filtered_df.empty:
        return {"sent_count": 0, "errors": [], "groups": {},
                "message": "No notifications match the applied filters."}

    # Step 2: Extract notification records
    notifications = extract_notifications(filtered_df)

    # Only keep MR/MS notifications (matching frontend behavior)
    notifications = [
        n for n in notifications
        if n["workCtr"].startswith("MR") or n["workCtr"].startswith("MS")
    ]

    if not notifications:
        return {"sent_count": 0, "errors": [], "groups": {},
                "message": "No MR/MS notifications found after filtering."}

    logger.info(f"Extracted {len(notifications)} MR/MS notifications for email routing")

    # Step 3 & 4: Route and group by target email
    groups: dict[str, list[dict]] = {}
    for notif in notifications:
        target_email = determine_target_email(notif)
        if target_email:
            if target_email not in groups:
                groups[target_email] = []
            groups[target_email].append(notif)

    if not groups:
        return {"sent_count": 0, "errors": [], "groups": {},
                "message": "No valid email targets resolved."}
    logger.info(f"EMAIL GROUPS: {groups.keys()}")

    # Step 5: Generate & send
    sent_count = 0
    errors = []

    try:
        server = None
        if settings.SMTP_HOST and settings.SMTP_USER:
            server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT)
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        else:
            logger.warning(
                "SMTP credentials not configured. Running in DRY RUN mode."
            )

        for target_email, notifs in groups.items():
            subject, text_body = generate_email_body(notifs, age_filter)

            msg = MIMEMultipart()
            msg["From"] = settings.SMTP_FROM_EMAIL
            msg["To"] = target_email
            msg["Subject"] = subject
            msg.attach(MIMEText(text_body, "html"))

            if server:
                server.send_message(msg)
                sent_count += 1
                logger.info(
                    f"✅ Sent email to {target_email} "
                    f"with {len(notifs)} notifications."
                )
            else:
                logger.info(
                    f"[DRY RUN] Would send email to {target_email}:\n"
                    f"  Subject: {subject}\n"
                    f"  Notifications: {len(notifs)}\n"
                    f"  Body length: {len(text_body)} chars"
                )
                sent_count += 1

        if server:
            server.quit()

    except Exception as e:
        logger.error(f"SMTP error: {e}")
        errors.append(str(e))

    return {
        "sent_count": sent_count,
        "total_notifications": sum(len(n) for n in groups.values()),
        "errors": errors,
        "groups": {email: len(notifs) for email, notifs in groups.items()},
    }
