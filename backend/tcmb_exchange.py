"""Exchange Rate Service — uses CurrencyAPI (same source as İkas).
Fetches EUR/USD/GBP rates and caches them.
"""
import logging
import time
import httpx

logger = logging.getLogger("exchange_rates")

CACHE_TTL = 3600  # 1 hour

_cache = {
    "rates": {},
    "fetched_at": 0,
}


def _get_api_key() -> str:
    import os
    return os.environ.get("CURRENCY_API_KEY", "")


def _fetch_rates_sync() -> dict:
    """Fetch exchange rates from CurrencyAPI.com (same source as İkas)."""
    api_key = _get_api_key()
    if not api_key:
        logger.warning("CURRENCY_API_KEY not set, falling back to open.er-api.com")
        return _fetch_rates_fallback()
    
    try:
        resp = httpx.get(
            "https://api.currencyapi.com/v3/latest",
            params={"apikey": api_key, "base_currency": "TRY", "currencies": "EUR,USD,GBP,CHF,SEK,NOK,DKK,JPY,CNY,RUB"},
            timeout=15,
        )
        if resp.status_code != 200:
            logger.warning(f"CurrencyAPI HTTP {resp.status_code}: {resp.text[:200]}")
            return _fetch_rates_fallback()
        
        data = resp.json().get("data", {})
        if not data:
            return _fetch_rates_fallback()
        
        # CurrencyAPI returns rates with TRY as base → 1 TRY = X EUR
        # We need: 1 EUR = X TRY (how much TRY per 1 unit of foreign currency)
        rates = {"TRY": 1.0}
        for cur, info in data.items():
            val = info.get("value", 0)
            if val and val > 0:
                rates[cur] = round(1.0 / val, 6)  # Invert: 1 EUR = 1/rate TRY
        
        logger.info(f"CurrencyAPI rates fetched: EUR={rates.get('EUR')}, USD={rates.get('USD')}")
        return rates
    except Exception as e:
        logger.error(f"CurrencyAPI fetch error: {e}")
        return _fetch_rates_fallback()


def _fetch_rates_fallback() -> dict:
    """Fallback: fetch from open.er-api.com (no key needed)."""
    try:
        resp = httpx.get("https://open.er-api.com/v6/latest/TRY", timeout=15)
        if resp.status_code != 200:
            return {}
        data = resp.json().get("rates", {})
        rates = {"TRY": 1.0}
        for cur in ["EUR", "USD", "GBP", "CHF", "SEK", "NOK", "DKK", "JPY", "CNY", "RUB"]:
            val = data.get(cur, 0)
            if val and val > 0:
                rates[cur] = round(1.0 / val, 6)
        logger.info(f"Fallback rates fetched: EUR={rates.get('EUR')}, USD={rates.get('USD')}")
        return rates
    except Exception as e:
        logger.error(f"Fallback rate fetch error: {e}")
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
    return _cache["rates"] or {"TRY": 1.0, "EUR": 55.0, "USD": 47.0}


def force_refresh_rates() -> dict:
    """Force refresh exchange rates, ignoring cache."""
    rates = _fetch_rates_sync()
    if rates:
        _cache["rates"] = rates
        _cache["fetched_at"] = time.time()
        logger.info(f"Rates force refreshed: EUR={rates.get('EUR')}, USD={rates.get('USD')}")
    return _cache["rates"] or {"TRY": 1.0, "EUR": 55.0, "USD": 47.0}


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
        logger.warning(f"No rate for {currency}")
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
        logger.warning(f"No rate for {currency}")
        return tl_amount
    return round(tl_amount / rate, 2)


def get_rate(currency: str) -> float:
    """Get the TRY rate for a single currency."""
    currency = currency.upper()
    if currency in ("TRY", "TL"):
        return 1.0
    rates = get_exchange_rates()
    return rates.get(currency, 0)
