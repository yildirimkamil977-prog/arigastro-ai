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

# ============ AKAKCE SCRAPING (curl_cffi + proxy support) ============

AKAKCE_SEARCH_URL = "https://www.akakce.com/arama/?q={query}"
AKAKCE_PROXY = os.environ.get("AKAKCE_PROXY", "")  # Optional: http://user:pass@proxy:port

def akakce_request(url: str):
    """Make request to Akakçe using curl_cffi with Chrome impersonation (bypasses Cloudflare TLS fingerprinting)."""
    try:
        from curl_cffi import requests as cffi_requests
        kwargs = {"impersonate": "chrome", "timeout": 15}
        if AKAKCE_PROXY:
            kwargs["proxies"] = {"http": AKAKCE_PROXY, "https": AKAKCE_PROXY}
        resp = cffi_requests.get(url, **kwargs)
        return resp
    except ImportError:
        logger.warning("curl_cffi not installed, falling back to httpx")
        import httpx as httpx_sync
        resp = httpx_sync.get(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        }, timeout=15, follow_redirects=True)
        return resp

def search_akakce_sync(product_name: str) -> dict:
    """Search Akakçe for a product. Uses curl_cffi with Chrome impersonation."""
    try:
        search_query = product_name.replace(" ", "+")
        url = AKAKCE_SEARCH_URL.format(query=search_query)
        
        resp = akakce_request(url)
        
        if resp.status_code == 403:
            return {
                "success": False,
                "error": "Akakce Cloudflare korumasi (403). Bu sunucunun IP'si datacenter IP olarak engelleniyor. Cozum: AKAKCE_PROXY env degiskeniyle bir residential proxy ekleyin veya sistemi kendi sunucunuza deploy edin.",
                "competitors": [],
                "search_url": url,
            }
        if resp.status_code != 200:
            return {"success": False, "error": f"HTTP {resp.status_code}", "competitors": [], "search_url": url}
        
        soup = BeautifulSoup(resp.content if hasattr(resp, 'content') else resp.text, "html.parser")
        results = []
        
        # Strategy 1: Find product cards with links and prices (Akakçe typical structure)
        for a_tag in soup.select("a[href*='/en-ucuz-']"):
            try:
                title = a_tag.get("title", "") or a_tag.get_text(strip=True)
                parent = a_tag.find_parent("li") or a_tag.find_parent("div")
                if not parent:
                    continue
                text = parent.get_text(" ", strip=True)
                price_matches = re.findall(r'([\d.]+)\s*,(\d{2})\s*TL', text)
                if price_matches:
                    price_str = price_matches[0][0].replace(".", "") + "." + price_matches[0][1]
                    price = float(price_str)
                    href = a_tag.get("href", "")
                    if href and not href.startswith("http"):
                        href = f"https://www.akakce.com{href}"
                    if price > 1 and title and len(title) > 3:
                        results.append({"name": title[:120], "price": price, "url": href})
            except Exception:
                continue
        
        # Strategy 2: Product detail page price selectors (from user's bot)
        if not results:
            for cls in ["pt_v8", "ps_v8", "pr_v8"]:
                el = soup.find("span", class_=cls)
                if el:
                    price = parse_turkish_price(el.text + " TL")
                    h1 = soup.find("h1")
                    name = h1.get_text(strip=True) if h1 else "Akakce urun"
                    if price and price > 1:
                        results.append({"name": name[:120], "price": price, "url": url})
        
        # Strategy 3: Fallback - find all TL prices on page
        if not results:
            page_text = soup.get_text()
            price_matches = re.findall(r'([\d.]+)\s*,(\d{2})\s*TL', page_text)
            for pm in price_matches[:5]:
                price_str = pm[0].replace(".", "") + "." + pm[1]
                try:
                    price = float(price_str)
                    if price > 1:
                        results.append({"name": "Akakce sonucu", "price": price, "url": url})
                except (ValueError, TypeError):
                    continue
        
        # Deduplicate
        seen = set()
        unique = []
        for r in results:
            key = f"{r['name'][:30]}_{r['price']}"
            if key not in seen:
                seen.add(key)
                unique.append(r)
        
        return {
            "success": len(unique) > 0,
            "search_url": url,
            "competitors": sorted(unique, key=lambda x: x["price"])[:10],
            "error": None if unique else "Sonuc bulunamadi",
        }
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
    try:
        loop = asyncio.get_event_loop()
        resp = await loop.run_in_executor(None, lambda: akakce_request(url))
        
        if resp.status_code == 403:
            return {"success": False, "error": "Akakce Cloudflare korumasi (403). Residential IP veya proxy gerekli.", "sellers": []}
        if resp.status_code != 200:
            return {"success": False, "error": f"HTTP {resp.status_code}", "sellers": []}
        
        soup = BeautifulSoup(resp.content if hasattr(resp, 'content') else resp.text, "html.parser")
        
        product_name = ""
        h1 = soup.find("h1")
        if h1:
            product_name = h1.get_text(strip=True)
        
        sellers = []
        # Parse seller listings from Akakçe product page
        # Each seller block contains price + seller name
        for li in soup.select("li[class], div[class]"):
            text = li.get_text(" ", strip=True)
            price_match = re.search(r'([\d.]+)\s*,(\d{2})\s*TL', text)
            if not price_match:
                continue
            
            price_str = price_match.group(1).replace(".", "") + "." + price_match.group(2)
            try:
                price = float(price_str)
            except ValueError:
                continue
            
            # Find seller name - usually bold or in specific elements
            seller_name = ""
            bold = li.select_one("b, strong, .v_v8")
            if bold:
                seller_name = bold.get_text(strip=True)
            
            if not seller_name:
                # Look for known patterns
                for pattern in [r'Stokta.*?([A-Za-zğüşıöçĞÜŞİÖÇ0-9.]+\.com[.a-z]*)', r'\*\*([^*]+)\*\*']:
                    m = re.search(pattern, text)
                    if m:
                        seller_name = m.group(1).strip()
                        break
            
            if price > 1 and seller_name and len(seller_name) > 2:
                sellers.append({"seller": seller_name, "price": price})
        
        # Deduplicate sellers
        seen = set()
        unique_sellers = []
        for s in sellers:
            key = s["seller"].lower()
            if key not in seen:
                seen.add(key)
                unique_sellers.append(s)
        
        return {
            "success": len(unique_sellers) > 0,
            "product_name": product_name,
            "sellers": sorted(unique_sellers, key=lambda x: x["price"]),
            "error": None if unique_sellers else "Satici bilgisi okunamadi"
        }
    except Exception as e:
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
    """Generate professional SEO content with SERP analysis using OpenAI."""
    product = await db.products.find_one({"slug": slug})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    openai_key = os.environ.get("OPENAI_API_KEY")
    if not openai_key:
        raise HTTPException(status_code=500, detail="OpenAI API key not configured")
    
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        import json
        
        product_name = product['name']
        brand = product.get('brand', '')
        category = product.get('category_path', '')
        price = product.get('our_price', '')
        
        chat = LlmChat(
            api_key=openai_key,
            session_id=f"seo-{slug}-{uuid.uuid4().hex[:8]}",
            system_message="""Sen Türkiye'nin en deneyimli SEO ve içerik uzmanısın. Endüstriyel mutfak ekipmanları sektöründe 15 yıllık tecrüben var.
Arıgastro Endüstriyel Mutfak Ekipmanları (arigastro.com) firması için çalışıyorsun.

GÖREV: Verilen ürün için Google'da üst sıralarda çıkacak, organik trafiği artıracak, profesyonel ve kapsamlı SEO içerikleri hazırla.

KURALLAR:
1. SEO Title: Max 60 karakter. Ana anahtar kelimeyi başa yerleştir. Marka adını dahil et. Tıklanma oranını artıracak şekilde yaz.
2. SEO Description: Max 160 karakter. Call-to-action içermeli. Fiyat bilgisi veya "En uygun fiyat" gibi tetikleyiciler kullan.
3. Ürün Açıklaması: MİNİMUM 500 KELİME (BU ZORUNLU, 500'DEN AZ KELİME KABUL EDİLMEZ). Aşağıdaki yapıda olmalı:
   - Giriş paragrafı (ürünü tanıt, anahtar kelimeyi ilk cümlede kullan)
   - "## {Ürün Adı} Özellikleri" alt başlığı
   - "## {Ürün Adı} Teknik Detayları" alt başlığı  
   - "## {Ürün Adı} Fiyatı" alt başlığı (insanların aradığı SEO başlığı)
   - "## {Ürün Adı} Neden Tercih Edilmeli?" alt başlığı
   - "## Sıkça Sorulan Sorular" alt başlığı (2-3 SSS)
   - Kapanış paragrafı (CTA içermeli)
4. Keyword Density: Ürün adını metin içinde %1 ile %2 arasında geçir (doğal şekilde).
5. Rakip sitelerin kullandığı anahtar kelimeleri tahmin et ve içeriğe serpiştir.
6. İçerik tamamen Türkçe, doğal, özgün ve profesyonel olmalı. Yapay zeka tarafından yazıldığı anlaşılmamalı.

Yanıtını tam olarak şu JSON formatında ver, başka hiçbir şey ekleme:
{"seo_title": "...", "seo_description": "...", "product_description": "..."}"""
        ).with_model("openai", "gpt-4o")
        
        prompt = f"""Aşağıdaki ürün için kapsamlı SEO içerikleri hazırla:

ÜRÜN BİLGİLERİ:
- Ürün Adı: {product_name}
- Marka: {brand}
- Kategori: {category}
- Fiyat: {price} TL
- Ürün URL: {product.get('url', '')}
- GTIN: {product.get('gtin', '')}

HEDEF KİTLE: Restoran sahipleri, otel mutfak yöneticileri, catering firmaları, endüstriyel mutfak kurulumcuları

RAKIP ANALİZİ TAHMİNİ:
- Rakiplerin muhtemelen kullandığı anahtar kelimeler: "{product_name}", "{product_name} fiyat", "{product_name} fiyatı", "{brand} {category.split('>')[-1].strip() if '>' in str(category) else ''}", "en uygun {product_name}", "{product_name} özellikleri", "{product_name} satın al"
- Bu anahtar kelimeleri doğal şekilde içeriğe serpiştir.

ÖNEMLI:
- Ürün açıklaması MİNİMUM 500 KELİME olmalı. Bu kesindir, kısaltma.
- Her alt başlık altında en az 2-3 paragraf yaz.
- Ürün adını ({product_name}) metin boyunca %1-%2 oranında tekrarla.
- Alt başlıklarda ## formatını kullan.
- "{product_name} Fiyatı" başlığı mutlaka olmalı.
- "{product_name} Neden Tercih Edilmeli?" başlığı mutlaka olmalı.
- "Sıkça Sorulan Sorular" bölümü en az 3 soru içermeli.
- İçerik özgün, insani ve profesyonel olmalı.

JSON formatında yanıt ver."""

        response = await chat.send_message(UserMessage(text=prompt))
        
        response_text = response.strip()
        if response_text.startswith("```"):
            response_text = re.sub(r'^```(?:json)?\s*', '', response_text)
            response_text = re.sub(r'\s*```$', '', response_text)
        
        seo_data = json.loads(response_text)
        
        # Calculate word count and keyword density
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
    tracked_products = await db.products.count_documents({"is_tracked": True})
    matched_products = await db.products.count_documents({"akakce_matched": True})
    unmatched = await db.products.count_documents({"akakce_matched": False})
    
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
    """Get products with price comparison data."""
    query = {"akakce_matched": True}
    
    if filter_type == "cheaper":
        query["$expr"] = {"$lt": ["$cheapest_price", "$our_price"]}
        query["cheapest_price"] = {"$ne": None}
        query["our_price"] = {"$ne": None}
    elif filter_type == "expensive":
        query["$expr"] = {"$gte": ["$cheapest_price", "$our_price"]}
        query["cheapest_price"] = {"$ne": None}
        query["our_price"] = {"$ne": None}
    
    if search:
        query["name"] = {"$regex": search, "$options": "i"}
    
    skip = (page - 1) * limit
    total = await db.products.count_documents(query)
    products = await db.products.find(query, {"_id": 0}).sort("price_difference", -1).skip(skip).limit(limit).to_list(limit)
    
    return {"products": products, "total": total, "page": page, "pages": (total + limit - 1) // limit}

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
    """Check Akakçe prices for products in TRACKED CATEGORIES only. Rate limited."""
    # Get tracked category names
    tracked_cats = await db.categories.find({"is_tracked": True}, {"_id": 0, "name": 1, "slug": 1}).to_list(500)
    if not tracked_cats:
        return {"checked": 0, "matched": 0, "failed": 0, "error": "Aktif kategori yok. Once Kategoriler sayfasindan takip edilecek kategorileri secin."}
    
    # Build regex pattern from tracked category names
    cat_names = [c["name"] for c in tracked_cats]
    cat_regex = "|".join([re.escape(name) for name in cat_names])
    
    # Find products whose category_path matches any tracked category
    products = await db.products.find(
        {"category_path": {"$regex": cat_regex, "$options": "i"}, "our_price": {"$ne": None}},
        {"_id": 0, "slug": 1, "name": 1}
    ).limit(20).to_list(20)
    
    results = {"checked": 0, "matched": 0, "failed": 0, "total_in_tracked_cats": len(products), "tracked_categories": len(tracked_cats)}
    
    for product in products:
        try:
            result = await search_akakce(product["name"])
            update_data = {
                "last_price_check": datetime.now(timezone.utc).isoformat(),
                "akakce_matched": result["success"],
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "is_tracked": True,
            }
            if result["success"] and result["competitors"]:
                cheapest = result["competitors"][0]
                update_data["cheapest_competitor"] = cheapest["name"]
                update_data["cheapest_price"] = cheapest["price"]
                update_data["competitors"] = result["competitors"]
                update_data["akakce_url"] = result.get("search_url", "")
                
                p = await db.products.find_one({"slug": product["slug"]})
                if p and p.get("our_price"):
                    update_data["price_difference"] = round(p["our_price"] - cheapest["price"], 2)
                
                results["matched"] += 1
            else:
                results["failed"] += 1
            
            await db.products.update_one({"slug": product["slug"]}, {"$set": update_data})
            results["checked"] += 1
            
            # Rate limiting - wait between requests (matching user's bot: 5-8 seconds)
            await asyncio.sleep(random.uniform(5, 8))
        except Exception as e:
            logger.error(f"Bulk check error for {product['slug']}: {e}")
            results["failed"] += 1
    
    return results

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
