"""AI Research Agents — Deep analysis with web scraping and competitive intelligence."""
import os
import json
import logging
import httpx
import asyncio
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup

logger = logging.getLogger("ai_agents")

SCRAPERAPI_KEY = os.environ.get("SCRAPERAPI_KEY", "")


async def scrape_url(url: str, timeout: int = 25) -> dict:
    """Scrape a URL using ScraperAPI and extract key page elements."""
    if not SCRAPERAPI_KEY:
        return {"error": "ScraperAPI key missing"}
    try:
        api_url = f"http://api.scraperapi.com?api_key={SCRAPERAPI_KEY}&url={url}"
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(api_url)
            if resp.status_code != 200:
                return {"error": f"HTTP {resp.status_code}"}
            html = resp.text

        soup = BeautifulSoup(html, "html.parser")

        # Extract key page elements
        title = soup.title.string.strip() if soup.title and soup.title.string else ""
        meta_desc = ""
        meta_tag = soup.find("meta", attrs={"name": "description"})
        if meta_tag:
            meta_desc = meta_tag.get("content", "")

        h1s = [h.get_text(strip=True) for h in soup.find_all("h1")][:3]
        h2s = [h.get_text(strip=True) for h in soup.find_all("h2")][:5]

        # Price elements
        prices = []
        for el in soup.find_all(class_=lambda c: c and ("price" in c.lower() or "fiyat" in c.lower())):
            txt = el.get_text(strip=True)
            if txt and len(txt) < 50:
                prices.append(txt)

        # CTA buttons
        ctas = []
        for btn in soup.find_all(["button", "a"]):
            txt = btn.get_text(strip=True)
            if txt and len(txt) < 40 and any(w in txt.lower() for w in ["sepet", "satın", "ekle", "buy", "cart", "incele", "sipariş"]):
                ctas.append(txt)

        # Images count
        images = len(soup.find_all("img"))

        # Body text length
        body = soup.find("body")
        body_text = body.get_text(" ", strip=True) if body else ""
        word_count = len(body_text.split())

        # Structured data
        has_schema = bool(soup.find("script", type="application/ld+json"))

        return {
            "url": url,
            "title": title[:200],
            "meta_description": meta_desc[:300],
            "h1": h1s,
            "h2": h2s,
            "prices": prices[:5],
            "ctas": ctas[:5],
            "image_count": images,
            "word_count": word_count,
            "has_schema": has_schema,
            "body_excerpt": body_text[:500],
        }
    except Exception as e:
        logger.error(f"Scrape error for {url}: {e}")
        return {"url": url, "error": str(e)}


async def scrape_google_serp(keyword: str) -> list:
    """Search Google for a keyword and get top organic results."""
    if not SCRAPERAPI_KEY:
        return []
    try:
        search_url = f"https://www.google.com.tr/search?q={keyword}&hl=tr&gl=tr"
        api_url = f"http://api.scraperapi.com?api_key={SCRAPERAPI_KEY}&url={search_url}"
        async with httpx.AsyncClient(timeout=25) as client:
            resp = await client.get(api_url)
            if resp.status_code != 200:
                return []

        soup = BeautifulSoup(resp.text, "html.parser")
        results = []

        for item in soup.select("div.g")[:5]:
            link = item.find("a")
            title_el = item.find("h3")
            desc_el = item.select_one("div[data-sncf], div.VwiC3b, span.aCOpRe")
            if link and title_el:
                href = link.get("href", "")
                if href.startswith("http"):
                    results.append({
                        "title": title_el.get_text(strip=True),
                        "url": href,
                        "description": desc_el.get_text(strip=True) if desc_el else "",
                    })
        return results
    except Exception as e:
        logger.error(f"SERP scrape error: {e}")
        return []


async def analyze_keyword_deep(keyword_data: dict, site_domain: str = "arigastro.com") -> dict:
    """Deep analysis for a single keyword — scrape landing page + competitors."""
    keyword = keyword_data.get("keyword", "")
    landing_url = keyword_data.get("landing_url", "")
    
    result = {
        "keyword": keyword,
        "ads_data": keyword_data,
        "our_page": None,
        "competitors": [],
        "serp_results": [],
    }

    tasks = []

    # 1. Scrape our landing page if we have a URL
    if landing_url:
        tasks.append(("our_page", scrape_url(landing_url)))

    # 2. Search Google for this keyword
    tasks.append(("serp", scrape_google_serp(keyword)))

    # Execute in parallel
    task_results = await asyncio.gather(*[t[1] for t in tasks], return_exceptions=True)

    for i, (key, _) in enumerate(tasks):
        if isinstance(task_results[i], Exception):
            continue
        if key == "our_page":
            result["our_page"] = task_results[i]
        elif key == "serp":
            result["serp_results"] = task_results[i] if isinstance(task_results[i], list) else []

    # 3. Scrape top 3 competitor pages from SERP
    comp_urls = [r["url"] for r in result["serp_results"] if site_domain not in r.get("url", "")][:3]
    if comp_urls:
        comp_results = await asyncio.gather(*[scrape_url(u) for u in comp_urls], return_exceptions=True)
        for cr in comp_results:
            if isinstance(cr, dict) and "error" not in cr:
                result["competitors"].append(cr)

    return result


async def run_deep_analysis(category: str, ads_data: dict, date_range: dict) -> dict:
    """Run deep AI analysis with web scraping for a report category."""
    
    analysis_data = {
        "category": category,
        "date_range": date_range,
        "scraped_pages": [],
        "competitor_insights": [],
        "keyword_deep_analyses": [],
    }

    if category == "search_terms":
        # Find worst performing keywords with spend but no conversions
        search_terms = ads_data.get("search_terms", [])
        quality_scores = ads_data.get("quality_scores", [])
        
        # Pick top 3 problem keywords for deep analysis
        problem_keywords = sorted(
            [t for t in search_terms if t.get("clicks", 0) >= 5 and t.get("conversions", 0) == 0],
            key=lambda x: x.get("cost", 0), reverse=True
        )[:3]
        
        # Also pick top 2 low QS keywords
        low_qs = sorted(
            [k for k in quality_scores if k.get("quality_score") and k["quality_score"] < 5 and k.get("cost", 0) > 50],
            key=lambda x: x.get("cost", 0), reverse=True
        )[:2]

        all_keywords = problem_keywords + low_qs
        
        for kw in all_keywords:
            keyword_text = kw.get("term") or kw.get("keyword", "")
            if keyword_text:
                deep = await analyze_keyword_deep({"keyword": keyword_text, **kw})
                analysis_data["keyword_deep_analyses"].append(deep)

    elif category == "competition":
        # Scrape our homepage and category pages
        our_pages = await asyncio.gather(
            scrape_url("https://arigastro.com"),
            scrape_url("https://arigastro.com/buz-makineleri"),
            return_exceptions=True
        )
        for p in our_pages:
            if isinstance(p, dict) and "error" not in p:
                analysis_data["scraped_pages"].append(p)

        # Search for main competitor keywords
        competition = ads_data.get("competition", [])
        if competition:
            top_campaign = competition[0] if competition else {}
            # Search for main product categories
            serp = await scrape_google_serp("endüstriyel mutfak ekipmanları")
            analysis_data["competitor_insights"] = serp

    elif category == "ad_assets":
        # Scrape our main landing pages to check ad-page alignment
        pages_to_check = [
            "https://arigastro.com",
            "https://arigastro.com/buz-makineleri",
            "https://arigastro.com/oztiryakiler",
        ]
        results = await asyncio.gather(*[scrape_url(u) for u in pages_to_check], return_exceptions=True)
        for r in results:
            if isinstance(r, dict) and "error" not in r:
                analysis_data["scraped_pages"].append(r)

    elif category == "seo":
        # Scrape top performing and underperforming pages
        gsc_pages = ads_data.get("gsc_pages", [])
        landing_pages = ads_data.get("landing_pages", [])
        
        # Scrape top 3 pages with high impressions but low CTR
        low_ctr_pages = sorted(
            [p for p in (gsc_pages or []) if p.get("impressions", 0) > 50 and p.get("ctr", 0) < 3],
            key=lambda x: x.get("impressions", 0), reverse=True
        )[:3]
        
        for page in low_ctr_pages:
            scraped = await scrape_url(page.get("page", ""))
            if "error" not in scraped:
                analysis_data["scraped_pages"].append(scraped)

        # Search Google for top GSC query to see competitors
        gsc_queries = ads_data.get("gsc_queries", [])
        if gsc_queries:
            top_query = gsc_queries[0].get("query", "")
            if top_query:
                serp = await scrape_google_serp(top_query)
                analysis_data["competitor_insights"] = serp
                # Scrape top 2 competitor pages
                comp_urls = [r["url"] for r in serp if "arigastro" not in r.get("url", "")][:2]
                comp_results = await asyncio.gather(*[scrape_url(u) for u in comp_urls], return_exceptions=True)
                for cr in comp_results:
                    if isinstance(cr, dict) and "error" not in cr:
                        analysis_data["scraped_pages"].append(cr)

    return analysis_data
