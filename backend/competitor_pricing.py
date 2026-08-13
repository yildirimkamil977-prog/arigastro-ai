"""Competitor Price Tracking — Product matching, price scraping, auto-pricing."""
import os
import re
import json
import logging
import asyncio
import requests as req_sync
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup

logger = logging.getLogger("competitor_pricing")

SCRAPERAPI_KEY = os.environ.get("SCRAPERAPI_KEY", "")
TR_TO_ASCII = str.maketrans("ıİşŞğĞüÜöÖçÇ", "iIsSgGuUoOcC")

COMPETITORS = {
    "mutfak10": {"domain": "mutfak10.com", "name": "Mutfak10", "icon": "🟠", "base_url": "https://www.mutfak10.com"},
    "cafemarkt": {"domain": "cafemarkt.com", "name": "Cafemarkt", "icon": "🔵", "base_url": "https://www.cafemarkt.com"},
    "mutbex": {"domain": "mutbex.com", "name": "Mutbex", "icon": "🟢", "base_url": "https://www.mutbex.com"},
    "hakbilenler": {"domain": "shop.hakbilenler.com.tr", "name": "Hakbilenler", "icon": "🟣", "base_url": "https://shop.hakbilenler.com.tr"},
}


def search_competitor_product(product_name: str, competitor_key: str) -> dict:
    """Search for a product on a competitor site using Google."""
    if not SCRAPERAPI_KEY:
        return {"matched": False, "error": "ScraperAPI key missing"}
    
    comp = COMPETITORS.get(competitor_key)
    if not comp:
        return {"matched": False, "error": f"Unknown competitor: {competitor_key}"}
    
    search_name = " ".join(product_name.split()[:6])
    ascii_name = search_name.translate(TR_TO_ASCII)
    
    try:
        resp = req_sync.get("https://api.scraperapi.com/structured/google/search", params={
            "api_key": SCRAPERAPI_KEY,
            "query": f"site:{comp['domain']} {ascii_name}",
            "country_code": "tr",
            "tld": "com.tr",
            "num": "5",
        }, timeout=25)
        
        if resp.status_code != 200:
            return {"matched": False, "error": f"SERP API {resp.status_code}"}
        
        results = resp.json().get("organic_results", [])
        if not results:
            return {"matched": False, "error": "No results"}
        
        # Return best match
        best = results[0]
        return {
            "matched": True,
            "url": best.get("link", ""),
            "title": best.get("title", ""),
            "snippet": best.get("snippet", ""),
            "competitor_key": competitor_key,
            "competitor_name": comp["name"],
        }
    except Exception as e:
        return {"matched": False, "error": str(e)}


def scrape_competitor_price(url: str, competitor_key: str) -> dict:
    """Scrape the price from a competitor product page."""
    if not SCRAPERAPI_KEY:
        return {"success": False, "error": "ScraperAPI key missing"}
    
    try:
        resp = req_sync.get("http://api.scraperapi.com", params={
            "api_key": SCRAPERAPI_KEY,
            "url": url,
            "render": "true",
        }, timeout=45)
        
        if resp.status_code != 200:
            return {"success": False, "error": f"HTTP {resp.status_code}"}
        
        soup = BeautifulSoup(resp.text, "html.parser")
        price = _extract_price(soup, competitor_key)
        
        if price and price > 0:
            return {
                "success": True,
                "price": price,
                "currency": "TRY",
                "scraped_at": datetime.now(timezone.utc).isoformat(),
            }
        else:
            return {"success": False, "error": "Price not found on page"}
    
    except Exception as e:
        return {"success": False, "error": str(e)}


def _extract_price(soup: BeautifulSoup, competitor_key: str) -> float:
    """Extract price from competitor page HTML."""
    
    # Strategy 1: Schema.org / JSON-LD (returns price as number or string)
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string)
            if isinstance(data, list):
                data = data[0]
            offers = data.get("offers", data.get("Offers", {}))
            if isinstance(offers, list):
                offers = offers[0]
            p = offers.get("price") or offers.get("lowPrice")
            if p:
                return _parse_price_smart(str(p))
        except:
            pass
    
    # Strategy 2: Meta tags
    for meta in soup.find_all("meta"):
        prop = meta.get("property", "") or meta.get("name", "")
        if "price" in prop.lower() and "amount" in prop.lower():
            try:
                return _parse_price_smart(meta.get("content", "0"))
            except:
                pass
    
    # Strategy 3: itemprop="price"
    for el in soup.find_all(attrs={"itemprop": "price"}):
        try:
            val = el.get("content") or el.get_text(strip=True)
            return _parse_price_smart(val)
        except:
            pass
    
    # Strategy 4: Common CSS classes
    price_selectors = [
        ".product-price", ".current-price", ".sales-price", ".discounted-price",
        ".price-new", ".product-info-price", "[data-price]", ".product_price",
        ".price--sale", ".price-box__price", ".ty-price-num", ".price_color",
    ]
    for selector in price_selectors:
        for el in soup.select(selector):
            text = el.get_text(strip=True)
            p = _parse_turkish_price(text)
            if p and p > 10:
                return p
    
    # Strategy 5: Regex on page text for TL prices
    text = soup.get_text()
    patterns = [
        r'([\d.]+[.,]\d{2})\s*(?:TL|₺)',
        r'(?:TL|₺)\s*([\d.]+[.,]\d{2})',
    ]
    for pattern in patterns:
        matches = re.findall(pattern, text)
        for m in matches:
            p = _parse_turkish_price(m)
            if p and p > 10:
                return p
    
    return None


def _parse_price_smart(text: str) -> float:
    """Smart price parser: handles both '970.74' (English) and '1.234,56' (Turkish) formats."""
    if not text:
        return None
    try:
        clean = re.sub(r'[^\d.,]', '', text.strip())
        if not clean:
            return None
        
        # Case 1: Only digits (e.g. "97074") → treat as integer
        if "." not in clean and "," not in clean:
            return float(clean)
        
        # Case 2: Has comma AND dot → Turkish format "1.234,56"
        if "," in clean and "." in clean:
            # Turkish: dots are thousands, comma is decimal
            return float(clean.replace(".", "").replace(",", "."))
        
        # Case 3: Only dot, no comma
        if "." in clean and "," not in clean:
            # Check if dot is decimal or thousands separator
            parts = clean.split(".")
            if len(parts) == 2 and len(parts[1]) <= 2:
                # "970.74" → English decimal (2 or fewer decimal digits)
                return float(clean)
            elif len(parts) == 2 and len(parts[1]) == 3:
                # "970.740" or "1.234" → could be thousands separator
                # If first part <= 3 digits, likely thousands: "1.234" → 1234
                return float(clean.replace(".", ""))
            else:
                # Multiple dots: "1.234.567" → thousands separators
                return float(clean.replace(".", ""))
        
        # Case 4: Only comma, no dot → "970,74" Turkish decimal
        if "," in clean:
            return float(clean.replace(",", "."))
        
        return float(clean)
    except:
        return None


def _parse_turkish_price(text: str) -> float:
    """Parse Turkish formatted price: '1.234,56 TL' -> 1234.56"""
    if not text:
        return None
    try:
        clean = re.sub(r'[^\d.,]', '', text.strip())
        if not clean:
            return None
        # Turkish format: 1.234,56
        if "," in clean and "." in clean:
            clean = clean.replace(".", "").replace(",", ".")
        elif "," in clean:
            clean = clean.replace(",", ".")
        return float(clean)
    except:
        return None


def match_all_competitors_for_product(product_name: str) -> dict:
    """Match a product across all competitor sites."""
    results = {}
    for key in COMPETITORS:
        result = search_competitor_product(product_name, key)
        results[key] = result
        import time
        time.sleep(0.5)
    return results


def scrape_all_competitor_prices(matches: dict) -> dict:
    """Scrape prices from all matched competitor URLs."""
    prices = {}
    for comp_key, match in matches.items():
        if match.get("url"):
            result = scrape_competitor_price(match["url"], comp_key)
            if result.get("success"):
                prices[comp_key] = {
                    "price": result["price"],
                    "url": match["url"],
                    "competitor_name": COMPETITORS[comp_key]["name"],
                    "scraped_at": result["scraped_at"],
                }
            import time
            time.sleep(0.5)
    return prices


def calculate_optimal_price(competitor_prices: dict, current_price: float, floor_price: float, undercut_amount: float = 100) -> dict:
    """Calculate the optimal price based on competitor prices and floor price."""
    if not competitor_prices:
        return {"action": "no_change", "reason": "Rakip fiyatı bulunamadı"}
    
    cheapest_comp = min(competitor_prices.items(), key=lambda x: x[1]["price"])
    cheapest_price = cheapest_comp[1]["price"]
    cheapest_name = cheapest_comp[1]["competitor_name"]
    
    if current_price <= cheapest_price:
        return {
            "action": "no_change",
            "reason": f"Zaten en ucuz (bizim: {current_price:.2f} TL, en ucuz rakip: {cheapest_name} {cheapest_price:.2f} TL)",
            "cheapest_competitor": cheapest_name,
            "cheapest_price": cheapest_price,
        }
    
    target_price = cheapest_price - undercut_amount
    
    if target_price < floor_price:
        return {
            "action": "floor_hit",
            "reason": f"Hedef fiyat ({target_price:.2f} TL) dip fiyatın ({floor_price:.2f} TL) altında. Fiyat değiştirilmedi.",
            "target_price": target_price,
            "floor_price": floor_price,
            "cheapest_competitor": cheapest_name,
            "cheapest_price": cheapest_price,
        }
    
    return {
        "action": "update",
        "new_price": target_price,
        "old_price": current_price,
        "savings": current_price - target_price,
        "reason": f"En ucuz rakip: {cheapest_name} ({cheapest_price:.2f} TL). Yeni fiyat: {target_price:.2f} TL",
        "cheapest_competitor": cheapest_name,
        "cheapest_price": cheapest_price,
    }
