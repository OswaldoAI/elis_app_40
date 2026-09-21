from datetime import datetime
try:
    from zoneinfo import ZoneInfo
    MADRID_TZ = ZoneInfo("Europe/Madrid")
except Exception:
    MADRID_TZ = None

def get_local_now() -> datetime:
    """Retorna la fecha y hora local actual configurada para Europe/Madrid (España)."""
    if MADRID_TZ:
        try:
            return datetime.now(MADRID_TZ)
        except Exception:
            pass
    return datetime.now()

def get_local_now_str(fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """Retorna la fecha y hora local formateada como string."""
    return get_local_now().strftime(fmt)
