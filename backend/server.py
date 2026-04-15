from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

from fastapi import FastAPI, APIRouter, HTTPException, Request, Response, Depends
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
import os
import logging
import bcrypt
import jwt
import uuid
import httpx
import asyncio
import re
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel, Field
from typing import Optional, List
from bs4 import BeautifulSoup

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# MongoDB
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

app = FastAPI()
api_router = APIRouter(prefix="/api")

# JWT Config
JWT_SECRET = os.environ.get("JWT_SECRET", "fallback-secret-key-change-me")
JWT_ALGORITHM = "HS256"

# ============ AUTH HELPERS ============

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))

def create_access_token(user_id: str, username: str) -> str:
    payload = {
        "sub": user_id, "username": username,
        "exp": datetime.now(timezone.utc) + timedelta(hours=24),
        "type": "access"
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

async def get_current_user(request: Request) -> dict:
    token = request.cookies.get("access_token")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
        user = await db.users.find_one({"_id": ObjectId(payload["sub"])})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        return {"id": str(user["_id"]), "username": user["username"], "name": user.get("name", ""), "role": user.get("role", "user")}
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except (jwt.InvalidTokenError, Exception) as e:
        raise HTTPException(status_code=401, detail="Invalid token")

# ============ AUTH MODELS ============

class LoginRequest(BaseModel):
    username: str
    password: str

# ============ AUTH ENDPOINTS ============

@api_router.post("/auth/login")
async def login(req: LoginRequest, response: Response):
    user = await db.users.find_one({"username": req.username.strip().lower()})
    if not user or not verify_password(req.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token(str(user["_id"]), user["username"])
    response.set_cookie(key="access_token", value=token, httponly=True, secure=False, samesite="lax", max_age=86400, path="/")
    return {"id": str(user["_id"]), "username": user["username"], "name": user.get("name", ""), "role": user.get("role", "user"), "token": token}

@api_router.get("/auth/me")
async def get_me(user: dict = Depends(get_current_user)):
    return user

@api_router.post("/auth/logout")
async def logout(response: Response):
    response.delete_cookie("access_token", path="/")
    return {"message": "Logged out"}

# ============ SITEMAP HELPERS ============

def slug_to_name(slug: str) -> str:
    """Convert URL slug to readable product name."""
    name = slug.replace("-", " ").strip()
    # Capitalize first letter of each word
    return " ".join(w.capitalize() if len(w) > 2 else w.upper() for w in name.split())

async def fetch_and_parse_sitemap(url: str) -> list:
    """Fetch and parse XML sitemap."""
    async with httpx.AsyncClient(timeout=30.0) as client_http:
        resp = await client_http.get(url, headers={"User-Agent": "Mozilla/5.0 (compatible; AriBot/1.0)"})
        resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml-xml")
    items = []
    for url_tag in soup.find_all("url"):
        loc = url_tag.find("loc")
        if not loc:
            continue
        item = {"url": loc.text.strip()}
        lastmod = url_tag.find("lastmod")
        if lastmod:
            item["lastmod"] = lastmod.text.strip()
        image = url_tag.find("image:image")
        if image:
            img_loc = image.find("image:loc")
            if img_loc:
                item["image_url"] = img_loc.text.strip()
        # Extract slug from URL
        slug = item["url"].rstrip("/").split("/")[-1]
        item["slug"] = slug
        item["name"] = slug_to_name(slug)
        items.append(item)
    return items

# ============ SITEMAP ENDPOINTS ============

@api_router.post("/sitemap/import-categories")
async def import_categories(user: dict = Depends(get_current_user)):
    """Import categories from collections sitemap."""
    try:
        items = await fetch_and_parse_sitemap("https://arigastro.com/collections.xml")
        imported = 0
        for item in items:
            existing = await db.categories.find_one({"slug": item["slug"]})
            if not existing:
                await db.categories.insert_one({
                    "slug": item["slug"],
                    "name": item["name"],
                    "url": item["url"],
                    "image_url": item.get("image_url", ""),
                    "is_tracked": False,
                    "product_count": 0,
                    "created_at": datetime.now(timezone.utc).isoformat()
                })
                imported += 1
        total = await db.categories.count_documents({})
        return {"imported": imported, "total": total, "message": f"{imported} new categories imported"}
    except Exception as e:
        logger.error(f"Error importing categories: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/sitemap/import-products")
async def import_products(user: dict = Depends(get_current_user)):
    """Import products from products sitemap."""
    try:
        items = await fetch_and_parse_sitemap("https://arigastro.com/products.xml")
        imported = 0
        for item in items:
            existing = await db.products.find_one({"slug": item["slug"]})
            if not existing:
                await db.products.insert_one({
                    "slug": item["slug"],
                    "name": item["name"],
                    "url": item["url"],
                    "image_url": item.get("image_url", ""),
                    "our_price": None,
                    "category_slug": "",
                    "is_tracked": False,
                    "akakce_matched": False,
                    "akakce_url": "",
                    "last_price_check": None,
                    "cheapest_competitor": None,
                    "cheapest_price": None,
                    "price_difference": None,
                    "competitors": [],
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "updated_at": datetime.now(timezone.utc).isoformat()
                })
                imported += 1
        total = await db.products.count_documents({})
        return {"imported": imported, "total": total, "message": f"{imported} new products imported"}
    except Exception as e:
        logger.error(f"Error importing products: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============ CATEGORY ENDPOINTS ============

@api_router.get("/categories")
async def list_categories(user: dict = Depends(get_current_user)):
    cats = await db.categories.find({}, {"_id": 0}).sort("name", 1).to_list(500)
    return cats

@api_router.put("/categories/{slug}/toggle-tracking")
async def toggle_category_tracking(slug: str, user: dict = Depends(get_current_user)):
    cat = await db.categories.find_one({"slug": slug})
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    new_val = not cat.get("is_tracked", False)
    await db.categories.update_one({"slug": slug}, {"$set": {"is_tracked": new_val}})
    return {"slug": slug, "is_tracked": new_val}

# ============ PRODUCT ENDPOINTS ============

class ProductUpdate(BaseModel):
    our_price: Optional[float] = None
    category_slug: Optional[str] = None
    is_tracked: Optional[bool] = None

@api_router.get("/products")
async def list_products(
    user: dict = Depends(get_current_user),
    search: str = "",
    category: str = "",
    tracked_only: bool = False,
    tracked_categories_only: bool = False,
    cheaper_only: bool = False,
    unmatched_only: bool = False,
    matched_only: bool = False,
    page: int = 1,
    limit: int = 50
):
    query = {}
    if search:
        query["name"] = {"$regex": search, "$options": "i"}
    if category:
        query["category_slug"] = category
    if tracked_only:
        query["is_tracked"] = True
    if tracked_categories_only:
        tracked_cats = await db.categories.find({"is_tracked": True}, {"_id": 0, "name": 1}).to_list(500)
        if tracked_cats:
            cat_names = [c["name"] for c in tracked_cats]
            cat_regex = "|".join([re.escape(n) for n in cat_names])
            query["category_path"] = {"$regex": cat_regex, "$options": "i"}
        else:
            return {"products": [], "total": 0, "page": 1, "pages": 0}
    if cheaper_only:
        query["$and"] = [
            {"cheapest_price": {"$ne": None}},
            {"our_price": {"$ne": None}},
            {"$expr": {"$lt": ["$cheapest_price", "$our_price"]}}
        ]
    if unmatched_only:
        query["akakce_matched"] = {"$ne": True}
    if matched_only:
        query["akakce_matched"] = True

    skip = (page - 1) * limit
    total = await db.products.count_documents(query)
    products = await db.products.find(query, {"_id": 0}).sort("name", 1).skip(skip).limit(limit).to_list(limit)
    return {"products": products, "total": total, "page": page, "pages": (total + limit - 1) // limit}

@api_router.get("/products/ai-match-status")
async def ai_match_status(user: dict = Depends(get_current_user)):
    """Get AI matching progress."""
    status = await db.system_status.find_one({"task": "ai_match"}, {"_id": 0})
    return status or {"running": False, "matched": 0, "failed": 0, "skipped": 0, "total": 0}

@api_router.get("/products/price-check-status")
async def price_check_status(user: dict = Depends(get_current_user)):
    status = await db.system_status.find_one({"task": "price_check"}, {"_id": 0})
    return status or {"running": False, "checked": 0, "success": 0, "failed": 0, "total": 0}

@api_router.get("/products/{slug}")
async def get_product(slug: str, user: dict = Depends(get_current_user)):
    product = await db.products.find_one({"slug": slug}, {"_id": 0})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product

@api_router.put("/products/{slug}")
async def update_product(slug: str, update: ProductUpdate, user: dict = Depends(get_current_user)):
    update_dict = {k: v for k, v in update.model_dump().items() if v is not None}
    update_dict["updated_at"] = datetime.now(timezone.utc).isoformat()
    result = await db.products.update_one({"slug": slug}, {"$set": update_dict})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Product not found")
    return {"message": "Updated", "slug": slug}

@api_router.put("/products/{slug}/toggle-tracking")
async def toggle_product_tracking(slug: str, user: dict = Depends(get_current_user)):
    product = await db.products.find_one({"slug": slug})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    new_val = not product.get("is_tracked", False)
    await db.products.update_one({"slug": slug}, {"$set": {"is_tracked": new_val, "updated_at": datetime.now(timezone.utc).isoformat()}})
    return {"slug": slug, "is_tracked": new_val}

# ============ FEED PRICE SYNC (Google Merchant Feed) ============

import random

FEED_URL = os.environ.get("FEED_URL", "")

async def fetch_and_parse_feed() -> list:
    """Fetch and parse Google Merchant Center feed XML."""
    if not FEED_URL:
        return []
    try:
        async with httpx.AsyncClient(timeout=60.0) as http_client:
            resp = await http_client.get(FEED_URL, headers={"User-Agent": "AriAI/1.0"})
            resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "lxml-xml")
        items = []
        for entry in soup.find_all("item") or soup.find_all("entry"):
            item = {}
            # Google Merchant fields use g: namespace
            for tag_name, key in [
                ("g:id", "feed_id"), ("g:title", "title"), ("g:link", "url"),
                ("g:price", "price_raw"), ("g:brand", "brand"),
                ("g:product_type", "category"), ("g:availability", "availability"),
                ("g:image_link", "image_url"), ("g:gtin", "gtin"),
            ]:
                el = entry.find(tag_name)
                if not el:
                    # Try without namespace prefix
                    el = entry.find(tag_name.split(":")[-1])
                if el:
                    item[key] = el.get_text(strip=True)

            # Also try <link> directly
            if "url" not in item:
                link_el = entry.find("link")
                if link_el:
                    item["url"] = link_el.get_text(strip=True)

            # Parse price: "18937.06TRY" or "18937.06 TRY"
            if "price_raw" in item:
                price_text = item["price_raw"].replace("TRY", "").replace("₺", "").strip()
                try:
                    item["price"] = float(price_text)
                except (ValueError, TypeError):
                    item["price"] = None
            else:
                item["price"] = None

            # Extract slug from URL
            if "url" in item:
                item["slug"] = item["url"].rstrip("/").split("/")[-1]

            if item.get("slug"):
                items.append(item)
        return items
    except Exception as e:
        logger.error(f"Feed parse error: {e}")
        return []

@api_router.post("/feed/sync-prices")
async def sync_prices_from_feed(user: dict = Depends(get_current_user)):
    """Sync product prices, names, brands and categories from Google Merchant Feed."""
    feed_items = await fetch_and_parse_feed()
    if not feed_items:
        raise HTTPException(status_code=500, detail="Feed okunamadi veya bos")

    updated = 0
    new_products = 0
    for item in feed_items:
        slug = item.get("slug", "")
        if not slug:
            continue

        update_data = {"updated_at": datetime.now(timezone.utc).isoformat()}
        if item.get("price"):
            update_data["our_price"] = item["price"]
        if item.get("title"):
            update_data["name"] = item["title"]
        if item.get("brand"):
            update_data["brand"] = item["brand"]
        if item.get("category"):
            update_data["category_path"] = item["category"]
        if item.get("availability"):
            update_data["availability"] = item["availability"]
        if item.get("gtin"):
            update_data["gtin"] = item["gtin"]
        if item.get("image_url"):
            update_data["image_url"] = item["image_url"]

        existing = await db.products.find_one({"slug": slug})
        if existing:
            await db.products.update_one({"slug": slug}, {"$set": update_data})
            updated += 1
        else:
            # Create new product from feed
            await db.products.insert_one({
                "slug": slug,
                "url": item.get("url", ""),
                "name": item.get("title", slug_to_name(slug)),
                "image_url": item.get("image_url", ""),
                "our_price": item.get("price"),
                "brand": item.get("brand", ""),
                "category_path": item.get("category", ""),
                "category_slug": "",
                "gtin": item.get("gtin", ""),
                "availability": item.get("availability", ""),
                "is_tracked": False,
                "akakce_matched": False,
                "akakce_url": "",
                "last_price_check": None,
                "cheapest_competitor": None,
                "cheapest_price": None,
                "price_difference": None,
                "competitors": [],
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            })
            new_products += 1

    total = await db.products.count_documents({})
    priced = await db.products.count_documents({"our_price": {"$ne": None}})
    return {
        "updated": updated,
        "new_products": new_products,
        "total_products": total,
        "products_with_price": priced,
        "feed_items": len(feed_items),
        "message": f"{updated} urun guncellendi, {new_products} yeni urun eklendi"
    }

@api_router.get("/feed/status")
async def feed_status(user: dict = Depends(get_current_user)):
    """Check feed sync status."""
    total = await db.products.count_documents({})
    priced = await db.products.count_documents({"our_price": {"$ne": None}})
    unpriced = await db.products.count_documents({"our_price": None})
    return {
        "feed_url": FEED_URL[:50] + "..." if FEED_URL else "Not configured",
        "total_products": total,
        "products_with_price": priced,
        "products_without_price": unpriced,
    }

# ============ AKAKCE SCRAPING (curl_cffi + ScraperAPI + proxy) ============

AKAKCE_SEARCH_URL = "https://www.akakce.com/arama/?q={query}"
AKAKCE_PROXY = os.environ.get("AKAKCE_PROXY", "")
SCRAPERAPI_KEY = os.environ.get("SCRAPERAPI_KEY", "")

def akakce_request(url: str):
    """Make request to Akakçe. Tries: 1) ScraperAPI 2) curl_cffi+proxy 3) curl_cffi direct."""
    
    # Method 1: ScraperAPI (most reliable for VPS)
    if SCRAPERAPI_KEY:
        try:
            import requests as req_sync
            resp = req_sync.get("http://api.scraperapi.com", params={
                "api_key": SCRAPERAPI_KEY, "url": url, "country_code": "tr",
            }, timeout=45)
            if resp.status_code == 200:
                return resp
            logger.warning(f"ScraperAPI returned {resp.status_code}")
        except Exception as e:
            logger.warning(f"ScraperAPI error: {e}")
    
    # Method 2: curl_cffi with proxy or direct
    try:
        from curl_cffi import requests as cffi_requests
        kwargs = {
            "impersonate": random.choice(["chrome", "chrome110", "chrome120"]),
            "timeout": 10,
        }
        if AKAKCE_PROXY:
            kwargs["proxies"] = {"http": AKAKCE_PROXY, "https": AKAKCE_PROXY}
        resp = cffi_requests.get(url, **kwargs)
        return resp
    except ImportError:
        import httpx as httpx_sync
        resp = httpx_sync.get(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        }, timeout=10, follow_redirects=True)
        return resp

# Cache the block status to avoid repeated slow failures
_akakce_blocked = {"status": None, "checked_at": None}

def is_akakce_blocked() -> bool:
    """Check if Akakçe is blocking us. If ScraperAPI is configured, always return False."""
    if SCRAPERAPI_KEY:
        return False  # ScraperAPI handles Cloudflare bypass
    if _akakce_blocked["status"] is not None and _akakce_blocked["checked_at"]:
        elapsed = (datetime.now(timezone.utc) - datetime.fromisoformat(_akakce_blocked["checked_at"])).total_seconds()
        if elapsed < 600:
            return _akakce_blocked["status"]
    try:
        resp = akakce_request("https://www.akakce.com/")
        blocked = resp.status_code == 403
        _akakce_blocked["status"] = blocked
        _akakce_blocked["checked_at"] = datetime.now(timezone.utc).isoformat()
        return blocked
    except Exception:
        _akakce_blocked["status"] = True
        _akakce_blocked["checked_at"] = datetime.now(timezone.utc).isoformat()
        return True

def get_akakce_access_error() -> str:
    if not SCRAPERAPI_KEY and not AKAKCE_PROXY:
        return "Akakce'ye erisim engellendi (Cloudflare 403). Cozum: ScraperAPI ucretsiz hesap acin (scraperapi.com), API key'i backend .env dosyasina SCRAPERAPI_KEY olarak ekleyin."
    return "Akakce'ye erisim engellendi (Cloudflare 403). Proxy/ScraperAPI ayarlarinizi kontrol edin."

def search_akakce_via_google(product_name: str) -> dict:
    """Search Google for the product on Akakçe. More accurate than Akakçe's own search (no char limit)."""
    if not SCRAPERAPI_KEY:
        return {"success": False, "error": "SCRAPERAPI_KEY gerekli", "candidates": []}
    try:
        import requests as req_sync
        from urllib.parse import quote
        
        query = f"{product_name} site:akakce.com"
        resp = req_sync.get("http://api.scraperapi.com", params={
            "api_key": SCRAPERAPI_KEY,
            "url": f"https://www.google.com.tr/search?q={quote(query)}&hl=tr&num=8",
        }, timeout=60)
        
        if resp.status_code != 200:
            return {"success": False, "error": f"Google HTTP {resp.status_code}", "candidates": []}
        
        soup = BeautifulSoup(resp.text, "html.parser")
        candidates = []
        seen_urls = set()
        
        # Method 1: Structured Google results
        for div in soup.select("div.g, div[data-sokoban-container]"):
            a = div.select_one("a[href]")
            if not a:
                continue
            href = a.get("href", "")
            if "akakce.com" not in href or "en-ucuz" not in href:
                continue
            h3 = div.select_one("h3")
            title = h3.get_text(strip=True) if h3 else ""
            # Clean title (remove "akakce.com" suffix)
            title = re.sub(r'akakce\.com.*$', '', title).strip()
            if href not in seen_urls and title:
                seen_urls.add(href)
                candidates.append({"name": title[:150], "url": href, "price": 0})
        
        # Method 2: Direct link extraction (fallback)
        if not candidates:
            for a in soup.find_all("a", href=True):
                href = a.get("href", "")
                if "akakce.com" in href and "en-ucuz" in href:
                    if href.startswith("/url?q="):
                        href = href.split("/url?q=")[1].split("&")[0]
                    if href in seen_urls:
                        continue
                    seen_urls.add(href)
                    title = a.get_text(strip=True)[:150]
                    title = re.sub(r'akakce\.com.*$', '', title).strip()
                    if title and len(title) > 5:
                        candidates.append({"name": title, "url": href, "price": 0})
        
        return {
            "success": len(candidates) > 0,
            "candidates": candidates[:10],
            "error": None if candidates else "Google'da Akakce sonucu bulunamadi",
        }
    except Exception as e:
        logger.error(f"Google search error: {e}")
        return {"success": False, "error": str(e), "candidates": []}

def search_akakce_sync(product_name: str) -> dict:
    """Search for product on Akakçe. Tries Google first (better for long names), then Akakçe direct."""
    # Method 1: Google search (handles full product name, no char limit)
    google_result = search_akakce_via_google(product_name)
    if google_result["success"]:
        return {"success": True, "competitors": google_result["candidates"], "search_url": "", "error": None}
    
    # Method 2: Akakçe direct search (fallback)
    try:
        search_query = product_name.replace(" ", "+")
        url = AKAKCE_SEARCH_URL.format(query=search_query)
        resp = akakce_request(url)
        
        if resp.status_code == 403:
            return {"success": False, "error": get_akakce_access_error(), "competitors": [], "search_url": url}
        if resp.status_code != 200:
            return {"success": False, "error": f"HTTP {resp.status_code}", "competitors": [], "search_url": url}
        
        soup = BeautifulSoup(resp.content if hasattr(resp, 'content') else resp.text, "html.parser")
        results = []
        seen_urls = set()
        
        for a_tag in soup.select("a[href*='/en-ucuz-']"):
            title = a_tag.get("title", "") or a_tag.get_text(strip=True)
            if not title or len(title) < 5:
                continue
            href = a_tag.get("href", "")
            if href and not href.startswith("http"):
                href = f"https://www.akakce.com{href}"
            if href in seen_urls:
                continue
            seen_urls.add(href)
            
            price = 0
            parent = a_tag.find_parent("li") or a_tag.find_parent("div")
            if parent:
                text = parent.get_text(" ", strip=True)
                pm = re.findall(r'([\d.]+)\s*,(\d{2})\s*TL', text)
                if pm:
                    price = float(pm[0][0].replace(".", "") + "." + pm[0][1])
            
            results.append({"name": title[:120], "price": price, "url": href})
        
        unique = []
        seen_names = set()
        for r in results:
            key = r["name"][:40].lower()
            if key not in seen_names:
                seen_names.add(key)
                unique.append(r)
        
        return {"success": len(unique) > 0, "search_url": url, "competitors": unique[:15], "error": None if unique else "Sonuc bulunamadi"}
    except Exception as e:
        logger.error(f"Akakce search error: {e}")
        return {"success": False, "error": str(e), "competitors": [], "search_url": ""}

async def search_akakce(product_name: str) -> dict:
    """Async wrapper for Akakçe search (curl_cffi is sync)."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, search_akakce_sync, product_name)

def parse_turkish_price(text: str) -> Optional[float]:
    """Parse Turkish price format: 1.234,56 TL -> 1234.56"""
    if not text:
        return None
    text = text.replace("TL", "").replace("₺", "").strip()
    text = re.sub(r'[^\d.,]', '', text)
    if not text:
        return None
    try:
        # Turkish format: 1.234,56
        text = text.replace(".", "").replace(",", ".")
        return float(text)
    except (ValueError, TypeError):
        return None

@api_router.post("/products/{slug}/check-akakce")
async def check_akakce_price(slug: str, user: dict = Depends(get_current_user)):
    """Check prices from a MATCHED Akakçe product page. Requires akakce_product_url to be set."""
    product = await db.products.find_one({"slug": slug})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    akakce_url = product.get("akakce_product_url", "")
    if not akakce_url:
        return {"slug": slug, "success": False, "error": "Bu urun henuz Akakce ile eslestirilmemis. Once eslestirme yapin."}
    
    # Fetch the Akakçe product page and parse sellers
    result = await fetch_akakce_product_page(akakce_url)
    
    update_data = {
        "last_price_check": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    
    if result["success"] and result["sellers"]:
        # Filter out Arigastro from competitors
        competitors = [s for s in result["sellers"] if "arigastro" not in s["seller"].lower()]
        all_sellers = result["sellers"]
        
        if competitors:
            cheapest = competitors[0]
            update_data["cheapest_competitor"] = cheapest["seller"]
            update_data["cheapest_price"] = cheapest["price"]
            update_data["competitors"] = competitors
            update_data["all_sellers"] = all_sellers
            update_data["akakce_product_name"] = result.get("product_name", "")
            
            if product.get("our_price"):
                update_data["price_difference"] = round(product["our_price"] - cheapest["price"], 2)
            
            # Find our position among sellers
            our_position = None
            for i, s in enumerate(all_sellers):
                if "arigastro" in s["seller"].lower():
                    our_position = i + 1
                    break
            update_data["our_position"] = our_position
            update_data["total_sellers"] = len(all_sellers)
            
            await db.price_history.insert_one({
                "product_slug": slug,
                "our_price": product.get("our_price"),
                "cheapest_competitor": cheapest["seller"],
                "cheapest_price": cheapest["price"],
                "all_sellers": all_sellers,
                "our_position": our_position,
                "checked_at": datetime.now(timezone.utc).isoformat()
            })
    
    await db.products.update_one({"slug": slug}, {"$set": update_data})
    return {"slug": slug, "success": result["success"], "sellers": result.get("sellers", []), "error": result.get("error")}

async def fetch_akakce_product_page(url: str) -> dict:
    """Fetch and parse an Akakçe product detail page to extract all seller prices."""
    for attempt in range(2):  # Retry once on failure
        try:
            loop = asyncio.get_event_loop()
            resp = await loop.run_in_executor(None, lambda: akakce_request(url))
            
            if resp.status_code == 403:
                return {"success": False, "error": "Cloudflare 403", "sellers": []}
            if resp.status_code in [410, 404, 500] and attempt == 0:
                await asyncio.sleep(3)
                continue  # Retry
            if resp.status_code != 200:
                return {"success": False, "error": f"HTTP {resp.status_code}", "sellers": []}
            
            soup = BeautifulSoup(resp.content if hasattr(resp, 'content') else resp.text, "html.parser")
            
            product_name = ""
            h1 = soup.find("h1")
            if h1:
                product_name = h1.get_text(strip=True)
            
            # Extract seller names from v_v8 class spans
            seller_names = []
            for el in soup.find_all("span", class_="v_v8"):
                text = el.get_text(strip=True)
                if text.startswith("Satıcı:") or text.startswith("Satıcı :"):
                    continue
                text = text.strip().strip("/")
                if text and len(text) > 2 and len(text) < 60:
                    seller_names.append(text)
            
            # Extract prices from pb_v8 class spans
            prices = []
            for span in soup.find_all("span", class_="pb_v8"):
                text = span.get_text(strip=True)
                match = re.match(r'([\d.]+,\d{2})\s*TL', text)
                if match:
                    price_str = match.group(1)
                    price = float(price_str.replace(".", "").replace(",", "."))
                    if price > 1:
                        prices.append(price)
            
            # Deduplicate prices (sometimes same price appears twice)
            unique_prices = list(dict.fromkeys(prices))
            
            # Pair sellers with prices
            sellers = []
            for i in range(min(len(seller_names), len(unique_prices))):
                sellers.append({"seller": seller_names[i], "price": unique_prices[i]})
            
            sellers.sort(key=lambda x: x["price"])
            
            if sellers:
                return {"success": True, "product_name": product_name, "sellers": sellers, "error": None}
            elif attempt == 0:
                await asyncio.sleep(3)
                continue  # Retry
            else:
                return {"success": False, "product_name": product_name, "sellers": [], "error": "Satici bilgisi okunamadi"}
        except Exception as e:
            if attempt == 0:
                await asyncio.sleep(3)
                continue
            logger.error(f"Akakce product page error: {e}")
            return {"success": False, "error": str(e), "sellers": []}

# ============ AI-POWERED PRODUCT MATCHING ============

class AkakceMatchRequest(BaseModel):
    akakce_product_url: str
    akakce_product_name: Optional[str] = ""

@api_router.post("/products/{slug}/set-akakce-match")
async def set_akakce_match(slug: str, req: AkakceMatchRequest, user: dict = Depends(get_current_user)):
    """Manually set the Akakçe product URL for a product (admin override)."""
    product = await db.products.find_one({"slug": slug})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    await db.products.update_one({"slug": slug}, {"$set": {
        "akakce_product_url": req.akakce_product_url,
        "akakce_product_name": req.akakce_product_name,
        "akakce_matched": True,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }})
    return {"slug": slug, "matched": True, "akakce_product_url": req.akakce_product_url}

@api_router.post("/products/{slug}/ai-match-akakce")
async def ai_match_akakce(slug: str, user: dict = Depends(get_current_user)):
    """Use AI to search Akakçe and find the matching product. Searches, then uses GPT to pick the right one."""
    product = await db.products.find_one({"slug": slug})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    # Step 1: Search Akakçe
    search_result = search_akakce_sync(product["name"])
    
    if not search_result["success"]:
        return {"slug": slug, "matched": False, "error": search_result["error"], "candidates": []}
    
    candidates = search_result.get("competitors", [])
    if not candidates:
        return {"slug": slug, "matched": False, "error": "Akakce'de sonuc bulunamadi", "candidates": []}
    
    # Step 2: Use AI to find the best match
    openai_key = os.environ.get("OPENAI_API_KEY")
    if not openai_key:
        # Return candidates for manual selection
        return {"slug": slug, "matched": False, "candidates": candidates, "error": "AI anahtari yok. Manuel eslestirme yapabilirsiniz."}
    
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        import json
        
        chat = LlmChat(
            api_key=openai_key,
            session_id=f"match-{slug}-{uuid.uuid4().hex[:8]}",
            system_message="""Sen bir ürün eşleştirme uzmanısın. Sana bir ürün adı ve Akakçe arama sonuçlarından aday ürünler verilecek.
Görevin: Aday ürünlerden TAMAMEN AYNI ürünü bulmak. Marka, model, boyut, özellik gibi tüm detaylar eşleşmeli.
Eğer kesin eşleşme yoksa, "no_match" döndür.
Yanıtını JSON formatında ver: {"match_index": 0, "confidence": "high/medium/low", "reason": "..."}
Eğer eşleşme yoksa: {"match_index": -1, "confidence": "none", "reason": "..."}"""
        ).with_model("openai", "gpt-4o")
        
        candidates_text = "\n".join([f"{i}. {c['name']} - {c.get('price', '?')} TL (URL: {c.get('url', '')})" for i, c in enumerate(candidates)])
        
        prompt = f"""Ürünümüz: {product['name']}
Marka: {product.get('brand', 'Bilinmiyor')}
GTIN: {product.get('gtin', 'Yok')}

Akakçe aday ürünleri:
{candidates_text}

Hangi aday ürün bizim ürünümüzle AYNI üründür? Sadece bire bir aynı ürünü eşleştir."""
        
        response = await chat.send_message(UserMessage(text=prompt))
        response_text = response.strip()
        if response_text.startswith("```"):
            response_text = re.sub(r'^```(?:json)?\s*', '', response_text)
            response_text = re.sub(r'\s*```$', '', response_text)
        
        ai_result = json.loads(response_text)
        match_idx = ai_result.get("match_index", -1)
        confidence = ai_result.get("confidence", "none")
        
        if match_idx >= 0 and match_idx < len(candidates) and confidence in ["high", "medium"]:
            matched_product = candidates[match_idx]
            await db.products.update_one({"slug": slug}, {"$set": {
                "akakce_product_url": matched_product.get("url", ""),
                "akakce_product_name": matched_product["name"],
                "akakce_matched": True,
                "akakce_match_confidence": confidence,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }})
            return {
                "slug": slug, "matched": True,
                "akakce_product_url": matched_product.get("url", ""),
                "akakce_product_name": matched_product["name"],
                "confidence": confidence,
                "reason": ai_result.get("reason", ""),
                "candidates": candidates
            }
        else:
            return {
                "slug": slug, "matched": False,
                "candidates": candidates,
                "reason": ai_result.get("reason", "Kesin esleme bulunamadi"),
                "confidence": confidence
            }
    except Exception as e:
        logger.error(f"AI matching error: {e}")
        return {"slug": slug, "matched": False, "candidates": candidates, "error": str(e)}

# ============ SEO GENERATION ============

class SeoGenerateRequest(BaseModel):
    product_name: str
    product_url: Optional[str] = ""
    current_title: Optional[str] = ""
    current_description: Optional[str] = ""
    category: Optional[str] = ""

@api_router.post("/seo/generate/{slug}")
async def generate_seo(slug: str, user: dict = Depends(get_current_user)):
    """Generate SEO content: scrapes product page for specs, then uses AI."""
    product = await db.products.find_one({"slug": slug})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    openai_key = os.environ.get("OPENAI_API_KEY")
    if not openai_key:
        raise HTTPException(status_code=500, detail="OpenAI API key not configured")
    
    # Step 1: Scrape our own product page for technical specs and description
    product_page_data = ""
    try:
        product_url = product.get("url", "")
        if product_url:
            async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as http_client:
                resp = await http_client.get(product_url, headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
                    "Accept-Language": "tr-TR,tr;q=0.9",
                })
                if resp.status_code == 200:
                    page_soup = BeautifulSoup(resp.text, "html.parser")
                    # Extract all text content from product details
                    page_text = page_soup.get_text(" ", strip=True)
                    # Find technical specs section
                    specs_section = ""
                    for keyword in ["Teknik Özellik", "Teknik Detay", "Özellikler", "Tip:", "En (mm):", "Boy (mm):", "Kapasite"]:
                        idx = page_text.find(keyword)
                        if idx != -1:
                            specs_section = page_text[max(0, idx-50):idx+2000]
                            break
                    # Also find product description
                    desc_section = ""
                    for keyword in ["Ürün Detayı", "Ürün Açıklama"]:
                        idx = page_text.find(keyword)
                        if idx != -1:
                            desc_section = page_text[idx:idx+2000]
                            break
                    product_page_data = f"MEVCUT ÜRÜN SAYFASI VERİLERİ:\n{specs_section}\n\n{desc_section}".strip()
                    if len(product_page_data) < 50:
                        product_page_data = page_text[:3000]
    except Exception as e:
        logger.warning(f"Product page scrape for SEO failed: {e}")
    
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        import json
        
        product_name = product['name']
        brand = product.get('brand', '')
        category = product.get('category_path', '')
        
        chat = LlmChat(
            api_key=openai_key,
            session_id=f"seo-{slug}-{uuid.uuid4().hex[:8]}",
            system_message="""Sen Türkiye'nin en deneyimli SEO ve içerik uzmanısın. Endüstriyel mutfak ekipmanları sektöründe 15 yıllık tecrüben var.
Arıgastro Endüstriyel Mutfak Ekipmanları (arigastro.com) firması için çalışıyorsun.

GÖREV: Verilen ürün için Google'da üst sıralarda çıkacak, organik trafiği artıracak, profesyonel ve kapsamlı SEO içerikleri hazırla.

KURALLAR:
1. SEO Title: Max 60 karakter. Ana anahtar kelimeyi başa yerleştir. Marka adını dahil et. FİYAT BİLGİSİ YAZMA.
2. SEO Description: Max 160 karakter. Call-to-action içermeli. FİYAT BİLGİSİ YAZMA.
3. Ürün Açıklaması: MİNİMUM 500 KELİME. Aşağıdaki yapıda olmalı:
   - Giriş paragrafı (ürünü tanıt, anahtar kelimeyi ilk cümlede kullan)
   - "## {Ürün Adı} Özellikleri" - ürünün öne çıkan özelliklerini madde madde anlat
   - "## {Ürün Adı} Teknik Detayları" - SANA VERİLEN TEKNİK ÖZELLİKLERİ MUTLAKA EKLE. Boyut, ağırlık, kapasite, güç, voltaj, malzeme gibi TÜM teknik verileri detaylı tablo formatında veya madde madde yaz. Teknik özellikleri kesinlikle ATLAMA.
   - "## {Ürün Adı} Fiyatı" - fiyat RAKAMI YAZMA, genel ifadeler kullan
   - "## {Ürün Adı} Neden Tercih Edilmeli?" - avantajları anlat
   - "## Sıkça Sorulan Sorular" - en az 3 soru-cevap
   - Kapanış paragrafı (CTA içermeli)
4. Keyword Density: Ürün adını %1-%1.5 arasında geçir. %2'yi AŞMA.
5. ASLA FİYAT RAKAMI YAZMA.
6. Sana verilen teknik özellikleri BİREBİR kullan, tahmin etme. Gerçek verileri yaz.
7. İçerik Türkçe, doğal, özgün ve profesyonel olmalı.

Yanıtını tam olarak şu JSON formatında ver:
{"seo_title": "...", "seo_description": "...", "product_description": "..."}"""
        ).with_model("openai", "gpt-4o")
        
        prompt = f"""Aşağıdaki ürün için kapsamlı SEO içerikleri hazırla:

ÜRÜN BİLGİLERİ:
- Ürün Adı: {product_name}
- Marka: {brand}
- Kategori: {category}
- GTIN: {product.get('gtin', '')}

{product_page_data}

HEDEF KİTLE: Restoran sahipleri, otel mutfak yöneticileri, catering firmaları

ÖNEMLİ:
- Yukarıdaki teknik özellikleri MUTLAKA "Teknik Detayları" bölümünde eksiksiz kullan.
- Ürün açıklaması MİNİMUM 500 KELİME olmalı.
- Her alt başlık altında en az 2-3 paragraf yaz.
- Ürün adını ({product_name}) %1-%1.5 oranında tekrarla.
- FİYAT RAKAMI YAZMA.
- Sıkça Sorulan Sorular en az 3 soru içermeli.

JSON formatında yanıt ver."""

        response = await chat.send_message(UserMessage(text=prompt))
        
        response_text = response.strip()
        if response_text.startswith("```"):
            response_text = re.sub(r'^```(?:json)?\s*', '', response_text)
            response_text = re.sub(r'\s*```$', '', response_text)
        
        seo_data = json.loads(response_text)
        
        desc = seo_data.get("product_description", "")
        word_count = len(desc.split())
        keyword_count = desc.lower().count(product_name.lower())
        keyword_density = round((keyword_count / max(word_count, 1)) * 100, 1)
        
        seo_record = {
            "product_slug": slug,
            "product_name": product_name,
            "seo_title": seo_data.get("seo_title", ""),
            "seo_description": seo_data.get("seo_description", ""),
            "product_description": desc,
            "word_count": word_count,
            "keyword_density": keyword_density,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "status": "draft"
        }
        
        await db.seo_content.update_one(
            {"product_slug": slug},
            {"$set": seo_record},
            upsert=True
        )
        
        return seo_record
    except json.JSONDecodeError as e:
        logger.error(f"JSON parse error in SEO generation: {e}, response: {response_text[:200]}")
        raise HTTPException(status_code=500, detail="AI yanıtı parse edilemedi. Lütfen tekrar deneyin.")
    except Exception as e:
        logger.error(f"SEO generation error: {e}")
        raise HTTPException(status_code=500, detail=f"SEO generation failed: {str(e)}")

@api_router.get("/seo/{slug}")
async def get_seo_content(slug: str, user: dict = Depends(get_current_user)):
    """Get existing SEO content for a product."""
    seo = await db.seo_content.find_one({"product_slug": slug}, {"_id": 0})
    return seo or {}

# ============ DASHBOARD ============

@api_router.get("/dashboard/stats")
async def get_dashboard_stats(user: dict = Depends(get_current_user)):
    total_products = await db.products.count_documents({})
    
    # Count tracked = products in tracked categories
    tracked_cats = await db.categories.find({"is_tracked": True}, {"_id": 0, "name": 1}).to_list(500)
    tracked_products = 0
    if tracked_cats:
        cat_names = [c["name"] for c in tracked_cats]
        cat_regex = "|".join([re.escape(n) for n in cat_names])
        tracked_products = await db.products.count_documents({"category_path": {"$regex": cat_regex, "$options": "i"}, "our_price": {"$ne": None}})
    
    matched_products = await db.products.count_documents({"akakce_matched": True})
    unmatched = tracked_products - matched_products if tracked_products > matched_products else 0
    
    # Products where competitors are cheaper
    cheaper_pipeline = [
        {"$match": {
            "cheapest_price": {"$ne": None},
            "our_price": {"$ne": None},
            "$expr": {"$lt": ["$cheapest_price", "$our_price"]}
        }},
        {"$count": "count"}
    ]
    cheaper_result = await db.products.aggregate(cheaper_pipeline).to_list(1)
    competitors_cheaper = cheaper_result[0]["count"] if cheaper_result else 0
    
    # Products where we are cheapest
    we_cheaper_pipeline = [
        {"$match": {
            "cheapest_price": {"$ne": None},
            "our_price": {"$ne": None},
            "$expr": {"$gte": ["$cheapest_price", "$our_price"]}
        }},
        {"$count": "count"}
    ]
    we_cheaper_result = await db.products.aggregate(we_cheaper_pipeline).to_list(1)
    we_are_cheaper = we_cheaper_result[0]["count"] if we_cheaper_result else 0
    
    # SEO generated count
    seo_count = await db.seo_content.count_documents({})
    
    total_categories = await db.categories.count_documents({})
    tracked_categories = await db.categories.count_documents({"is_tracked": True})
    
    # Recent price alerts (products where competitors recently became cheaper)
    recent_alerts = await db.products.find(
        {"cheapest_price": {"$ne": None}, "our_price": {"$ne": None}, "price_difference": {"$gt": 0}},
        {"_id": 0, "name": 1, "our_price": 1, "cheapest_price": 1, "cheapest_competitor": 1, "price_difference": 1, "slug": 1}
    ).sort("price_difference", -1).limit(10).to_list(10)
    
    return {
        "total_products": total_products,
        "tracked_products": tracked_products,
        "matched_products": matched_products,
        "unmatched_products": unmatched,
        "competitors_cheaper": competitors_cheaper,
        "we_are_cheaper": we_are_cheaper,
        "seo_generated": seo_count,
        "total_categories": total_categories,
        "tracked_categories": tracked_categories,
        "recent_alerts": recent_alerts
    }

# ============ PRICE TRACKING ============

@api_router.get("/price-tracking")
async def get_price_tracking(
    user: dict = Depends(get_current_user),
    filter_type: str = "all",
    search: str = "",
    page: int = 1,
    limit: int = 50
):
    """Get products from TRACKED CATEGORIES for price comparison."""
    # First get tracked categories
    tracked_cats = await db.categories.find({"is_tracked": True}, {"_id": 0, "name": 1}).to_list(500)
    if not tracked_cats:
        return {"products": [], "total": 0, "page": 1, "pages": 0, "message": "Aktif kategori yok. Kategoriler sayfasindan kategori aktif edin."}
    
    cat_names = [c["name"] for c in tracked_cats]
    cat_regex = "|".join([re.escape(n) for n in cat_names])
    
    # Base query: products in tracked categories with prices
    query = {
        "category_path": {"$regex": cat_regex, "$options": "i"},
        "our_price": {"$ne": None},
    }
    
    if filter_type == "cheaper":
        query["cheapest_price"] = {"$ne": None}
        query["$expr"] = {"$lt": ["$cheapest_price", "$our_price"]}
    elif filter_type == "expensive":
        query["cheapest_price"] = {"$ne": None}
        query["$expr"] = {"$gte": ["$cheapest_price", "$our_price"]}
    elif filter_type == "matched":
        query["akakce_matched"] = True
    elif filter_type == "unmatched":
        query["$or"] = [{"akakce_matched": {"$ne": True}}, {"akakce_product_url": {"$in": [None, ""]}}]
    
    if search:
        query["name"] = {"$regex": search, "$options": "i"}
    
    skip = (page - 1) * limit
    total = await db.products.count_documents(query)
    
    sort_field = "price_difference" if filter_type in ["cheaper", "expensive"] else "name"
    sort_dir = -1 if filter_type == "cheaper" else 1
    products = await db.products.find(query, {"_id": 0}).sort(sort_field, sort_dir).skip(skip).limit(limit).to_list(limit)
    
    # Stats
    matched_count = await db.products.count_documents({**query, "akakce_matched": True}) if filter_type == "all" else 0
    
    return {
        "products": products, "total": total, "page": page,
        "pages": (total + limit - 1) // limit,
        "tracked_categories": len(tracked_cats),
        "matched_count": matched_count,
    }

@api_router.get("/price-history/{slug}")
async def get_price_history(slug: str, user: dict = Depends(get_current_user)):
    history = await db.price_history.find({"product_slug": slug}, {"_id": 0}).sort("checked_at", -1).limit(30).to_list(30)
    return history

# ============ BULK OPERATIONS ============

class BulkPriceUpdate(BaseModel):
    products: List[dict]  # [{slug: str, our_price: float}]

@api_router.post("/products/bulk-update-prices")
async def bulk_update_prices(data: BulkPriceUpdate, user: dict = Depends(get_current_user)):
    updated = 0
    for item in data.products:
        if "slug" in item and "our_price" in item:
            result = await db.products.update_one(
                {"slug": item["slug"]},
                {"$set": {"our_price": item["our_price"], "updated_at": datetime.now(timezone.utc).isoformat()}}
            )
            if result.modified_count:
                updated += 1
    return {"updated": updated}

@api_router.post("/products/bulk-check-akakce")
async def bulk_check_akakce(user: dict = Depends(get_current_user)):
    """Start bulk price check as background task."""
    status = await db.system_status.find_one({"task": "price_check"}, {"_id": 0})
    if status and status.get("running"):
        return {"started": False, "message": "Fiyat kontrolu zaten calisiyor.", "progress": status}
    
    tracked_cats = await db.categories.find({"is_tracked": True}, {"_id": 0, "name": 1}).to_list(500)
    if not tracked_cats:
        return {"started": False, "error": "Aktif kategori yok."}
    
    cat_names = [c["name"] for c in tracked_cats]
    cat_regex = "|".join([re.escape(n) for n in cat_names])
    
    count = await db.products.count_documents({
        "category_path": {"$regex": cat_regex, "$options": "i"},
        "akakce_product_url": {"$exists": True, "$ne": ""},
        "akakce_matched": True,
    })
    
    if count == 0:
        return {"started": False, "error": "Eslesmis urun yok. Once AI Eslestirme yapin."}
    
    await db.system_status.update_one(
        {"task": "price_check"},
        {"$set": {"running": True, "started_at": datetime.now(timezone.utc).isoformat(), "checked": 0, "success": 0, "failed": 0, "total": count, "current": 0}},
        upsert=True
    )
    
    asyncio.ensure_future(run_bulk_price_check(cat_regex))
    return {"started": True, "message": f"Fiyat kontrolu basladi. {count} eslesmis urun kontrol edilecek."}

async def run_bulk_price_check(cat_regex: str):
    """Background task for bulk price checking."""
    try:
        products = await db.products.find(
            {
                "category_path": {"$regex": cat_regex, "$options": "i"},
                "akakce_product_url": {"$exists": True, "$ne": ""},
                "akakce_matched": True,
            },
            {"_id": 0, "slug": 1, "name": 1, "akakce_product_url": 1, "our_price": 1}
        ).to_list(5000)
        
        checked = 0
        success = 0
        failed = 0
        
        for i, product in enumerate(products):
            try:
                await db.system_status.update_one({"task": "price_check"}, {"$set": {"current": i + 1, "current_product": product["name"][:50]}})
                
                result = await fetch_akakce_product_page(product["akakce_product_url"])
                update_data = {"last_price_check": datetime.now(timezone.utc).isoformat(), "updated_at": datetime.now(timezone.utc).isoformat()}
                
                if result["success"] and result["sellers"]:
                    competitors = [s for s in result["sellers"] if "arigastro" not in s["seller"].lower()]
                    all_sellers = result["sellers"]
                    our_pos = next((j+1 for j,s in enumerate(all_sellers) if "arigastro" in s["seller"].lower()), None)
                    if competitors:
                        cheapest = competitors[0]
                        update_data.update({
                            "cheapest_competitor": cheapest["seller"], "cheapest_price": cheapest["price"],
                            "competitors": competitors, "all_sellers": all_sellers,
                            "our_position": our_pos, "total_sellers": len(all_sellers),
                        })
                        if product.get("our_price"):
                            update_data["price_difference"] = round(product["our_price"] - cheapest["price"], 2)
                    success += 1
                else:
                    failed += 1
                
                await db.products.update_one({"slug": product["slug"]}, {"$set": update_data})
                checked += 1
                await db.system_status.update_one({"task": "price_check"}, {"$set": {"checked": checked, "success": success, "failed": failed}})
                await asyncio.sleep(random.uniform(3, 6))
            except Exception as e:
                logger.error(f"Price check error for {product.get('slug','?')}: {e}")
                failed += 1
        
        await db.system_status.update_one({"task": "price_check"}, {"$set": {
            "running": False, "checked": checked, "success": success, "failed": failed,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }})
    except Exception as e:
        logger.error(f"Bulk price check error: {e}")
        await db.system_status.update_one({"task": "price_check"}, {"$set": {"running": False, "error": str(e)}})

@api_router.post("/products/bulk-ai-match")
async def bulk_ai_match(request: Request, user: dict = Depends(get_current_user)):
    """Start AI matching as background task. Returns immediately."""
    from fastapi import BackgroundTasks
    
    # Check if already running
    status = await db.system_status.find_one({"task": "ai_match"}, {"_id": 0})
    if status and status.get("running"):
        return {"started": False, "message": "AI eslestirme zaten calisiyor. Lutfen bekleyin.", "progress": status}
    
    # Mark as running
    await db.system_status.update_one(
        {"task": "ai_match"},
        {"$set": {"running": True, "started_at": datetime.now(timezone.utc).isoformat(), "matched": 0, "failed": 0, "skipped": 0, "total": 0, "current": 0}},
        upsert=True
    )
    
    # Start background task
    asyncio.ensure_future(run_bulk_ai_match())
    
    return {"started": True, "message": "AI eslestirme basladi. İlerlemeyi takip edebilirsiniz."}

async def run_bulk_ai_match():
    """Background task for AI matching."""
    try:
        tracked_cats = await db.categories.find({"is_tracked": True}, {"_id": 0, "name": 1}).to_list(500)
        if not tracked_cats:
            await db.system_status.update_one({"task": "ai_match"}, {"$set": {"running": False, "error": "Aktif kategori yok."}})
            return
        
        cat_names = [c["name"] for c in tracked_cats]
        cat_regex = "|".join([re.escape(n) for n in cat_names])
        
        products = await db.products.find(
            {
                "category_path": {"$regex": cat_regex, "$options": "i"},
                "our_price": {"$ne": None},
                "akakce_matched": {"$ne": True},
            },
            {"_id": 0, "slug": 1, "name": 1, "brand": 1, "gtin": 1}
        ).to_list(5000)  # No limit - process all unmatched products
        
        await db.system_status.update_one({"task": "ai_match"}, {"$set": {"total": len(products)}})
        
        openai_key = os.environ.get("OPENAI_API_KEY")
        if not openai_key:
            await db.system_status.update_one({"task": "ai_match"}, {"$set": {"running": False, "error": "OpenAI API key yok"}})
            return
        
        matched = 0
        failed = 0
        skipped = 0
        
        for i, product in enumerate(products):
            try:
                await db.system_status.update_one({"task": "ai_match"}, {"$set": {"current": i + 1, "current_product": product["name"][:50]}})
                
                loop = asyncio.get_event_loop()
                search_result = await loop.run_in_executor(None, search_akakce_sync, product["name"])
                if not search_result["success"] or not search_result.get("competitors"):
                    await db.products.update_one({"slug": product["slug"]}, {"$set": {
                        "akakce_matched": False, "akakce_match_confidence": "not_found",
                        "akakce_product_name": "Akakce'de bulunamadi",
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    }})
                    failed += 1
                    await asyncio.sleep(random.uniform(3, 5))
                    continue
                
                candidates = search_result["competitors"]
                from emergentintegrations.llm.chat import LlmChat, UserMessage
                import json as json_mod
                
                chat = LlmChat(
                    api_key=openai_key,
                    session_id=f"match-{product['slug'][:20]}-{uuid.uuid4().hex[:6]}",
                    system_message="""Ürün eşleştirme uzmanısın. Bizim ürünümüzle Akakçe'deki AYNI ürünü bulmalısın.

KRİTİK KURALLAR:
- Marka AYNI olmalı (Öztiryakiler = Öztiryakiler)
- Ürün tipi AYNI olmalı (Fritöz = Fritöz, Tava = Tava)
- BOYUT/ÖLÇÜ KRİTİK: 40x60 ile 60x60 FARKLI üründür! Boyutlar eşleşmeli. * ve x aynı anlamda.
- Seri numarası eşleşmeli (600 Seri = 600 Seri)
- Enerji tipi eşleşmeli (Elektrikli = Elektrikli, Gazlı = Gazlı)
- Emin değilsen bile en yakın eşleşmeyi "medium" ile seç
- Sadece tamamen farklı bir ürünse veya boyut/ölçü uyuşmuyorsa -1 döndür

JSON yanıt: {"match_index": 0, "confidence": "high/medium/low"} veya {"match_index": -1, "confidence": "none"}"""
                ).with_model("openai", "gpt-4o")
                
                cands = "\n".join([f"{i}. {c['name']} ({c.get('url','')})" for i, c in enumerate(candidates[:8])])
                resp_ai = await chat.send_message(UserMessage(text=f"Urun: {product['name']}\nMarka: {product.get('brand','')}\nGTIN: {product.get('gtin','')}\n\nAdaylar:\n{cands}"))
                resp_text = resp_ai.strip()
                if resp_text.startswith("```"):
                    resp_text = re.sub(r'^```(?:json)?\s*', '', resp_text)
                    resp_text = re.sub(r'\s*```$', '', resp_text)
                ai_result = json_mod.loads(resp_text)
                
                idx = ai_result.get("match_index", -1)
                conf = ai_result.get("confidence", "none")
                if idx >= 0 and idx < len(candidates) and conf in ["high", "medium"]:
                    m = candidates[idx]
                    await db.products.update_one({"slug": product["slug"]}, {"$set": {
                        "akakce_product_url": m.get("url", ""), "akakce_product_name": m["name"],
                        "akakce_matched": True, "akakce_match_confidence": conf, "is_tracked": True,
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    }})
                    matched += 1
                else:
                    await db.products.update_one({"slug": product["slug"]}, {"$set": {
                        "akakce_matched": False, "akakce_match_confidence": "ai_uncertain",
                        "akakce_product_name": "AI eslestirme basarisiz - manuel eslestirme gerekli",
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    }})
                    skipped += 1
                
                await db.system_status.update_one({"task": "ai_match"}, {"$set": {"matched": matched, "failed": failed, "skipped": skipped}})
                await asyncio.sleep(random.uniform(3, 5))
            except Exception as e:
                logger.error(f"Bulk AI match error for {product.get('slug','?')}: {e}")
                failed += 1
        
        await db.system_status.update_one({"task": "ai_match"}, {"$set": {
            "running": False, "matched": matched, "failed": failed, "skipped": skipped,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }})
    except Exception as e:
        logger.error(f"Bulk AI match background error: {e}")
        await db.system_status.update_one({"task": "ai_match"}, {"$set": {"running": False, "error": str(e)}})

# ============ ROOT ============

@api_router.get("/")
async def root():
    return {"message": "ARI AI API is running", "version": "1.0"}

# Include router
app.include_router(api_router)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Startup
@app.on_event("startup")
async def startup():
    # Create indexes
    await db.users.create_index("username", unique=True)
    await db.products.create_index("slug", unique=True)
    await db.categories.create_index("slug", unique=True)
    await db.price_history.create_index("product_slug")
    await db.seo_content.create_index("product_slug", unique=True)
    
    # Seed admin
    admin_username = os.environ.get("ADMIN_USERNAME", "admin").lower()
    admin_password = os.environ.get("ADMIN_PASSWORD", "admin123")
    existing = await db.users.find_one({"username": admin_username})
    if not existing:
        await db.users.insert_one({
            "username": admin_username,
            "password_hash": hash_password(admin_password),
            "name": "Arıgastro Admin",
            "role": "admin",
            "created_at": datetime.now(timezone.utc).isoformat()
        })
        logger.info(f"Admin user '{admin_username}' created")
    elif not verify_password(admin_password, existing["password_hash"]):
        await db.users.update_one({"username": admin_username}, {"$set": {"password_hash": hash_password(admin_password)}})
        logger.info(f"Admin password updated for '{admin_username}'")
    
    # Write test credentials
    os.makedirs("/app/memory", exist_ok=True)
    with open("/app/memory/test_credentials.md", "w") as f:
        f.write(f"# Test Credentials\n\n")
        f.write(f"## Admin\n- Username: {admin_username}\n- Password: {admin_password}\n- Role: admin\n\n")
        f.write(f"## Auth Endpoints\n- POST /api/auth/login\n- GET /api/auth/me\n- POST /api/auth/logout\n")

@app.on_event("shutdown")
async def shutdown():
    client.close()
