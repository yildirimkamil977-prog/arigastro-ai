"""TCMB (Turkish Central Bank) Exchange Rate Service.
Fetches EUR/USD/GBP rates from TCMB XML feed and caches them.
"""
import logging
import time
import xml.etree.ElementTree as ET
import httpx

logger = logging.getLogger("tcmb_exchange")

TCMB_URL = "https://www.tcmb.gov.tr/kurlar/today.xml"
CACHE_TTL = 3600  # 1 hour

_cache = {
    "rates": {},
    "fetched_at": 0,
}


def _fetch_rates_sync() -> dict:
    """Fetch exchange rates from TCMB XML (synchronous)."""
    try:
        resp = httpx.get(TCMB_URL, timeout=15, headers={"User-Agent": "AriGastro/1.0"})
        if resp.status_code != 200:
            logger.warning(f"TCMB HTTP {resp.status_code}")
            return {}
        root = ET.fromstring(resp.content)
        rates = {"TRY": 1.0}
        for currency in root.findall("Currency"):
            code = currency.get("CurrencyCode")
            forex_buying = currency.find("ForexBuying")
            forex_selling = currency.find("ForexSelling")
            if code and forex_buying is not None and forex_buying.text:
                try:
                    buying = float(forex_buying.text)
                    selling = float(forex_selling.text) if forex_selling is not None and forex_selling.text else buying
                    # Use midpoint rate
                    rates[code] = round((buying + selling) / 2, 4)
                except (ValueError, TypeError):
                    pass
        logger.info(f"TCMB rates fetched: EUR={rates.get('EUR')}, USD={rates.get('USD')}")
        return rates
    except Exception as e:
        logger.error(f"TCMB fetch error: {e}")
        return {}


def get_exchange_rates() -> dict:
    """Get cached exchange rates. Returns {currency_code: rate_in_TRY}."""
    now = time.time()
    if _cache["rates"] and (now - _cache["fetched_at"]) < CACHE_TTL:
        return _cache["rates"]
    rates = _fetch_rates_sync()
    if rates:
        _cache["rates"] = rates
        _cache["fetched_at"] = now
    return _cache["rates"] or {"TRY": 1.0, "EUR": 38.0, "USD": 36.0}


def force_refresh_rates() -> dict:
    """Force refresh exchange rates from TCMB, ignoring cache."""
    rates = _fetch_rates_sync()
    if rates:
        _cache["rates"] = rates
        _cache["fetched_at"] = time.time()
        logger.info(f"TCMB rates force refreshed: EUR={rates.get('EUR')}, USD={rates.get('USD')}")
    return _cache["rates"] or {"TRY": 1.0, "EUR": 38.0, "USD": 36.0}


def convert_to_tl(amount: float, currency: str) -> float:
    """Convert amount in given currency to TRY."""
    if not amount:
        return 0.0
    currency = currency.upper()
    if currency in ("TRY", "TL"):
        return amount
    rates = get_exchange_rates()
    rate = rates.get(currency)
    if not rate:
        logger.warning(f"No TCMB rate for {currency}, using fallback")
        return amount
    return round(amount * rate, 2)


def convert_from_tl(tl_amount: float, currency: str) -> float:
    """Convert TRY amount to given currency."""
    if not tl_amount:
        return 0.0
    currency = currency.upper()
    if currency in ("TRY", "TL"):
        return tl_amount
    rates = get_exchange_rates()
    rate = rates.get(currency)
    if not rate or rate == 0:
        logger.warning(f"No TCMB rate for {currency}, using fallback")
        return tl_amount
    return round(tl_amount / rate, 2)


def get_rate(currency: str) -> float:
    """Get the TRY rate for a single currency."""
    currency = currency.upper()
    if currency in ("TRY", "TL"):
        return 1.0
    rates = get_exchange_rates()
    return rates.get(currency, 0)
