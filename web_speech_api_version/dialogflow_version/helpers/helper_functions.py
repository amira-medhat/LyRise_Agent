from datetime import datetime, timedelta
import pytz

LOCAL_TIMEZONE = pytz.timezone("Africa/Cairo")


def parse_datetime_param(date_param):
    """Parse a datetime parameter from LLM or JSON input, keeping local time unchanged."""
    try:
        if isinstance(date_param, str):
            # If contains timezone (like +02:00), remove it manually
            if "+" in date_param:
                date_param = date_param.split("+")[0]
            if "Z" in date_param:
                date_param = date_param.replace("Z", "")
            appointment_dt = datetime.fromisoformat(date_param)
        elif isinstance(date_param, dict):
            if "date_time" in date_param:
                date_param = date_param["date_time"]
                if "+" in date_param:
                    date_param = date_param.split("+")[0]
                if "Z" in date_param:
                    date_param = date_param.replace("Z", "")
                appointment_dt = datetime.fromisoformat(date_param)
            elif "startDate" in date_param:
                date_param = date_param["startDate"]
                if "+" in date_param:
                    date_param = date_param.split("+")[0]
                appointment_dt = datetime.fromisoformat(date_param)
            elif "date" in date_param and "time" in date_param:
                appointment_dt = datetime.fromisoformat(f"{date_param['date']}T{date_param['time']}")
            else:
                raise ValueError("Unrecognized date-time structure")
        else:
            raise ValueError("Unsupported type for date_param")

        # Do NOT apply timezone conversion; keep it local as in DB
        return appointment_dt

    except Exception as e:
        print(f"[ERROR] parse_datetime_param failed: {e} — Input was: {date_param}")
        return None


def parse_date_range_param(date_param):
    """Parse date or date range for listing schedules."""
    start_dt = None
    end_dt = None
    try:
        if isinstance(date_param, str):
            parsed_dt = datetime.fromisoformat(date_param)
            start_dt = LOCAL_TIMEZONE.localize(parsed_dt.replace(hour=0, minute=0, second=0, microsecond=0))
            end_dt = start_dt + timedelta(days=1)
        elif isinstance(date_param, dict) and "startDate" in date_param:
            parsed_start = datetime.fromisoformat(date_param["startDate"])
            parsed_end = datetime.fromisoformat(date_param["endDate"])
            start_dt = LOCAL_TIMEZONE.localize(parsed_start.replace(hour=0, minute=0, second=0, microsecond=0))
            end_dt = LOCAL_TIMEZONE.localize(parsed_end.replace(hour=0, minute=0, second=0, microsecond=0))
            if start_dt.date() == end_dt.date():
                end_dt += timedelta(days=1)
    except Exception as e:
        print(f"[ERROR] parse_date_range_param failed: {e}")
    return start_dt, end_dt

