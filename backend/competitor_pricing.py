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
    "mutfak10": {
        "domain": "mutfak10.com", "name": "Mutfak10",
        "base_url": "https://www.mutfak10.com",
        "search_url": "https://www.mutfak10.com/?s={query}&post_type=product",
        "search_needs_render": False,
    },
    "cafemarkt": {
        "domain": "cafemarkt.com", "name": "Cafemarkt",
        "base_url": "https://www.cafemarkt.com",
        "search_url": "https://www.cafemarkt.com/arama?q={query}",
        "search_needs_render": True,
    },
    "mutbex": {
        "domain": "mutbex.com", "name": "Mutbex",
        "base_url": "https://www.mutbex.com",
        "search_url": "https://www.mutbex.com/arama?q={query}",
        "search_needs_render": True,
    },
    "hakbilenler": {
        "domain": "shop.hakbilenler.com.tr", "name": "Hakbilenler",
        "base_url": "https://shop.hakbilenler.com.tr",
        "search_url": "https://shop.hakbilenler.com.tr/?s={query}&post_type=product",
        "search_needs_render": False,
    },
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


def _search_on_site(query: str, competitor_key: str, use_render: bool = None) -> list:
    """Search for products on competitor's own website search. Returns [{url, title}]."""
    comp = COMPETITORS[competitor_key]
    from urllib.parse import quote_plus
    search_url = comp["search_url"].format(query=quote_plus(query))
    params = {"api_key": SCRAPERAPI_KEY, "url": search_url}
    should_render = use_render if use_render is not None else comp.get("search_needs_render", False)
    if should_render:
        params["render"] = "true"
    timeout = 45 if should_render else 20
    try:
        resp = req_sync.get("http://api.scraperapi.com", params=params, timeout=timeout)
        if resp.status_code != 200:
            return []
        soup = BeautifulSoup(resp.text, "html.parser")
        domain = comp["domain"]
        base = comp["base_url"]
        
        # Extract query keywords for relevance filtering
        query_words = set(re.sub(r'[^a-z0-9\s]', ' ', query.lower()).split())
        query_words -= {"ve", "ic", "dis", "icin", "ile", "bir"}
        
        all_links = []
        seen = set()
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            title = a.get_text(strip=True)
            if not title or len(title) < 15:
                continue
            lt = title.lower()
            if any(skip in lt for skip in ["sepete ekle", "yanıt", "iptal", "giriş yap", "kayıt ol", "favoriler", "sepetim", "karşılaştır", "filtre"]):
                continue
            if href.startswith("/"):
                href = base + href
            if domain not in href:
                continue
            if not _is_valid_product_url(href, competitor_key):
                continue
            clean = href.split("?")[0].rstrip("/")
            if clean in seen:
                continue
            seen.add(clean)
            
            # Check relevance: does the link text contain any query keyword?
            title_lower = re.sub(r'[^a-z0-9\s]', ' ', title.lower())
            title_words = set(title_lower.split())
            overlap = query_words & title_words
            relevance = len(overlap) / max(len(query_words), 1)
            
            all_links.append({"url": href, "title": title, "relevance": relevance})
        
        # Sort by relevance, return only relevant links
        all_links.sort(key=lambda x: x["relevance"], reverse=True)
        return [{"url": l["url"], "title": l["title"]} for l in all_links if l["relevance"] > 0][:15]
    except Exception as e:
        logger.warning(f"Site search failed for {competitor_key}: {e}")
        return []


def _search_on_google(query: str, competitor_key: str) -> list:
    """Fallback: Google site: search. Returns [{url, title}]."""
    comp = COMPETITORS[competitor_key]
    try:
        resp = req_sync.get("https://api.scraperapi.com/structured/google/search", params={
            "api_key": SCRAPERAPI_KEY,
            "query": f"site:{comp['domain']} {query}",
            "country_code": "tr", "tld": "com.tr", "num": "10",
        }, timeout=25)
        if resp.status_code != 200:
            return []
        return [{"url": r["link"], "title": r.get("title", "")} for r in resp.json().get("organic_results", []) if _is_valid_product_url(r.get("link", ""), competitor_key)]
    except:
        return []


def search_competitor_product(product_name: str, competitor_key: str, brand: str = "", gtin: str = "") -> dict:
    """Multi-strategy matching: site search → Google fallback → GTIN verification."""
    if not SCRAPERAPI_KEY:
        return {"matched": False, "error": "ScraperAPI key missing"}
    comp = COMPETITORS.get(competitor_key)
    if not comp:
        return {"matched": False, "error": f"Unknown competitor"}

    search_terms = product_name
    if brand and brand.lower() not in product_name.lower():
        search_terms = f"{brand} {product_name}"
    ascii_full = search_terms.translate(TR_TO_ASCII)
    # Short query for site search (works better with fewer words)
    short_words = product_name.split()[:5]
    if brand and brand.lower() not in " ".join(short_words).lower():
        short_words = [brand] + short_words[:4]
    ascii_short = " ".join(short_words).translate(TR_TO_ASCII)

    # Collect candidates from strategies
    candidates_raw = []
    
    # Strategy 1: Site search with short query (fast, no render)
    site_results = _search_on_site(ascii_short, competitor_key, use_render=False)
    candidates_raw.extend(site_results)
    
    # Strategy 1b: Model-number focused query
    model_parts = re.findall(r'[A-Z0-9]{2,}[A-Za-z]*\d+[A-Za-z]*|[A-Za-z]+\d+[A-Za-z]*', product_name)
    if model_parts and len(candidates_raw) < 3:
        short_q = f"{brand} {' '.join(model_parts)}".translate(TR_TO_ASCII) if brand else " ".join(model_parts)
        extra = _search_on_site(short_q, competitor_key, use_render=False)
        seen = {c["url"].split("?")[0].rstrip("/") for c in candidates_raw}
        candidates_raw += [e for e in extra if e["url"].split("?")[0].rstrip("/") not in seen]
    
    # Strategy 2: Google fallback — only if site search found < 2 candidates
    if len(candidates_raw) < 2:
        google_results = _search_on_google(ascii_full, competitor_key)
        seen = {c["url"].split("?")[0].rstrip("/") for c in candidates_raw}
        candidates_raw += [e for e in google_results if e["url"].split("?")[0].rstrip("/") not in seen]

    if not candidates_raw:
        return {"matched": False, "error": "No results from site or Google"}

    # Score candidates
    product_norm = _normalize_text(product_name)
    product_words = product_norm.split()
    skip_words = {"cm", "lt", "mm", "kg", "gr", "ml", "adet", "li", "lu", "x", "set", "seri", "ve", "ic", "dis", "icin"}
    core_words = {w for w in product_words if w not in skip_words and not re.match(r'^\d+x?\d*$', w)}
    if product_words:
        core_words.discard(product_words[0])

    candidates = []
    for r in candidates_raw:
        title_norm = _normalize_text(r["title"])
        title_words_set = set(title_norm.split())
        core_overlap = core_words & title_words_set
        if len(core_words) >= 2 and not core_overlap:
            continue
        sim = _text_similarity(product_name, r["title"])
        pnums = set(re.findall(r'\d+', product_norm))
        tnums = set(re.findall(r'\d+', title_norm))
        nmatch = len(pnums & tnums) / max(len(pnums), 1) if pnums else 0.5
        score = (sim * 0.6) + (nmatch * 0.4)
        if core_words:
            score *= (0.5 + 0.5 * len(core_overlap) / len(core_words))
        if score >= 0.15:
            candidates.append({"url": r["url"], "title": r["title"], "score": score})

    if not candidates:
        return {"matched": False, "error": "No quality match in search results"}
    candidates.sort(key=lambda x: x["score"], reverse=True)

    # GTIN verification — only for medium-confidence matches (high score = already certain)
    if gtin and len(gtin) >= 8 and candidates[0]["score"] < 0.75:
        for cand in candidates[:3]:
            try:
                pr = req_sync.get("http://api.scraperapi.com", params={"api_key": SCRAPERAPI_KEY, "url": cand["url"]}, timeout=20)
                if pr.status_code == 200:
                    ps = BeautifulSoup(pr.text, "html.parser")
                    pg = _extract_gtin_from_page(pr.text, ps)
                    if pg and pg == gtin:
                        return {"matched": True, "url": cand["url"], "title": cand["title"], "score": 1.0, "match_method": "gtin", "competitor_key": competitor_key, "competitor_name": comp["name"]}
                    elif pg and pg != gtin:
                        cand["score"] = 0
                        continue
            except:
                pass
            import time; time.sleep(0.3)

    valid = [c for c in candidates if c["score"] >= 0.35]
    if valid:
        return {"matched": True, "url": valid[0]["url"], "title": valid[0]["title"], "score": round(valid[0]["score"], 3), "match_method": "text", "competitor_key": competitor_key, "competitor_name": comp["name"]}
    return {"matched": False, "error": f"No quality match (best: {candidates[0]['score']:.2f})"}


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
            if price and price > 100:
                logger.info(f"Scraped {competitor_key} price: {price} TL (no-render) from {url[:60]}")
                return {"success": True, "price": price, "currency": "TRY", "scraped_at": datetime.now(timezone.utc).isoformat()}
    except Exception:
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
            if price and price > 100:
                logger.info(f"Scraped {competitor_key} price: {price} TL (rendered) from {url[:60]}")
                return {"success": True, "price": price, "currency": "TRY", "scraped_at": datetime.now(timezone.utc).isoformat()}
            return {"success": False, "error": "Price not found on page (or below minimum threshold)"}
        return {"success": False, "error": f"HTTP {resp.status_code}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _extract_price(soup: BeautifulSoup, competitor_key: str) -> float:
    """Extract price from competitor page HTML with site-specific strategies.
    Returns the HIGHEST reasonable price found to avoid picking up accessory/shipping prices."""
    
    candidates = []  # Collect all found prices, pick the best one
    
    # Strategy 1: Schema.org / JSON-LD (most reliable)
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string)
            if isinstance(data, list):
                data = data[0]
            if data.get("@type") not in ("Product", "IndividualProduct", None):
                continue
            offers = data.get("offers", data.get("Offers", {}))
            if isinstance(offers, list):
                offers = offers[0]
            p = offers.get("price") or offers.get("lowPrice")
            if p:
                parsed = _parse_price_smart(str(p))
                if parsed and parsed > 100:
                    candidates.append(("jsonld", parsed))
        except Exception:
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
            if p and p > 100:
                candidates.append(("css", p))
            content = el.get("content")
            if content:
                p = _parse_price_smart(content)
                if p and p > 100:
                    candidates.append(("css_content", p))
    
    # Strategy 3: Meta tags
    for meta in soup.find_all("meta"):
        prop = (meta.get("property", "") or meta.get("name", "")).lower()
        if "price" in prop:
            content = meta.get("content", "")
            if content:
                p = _parse_price_smart(content)
                if p and p > 100:
                    candidates.append(("meta", p))
    
    # Strategy 4: itemprop="price"
    for el in soup.find_all(attrs={"itemprop": "price"}):
        val = el.get("content") or el.get_text(strip=True)
        if val:
            p = _parse_price_smart(val)
            if p and p > 100:
                candidates.append(("itemprop", p))
    
    # Strategy 5: data-price attributes
    for el in soup.find_all(attrs={"data-price": True}):
        p = _parse_price_smart(el["data-price"])
        if p and p > 100:
            candidates.append(("data_attr", p))
    
    if not candidates:
        # Strategy 6: Broad regex (last resort)
        text = soup.get_text()
        patterns = [
            r'([\d.]+[.,]\d{2,3})\s*(?:TL|₺|tl)',
            r'(?:TL|₺|tl)\s*([\d.]+[.,]\d{2,3})',
        ]
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for m in matches:
                p = _parse_turkish_price(m)
                if p and p > 100:
                    candidates.append(("regex", p))
    
    if not candidates:
        return None
    
    # Pick the best price: prefer JSON-LD/meta > CSS > regex
    # Among same source, prefer higher price (main product price is typically the largest)
    priority = {"jsonld": 0, "itemprop": 1, "meta": 2, "css_content": 3, "css": 4, "data_attr": 5, "regex": 6}
    
    # Group by source priority, take the max price from the highest priority group
    candidates.sort(key=lambda x: (priority.get(x[0], 99), -x[1]))
    
    best_source = candidates[0][0]
    best_candidates = [c for c in candidates if c[0] == best_source]
    # Return the highest price from the best source (product price > accessory price)
    return max(c[1] for c in best_candidates)


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
    """Parse Turkish formatted price: '1.234,56 TL' -> 1234.56, '94.464 TL' -> 94464"""
    if not text:
        return None
    try:
        clean = re.sub(r'[^\d.,]', '', text.strip())
        if not clean:
            return None
        # Turkish format with both: 1.234,56 or 94.464,00
        if "," in clean and "." in clean:
            clean = clean.replace(".", "").replace(",", ".")
        elif "," in clean:
            # Only comma: "475,00" -> 475.00
            clean = clean.replace(",", ".")
        elif "." in clean:
            # Only dot: could be thousands (94.464) or decimal (970.74)
            parts = clean.split(".")
            if len(parts) == 2 and len(parts[1]) == 3:
                # "94.464" -> 3 digits after dot = thousands separator
                clean = clean.replace(".", "")
            elif len(parts) > 2:
                # Multiple dots: "1.234.567" -> thousands
                clean = clean.replace(".", "")
            # else: "970.74" with 2 digits = decimal, keep as-is
        return float(clean)
    except Exception:
        return None


def match_all_competitors_for_product(product_name: str, brand: str = "", gtin: str = "") -> dict:
    """Match a product across all competitor sites IN PARALLEL."""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    results = {}
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {
            executor.submit(search_competitor_product, product_name, key, brand, gtin): key
            for key in COMPETITORS
        }
        for future in as_completed(futures):
            key = futures[future]
            try:
                results[key] = future.result()
            except Exception as e:
                results[key] = {"matched": False, "error": str(e)}
    return results


def scrape_all_competitor_prices(matches: dict) -> dict:
    """Scrape prices from all matched competitor URLs IN PARALLEL."""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    prices = {}
    jobs = {k: m for k, m in matches.items() if m.get("url")}
    if not jobs:
        return prices
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {
            executor.submit(scrape_competitor_price, m["url"], k): k
            for k, m in jobs.items()
        }
        for future in as_completed(futures):
            key = futures[future]
            try:
                result = future.result()
                if result.get("success"):
                    prices[key] = {
                        "price": result["price"],
                        "url": jobs[key]["url"],
                        "competitor_name": COMPETITORS[key]["name"],
                        "scraped_at": result["scraped_at"],
                    }
            except:
                pass
    return prices


def calculate_optimal_price(
    competitor_prices: dict,
    our_price_tl: float,
    floor_price: float,
    base_currency: str = "TRY",
    undercut_amount: float = 100,
) -> dict:
    """Calculate the optimal price based on competitor prices and floor price.
    
    - competitor_prices: dict of competitor TL prices
    - our_price_tl: our current price in TL
    - floor_price: floor price in the product's BASE CURRENCY (EUR/USD/TL)
    - base_currency: the product's original İkas currency
    - undercut_amount: TL amount to undercut the cheapest competitor (default 100 TL)
    
    Logic:
    1. Find cheapest competitor (TL)
    2. Convert cheapest competitor TL to base_currency using TCMB
    3. Compare with floor_price (in base_currency)
    4. If viable: new_price_tl = cheapest_tl - undercut_amount
    5. Convert new_price_tl to base_currency for İkas update
    """
    from tcmb_exchange import convert_from_tl, convert_to_tl, get_rate

    if not competitor_prices:
        return {"action": "no_change", "reason": "Rakip fiyatı bulunamadı"}

    # SANITY CHECK: Filter out unreliable prices (< 10% of our price = likely scrape error)
    if our_price_tl and our_price_tl > 0:
        min_threshold = our_price_tl * 0.10
        reliable_prices = {}
        rejected = []
        for k, v in competitor_prices.items():
            if v["price"] >= min_threshold:
                reliable_prices[k] = v
            else:
                rejected.append(f"{v['competitor_name']}: {v['price']:.0f} TL (< %10 eşik: {min_threshold:.0f} TL)")
        if rejected:
            logger.warning(f"Güvenilmez fiyatlar filtrelendi: {', '.join(rejected)}")
        competitor_prices = reliable_prices

    if not competitor_prices:
        return {"action": "no_change", "reason": "Güvenilir rakip fiyatı bulunamadı (tümü eşik altı)"}

    cheapest_comp = min(competitor_prices.items(), key=lambda x: x[1]["price"])
    cheapest_price_tl = cheapest_comp[1]["price"]
    cheapest_name = cheapest_comp[1]["competitor_name"]

    cur_label = "TL" if base_currency in ("TRY", "TL") else base_currency

    # Convert our TL price to base currency for display
    floor_price_tl = convert_to_tl(floor_price, base_currency) if floor_price else 0

    # Are we already cheaper than the cheapest competitor?
    if our_price_tl <= cheapest_price_tl:
        return {
            "action": "no_change",
            "reason": f"Zaten en ucuz (bizim: {our_price_tl:,.2f} TL, rakip: {cheapest_name} {cheapest_price_tl:,.2f} TL)",
            "cheapest_competitor": cheapest_name,
            "cheapest_price": cheapest_price_tl,
        }

    # Target price in TL: undercut by 100 TL
    target_price_tl = cheapest_price_tl - undercut_amount

    # Convert target price to base currency
    target_price_base = convert_from_tl(target_price_tl, base_currency)

    # Floor check: compare in base currency
    if floor_price and target_price_base < floor_price:
        return {
            "action": "floor_hit",
            "reason": f"Hedef fiyat ({target_price_base:,.2f} {cur_label}) dip fiyatın ({floor_price:,.2f} {cur_label}) altında.",
            "target_price_tl": target_price_tl,
            "target_price_base": target_price_base,
            "floor_price": floor_price,
            "floor_price_tl": floor_price_tl,
            "base_currency": base_currency,
            "cheapest_competitor": cheapest_name,
            "cheapest_price": cheapest_price_tl,
        }

    return {
        "action": "update",
        "new_price_tl": target_price_tl,
        "new_price_base": target_price_base,
        "old_price_tl": our_price_tl,
        "base_currency": base_currency,
        "savings_tl": our_price_tl - target_price_tl,
        "reason": f"Rakip: {cheapest_name} ({cheapest_price_tl:,.2f} TL). Yeni: {target_price_base:,.2f} {cur_label} ({target_price_tl:,.2f} TL)",
        "cheapest_competitor": cheapest_name,
        "cheapest_price": cheapest_price_tl,
    }
