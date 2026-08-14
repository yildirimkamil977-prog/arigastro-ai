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


def _normalize_text(text: str) -> str:
    """Normalize text for comparison: lowercase, remove special chars, Turkish→ASCII."""
    if not text:
        return ""
    t = text.lower().translate(TR_TO_ASCII)
    t = re.sub(r'[^a-z0-9\s]', ' ', t)
    return ' '.join(t.split())


def _text_similarity(a: str, b: str) -> float:
    """Simple word-overlap similarity between two texts (0-1)."""
    words_a = set(_normalize_text(a).split())
    words_b = set(_normalize_text(b).split())
    if not words_a or not words_b:
        return 0
    intersection = words_a & words_b
    return len(intersection) / max(len(words_a), len(words_b))


# URL patterns that indicate a PRODUCT page (not category/homepage)
_PRODUCT_URL_PATTERNS = {
    "mutfak10":    ["/urun/"],
    "cafemarkt":   [],  # cafemarkt uses direct slugs like /product-name
    "mutbex":      [],  # mutbex uses direct slugs like /product-name
    "hakbilenler": ["/urun/"],
}

# URL patterns to REJECT (category, search, homepage, pagination)
_REJECT_URL_PATTERNS = [
    "/kategori/", "/category/", "/c/", "/marka/", "/etiket/", "/tag/",
    "/page/", "/search", "/ara?", "?q=", "/sayfa/",
    "/blog/", "/hakkimizda", "/iletisim", "/sepet", "/cart",
]


def _is_valid_product_url(url: str, competitor_key: str) -> bool:
    """Check if a URL looks like a product page, not a category/search/home page."""
    url_lower = url.lower()

    # Reject known non-product patterns
    for pattern in _REJECT_URL_PATTERNS:
        if pattern in url_lower:
            return False

    comp = COMPETITORS.get(competitor_key, {})
    domain = comp.get("domain", "")

    # Check domain matches
    if domain and domain not in url_lower:
        return False

    # Homepage check: URL is just the domain with no path
    from urllib.parse import urlparse
    parsed = urlparse(url)
    path = parsed.path.rstrip("/")
    if not path or path == "":
        return False

    # For sites with known product URL patterns, require them
    required_patterns = _PRODUCT_URL_PATTERNS.get(competitor_key, [])
    if required_patterns:
        if not any(p in url_lower for p in required_patterns):
            return False

    # For cafemarkt/mutbex: URL should have a meaningful slug (at least 10 chars after domain)
    if competitor_key in ("cafemarkt", "mutbex"):
        if len(path) < 10:
            return False

    return True


def _extract_gtin_from_page(html_text: str, soup: BeautifulSoup) -> str:
    """Extract GTIN/barcode from a competitor product page."""
    # 1. JSON-LD
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string)
            if isinstance(data, list):
                data = data[0]
            for field in ["gtin13", "gtin12", "gtin8", "gtin", "ean", "isbn"]:
                val = data.get(field)
                if val and re.match(r'^\d{8,14}$', str(val).strip()):
                    return str(val).strip()
        except:
            pass
    # 2. Meta tags
    for meta in soup.find_all("meta"):
        prop = (meta.get("property", "") + meta.get("name", "")).lower()
        if any(k in prop for k in ["gtin", "barcode", "ean"]):
            val = meta.get("content", "").strip()
            if re.match(r'^\d{8,14}$', val):
                return val
    # 3. itemprop
    for el in soup.find_all(attrs={"itemprop": True}):
        if any(k in el["itemprop"].lower() for k in ["gtin", "barcode", "ean"]):
            val = (el.get("content") or el.get_text(strip=True)).strip()
            if re.match(r'^\d{8,14}$', val):
                return val
    return None


def search_competitor_product(product_name: str, competitor_key: str, brand: str = "", gtin: str = "") -> dict:
    """Multi-signal product matching: GTIN verification + text similarity."""
    if not SCRAPERAPI_KEY:
        return {"matched": False, "error": "ScraperAPI key missing"}

    comp = COMPETITORS.get(competitor_key)
    if not comp:
        return {"matched": False, "error": f"Unknown competitor: {competitor_key}"}

    # Build search query: include brand for better accuracy
    search_name = " ".join(product_name.split()[:8])
    if brand and brand.lower() not in product_name.lower():
        search_name = f"{brand} {search_name}"
    ascii_name = search_name.translate(TR_TO_ASCII)

    try:
        resp = req_sync.get("https://api.scraperapi.com/structured/google/search", params={
            "api_key": SCRAPERAPI_KEY,
            "query": f"site:{comp['domain']} {ascii_name}",
            "country_code": "tr",
            "tld": "com.tr",
            "num": "10",
        }, timeout=25)

        if resp.status_code != 200:
            return {"matched": False, "error": f"SERP API {resp.status_code}"}

        results = resp.json().get("organic_results", [])
        if not results:
            return {"matched": False, "error": "No results"}

        # Score and filter results
        candidates = []

        # Extract "core" product words (exclude brand-like first word and pure numbers/units)
        product_norm = _normalize_text(product_name)
        product_words = product_norm.split()
        skip_words = {"cm", "lt", "mm", "kg", "gr", "ml", "adet", "li", "lu", "x", "set", "seri", "ve", "ic", "dis", "icin"}
        core_words = set()
        for w in product_words:
            if w in skip_words or re.match(r'^\d+x?\d*$', w):
                continue
            # Skip if it looks like a brand (first word or very short)
            core_words.add(w)
        # Remove the first word (usually brand) from core to avoid brand-only matches
        if product_words:
            core_words.discard(product_words[0])

        for r in results:
            url = r.get("link", "")
            title = r.get("title", "")

            # Step 1: Must be a valid product URL
            if not _is_valid_product_url(url, competitor_key):
                continue

            # Step 2: Core keyword check — at least 1 core product word must appear in title
            title_norm = _normalize_text(title)
            title_words_set = set(title_norm.split())
            core_overlap = core_words & title_words_set
            if len(core_words) >= 2 and len(core_overlap) == 0:
                continue  # No core product word found in title — skip

            # Step 3: Calculate title similarity
            similarity = _text_similarity(product_name, title)

            # Step 4: Number matching (sizes, volumes)
            product_numbers = re.findall(r'\d+', product_norm)
            title_numbers = re.findall(r'\d+', title_norm)
            number_match = len(set(product_numbers) & set(title_numbers)) / max(len(set(product_numbers)), 1) if product_numbers else 0.5

            # Combined score
            score = (similarity * 0.6) + (number_match * 0.4)

            # Bonus for core word overlap
            if core_words:
                core_ratio = len(core_overlap) / len(core_words)
                score = score * (0.5 + 0.5 * core_ratio)

            if score >= 0.20:
                candidates.append({"url": url, "title": title, "score": score})

        if not candidates:
            return {"matched": False, "error": "No quality match found"}

        # Sort candidates by score
        candidates.sort(key=lambda x: x["score"], reverse=True)

        # GTIN VERIFICATION: scrape top candidates to verify via barcode
        if gtin and len(gtin) >= 8:
            for cand in candidates[:3]:
                try:
                    page_resp = req_sync.get("http://api.scraperapi.com", params={
                        "api_key": SCRAPERAPI_KEY, "url": cand["url"],
                    }, timeout=20)
                    if page_resp.status_code == 200:
                        page_soup = BeautifulSoup(page_resp.text, "html.parser")
                        page_gtin = _extract_gtin_from_page(page_resp.text, page_soup)
                        if page_gtin and page_gtin == gtin:
                            return {
                                "matched": True, "url": cand["url"], "title": cand["title"],
                                "score": 1.0, "match_method": "gtin",
                                "competitor_key": competitor_key, "competitor_name": comp["name"],
                            }
                        elif page_gtin and page_gtin != gtin:
                            cand["score"] = 0  # Wrong product
                            continue
                except:
                    pass
                import time; time.sleep(0.5)

        # Return best text-match (exclude disqualified)
        valid = [c for c in candidates if c["score"] >= 0.30]
        if valid:
            best = valid[0]
            return {
                "matched": True, "url": best["url"], "title": best["title"],
                "score": round(best["score"], 3), "match_method": "text",
                "competitor_key": competitor_key, "competitor_name": comp["name"],
            }

        return {"matched": False, "error": f"No quality match (best: {candidates[0]['score']:.2f} after GTIN check)"}
    except Exception as e:
        return {"matched": False, "error": str(e)}


def scrape_competitor_price(url: str, competitor_key: str, retries: int = 2) -> dict:
    """Scrape price: first try fast (no render), then retry with JS render if needed."""
    if not SCRAPERAPI_KEY:
        return {"success": False, "error": "ScraperAPI key missing"}
    
    # Phase 1: Fast scrape without render (3-5 seconds)
    try:
        resp = req_sync.get("http://api.scraperapi.com", params={
            "api_key": SCRAPERAPI_KEY,
            "url": url,
        }, timeout=25)
        
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            price = _extract_price(soup, competitor_key)
            if price and price > 0:
                return {"success": True, "price": price, "currency": "TRY", "scraped_at": datetime.now(timezone.utc).isoformat()}
    except:
        pass
    
    # Phase 2: Retry with JS render (for sites that need it)
    import time; time.sleep(1)
    try:
        resp = req_sync.get("http://api.scraperapi.com", params={
            "api_key": SCRAPERAPI_KEY,
            "url": url,
            "render": "true",
        }, timeout=50)
        
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            price = _extract_price(soup, competitor_key)
            if price and price > 0:
                return {"success": True, "price": price, "currency": "TRY", "scraped_at": datetime.now(timezone.utc).isoformat()}
            return {"success": False, "error": "Price not found on page"}
        return {"success": False, "error": f"HTTP {resp.status_code}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _extract_price(soup: BeautifulSoup, competitor_key: str) -> float:
    """Extract price from competitor page HTML with site-specific strategies."""
    
    # Strategy 1: Schema.org / JSON-LD
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
                parsed = _parse_price_smart(str(p))
                if parsed and parsed > 5:
                    return parsed
        except:
            pass
    
    # Strategy 2: Site-specific selectors
    site_selectors = {
        "mutfak10": [
            ".product-price .current", ".product-price", ".ty-price-num",
            ".ty-price", "[data-price]", ".price-sale", ".sales-price",
        ],
        "cafemarkt": [
            ".product-info-price", ".current-price", ".price-new",
            ".product-price", ".sales-price", ".discounted-price",
            "span.price", ".product_price",
        ],
        "mutbex": [
            ".current-price", ".product-price", ".price",
            ".sales-price", ".product_price", "span.price",
            ".discounted-price", ".price-new",
        ],
        "hakbilenler": [
            ".product-price", ".current-price", ".price",
            ".ty-price-num", "span.price", ".product_price",
        ],
    }
    
    selectors = site_selectors.get(competitor_key, [])
    for selector in selectors:
        for el in soup.select(selector):
            text = el.get_text(strip=True)
            p = _parse_turkish_price(text)
            if p and p > 5:
                return p
            # Also check content attribute
            content = el.get("content")
            if content:
                p = _parse_price_smart(content)
                if p and p > 5:
                    return p
    
    # Strategy 3: Meta tags
    for meta in soup.find_all("meta"):
        prop = (meta.get("property", "") or meta.get("name", "")).lower()
        if "price" in prop:
            content = meta.get("content", "")
            if content:
                p = _parse_price_smart(content)
                if p and p > 5:
                    return p
    
    # Strategy 4: itemprop="price"
    for el in soup.find_all(attrs={"itemprop": "price"}):
        val = el.get("content") or el.get_text(strip=True)
        if val:
            p = _parse_price_smart(val)
            if p and p > 5:
                return p
    
    # Strategy 5: Generic price CSS classes
    generic_selectors = [
        ".product-price", ".current-price", ".sales-price",
        ".price-new", "[data-price]", ".price--sale",
        ".price-box__price", ".price_color", "span.price",
        ".product_price", ".discounted-price", ".woocommerce-Price-amount",
        "ins .amount", ".summary .price",
    ]
    for selector in generic_selectors:
        for el in soup.select(selector):
            text = el.get_text(strip=True)
            p = _parse_turkish_price(text)
            if p and p > 5:
                return p
    
    # Strategy 6: data-price attributes
    for el in soup.find_all(attrs={"data-price": True}):
        p = _parse_price_smart(el["data-price"])
        if p and p > 5:
            return p
    
    # Strategy 7: Broad regex on page text for TL prices
    text = soup.get_text()
    patterns = [
        r'([\d.]+[.,]\d{2})\s*(?:TL|₺|tl)',
        r'(?:TL|₺|tl)\s*([\d.]+[.,]\d{2})',
        r'(?:fiyat|price|tutar)[^\d]{0,20}([\d.]+[.,]\d{2})',
    ]
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for m in matches:
            p = _parse_turkish_price(m)
            if p and p > 5:
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


def match_all_competitors_for_product(product_name: str, brand: str = "", gtin: str = "") -> dict:
    """Match a product across all competitor sites with GTIN verification."""
    results = {}
    for key in COMPETITORS:
        result = search_competitor_product(product_name, key, brand=brand, gtin=gtin)
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
