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
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

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
    response.set_cookie(key="access_token", value=token, httponly=True, secure=True, samesite="lax", max_age=86400, path="/")
    return {"id": str(user["_id"]), "username": user["username"], "name": user.get("name", ""), "role": user.get("role", "user"), "token": token}

@api_router.get("/auth/me")
async def get_me(user: dict = Depends(get_current_user)):
    return user

@api_router.post("/auth/logout")
async def logout(response: Response):
    response.delete_cookie("access_token", path="/")
    return {"message": "Logged out"}

# ============ MARKDOWN TO HTML ============

def markdown_to_html(md_text: str) -> str:
    """Convert markdown to clean HTML for İkas product descriptions."""
    if not md_text:
        return ""
    lines = md_text.split("\n")
    html_lines = []
    in_list = False
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            continue
        # Headings (h4, h3, h2, h1 — order matters, longest prefix first)
        if stripped.startswith("#### "):
            if in_list: html_lines.append("</ul>"); in_list = False
            title = re.sub(r'\*\*(.*?)\*\*', r'\1', stripped[5:])
            html_lines.append(f"<h4>{title}</h4>")
        elif stripped.startswith("### "):
            if in_list: html_lines.append("</ul>"); in_list = False
            title = re.sub(r'\*\*(.*?)\*\*', r'\1', stripped[4:])
            html_lines.append(f"<h3>{title}</h3>")
        elif stripped.startswith("## "):
            if in_list: html_lines.append("</ul>"); in_list = False
            title = re.sub(r'\*\*(.*?)\*\*', r'\1', stripped[3:])
            html_lines.append(f"<h2>{title}</h2>")
        elif stripped.startswith("# "):
            if in_list: html_lines.append("</ul>"); in_list = False
            title = re.sub(r'\*\*(.*?)\*\*', r'\1', stripped[2:])
            html_lines.append(f"<h1>{title}</h1>")
        elif stripped.startswith("- ") or stripped.startswith("* "):
            if not in_list:
                html_lines.append("<ul>")
                in_list = True
            item = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', stripped[2:])
            html_lines.append(f"<li>{item}</li>")
        else:
            if in_list: html_lines.append("</ul>"); in_list = False
            text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', stripped)
            html_lines.append(f"<p>{text}</p>")
    if in_list:
        html_lines.append("</ul>")
    return "\n".join(html_lines)

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
            tracked_filter = build_tracked_query(cat_names)
            query.update(tracked_filter)
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
    """Get AI matching progress. Auto-resets stuck tasks (>20 min idle)."""
    status = await db.system_status.find_one({"task": "ai_match"}, {"_id": 0})
    if status and status.get("running"):
        started = status.get("started_at", "")
        if started:
            try:
                started_dt = datetime.fromisoformat(started)
                elapsed = (datetime.now(timezone.utc) - started_dt).total_seconds()
                if elapsed > 1200:  # 20 minutes
                    logger.warning(f"AI match stuck for {elapsed:.0f}s, auto-resetting")
                    await db.system_status.update_one({"task": "ai_match"}, {"$set": {
                        "running": False, "error": "Gorev otomatik sifirlandi (20dk+ yanit yok)",
                        "completed_at": datetime.now(timezone.utc).isoformat()
                    }})
                    status["running"] = False
                    status["error"] = "Gorev otomatik sifirlandi (20dk+ yanit yok)"
            except Exception:
                pass
    return status or {"running": False, "matched": 0, "failed": 0, "skipped": 0, "total": 0}

@api_router.get("/products/price-check-status")
async def price_check_status(user: dict = Depends(get_current_user)):
    status = await db.system_status.find_one({"task": "price_check"}, {"_id": 0})
    if status and status.get("running"):
        started = status.get("started_at", "")
        if started:
            try:
                started_dt = datetime.fromisoformat(started)
                elapsed = (datetime.now(timezone.utc) - started_dt).total_seconds()
                if elapsed > 1800:  # 30 minutes
                    logger.warning(f"Price check stuck for {elapsed:.0f}s, auto-resetting")
                    await db.system_status.update_one({"task": "price_check"}, {"$set": {
                        "running": False, "error": "Gorev otomatik sifirlandi (30dk+ yanit yok)",
                        "completed_at": datetime.now(timezone.utc).isoformat()
                    }})
                    status["running"] = False
            except Exception:
                pass
    return status or {"running": False, "checked": 0, "success": 0, "failed": 0, "total": 0}

@api_router.post("/products/reset-task-status")
async def reset_task_status(user: dict = Depends(get_current_user)):
    """Manually reset stuck task statuses."""
    await db.system_status.update_many(
        {"running": True},
        {"$set": {"running": False, "error": "Manuel sifirlama", "completed_at": datetime.now(timezone.utc).isoformat()}}
    )
    return {"message": "Tum gorevler sifirlandi"}

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
    
    # Mark products NOT in feed as inactive
    feed_slugs = set(item.get("slug", "") for item in feed_items if item.get("slug"))
    all_slugs = await db.products.find({}, {"_id": 0, "slug": 1}).to_list(10000)
    inactive_count = 0
    for p in all_slugs:
        if p["slug"] not in feed_slugs:
            await db.products.update_one({"slug": p["slug"]}, {"$set": {"feed_active": False}})
            inactive_count += 1
        else:
            await db.products.update_one({"slug": p["slug"]}, {"$set": {"feed_active": True}})
    
    active = await db.products.count_documents({"feed_active": True})
    return {
        "updated": updated,
        "new_products": new_products,
        "total_products": total,
        "active_products": active,
        "inactive_products": inactive_count,
        "products_with_price": priced,
        "feed_items": len(feed_items),
        "message": f"{updated} urun guncellendi, {new_products} yeni urun eklendi, {inactive_count} urun pasif yapildi"
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

# ============ AKAKCE PANEL IMPORT (FREE - no ScraperAPI needed) ============

AKAKCE_EMAIL = os.environ.get("AKAKCE_EMAIL", "")
AKAKCE_PASSWORD = os.environ.get("AKAKCE_PASSWORD", "")

async def scrape_akakce_panel() -> dict:
    """Login to Akakçe seller panel via ScraperAPI and scrape all product links."""
    import requests as req_sync
    
    if not AKAKCE_EMAIL or not AKAKCE_PASSWORD:
        return {"success": False, "error": "AKAKCE_EMAIL ve AKAKCE_PASSWORD .env dosyasinda tanimlanmali"}
    
    if not SCRAPERAPI_KEY:
        return {"success": False, "error": "SCRAPERAPI_KEY gerekli"}
    
    session = req_sync.Session()
    
    try:
        # Step 1: Login via ScraperAPI
        logger.info("Akakce panel: ScraperAPI ile giris yapiliyor...")
        login_resp = session.post("http://api.scraperapi.com", params={
            "api_key": SCRAPERAPI_KEY,
            "url": "https://www.akakce.com/akakcem/giris.asp",
            "method": "POST",
        }, data={
            "email": AKAKCE_EMAIL,
            "password": AKAKCE_PASSWORD,
        }, timeout=60, allow_redirects=True)
        
        logger.info(f"Akakce panel login attempt: status={login_resp.status_code}, len={len(login_resp.text)}")
        
        # Try getting cookies from response for session
        # ScraperAPI may not forward cookies properly, so try direct session approach
        # Step 1b: Try using ScraperAPI session/cookie support
        # First get the login page to get any CSRF tokens
        login_page = session.get("http://api.scraperapi.com", params={
            "api_key": SCRAPERAPI_KEY,
            "url": "https://www.akakce.com/akakcem/giris.asp",
            "keep_headers": "true",
        }, timeout=60)
        
        # Extract any hidden form fields
        soup_login = BeautifulSoup(login_page.text, "html.parser")
        form_data = {}
        for inp in soup_login.find_all("input", {"type": "hidden"}):
            name = inp.get("name", "")
            value = inp.get("value", "")
            if name:
                form_data[name] = value
        form_data["email"] = AKAKCE_EMAIL
        form_data["password"] = AKAKCE_PASSWORD
        form_data["sifre"] = AKAKCE_PASSWORD
        
        logger.info(f"Login form fields: {list(form_data.keys())}")
        
        # Step 2: Try to access product list directly via ScraperAPI
        # Akakce panel might use different auth - try with cookies
        products = []
        page_num = 1
        max_pages = 250
        consecutive_empty = 0
        
        while page_num <= max_pages:
            list_url = f"https://www.akakce.com/akakcem/online-store/urun-yonetimi/urun-listesi.asp?sayfa={page_num}"
            
            resp = req_sync.get("http://api.scraperapi.com", params={
                "api_key": SCRAPERAPI_KEY,
                "url": list_url,
                "session_number": "12345",
            }, timeout=60)
            
            if resp.status_code != 200:
                logger.warning(f"Akakce panel page {page_num}: HTTP {resp.status_code}")
                break
            
            soup = BeautifulSoup(resp.text, "html.parser")
            
            # Check if we're on login page (not authenticated)
            if "giris" in resp.text.lower()[:500] and page_num == 1:
                # Try posting login through ScraperAPI
                logger.info("Login gerekli, ScraperAPI session ile deneniyor...")
                login_post = req_sync.post("http://api.scraperapi.com", params={
                    "api_key": SCRAPERAPI_KEY,
                    "url": "https://www.akakce.com/akakcem/giris.asp",
                    "session_number": "12345",
                }, json=form_data, timeout=60)
                logger.info(f"Session login: status={login_post.status_code}")
                
                # Retry the product list
                resp = req_sync.get("http://api.scraperapi.com", params={
                    "api_key": SCRAPERAPI_KEY,
                    "url": list_url,
                    "session_number": "12345",
                }, timeout=60)
                soup = BeautifulSoup(resp.text, "html.parser")
            
            found_on_page = 0
            for a_tag in soup.find_all("a", href=True):
                href = a_tag["href"]
                if "/en-ucuz-" in href and "fiyati," in href:
                    if not href.startswith("http"):
                        href = f"https://www.akakce.com{href}"
                    
                    name = a_tag.get_text(strip=True)
                    if not name or len(name) < 3:
                        td = a_tag.find_parent("td")
                        if td:
                            name = td.get_text(strip=True)
                    
                    price = None
                    row = a_tag.find_parent("tr")
                    if row:
                        text = row.get_text(" ", strip=True)
                        pm = re.findall(r'([\d.]+),(\d{2})\s*TL', text)
                        if pm:
                            price = float(pm[0][0].replace(".", "") + "." + pm[0][1])
                    
                    category = ""
                    brand = ""
                    if row:
                        tds = row.find_all("td")
                        if len(tds) >= 6:
                            category = tds[-3].get_text(strip=True) if len(tds) > 4 else ""
                            brand = tds[-2].get_text(strip=True) if len(tds) > 5 else ""
                    
                    products.append({
                        "akakce_url": href,
                        "akakce_name": name[:200],
                        "akakce_price": price,
                        "akakce_category": category,
                        "akakce_brand": brand,
                    })
                    found_on_page += 1
            
            logger.info(f"Akakce panel sayfa {page_num}: {found_on_page} urun bulundu (toplam: {len(products)})")
            
            if found_on_page == 0:
                consecutive_empty += 1
                if consecutive_empty >= 2:
                    break
            else:
                consecutive_empty = 0
            
            page_num += 1
            await asyncio.sleep(1)
        
        return {"success": len(products) > 0, "products": products, "total": len(products)}
    except Exception as e:
        logger.error(f"Akakce panel scrape error: {e}")
        return {"success": False, "error": str(e), "products": []}

@api_router.post("/akakce-panel/import")
async def import_from_akakce_panel(user: dict = Depends(get_current_user)):
    """Import product-Akakce URL mappings from uploaded JSON file. FREE - 0 credits!"""
    status = await db.system_status.find_one({"task": "akakce_panel_import"}, {"_id": 0})
    if status and status.get("running"):
        return {"started": False, "message": "Akakce panel aktarimi zaten calisiyor."}
    
    # Load the JSON file
    import json as json_mod
    json_path = os.path.join(os.path.dirname(__file__), "akakce_products.json")
    if not os.path.exists(json_path):
        return {"started": False, "error": "akakce_products.json dosyasi bulunamadi. Dosyayi backend klasorune yukleyin."}
    
    with open(json_path, "r", encoding="utf-8") as f:
        akakce_data = json_mod.load(f)
    
    if not akakce_data or not isinstance(akakce_data, list):
        return {"started": False, "error": "JSON dosyasi bos veya gecersiz."}
    
    await db.system_status.update_one(
        {"task": "akakce_panel_import"},
        {"$set": {"running": True, "started_at": datetime.now(timezone.utc).isoformat(), "matched": 0, "total": len(akakce_data)}},
        upsert=True
    )
    
    asyncio.ensure_future(run_akakce_json_import(akakce_data))
    return {"started": True, "message": f"Akakce aktarimi basladi. {len(akakce_data)} urun eslestirilecek."}

async def run_akakce_json_import(akakce_data: list):
    """Background task: match Akakce JSON data with our products using product names."""
    try:
        matched = 0
        not_found = 0
        search_url_count = 0
        
        our_products = await db.products.find({}, {"_id": 0, "slug": 1, "name": 1, "gtin": 1, "brand": 1}).to_list(10000)
        
        if not our_products:
            await db.system_status.update_one({"task": "akakce_panel_import"}, {"$set": {"running": False, "error": "Veritabaninda urun yok"}})
            return
        
        def normalize(text):
            return text.lower().replace("ö", "o").replace("ü", "u").replace("ş", "s").replace("ç", "c").replace("ğ", "g").replace("ı", "i").replace("İ", "i").replace(",", " ").replace(".", " ").replace("-", " ").replace("*", "x").strip()
        
        def get_words(text):
            return [w for w in normalize(text).split() if len(w) > 1]
        
        our_index = []
        for p in our_products:
            words = get_words(p.get("name", ""))
            our_index.append({"product": p, "words": set(words), "name_norm": normalize(p.get("name", ""))})
        
        for i, ap in enumerate(akakce_data):
            akakce_url = ap.get("url", "")
            akakce_name = ap.get("name", "")
            akakce_price = ap.get("price", "")
            
            if not akakce_url:
                not_found += 1
                continue
            
            is_product_url = "/en-ucuz-" in akakce_url and "fiyati," in akakce_url
            if not is_product_url:
                search_url_count += 1
            
            ak_words = set(get_words(akakce_name))
            best_match = None
            best_score = 0
            
            for entry in our_index:
                if not entry["words"]:
                    continue
                common = ak_words & entry["words"]
                if len(common) < 2:
                    continue
                score = len(common) / max(len(ak_words), len(entry["words"]))
                if len(common) >= 4:
                    score += 0.1
                if len(common) >= 6:
                    score += 0.1
                if score > best_score:
                    best_score = score
                    best_match = entry["product"]
            
            if best_match and best_score >= 0.35 and len(ak_words & set(get_words(best_match.get("name", "")))) >= 3:
                update_data = {
                    "akakce_product_name": akakce_name,
                    "akakce_matched": True,
                    "akakce_match_confidence": "panel_import",
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
                if is_product_url:
                    update_data["akakce_product_url"] = akakce_url
                else:
                    existing = await db.products.find_one({"slug": best_match["slug"]}, {"_id": 0, "akakce_product_url": 1})
                    if not existing or not existing.get("akakce_product_url") or "fiyati," not in existing.get("akakce_product_url", ""):
                        update_data["akakce_product_url"] = akakce_url
                        update_data["akakce_match_confidence"] = "panel_import_search"
                
                await db.products.update_one({"slug": best_match["slug"]}, {"$set": update_data})
                matched += 1
            else:
                not_found += 1
            
            if i % 200 == 0:
                await db.system_status.update_one({"task": "akakce_panel_import"}, {"$set": {"current": i + 1, "matched": matched, "not_found": not_found}})
        
        await db.system_status.update_one({"task": "akakce_panel_import"}, {"$set": {
            "running": False, "matched": matched, "not_found": not_found, "total": len(akakce_data),
            "search_urls": search_url_count,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }})
        logger.info(f"Akakce JSON import: {matched} eslesti, {not_found} eslesemedi, {search_url_count} arama URL, toplam {len(akakce_data)}")
    except Exception as e:
        logger.error(f"Akakce JSON import error: {e}")
        await db.system_status.update_one({"task": "akakce_panel_import"}, {"$set": {"running": False, "error": str(e)}})

@api_router.get("/akakce-panel/status")
async def akakce_panel_status(user: dict = Depends(get_current_user)):
    status = await db.system_status.find_one({"task": "akakce_panel_import"}, {"_id": 0})
    return status or {"running": False}

# ============ AKAKCE SCRAPING (curl_cffi + ScraperAPI + proxy) ============

AKAKCE_SEARCH_URL = "https://www.akakce.com/arama/?q={query}"
AKAKCE_PROXY = os.environ.get("AKAKCE_PROXY", "")
SCRAPERAPI_KEY = os.environ.get("SCRAPERAPI_KEY", "")

def akakce_request(url: str):
    """Make request to Akakçe via ScraperAPI."""
    import requests as req_sync
    
    # ScraperAPI (simple mode - no render/premium needed for Akakce)
    if SCRAPERAPI_KEY:
        try:
            resp = req_sync.get("http://api.scraperapi.com", params={
                "api_key": SCRAPERAPI_KEY, "url": url,
            }, timeout=90)
            if resp.status_code == 200:
                logger.info(f"ScraperAPI basarili: {url[:60]}")
                return resp
            logger.warning(f"ScraperAPI returned {resp.status_code} for {url[:60]}")
        except Exception as e:
            logger.warning(f"ScraperAPI error: {e}")
    
    # Fallback: curl_cffi direct (works from residential IPs)
    try:
        from curl_cffi import requests as cffi_requests
        kwargs = {
            "impersonate": random.choice(["chrome", "chrome110", "chrome120"]),
            "timeout": 15,
        }
        if AKAKCE_PROXY:
            kwargs["proxies"] = {"http": AKAKCE_PROXY, "https": AKAKCE_PROXY}
        resp = cffi_requests.get(url, **kwargs)
        if resp.status_code == 200:
            logger.info(f"curl_cffi basarili: {url[:60]}")
            return resp
    except Exception as e:
        logger.warning(f"curl_cffi error: {e}")
    
    raise Exception(f"Tum yontemler basarisiz: {url[:60]}")

# Cache the block status to avoid repeated slow failures
_akakce_blocked = {"status": None, "checked_at": None}

def is_akakce_blocked() -> bool:
    """Check if Akakçe is blocking us. Tests free methods first."""
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
    """Search Google for the product on Akakçe. Tries free first, then ScraperAPI."""
    import requests as req_sync
    
    query = f"{product_name} akakçe"
    
    # Method 1: Free Google search via direct request
    try:
        import urllib.parse
        encoded_q = urllib.parse.quote_plus(query)
        google_url = f"https://www.google.com.tr/search?q={encoded_q}&num=10&hl=tr"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        resp = req_sync.get(google_url, headers=headers, timeout=12, allow_redirects=True)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            candidates = []
            seen_urls = set()
            for a_tag in soup.find_all("a", href=True):
                href = a_tag["href"]
                # Extract URL from Google redirect
                if "/url?q=" in href:
                    href = href.split("/url?q=")[1].split("&")[0]
                    href = urllib.parse.unquote(href)
                if "akakce.com" in href and "en-ucuz" in href and href not in seen_urls:
                    seen_urls.add(href)
                    title = a_tag.get_text(strip=True)
                    title = re.sub(r'\s*\|.*$', '', title).strip()
                    title = re.sub(r'\s*-\s*Akakçe.*$', '', title).strip()
                    if title and len(title) > 5:
                        candidates.append({"name": title[:150], "url": href, "price": 0})
            if candidates:
                logger.info(f"Google UCRETSIZ arama basarili: {len(candidates)} sonuc ({product_name[:40]})")
                return {"success": True, "candidates": candidates[:10], "error": None}
    except Exception as e:
        logger.warning(f"Free Google search error: {e}")
    
    # Method 2: ScraperAPI structured SERP (paid fallback)
    if not SCRAPERAPI_KEY:
        return {"success": False, "error": "Google araması başarısız", "candidates": []}
    try:
        logger.info(f"Ucretsiz Google basarisiz, ScraperAPI SERP kullaniliyor: {product_name[:40]}")
        resp = req_sync.get("https://api.scraperapi.com/structured/google/search", params={
            "api_key": SCRAPERAPI_KEY,
            "query": query,
            "num": "10",
        }, timeout=60)
        
        if resp.status_code != 200:
            return {"success": False, "error": f"Google SERP API HTTP {resp.status_code}", "candidates": []}
        
        data = resp.json()
        candidates = []
        seen_urls = set()
        
        for r in data.get("organic_results", []):
            link = r.get("link", "")
            title = r.get("title", "")
            if "akakce.com" in link and "en-ucuz" in link:
                if link not in seen_urls:
                    seen_urls.add(link)
                    title = re.sub(r'\s*\|.*$', '', title).strip()
                    title = re.sub(r'\s*-\s*Akakçe.*$', '', title).strip()
                    candidates.append({"name": title[:150], "url": link, "price": 0})
        
        return {
            "success": len(candidates) > 0,
            "candidates": candidates[:10],
            "error": None if candidates else "Google'da Akakce urun sayfasi bulunamadi",
        }
    except Exception as e:
        logger.error(f"Google SERP search error: {e}")
        return {"success": False, "error": str(e), "candidates": []}

def search_akakce_sync(product_name: str) -> dict:
    """Search for product on Akakçe directly via ScraperAPI (1 credit per search)."""
    try:
        import requests as req_sync
        search_query = product_name.replace(" ", "+")
        url = AKAKCE_SEARCH_URL.format(query=search_query)
        
        # Use ScraperAPI for Akakce search (1 credit, no render needed)
        if SCRAPERAPI_KEY:
            resp = req_sync.get("http://api.scraperapi.com", params={
                "api_key": SCRAPERAPI_KEY, "url": url,
            }, timeout=60)
        else:
            # Direct access (works from residential IPs)
            try:
                from curl_cffi import requests as cffi_requests
                resp = cffi_requests.get(url, impersonate="chrome", timeout=15)
            except Exception:
                resp = req_sync.get(url, headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                }, timeout=15)
        
        if resp.status_code == 403:
            return {"success": False, "error": "Akakce erisim engellendi (403)", "competitors": [], "search_url": url}
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
    """Fetch and parse an Akakçe product detail page to extract all seller prices. Single request only."""
    try:
        loop = asyncio.get_event_loop()
        resp = await loop.run_in_executor(None, lambda: akakce_request(url))
        
        if resp.status_code == 403:
            return {"success": False, "error": "Cloudflare 403", "sellers": []}
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
        
        unique_prices = list(dict.fromkeys(prices))
        
        sellers = []
        for i in range(min(len(seller_names), len(unique_prices))):
            sellers.append({"seller": seller_names[i], "price": unique_prices[i]})
        
        sellers.sort(key=lambda x: x["price"])
        
        return {"success": len(sellers) > 0, "product_name": product_name, "sellers": sellers, "error": None if sellers else "Satici bilgisi okunamadi"}
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

# ============ IKAS API INTEGRATION ============

IKAS_CLIENT_ID = os.environ.get("IKAS_CLIENT_ID", "")
IKAS_CLIENT_SECRET = os.environ.get("IKAS_CLIENT_SECRET", "")
IKAS_TOKEN_URL = "https://api.myikas.com/api/admin/oauth/token"
IKAS_GRAPHQL_URL = "https://api.myikas.com/api/v2/admin/graphql"

# Token cache
_ikas_token = {"access_token": "", "expires_at": 0}

def get_ikas_token() -> str:
    """Get İkas access token using client_credentials flow."""
    import requests as req_sync
    import time as time_mod
    
    if _ikas_token["access_token"] and time_mod.time() < _ikas_token["expires_at"] - 60:
        return _ikas_token["access_token"]
    
    resp = req_sync.post(IKAS_TOKEN_URL, data={
        "grant_type": "client_credentials",
        "client_id": IKAS_CLIENT_ID,
        "client_secret": IKAS_CLIENT_SECRET,
    }, headers={"Content-Type": "application/x-www-form-urlencoded"}, timeout=15)
    
    if resp.status_code != 200:
        raise Exception(f"Ikas token hatasi: HTTP {resp.status_code} - {resp.text[:200]}")
    
    data = resp.json()
    _ikas_token["access_token"] = data["access_token"]
    _ikas_token["expires_at"] = time_mod.time() + data.get("expires_in", 14400)
    logger.info("Ikas API token alindi")
    return _ikas_token["access_token"]

def ikas_graphql(query: str, variables: dict = None) -> dict:
    """Execute İkas GraphQL query/mutation."""
    import requests as req_sync
    
    token = get_ikas_token()
    resp = req_sync.post(IKAS_GRAPHQL_URL, json={
        "query": query,
        "variables": variables or {},
    }, headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }, timeout=30)
    
    if resp.status_code != 200:
        raise Exception(f"Ikas GraphQL hatasi: HTTP {resp.status_code} - {resp.text[:200]}")
    
    data = resp.json()
    if data.get("errors"):
        raise Exception(f"Ikas GraphQL hatasi: {data['errors'][0].get('message', str(data['errors']))}")
    return data.get("data", {})

def ikas_search_product(product_name: str) -> list:
    """Search for a product in İkas by name."""
    query = """
    query ListProducts($search: String, $pagination: PaginationInput) {
        listProduct(search: $search, pagination: $pagination) {
            data { id name description }
            count
        }
    }
    """
    result = ikas_graphql(query, {"search": product_name[:100], "pagination": {"page": 1, "limit": 5}})
    products = result.get("listProduct", {}).get("data", [])
    
    if not products:
        # Try shorter name
        short_name = " ".join(product_name.split()[:3])
        result = ikas_graphql(query, {"search": short_name, "pagination": {"page": 1, "limit": 10}})
        products = result.get("listProduct", {}).get("data", [])
    
    return products

def ikas_update_product(product_id: str, meta_title: str = None, meta_description: str = None, description: str = None) -> dict:
    """Update product SEO fields in İkas."""
    mutation = """
    mutation UpdateProduct($input: UpdateProductInput!) {
        updateProduct(input: $input) { id name updatedAt }
    }
    """
    input_data = {"id": product_id}
    
    # Product description (main body)
    if description is not None:
        input_data["description"] = description[:32000]
    
    # SEO meta data (pageTitle + description)
    meta_data = {}
    if meta_title is not None:
        meta_data["pageTitle"] = meta_title[:256]
    if meta_description is not None:
        meta_data["description"] = meta_description[:320]
    if meta_data:
        input_data["metaData"] = meta_data
    
    return ikas_graphql(mutation, {"input": input_data})

class IkasSearchRequest(BaseModel):
    product_name: str

@api_router.post("/ikas/search-product")
async def ikas_search(req: IkasSearchRequest, user: dict = Depends(get_current_user)):
    """Search for a product in İkas."""
    if not IKAS_CLIENT_ID or not IKAS_CLIENT_SECRET:
        raise HTTPException(status_code=400, detail="Ikas API yapilandirilmamis")
    try:
        loop = asyncio.get_event_loop()
        products = await loop.run_in_executor(None, ikas_search_product, req.product_name)
        return {"products": products, "count": len(products)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class IkasPushRequest(BaseModel):
    product_slug: str
    ikas_product_id: Optional[str] = ""
    meta_title: Optional[str] = ""
    meta_description: Optional[str] = ""
    product_description: Optional[str] = ""

@api_router.post("/ikas/push-seo")
async def ikas_push_seo(req: IkasPushRequest, user: dict = Depends(get_current_user)):
    """Push SEO content to İkas product."""
    if not IKAS_CLIENT_ID or not IKAS_CLIENT_SECRET:
        raise HTTPException(status_code=400, detail="Ikas API yapilandirilmamis")
    
    try:
        loop = asyncio.get_event_loop()
        
        # Find İkas product ID if not provided
        ikas_id = req.ikas_product_id
        if not ikas_id:
            # Get product name from our DB
            product = await db.products.find_one({"slug": req.product_slug}, {"_id": 0, "name": 1})
            if not product:
                raise HTTPException(status_code=404, detail="Urun bulunamadi")
            
            products = await loop.run_in_executor(None, ikas_search_product, product["name"])
            if not products:
                raise HTTPException(status_code=404, detail="Urun Ikas'ta bulunamadi. Urun adini kontrol edin.")
            ikas_id = products[0]["id"]
        
        # Convert markdown to HTML for İkas
        desc_html = req.product_description or ""
        if desc_html:
            desc_html = markdown_to_html(desc_html)
        
        result = await loop.run_in_executor(None, ikas_update_product, ikas_id, req.meta_title, req.meta_description, desc_html)
        
        # Save to our DB that it was pushed
        await db.products.update_one({"slug": req.product_slug}, {"$set": {
            "ikas_seo_pushed": True,
            "ikas_product_id": ikas_id,
            "ikas_pushed_at": datetime.now(timezone.utc).isoformat(),
        }})
        
        return {"success": True, "message": "SEO icerigi Ikas'a gonderildi", "ikas_product_id": ikas_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ikas push SEO error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/ikas/status")
async def ikas_status(user: dict = Depends(get_current_user)):
    """Check İkas API connection."""
    if not IKAS_CLIENT_ID or not IKAS_CLIENT_SECRET:
        return {"configured": False}
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, get_ikas_token)
        return {"configured": True, "connected": True}
    except Exception as e:
        return {"configured": True, "connected": False, "error": str(e)}

@api_router.post("/ikas/repush-all-seo")
async def ikas_repush_all_seo(request: Request, user: dict = Depends(get_current_user)):
    """Re-push all existing SEO content to İkas with fixed HTML formatting."""
    if not IKAS_CLIENT_ID or not IKAS_CLIENT_SECRET:
        raise HTTPException(status_code=400, detail="Ikas API yapilandirilmamis")
    
    # Check if already running
    status = await db.system_status.find_one({"task": "ikas_repush"})
    if status and status.get("running"):
        return {"message": "Yeniden aktarim zaten devam ediyor", "running": True}

    # Start background task
    asyncio.create_task(run_ikas_repush())
    return {"message": "Tum SEO icerikleri Ikas'a yeniden aktariliyor (duzeltilmis format)", "running": True}

async def run_ikas_repush():
    """Background task: re-push all SEO content with correct HTML formatting."""
    await db.system_status.update_one(
        {"task": "ikas_repush"}, 
        {"$set": {"running": True, "started_at": datetime.now(timezone.utc).isoformat(), "progress": 0, "total": 0, "success": 0, "failed": 0, "error": None}},
        upsert=True
    )
    try:
        # Get all products with SEO content
        seo_docs = []
        async for doc in db.seo_content.find({"product_description": {"$exists": True, "$ne": ""}}):
            seo_docs.append(doc)

        total = len(seo_docs)
        await db.system_status.update_one({"task": "ikas_repush"}, {"$set": {"total": total}})

        success = 0
        failed = 0
        loop = asyncio.get_event_loop()

        for i, seo in enumerate(seo_docs):
            slug = seo.get("product_slug", "")
            try:
                product = await db.products.find_one({"slug": slug}, {"_id": 0, "name": 1, "ikas_product_id": 1})
                if not product:
                    failed += 1
                    continue

                # Get İkas product ID
                ikas_id = product.get("ikas_product_id", "")
                if not ikas_id:
                    ikas_products = await loop.run_in_executor(None, ikas_search_product, product["name"])
                    if not ikas_products:
                        failed += 1
                        continue
                    ikas_id = ikas_products[0]["id"]

                # Convert markdown to HTML (FIXED)
                desc_html = markdown_to_html(seo.get("product_description", ""))

                # Push to İkas
                await loop.run_in_executor(
                    None, ikas_update_product, ikas_id,
                    seo.get("seo_title", ""), seo.get("seo_description", ""), desc_html
                )

                await db.products.update_one({"slug": slug}, {"$set": {
                    "ikas_seo_pushed": True, "ikas_product_id": ikas_id,
                    "ikas_pushed_at": datetime.now(timezone.utc).isoformat(),
                }})
                success += 1
            except Exception as e:
                logger.warning(f"Repush failed for {slug}: {e}")
                failed += 1

            # Update progress
            await db.system_status.update_one({"task": "ikas_repush"}, {"$set": {"progress": i + 1, "success": success, "failed": failed}})
            await asyncio.sleep(1.5)  # Rate limit

        await db.system_status.update_one({"task": "ikas_repush"}, {"$set": {
            "running": False, "completed_at": datetime.now(timezone.utc).isoformat(),
            "progress": total, "success": success, "failed": failed,
        }})
        logger.info(f"İkas repush completed: {success}/{total} success, {failed} failed")
    except Exception as e:
        logger.error(f"İkas repush error: {e}")
        await db.system_status.update_one({"task": "ikas_repush"}, {"$set": {"running": False, "error": str(e)}})

@api_router.get("/ikas/repush-status")
async def ikas_repush_status(user: dict = Depends(get_current_user)):
    """Get status of the İkas repush task."""
    status = await db.system_status.find_one({"task": "ikas_repush"}, {"_id": 0})
    return status or {"running": False, "progress": 0, "total": 0}

@api_router.post("/ikas/import-seo")
async def ikas_import_seo(request: Request, user: dict = Depends(get_current_user)):
    """Import existing SEO data from İkas back into MongoDB."""
    if not IKAS_CLIENT_ID or not IKAS_CLIENT_SECRET:
        raise HTTPException(status_code=400, detail="Ikas API yapilandirilmamis")
    
    status = await db.system_status.find_one({"task": "ikas_import_seo"})
    if status and status.get("running"):
        return {"message": "Ikas'tan SEO verisi aktarimi devam ediyor", "running": True}

    asyncio.create_task(run_ikas_import_seo())
    return {"message": "Ikas'tan SEO verileri geri cekiliyor", "running": True}

async def run_ikas_import_seo():
    """Background task: pull all products from İkas and save SEO data to MongoDB."""
    await db.system_status.update_one(
        {"task": "ikas_import_seo"},
        {"$set": {"running": True, "started_at": datetime.now(timezone.utc).isoformat(), "progress": 0, "total": 0, "imported": 0, "skipped": 0, "error": None}},
        upsert=True
    )
    try:
        loop = asyncio.get_event_loop()
        page = 1
        imported = 0
        skipped = 0
        total_fetched = 0

        while True:
            query = """
            query ListProducts($pagination: PaginationInput) {
                listProduct(pagination: $pagination) {
                    data { id name description metaData { pageTitle description } }
                    count
                }
            }
            """
            result = await loop.run_in_executor(None, ikas_graphql, query, {"pagination": {"page": page, "limit": 50}})
            products = result.get("listProduct", {}).get("data", [])
            total_count = result.get("listProduct", {}).get("count", 0)

            if not products:
                break

            if page == 1:
                await db.system_status.update_one({"task": "ikas_import_seo"}, {"$set": {"total": total_count}})

            for ikas_product in products:
                total_fetched += 1
                ikas_id = ikas_product.get("id", "")
                name = ikas_product.get("name", "")
                description = ikas_product.get("description", "")
                meta = ikas_product.get("metaData") or {}
                page_title = meta.get("pageTitle", "")
                meta_desc = meta.get("description", "")

                # Only import if there's actual SEO content
                if not description and not page_title and not meta_desc:
                    skipped += 1
                    continue

                # Find matching product in our DB by name
                our_product = await db.products.find_one({"name": {"$regex": f"^{name[:30]}", "$options": "i"}}, {"_id": 0, "slug": 1, "name": 1})
                if not our_product:
                    # Try shorter match
                    short = " ".join(name.split()[:3])
                    our_product = await db.products.find_one({"name": {"$regex": short, "$options": "i"}}, {"_id": 0, "slug": 1, "name": 1})

                if our_product:
                    slug = our_product["slug"]
                    # Save to seo_content
                    await db.seo_content.update_one(
                        {"product_slug": slug},
                        {"$set": {
                            "product_slug": slug,
                            "product_name": our_product["name"],
                            "seo_title": page_title,
                            "seo_description": meta_desc,
                            "product_description": description,
                            "imported_from_ikas": True,
                            "ikas_product_id": ikas_id,
                            "generated_at": datetime.now(timezone.utc).isoformat(),
                            "status": "imported",
                        }},
                        upsert=True
                    )
                    # Update product record
                    await db.products.update_one({"slug": slug}, {"$set": {
                        "ikas_seo_pushed": True,
                        "ikas_product_id": ikas_id,
                    }})
                    imported += 1
                else:
                    skipped += 1

            await db.system_status.update_one({"task": "ikas_import_seo"}, {"$set": {"progress": total_fetched, "imported": imported, "skipped": skipped}})
            page += 1
            await asyncio.sleep(1)

        await db.system_status.update_one({"task": "ikas_import_seo"}, {"$set": {
            "running": False, "completed_at": datetime.now(timezone.utc).isoformat(),
            "progress": total_fetched, "imported": imported, "skipped": skipped,
        }})
        logger.info(f"İkas SEO import completed: {imported} imported, {skipped} skipped out of {total_fetched}")
    except Exception as e:
        logger.error(f"İkas SEO import error: {e}")
        await db.system_status.update_one({"task": "ikas_import_seo"}, {"$set": {"running": False, "error": str(e)}})

@api_router.get("/ikas/import-seo-status")
async def ikas_import_seo_status(user: dict = Depends(get_current_user)):
    """Get status of the İkas SEO import task."""
    status = await db.system_status.find_one({"task": "ikas_import_seo"}, {"_id": 0})
    return status or {"running": False, "progress": 0, "total": 0}

@api_router.post("/seo/generate-all")
async def generate_all_seo(request: Request, user: dict = Depends(get_current_user)):
    """Start background task to generate SEO for ALL products and push to İkas."""
    status = await db.system_status.find_one({"task": "generate_all_seo"})
    if status and status.get("running"):
        return {"message": "Toplu uretim zaten devam ediyor", "running": True}

    asyncio.create_task(run_generate_all_seo())
    return {"message": "Tum urunler icin SEO uretimi ve Ikas aktarimi baslatildi", "running": True}

async def run_generate_all_seo():
    """Background task: generate SEO for products without it, then push all to İkas."""
    await db.system_status.update_one(
        {"task": "generate_all_seo"},
        {"$set": {"running": True, "started_at": datetime.now(timezone.utc).isoformat(), "progress": 0, "total": 0, "generated": 0, "pushed": 0, "failed": 0, "error": None}},
        upsert=True
    )
    try:
        # Get all active products
        products = []
        async for p in db.products.find({"inactive": {"$ne": True}}, {"_id": 0, "slug": 1, "name": 1, "title": 1, "brand": 1, "category": 1, "price": 1}):
            products.append(p)

        total = len(products)
        await db.system_status.update_one({"task": "generate_all_seo"}, {"$set": {"total": total}})

        generated = 0
        pushed = 0
        failed = 0
        openai_key = os.environ.get("OPENAI_API_KEY")
        loop = asyncio.get_event_loop()

        for i, product in enumerate(products):
            slug = product["slug"]
            product_name = product.get("name") or product.get("title", slug)

            try:
                # Check if SEO already exists
                existing_seo = await db.seo_content.find_one({"product_slug": slug})
                
                if not existing_seo or not existing_seo.get("product_description"):
                    # Generate SEO content
                    if not openai_key:
                        failed += 1
                        continue

                    from emergentintegrations.llm.chat import LlmChat, UserMessage
                    
                    chat = LlmChat(
                        api_key=openai_key,
                        session_id=f"seo-all-{slug[:20]}-{uuid.uuid4().hex[:6]}",
                        system_message="""Sen bir e-ticaret SEO uzmanısın. Endüstriyel mutfak ekipmanları satan Arıgastro.com için ürün açıklamaları yazıyorsun.
Her ürün için üret:
1. SEO başlığı (50-60 karakter)
2. Meta açıklama (140-160 karakter)
3. Ürün açıklaması (detaylı, HTML uyumlu markdown formatında)

Yanıtını şu JSON formatında ver:
{"seo_title": "...", "seo_description": "...", "product_description": "..."}"""
                    ).with_model("openai", "gpt-4o")

                    prompt = f"Ürün: {product_name}\nMarka: {product.get('brand', '')}\nKategori: {product.get('category', '')}\nFiyat: {product.get('price', '')} TL"
                    response_text = await chat.send_message(UserMessage(text=prompt))
                    
                    # Parse JSON response
                    import json as json_mod
                    clean = response_text.strip()
                    if clean.startswith("```"):
                        clean = clean.split("\n", 1)[1] if "\n" in clean else clean[3:]
                        clean = clean.rsplit("```", 1)[0]
                    seo_data = json_mod.loads(clean)
                    
                    desc = seo_data.get("product_description", "")
                    seo_record = {
                        "product_slug": slug,
                        "product_name": product_name,
                        "seo_title": seo_data.get("seo_title", ""),
                        "seo_description": seo_data.get("seo_description", ""),
                        "product_description": desc,
                        "generated_at": datetime.now(timezone.utc).isoformat(),
                        "status": "generated"
                    }
                    await db.seo_content.update_one({"product_slug": slug}, {"$set": seo_record}, upsert=True)
                    generated += 1
                    existing_seo = seo_record
                
                # Push to İkas
                if IKAS_CLIENT_ID and IKAS_CLIENT_SECRET and existing_seo:
                    ikas_products = await loop.run_in_executor(None, ikas_search_product, product_name)
                    if ikas_products:
                        ikas_id = ikas_products[0]["id"]
                        desc_html = markdown_to_html(existing_seo.get("product_description", ""))
                        await loop.run_in_executor(
                            None, ikas_update_product, ikas_id,
                            existing_seo.get("seo_title", ""), existing_seo.get("seo_description", ""), desc_html
                        )
                        await db.products.update_one({"slug": slug}, {"$set": {
                            "ikas_seo_pushed": True, "ikas_product_id": ikas_id,
                            "ikas_pushed_at": datetime.now(timezone.utc).isoformat(),
                        }})
                        pushed += 1
            except Exception as e:
                logger.warning(f"Generate-all failed for {slug}: {e}")
                failed += 1

            await db.system_status.update_one({"task": "generate_all_seo"}, {"$set": {"progress": i + 1, "generated": generated, "pushed": pushed, "failed": failed}})
            await asyncio.sleep(2)  # Rate limit

        await db.system_status.update_one({"task": "generate_all_seo"}, {"$set": {
            "running": False, "completed_at": datetime.now(timezone.utc).isoformat(),
            "progress": total, "generated": generated, "pushed": pushed, "failed": failed,
        }})
        logger.info(f"Generate-all completed: {total} total, {generated} generated, {pushed} pushed, {failed} failed")
    except Exception as e:
        logger.error(f"Generate-all error: {e}")
        await db.system_status.update_one({"task": "generate_all_seo"}, {"$set": {"running": False, "error": str(e)}})

@api_router.get("/seo/generate-all-status")
async def generate_all_seo_status(user: dict = Depends(get_current_user)):
    """Get status of the generate-all-seo task."""
    status = await db.system_status.find_one({"task": "generate_all_seo"}, {"_id": 0})
    return status or {"running": False, "progress": 0, "total": 0}

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

# ============ BULK SEO GENERATION + IKAS PUSH ============

@api_router.get("/seo/categories/stats")
async def seo_category_stats(user: dict = Depends(get_current_user)):
    """Get SEO generation stats per İkas category."""
    pipeline = [
        {"$match": {"our_price": {"$ne": None}, "feed_active": {"$ne": False}}},
        {"$group": {"_id": "$category_path", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]
    cat_groups = await db.products.aggregate(pipeline).to_list(500)
    
    categories = []
    for cg in cat_groups:
        cat_name = cg["_id"] or "Kategori Yok"
        total = cg["count"]
        
        if cat_name == "Kategori Yok":
            slugs = await db.products.find({"category_path": {"$in": [None, ""]}, "our_price": {"$ne": None}, "feed_active": {"$ne": False}}, {"_id": 0, "slug": 1}).to_list(5000)
        else:
            slugs = await db.products.find({"category_path": cat_name, "our_price": {"$ne": None}, "feed_active": {"$ne": False}}, {"_id": 0, "slug": 1}).to_list(5000)
        slug_list = [s["slug"] for s in slugs]
        
        seo_done = await db.seo_content.count_documents({"product_slug": {"$in": slug_list}})
        ikas_pushed = await db.products.count_documents({"slug": {"$in": slug_list}, "ikas_seo_pushed": True})
        
        # Check if this category has a running task
        task_key = f"bulk_seo_{cat_name[:50]}"
        task_status = await db.system_status.find_one({"task": task_key}, {"_id": 0})
        running = task_status.get("running", False) if task_status else False
        paused = task_status.get("paused", False) if task_status else False
        
        categories.append({
            "category": cat_name,
            "total": total,
            "seo_generated": seo_done,
            "ikas_pushed": ikas_pushed,
            "remaining": total - seo_done,
            "running": running,
            "paused": paused,
            "task_status": task_status,
        })
    
    return {"categories": categories}

@api_router.post("/seo/bulk-generate-push")
async def bulk_seo_generate_push(category: str = "", user: dict = Depends(get_current_user)):
    """Start bulk SEO generation + İkas push for a category. Supports parallel categories."""
    task_key = f"bulk_seo_{category[:50]}" if category else "bulk_seo_all"
    
    status = await db.system_status.find_one({"task": task_key}, {"_id": 0})
    if status and status.get("running") and not status.get("paused"):
        return {"started": False, "message": "Bu kategori icin SEO uretimi zaten calisiyor."}
    
    query = {"our_price": {"$ne": None}, "feed_active": {"$ne": False}}
    if category and category != "Kategori Yok":
        query["category_path"] = category
    elif category == "Kategori Yok":
        query["category_path"] = {"$in": [None, ""]}
    
    products = await db.products.find(query, {"_id": 0, "slug": 1, "name": 1}).to_list(10000)
    slug_list = [p["slug"] for p in products]
    
    existing_seo = await db.seo_content.find({"product_slug": {"$in": slug_list}}, {"_id": 0, "product_slug": 1}).to_list(10000)
    existing_slugs = set(s["product_slug"] for s in existing_seo)
    pending = [p for p in products if p["slug"] not in existing_slugs]
    
    if not pending:
        return {"started": False, "message": "Bu kategorideki tum urunlerin SEO icerigi zaten uretilmis."}
    
    await db.system_status.update_one(
        {"task": task_key},
        {"$set": {"running": True, "paused": False, "started_at": datetime.now(timezone.utc).isoformat(), "total": len(pending), "current": 0, "success": 0, "failed": 0, "category": category or "Tumu", "error": ""}},
        upsert=True
    )
    
    asyncio.ensure_future(run_bulk_seo_generate(pending, category, task_key))
    return {"started": True, "message": f"{len(pending)} urun icin SEO uretimi basladi ({category or 'Tum kategoriler'})"}

async def run_bulk_seo_generate(products: list, category: str, task_key: str):
    """Background: Generate SEO for each product and push to İkas."""
    openai_key = os.environ.get("OPENAI_API_KEY")
    if not openai_key:
        await db.system_status.update_one({"task": task_key}, {"$set": {"running": False, "error": "OpenAI key yok"}})
        return
    
    success = 0
    failed = 0
    
    for i, prod in enumerate(products):
        # Check if paused/stopped
        current_status = await db.system_status.find_one({"task": task_key}, {"_id": 0})
        if current_status and (not current_status.get("running") or current_status.get("paused")):
            logger.info(f"Bulk SEO {task_key} durduruldu (paused/stopped)")
            break
        
        slug = prod["slug"]
        try:
            await db.system_status.update_one({"task": task_key}, {"$set": {"current": i + 1, "success": success, "failed": failed, "current_product": prod["name"][:50]}})
            
            # Skip if already generated
            existing = await db.seo_content.find_one({"product_slug": slug})
            if existing:
                success += 1
                continue
            
            product = await db.products.find_one({"slug": slug})
            if not product:
                failed += 1
                continue
            
            # Scrape product page for specs
            product_page_data = ""
            try:
                product_url = product.get("url", "")
                if product_url:
                    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as http_client:
                        resp = await http_client.get(product_url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36", "Accept-Language": "tr-TR,tr;q=0.9"})
                        if resp.status_code == 200:
                            page_soup = BeautifulSoup(resp.text, "html.parser")
                            page_text = page_soup.get_text(" ", strip=True)
                            specs_section = ""
                            for keyword in ["Teknik Özellik", "Teknik Detay", "Özellikler", "Tip:", "En (mm):", "Boy (mm):", "Kapasite"]:
                                idx = page_text.find(keyword)
                                if idx != -1:
                                    specs_section = page_text[max(0, idx-50):idx+2000]
                                    break
                            desc_section = ""
                            for keyword in ["Ürün Detayı", "Ürün Açıklama"]:
                                idx = page_text.find(keyword)
                                if idx != -1:
                                    desc_section = page_text[idx:idx+2000]
                                    break
                            product_page_data = f"MEVCUT ÜRÜN SAYFASI VERİLERİ:\n{specs_section}\n\n{desc_section}".strip()
                            if len(product_page_data) < 50:
                                product_page_data = page_text[:3000]
            except Exception:
                pass
            
            # Generate SEO with AI
            from emergentintegrations.llm.chat import LlmChat, UserMessage
            import json as json_mod
            
            product_name = product['name']
            brand = product.get('brand', '')
            cat = product.get('category_path', '')
            
            try:
                chat = LlmChat(
                    api_key=openai_key,
                    session_id=f"seo-bulk-{slug[:15]}-{uuid.uuid4().hex[:6]}",
                    system_message="""Sen Türkiye'nin en deneyimli SEO ve içerik uzmanısın. Endüstriyel mutfak ekipmanları sektöründe 15 yıllık tecrüben var.
Arıgastro Endüstriyel Mutfak Ekipmanları (arigastro.com) firması için çalışıyorsun.

GÖREV: Verilen ürün için Google'da üst sıralarda çıkacak SEO içerikleri hazırla.

KURALLAR:
1. SEO Title: Max 60 karakter. Ana anahtar kelimeyi başa yerleştir. FİYAT BİLGİSİ YAZMA.
2. SEO Description: Max 160 karakter. Call-to-action içermeli. FİYAT BİLGİSİ YAZMA.
3. Ürün Açıklaması: MİNİMUM 500 KELİME. Başlıklar, maddeler, SSS içermeli. Teknik özellikleri mutlaka ekle.
4. ASLA FİYAT RAKAMI YAZMA.
5. İçerik Türkçe, doğal ve profesyonel olmalı.

JSON yanıt: {"seo_title": "...", "seo_description": "...", "product_description": "..."}"""
                ).with_model("openai", "gpt-4o")
                
                prompt = f"Ürün: {product_name}\nMarka: {brand}\nKategori: {cat}\nGTIN: {product.get('gtin', '')}\n\n{product_page_data}\n\nJSON formatında yanıt ver."
                response = await chat.send_message(UserMessage(text=prompt))
            except Exception as e:
                error_str = str(e).lower()
                if "insufficient" in error_str or "quota" in error_str or "rate" in error_str or "credit" in error_str or "balance" in error_str:
                    logger.warning(f"Bulk SEO {task_key}: Kredi yetersiz, duraklatiliyor - {e}")
                    await db.system_status.update_one({"task": task_key}, {"$set": {
                        "paused": True, "running": True, "error": "Yapay zeka kredisi yetersiz. Bakiye yukleyip devam edebilirsiniz.",
                        "success": success, "failed": failed,
                    }})
                    return
                raise
            
            response_text = response.strip()
            if response_text.startswith("```"):
                response_text = re.sub(r'^```(?:json)?\s*', '', response_text)
                response_text = re.sub(r'\s*```$', '', response_text)
            
            seo_data = json_mod.loads(response_text)
            desc = seo_data.get("product_description", "")
            word_count = len(desc.split())
            
            seo_record = {
                "product_slug": slug, "product_name": product_name,
                "seo_title": seo_data.get("seo_title", ""),
                "seo_description": seo_data.get("seo_description", ""),
                "product_description": desc,
                "word_count": word_count,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "status": "generated"
            }
            await db.seo_content.update_one({"product_slug": slug}, {"$set": seo_record}, upsert=True)
            
            # Push to İkas
            ikas_pushed = False
            if IKAS_CLIENT_ID and IKAS_CLIENT_SECRET:
                try:
                    loop = asyncio.get_event_loop()
                    ikas_products = await loop.run_in_executor(None, ikas_search_product, product_name)
                    if ikas_products:
                        ikas_id = ikas_products[0]["id"]
                        desc_html = markdown_to_html(desc)
                        
                        await loop.run_in_executor(None, ikas_update_product, ikas_id, seo_data.get("seo_title", ""), seo_data.get("seo_description", ""), desc_html)
                        ikas_pushed = True
                        await db.products.update_one({"slug": slug}, {"$set": {"ikas_seo_pushed": True, "ikas_product_id": ikas_id, "ikas_pushed_at": datetime.now(timezone.utc).isoformat()}})
                except Exception as e:
                    logger.warning(f"Ikas push failed for {slug}: {e}")
            
            await db.seo_logs.insert_one({
                "product_slug": slug, "product_name": product_name, "category": cat,
                "seo_generated": True, "ikas_pushed": ikas_pushed,
                "word_count": word_count, "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            
            success += 1
            await asyncio.sleep(2)
        except Exception as e:
            logger.error(f"Bulk SEO error for {slug}: {e}")
            await db.seo_logs.insert_one({
                "product_slug": slug, "product_name": prod.get("name", ""),
                "seo_generated": False, "ikas_pushed": False, "error": str(e)[:200],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            failed += 1
            await asyncio.sleep(1)
    
    await db.system_status.update_one({"task": task_key}, {"$set": {
        "running": False, "paused": False, "success": success, "failed": failed, "total": len(products),
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }})
    logger.info(f"Bulk SEO {task_key} tamamlandi: {success} basarili, {failed} basarisiz")

@api_router.get("/seo/bulk-status")
async def seo_bulk_status(user: dict = Depends(get_current_user)):
    """Get all bulk SEO task statuses."""
    tasks = await db.system_status.find({"task": {"$regex": "^bulk_seo"}}, {"_id": 0}).to_list(100)
    running_count = sum(1 for t in tasks if t.get("running") and not t.get("paused"))
    paused_count = sum(1 for t in tasks if t.get("paused"))
    return {"tasks": tasks, "running_count": running_count, "paused_count": paused_count}

@api_router.get("/seo/logs")
async def get_seo_logs(page: int = 1, limit: int = 50, user: dict = Depends(get_current_user)):
    """Get SEO generation logs."""
    skip = (page - 1) * limit
    total = await db.seo_logs.count_documents({})
    logs = await db.seo_logs.find({}, {"_id": 0}).sort("timestamp", -1).skip(skip).limit(limit).to_list(limit)
    
    # Stats
    total_generated = await db.seo_logs.count_documents({"seo_generated": True})
    total_pushed = await db.seo_logs.count_documents({"ikas_pushed": True})
    total_failed = await db.seo_logs.count_documents({"seo_generated": False})
    
    return {
        "logs": logs, "total": total, "page": page, "pages": (total + limit - 1) // limit,
        "stats": {"generated": total_generated, "pushed": total_pushed, "failed": total_failed}
    }

# ============ DASHBOARD ============

@api_router.get("/dashboard/stats")
async def get_dashboard_stats(user: dict = Depends(get_current_user)):
    total_products = await db.products.count_documents({})
    
    # Count tracked = products in tracked categories or matching brand
    tracked_cats = await db.categories.find({"is_tracked": True}, {"_id": 0, "name": 1}).to_list(500)
    tracked_products = 0
    if tracked_cats:
        cat_names = [c["name"] for c in tracked_cats]
        tracked_filter = build_tracked_query(cat_names)
        tracked_products = await db.products.count_documents({**tracked_filter, "our_price": {"$ne": None}})
    
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

def build_tracked_query(cat_names: list) -> dict:
    """Build MongoDB query that matches products by category_path, brand, or url with Turkish char support."""
    patterns = []
    for name in cat_names:
        # Build Turkish-aware regex: ö↔o, ü↔u, ş↔s, ç↔c, ğ↔g, ı↔i, İ↔I
        turkish_map = {
            'o': '[oöOÖ]', 'ö': '[oöOÖ]', 'O': '[oöOÖ]', 'Ö': '[oöOÖ]',
            'u': '[uüUÜ]', 'ü': '[uüUÜ]', 'U': '[uüUÜ]', 'Ü': '[uüUÜ]',
            's': '[sşSŞ]', 'ş': '[sşSŞ]', 'S': '[sşSŞ]', 'Ş': '[sşSŞ]',
            'c': '[cçCÇ]', 'ç': '[cçCÇ]', 'C': '[cçCÇ]', 'Ç': '[cçCÇ]',
            'g': '[gğGĞ]', 'ğ': '[gğGĞ]', 'G': '[gğGĞ]', 'Ğ': '[gğGĞ]',
            'i': '[iıİI]', 'ı': '[iıİI]', 'I': '[iıİI]', 'İ': '[iıİI]',
        }
        pattern = ""
        for ch in name:
            if ch in turkish_map:
                pattern += turkish_map[ch]
            else:
                pattern += re.escape(ch)
        patterns.append(pattern)
    
    combined = "|".join(patterns)
    # Also create slug version for URL matching (lowercase, spaces→hyphens)
    slug_patterns = []
    for name in cat_names:
        slug = name.lower().replace(" ", "-")
        for tr_char, latin in [('ö','o'),('ü','u'),('ş','s'),('ç','c'),('ğ','g'),('ı','i'),('İ','i')]:
            slug = slug.replace(tr_char, latin)
        slug_patterns.append(re.escape(slug))
    slug_combined = "|".join(slug_patterns)
    
    return {"$or": [
        {"category_path": {"$regex": combined, "$options": "i"}},
        {"brand": {"$regex": combined, "$options": "i"}},
        {"url": {"$regex": slug_combined, "$options": "i"}},
    ]}

@api_router.get("/price-tracking")
async def get_price_tracking(
    user: dict = Depends(get_current_user),
    filter_type: str = "all",
    search: str = "",
    category: str = "",
    page: int = 1,
    limit: int = 50
):
    """Get products from TRACKED CATEGORIES for price comparison."""
    # First get tracked categories
    tracked_cats = await db.categories.find({"is_tracked": True}, {"_id": 0, "name": 1, "slug": 1}).to_list(500)
    if not tracked_cats:
        return {"products": [], "total": 0, "page": 1, "pages": 0, "tracked_categories_list": [], "message": "Aktif kategori yok. Kategoriler sayfasindan kategori aktif edin."}
    
    # If specific category selected, filter only that one
    if category:
        selected_cats = [c for c in tracked_cats if c["slug"] == category]
        if not selected_cats:
            return {"products": [], "total": 0, "page": 1, "pages": 0, "tracked_categories_list": tracked_cats}
        cat_names = [c["name"] for c in selected_cats]
    else:
        cat_names = [c["name"] for c in tracked_cats]
    
    # Base query: products matching category_path OR brand, with prices, NOT excluded
    tracked_filter = build_tracked_query(cat_names)
    query = {
        **tracked_filter,
        "our_price": {"$ne": None},
        "excluded_from_tracking": {"$ne": True},
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
    elif filter_type == "excluded":
        # Special: show excluded products
        query.pop("excluded_from_tracking", None)
        query["excluded_from_tracking"] = True
    
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
        "tracked_categories_list": tracked_cats,
        "matched_count": matched_count,
    }

@api_router.put("/products/{slug}/exclude-tracking")
async def toggle_exclude_tracking(slug: str, user: dict = Depends(get_current_user)):
    """Toggle exclude a product from price tracking (without losing match data)."""
    product = await db.products.find_one({"slug": slug})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    new_val = not product.get("excluded_from_tracking", False)
    await db.products.update_one({"slug": slug}, {"$set": {
        "excluded_from_tracking": new_val,
        "updated_at": datetime.now(timezone.utc).isoformat()
    }})
    return {"slug": slug, "excluded_from_tracking": new_val}

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
    tracked_filter = build_tracked_query(cat_names)
    
    count = await db.products.count_documents({
        **tracked_filter,
        "akakce_product_url": {"$exists": True, "$ne": ""},
        "akakce_matched": True,
        "excluded_from_tracking": {"$ne": True},
    })
    
    if count == 0:
        return {"started": False, "error": "Eslesmis urun yok. Once AI Eslestirme yapin."}
    
    await db.system_status.update_one(
        {"task": "price_check"},
        {"$set": {"running": True, "started_at": datetime.now(timezone.utc).isoformat(), "checked": 0, "success": 0, "failed": 0, "total": count, "current": 0}},
        upsert=True
    )
    
    asyncio.ensure_future(run_bulk_price_check(cat_names))
    return {"started": True, "message": f"Fiyat kontrolu basladi. {count} eslesmis urun kontrol edilecek."}

async def run_bulk_price_check(cat_names: list):
    """Background task for bulk price checking with parallel workers."""
    try:
        tracked_filter = build_tracked_query(cat_names)
        products = await db.products.find(
            {
                **tracked_filter,
                "akakce_product_url": {"$exists": True, "$ne": ""},
                "akakce_matched": True,
                "excluded_from_tracking": {"$ne": True},
            },
            {"_id": 0, "slug": 1, "name": 1, "akakce_product_url": 1, "our_price": 1}
        ).to_list(5000)
        
        # Filter out search URLs - only check actual product pages
        products = [p for p in products if "fiyati," in p.get("akakce_product_url", "")]
        
        checked = 0
        success = 0
        failed = 0
        lock = asyncio.Lock()
        semaphore = asyncio.Semaphore(5)  # 5 parallel workers
        
        async def check_one(product):
            nonlocal checked, success, failed
            async with semaphore:
                try:
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
                        async with lock:
                            success += 1
                    else:
                        async with lock:
                            failed += 1
                    
                    await db.products.update_one({"slug": product["slug"]}, {"$set": update_data})
                    async with lock:
                        checked += 1
                    await asyncio.sleep(random.uniform(0.3, 0.8))
                except Exception as e:
                    logger.error(f"Price check error for {product.get('slug','?')}: {e}")
                    async with lock:
                        failed += 1
        
        # Process in batches of 5
        batch_size = 5
        for i in range(0, len(products), batch_size):
            batch = products[i:i+batch_size]
            await asyncio.gather(*[check_one(p) for p in batch])
            await db.system_status.update_one({"task": "price_check"}, {"$set": {
                "current": min(i + batch_size, len(products)), "checked": checked,
                "success": success, "failed": failed,
                "current_product": products[min(i, len(products)-1)]["name"][:50]
            }})
        
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
        tracked_filter = build_tracked_query(cat_names)
        
        products = await db.products.find(
            {
                **tracked_filter,
                "our_price": {"$ne": None},
                "akakce_matched": {"$ne": True},
                "excluded_from_tracking": {"$ne": True},
            },
            {"_id": 0, "slug": 1, "name": 1, "brand": 1, "gtin": 1}
        ).to_list(5000)
        
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
                    await db.system_status.update_one({"task": "ai_match"}, {"$set": {"matched": matched, "failed": failed, "skipped": skipped}})
                    await asyncio.sleep(random.uniform(2, 4))
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
                
                cands = "\n".join([f"{j}. {c['name']} ({c.get('url','')})" for j, c in enumerate(candidates[:8])])
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
                await asyncio.sleep(random.uniform(2, 4))
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

# ============ SCHEDULED TASKS ============

scheduler = AsyncIOScheduler()

async def scheduled_feed_sync():
    """Scheduled task: sync prices from feed every 12 hours."""
    logger.info("CRON: Feed sync basladi")
    try:
        feed_items = await fetch_and_parse_feed()
        if not feed_items:
            logger.warning("CRON: Feed bos veya okunamadi")
            return
        updated = 0
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
            if item.get("gtin"):
                update_data["gtin"] = item["gtin"]
            if item.get("image_url"):
                update_data["image_url"] = item["image_url"]
            existing = await db.products.find_one({"slug": slug})
            if existing:
                await db.products.update_one({"slug": slug}, {"$set": update_data})
                updated += 1
        await db.system_status.update_one(
            {"task": "scheduled_feed_sync"},
            {"$set": {"last_run": datetime.now(timezone.utc).isoformat(), "updated": updated, "feed_items": len(feed_items)}},
            upsert=True
        )
        # Mark inactive products
        feed_slugs = set(item.get("slug", "") for item in feed_items if item.get("slug"))
        await db.products.update_many({"slug": {"$nin": list(feed_slugs)}}, {"$set": {"feed_active": False}})
        await db.products.update_many({"slug": {"$in": list(feed_slugs)}}, {"$set": {"feed_active": True}})
        logger.info(f"CRON: Feed sync tamamlandi. {updated} urun guncellendi.")
    except Exception as e:
        logger.error(f"CRON: Feed sync hatasi: {e}")

async def scheduled_price_check():
    """Scheduled task: check Akakce prices every 24 hours."""
    logger.info("CRON: Fiyat kontrolu basladi")
    try:
        status = await db.system_status.find_one({"task": "price_check"}, {"_id": 0})
        if status and status.get("running"):
            logger.info("CRON: Fiyat kontrolu zaten calisiyor, atlanıyor")
            return

        tracked_cats = await db.categories.find({"is_tracked": True}, {"_id": 0, "name": 1}).to_list(500)
        if not tracked_cats:
            logger.info("CRON: Aktif kategori yok, atlanıyor")
            return
        cat_names = [c["name"] for c in tracked_cats]
        tracked_filter = build_tracked_query(cat_names)

        count = await db.products.count_documents({
            **tracked_filter,
            "akakce_product_url": {"$exists": True, "$ne": ""},
            "akakce_matched": True,
        })
        if count == 0:
            logger.info("CRON: Eslesmis urun yok, atlanıyor")
            return

        await db.system_status.update_one(
            {"task": "price_check"},
            {"$set": {"running": True, "started_at": datetime.now(timezone.utc).isoformat(), "checked": 0, "success": 0, "failed": 0, "total": count, "current": 0}},
            upsert=True
        )
        await run_bulk_price_check(cat_names)
        await db.system_status.update_one(
            {"task": "scheduled_price_check"},
            {"$set": {"last_run": datetime.now(timezone.utc).isoformat(), "products_checked": count}},
            upsert=True
        )
        logger.info(f"CRON: Fiyat kontrolu tamamlandi. {count} urun kontrol edildi.")
    except Exception as e:
        logger.error(f"CRON: Fiyat kontrolu hatasi: {e}")

# ============ SCHEDULER STATUS ENDPOINT ============

@api_router.get("/scheduler/status")
async def get_scheduler_status(user: dict = Depends(get_current_user)):
    """Get scheduler status and last run times."""
    feed_sync = await db.system_status.find_one({"task": "scheduled_feed_sync"}, {"_id": 0})
    price_check = await db.system_status.find_one({"task": "scheduled_price_check"}, {"_id": 0})
    jobs = []
    for job in scheduler.get_jobs():
        trigger = job.trigger
        next_run = job.next_run_time.isoformat() if job.next_run_time else None
        jobs.append({"id": job.id, "name": job.name, "next_run": next_run})
    return {
        "scheduler_running": scheduler.running,
        "jobs": jobs,
        "feed_sync_last": feed_sync,
        "price_check_last": price_check,
    }

# ============ SCRAPERAPI ACCOUNT ============

@api_router.get("/scraperapi/account")
async def get_scraperapi_account(user: dict = Depends(get_current_user)):
    """Get ScraperAPI account info (credits, usage)."""
    if not SCRAPERAPI_KEY:
        return {"error": "ScraperAPI key yapilandirilmamis", "configured": False}
    try:
        import requests as req_sync
        resp = req_sync.get(f"http://api.scraperapi.com/account?api_key={SCRAPERAPI_KEY}", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            return {
                "configured": True,
                "request_count": data.get("requestCount", 0),
                "request_limit": data.get("requestLimit", 0),
                "concurrent_limit": data.get("concurrencyLimit", 0),
                "failed_request_count": data.get("failedRequestCount", 0),
            }
        return {"configured": True, "error": f"HTTP {resp.status_code}"}
    except Exception as e:
        logger.error(f"ScraperAPI account error: {e}")
        return {"configured": True, "error": str(e)}

# ============ USER MANAGEMENT ============

class CreateUserRequest(BaseModel):
    username: str
    password: str
    name: Optional[str] = ""
    role: Optional[str] = "admin"

class ChangePasswordRequest(BaseModel):
    new_password: str

@api_router.get("/users")
async def list_users(user: dict = Depends(get_current_user)):
    """List all users."""
    users = await db.users.find({}, {"_id": 0, "password_hash": 0}).sort("username", 1).to_list(100)
    # Add string id from username for frontend
    for u in users:
        u["id"] = u["username"]
    return users

@api_router.post("/users")
async def create_user(req: CreateUserRequest, user: dict = Depends(get_current_user)):
    """Create a new user."""
    username = req.username.strip().lower()
    if not username or len(username) < 3:
        raise HTTPException(status_code=400, detail="Kullanici adi en az 3 karakter olmali")
    if not req.password or len(req.password) < 6:
        raise HTTPException(status_code=400, detail="Sifre en az 6 karakter olmali")
    existing = await db.users.find_one({"username": username})
    if existing:
        raise HTTPException(status_code=400, detail="Bu kullanici adi zaten mevcut")
    await db.users.insert_one({
        "username": username,
        "password_hash": hash_password(req.password),
        "name": req.name or username,
        "role": req.role or "admin",
        "created_at": datetime.now(timezone.utc).isoformat()
    })
    return {"username": username, "name": req.name or username, "role": req.role, "message": "Kullanici olusturuldu"}

@api_router.put("/users/{username}/password")
async def change_user_password(username: str, req: ChangePasswordRequest, user: dict = Depends(get_current_user)):
    """Change a user's password."""
    if not req.new_password or len(req.new_password) < 6:
        raise HTTPException(status_code=400, detail="Sifre en az 6 karakter olmali")
    target = await db.users.find_one({"username": username.lower()})
    if not target:
        raise HTTPException(status_code=404, detail="Kullanici bulunamadi")
    await db.users.update_one({"username": username.lower()}, {"$set": {"password_hash": hash_password(req.new_password)}})
    return {"message": "Sifre guncellendi", "username": username}

@api_router.delete("/users/{username}")
async def delete_user(username: str, user: dict = Depends(get_current_user)):
    """Delete a user. Cannot delete yourself."""
    if username.lower() == user["username"].lower():
        raise HTTPException(status_code=400, detail="Kendinizi silemezsiniz")
    total_users = await db.users.count_documents({})
    if total_users <= 1:
        raise HTTPException(status_code=400, detail="Son kullaniciyi silemezsiniz")
    result = await db.users.delete_one({"username": username.lower()})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Kullanici bulunamadi")
    return {"message": "Kullanici silindi", "username": username}

# ============ ROOT ============



# ============ GOOGLE MARKETING ENDPOINTS ============

from google_marketing import (
    fetch_ads_campaigns, fetch_ads_keywords,
    fetch_ga4_overview, fetch_ga4_traffic_sources,
    fetch_gsc_data, fetch_all_marketing_data, get_sa_path,
    fetch_search_terms, fetch_keyword_quality_scores,
    fetch_ad_assets, fetch_campaign_competition,
    fetch_device_performance, fetch_hourly_performance,
    fetch_gsc_pages, fetch_ga4_landing_pages
)

@api_router.get("/marketing/test-connection")
async def test_marketing_connection(user: dict = Depends(get_current_user)):
    """Test Google API connections."""
    results = {}
    sa_path = get_sa_path()
    sa_exists = os.path.exists(sa_path)
    results["service_account"] = {"ok": sa_exists, "path": sa_path}

    # Test GA4
    try:
        ga4_data = fetch_ga4_overview()
        if isinstance(ga4_data, dict) and "error" in ga4_data:
            results["ga4"] = {"ok": False, "error": ga4_data["error"]}
        else:
            results["ga4"] = {"ok": True, "sessions": ga4_data.get("sessions", 0)}
    except Exception as e:
        results["ga4"] = {"ok": False, "error": str(e)}

    # Test Search Console
    try:
        gsc_data = fetch_gsc_data(limit=5)
        if gsc_data and isinstance(gsc_data[0], dict) and "error" in gsc_data[0]:
            results["search_console"] = {"ok": False, "error": gsc_data[0]["error"]}
        else:
            results["search_console"] = {"ok": True, "queries": len(gsc_data)}
    except Exception as e:
        results["search_console"] = {"ok": False, "error": str(e)}

    # Test Google Ads
    try:
        ads_data = fetch_ads_campaigns()
        if ads_data and isinstance(ads_data[0], dict) and "error" in ads_data[0]:
            results["google_ads"] = {"ok": False, "error": ads_data[0]["error"]}
        else:
            results["google_ads"] = {"ok": True, "campaigns": len(ads_data)}
    except Exception as e:
        results["google_ads"] = {"ok": False, "error": str(e)}

    return results

@api_router.get("/marketing/dashboard")
async def marketing_dashboard(
    date_from: str = None,
    date_to: str = None,
    user: dict = Depends(get_current_user)
):
    """Fetch all marketing data from Google APIs."""
    try:
        data = fetch_all_marketing_data(date_from, date_to)
        # Check for errors in each source
        errors = []
        if isinstance(data.get("ga4_overview"), dict) and "error" in data["ga4_overview"]:
            errors.append(f"GA4: {str(data['ga4_overview']['error'])[:100]}")
        if data.get("ads_campaigns") and isinstance(data["ads_campaigns"][0], dict) and "error" in data["ads_campaigns"][0]:
            err = str(data['ads_campaigns'][0]['error'])
            if "NOT_ADS_USER" in err:
                errors.append("Google Ads: Service Account hesabi Google Ads'e bagli degil. Impersonated email veya OAuth2 kurulumu gerekli.")
                data["ads_campaigns"] = []
            else:
                errors.append(f"Google Ads: {err[:100]}")
                data["ads_campaigns"] = []
        if data.get("gsc_queries") and isinstance(data["gsc_queries"][0], dict) and "error" in data["gsc_queries"][0]:
            errors.append(f"Search Console: {str(data['gsc_queries'][0]['error'])[:100]}")
        data["api_errors"] = errors
        return data
    except Exception as e:
        logger.error(f"Marketing dashboard error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/marketing/ai-analyze")
async def ai_analyze_marketing(request: Request, user: dict = Depends(get_current_user)):
    """Send marketing data to AI for professional analysis."""
    body = await request.json()
    date_from = body.get("date_from")
    date_to = body.get("date_to")
    focus = body.get("focus", "genel")  # genel, ads, seo, traffic

    # Fetch data
    data = fetch_all_marketing_data(date_from, date_to)

    openai_key = os.environ.get("OPENAI_API_KEY")
    if not openai_key:
        raise HTTPException(status_code=400, detail="OpenAI API anahtari bulunamadi")

    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage

        system_prompt = """Sen dünya standartlarında bir Dijital Pazarlama Uzmanısın. Google Ads, Google Analytics (GA4) ve Google Search Console verilerini analiz ediyorsun.

GÖREV: Verilen metrikleri detaylı analiz et ve aşağıdaki formatta Türkçe rapor oluştur.

## FORMAT (Bu başlıkları kullan):

### 🎯 GENEL PERFORMANS DEĞERLENDİRMESİ
Kısa ve net genel durum özeti (2-3 cümle).

### 🚨 KRİTİK SORUNLAR VE HATALAR
Her sorun için:
- **Sorun**: Ne olduğu
- **Etki**: Neden önemli
- **Çözüm**: Spesifik aksiyon adımı

### 💡 OPTİMİZASYON ÖNERİLERİ
Öncelik sırasına göre sırala (en yüksek ROI potansiyeli önce).
Her öneri için:
- **Öneri**: Ne yapılmalı
- **Beklenen Etki**: Tahmini iyileşme
- **Zorluk**: Kolay / Orta / Zor
- **Aksiyon Tipi**: budget_increase | budget_decrease | pause_campaign | enable_campaign | keyword_add | keyword_remove | bid_adjust | none
- **Hedef**: İlgili kampanya adı veya keyword (varsa)

### 📊 REKLAM ANALİZİ (Google Ads varsa)
- ROAS ve maliyet analizi
- En iyi/kötü performans gösteren kampanyalar
- Anahtar kelime performansı
- Bütçe dağılımı değerlendirmesi

### 🔍 SEO ANALİZİ (Search Console varsa)
- Organik trafik trendi
- En iyi performans gösteren sorgular
- Sıralama fırsatları (5-15 arası pozisyon)
- Düşük CTR'li yüksek gösterimli sorgular

### 📈 TRAFİK ANALİZİ (GA4 varsa)
- Kanal bazlı performans
- Dönüşüm oranları
- Hemen çıkma oranı değerlendirmesi
- Kullanıcı davranışı

### 🎬 HEMEN YAPILACAKLAR
En acil 3-5 aksiyon maddesi. Her biri kısa, net ve uygulanabilir olmalı.

ÖNEMLİ KURALLAR:
- Veri yoksa o bölümü "Veri bulunamadı" olarak belirt, uydurma
- TL cinsinden parasal değerler kullan
- Yüzdelik değişimleri belirt
- Spesifik kampanya/keyword isimlerini kullan
- Jargon yerine anlaşılır Türkçe kullan"""

        chat = LlmChat(
            api_key=openai_key,
            session_id=f"marketing-{uuid.uuid4().hex[:8]}",
            system_message=system_prompt
        ).with_model("openai", "gpt-4o")

        # Build the data summary for AI
        data_text = f"Tarih Aralığı: {data.get('date_range', {}).get('from', 'Son 30 gün')} - {data.get('date_range', {}).get('to', 'Bugün')}\n\n"

        # GA4 Overview
        ga4 = data.get("ga4_overview", {})
        if ga4 and "error" not in ga4:
            data_text += f"""## GA4 VERİLERİ
- Oturumlar: {ga4.get('sessions', 0):,}
- Toplam Kullanıcı: {ga4.get('total_users', 0):,}
- Yeni Kullanıcı: {ga4.get('new_users', 0):,}
- Hemen Çıkma Oranı: %{ga4.get('bounce_rate', 0)}
- Ort. Oturum Süresi: {ga4.get('avg_session_duration', 0)} sn
- Sayfa Görüntüleme: {ga4.get('page_views', 0):,}
- E-ticaret Satış: {ga4.get('purchases', 0)}
- Gelir: {ga4.get('revenue', 0):,.2f} TL
"""
        else:
            data_text += "## GA4 VERİLERİ\nVeri alınamadı.\n"

        # Traffic sources
        traffic = data.get("ga4_traffic", [])
        if traffic and not (isinstance(traffic[0], dict) and "error" in traffic[0]):
            data_text += "\n## TRAFİK KAYNAKLARI\n"
            for t in traffic[:15]:
                data_text += f"- {t['source']}/{t['medium']}: {t['sessions']} oturum, {t['users']} kullanıcı, {t['purchases']} satış, {t['revenue']:.2f} TL\n"

        # Ads campaigns
        campaigns = data.get("ads_campaigns", [])
        if campaigns and not (isinstance(campaigns[0], dict) and "error" in campaigns[0]):
            data_text += "\n## GOOGLE ADS KAMPANYALARI\n"
            for c in campaigns:
                data_text += f"- {c['name']} ({c['status']}): {c['impressions']:,} gösterim, {c['clicks']:,} tıklama, CTR %{c['ctr']}, Maliyet {c['cost']:.2f} TL, {c['conversions']} dönüşüm, ROAS {c['roas']}\n"

        # Ads keywords
        keywords = data.get("ads_keywords", [])
        if keywords and not (isinstance(keywords[0], dict) and "error" in keywords[0]):
            data_text += "\n## ANAHTAR KELİME PERFORMANSI\n"
            for k in keywords[:30]:
                data_text += f"- \"{k['keyword']}\" ({k['match_type']}, {k['campaign']}): {k['impressions']:,} gösterim, {k['clicks']} tıklama, CTR %{k['ctr']}, Maliyet {k['cost']:.2f} TL, {k['conversions']} dönüşüm\n"

        # Search Console
        gsc = data.get("gsc_queries", [])
        if gsc and not (isinstance(gsc[0], dict) and "error" in gsc[0]):
            data_text += "\n## SEARCH CONSOLE VERİLERİ\n"
            for q in gsc:
                data_text += f"- \"{q['query']}\": {q['clicks']} tıklama, {q['impressions']:,} gösterim, CTR %{q['ctr']}, Pozisyon {q['position']}\n"

        if focus != "genel":
            data_text += f"\n\n## ODAK ALANI: {focus.upper()}\nLütfen bu alana özellikle odaklan.\n"

        response = await chat.send_message(UserMessage(text=data_text))

        # Save analysis to DB
        analysis_doc = {
            "date_from": date_from,
            "date_to": date_to,
            "focus": focus,
            "analysis": response,
            "raw_data_summary": {
                "campaigns_count": len([c for c in campaigns if not (isinstance(c, dict) and "error" in c)]),
                "keywords_count": len([k for k in keywords if not (isinstance(k, dict) and "error" in k)]),
                "gsc_queries_count": len([q for q in gsc if not (isinstance(q, dict) and "error" in q)]),
                "ga4_sessions": ga4.get("sessions", 0) if isinstance(ga4, dict) and "error" not in ga4 else 0,
            },
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": user["username"],
        }
        await db.marketing_analyses.insert_one(analysis_doc)

        return {"analysis": response, "data_summary": analysis_doc["raw_data_summary"]}
    except Exception as e:
        logger.error(f"AI marketing analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/marketing/analyses")
async def get_marketing_analyses(limit: int = 10, user: dict = Depends(get_current_user)):
    """Get past marketing analyses."""
    cursor = db.marketing_analyses.find({}, {"_id": 0}).sort("created_at", -1).limit(limit)
    analyses = []
    async for doc in cursor:
        analyses.append(doc)
    return analyses

@api_router.post("/marketing/ads-action")
async def execute_ads_action(request: Request, user: dict = Depends(get_current_user)):
    """Execute a Google Ads action (budget change, pause, enable)."""
    body = await request.json()
    action_type = body.get("action_type")  # budget_increase, budget_decrease, pause_campaign, enable_campaign
    campaign_id = body.get("campaign_id")
    value = body.get("value")  # New budget amount for budget changes

    if not action_type or not campaign_id:
        raise HTTPException(status_code=400, detail="action_type ve campaign_id gerekli")

    customer_id = os.environ.get("GOOGLE_ADS_CUSTOMER_ID", "").replace("-", "")
    developer_token = os.environ.get("GOOGLE_ADS_DEVELOPER_TOKEN", "")
    mcc_id = os.environ.get("GOOGLE_ADS_MCC_ID", "").replace("-", "")

    if not customer_id or not developer_token:
        raise HTTPException(status_code=400, detail="Google Ads kimlik bilgileri eksik")

    try:
        from google.ads.googleads.client import GoogleAdsClient

        sa_path = get_sa_path()
        config = {
            "developer_token": developer_token,
            "json_key_file_path": sa_path,
            "impersonated_email": "",
            "login_customer_id": mcc_id,
            "use_proto_plus": True,
        }
        ads_client = GoogleAdsClient.load_from_dict(config)

        if action_type in ("pause_campaign", "enable_campaign"):
            campaign_service = ads_client.get_service("CampaignService")
            campaign_operation = ads_client.get_type("CampaignOperation")
            campaign = campaign_operation.update
            campaign.resource_name = ads_client.get_service("CampaignService").campaign_path(customer_id, campaign_id)

            if action_type == "pause_campaign":
                campaign.status = ads_client.enums.CampaignStatusEnum.PAUSED
            else:
                campaign.status = ads_client.enums.CampaignStatusEnum.ENABLED

            field_mask = ads_client.get_type("FieldMask")
            field_mask.paths.append("status")
            campaign_operation.update_mask.CopyFrom(field_mask)

            campaign_service.mutate_campaigns(
                customer_id=customer_id,
                operations=[campaign_operation]
            )

            # Log action
            await db.marketing_actions.insert_one({
                "action_type": action_type,
                "campaign_id": campaign_id,
                "executed_by": user["username"],
                "executed_at": datetime.now(timezone.utc).isoformat(),
                "status": "success",
            })

            status_text = "duraklatıldı" if action_type == "pause_campaign" else "etkinleştirildi"
            return {"success": True, "message": f"Kampanya başarıyla {status_text}"}

        elif action_type in ("budget_increase", "budget_decrease"):
            if not value or value <= 0:
                raise HTTPException(status_code=400, detail="Geçerli bir bütçe değeri gerekli")

            # First get current campaign to find budget resource
            ga_service = ads_client.get_service("GoogleAdsService")
            query = f"""
                SELECT campaign.id, campaign.name, campaign_budget.resource_name, campaign_budget.amount_micros
                FROM campaign
                WHERE campaign.id = {campaign_id}
            """
            response = ga_service.search(customer_id=customer_id, query=query)
            row = None
            for r in response:
                row = r
                break

            if not row:
                raise HTTPException(status_code=404, detail="Kampanya bulunamadı")

            budget_service = ads_client.get_service("CampaignBudgetService")
            budget_operation = ads_client.get_type("CampaignBudgetOperation")
            budget = budget_operation.update
            budget.resource_name = row.campaign_budget.resource_name
            budget.amount_micros = int(value * 1_000_000)

            field_mask = ads_client.get_type("FieldMask")
            field_mask.paths.append("amount_micros")
            budget_operation.update_mask.CopyFrom(field_mask)

            budget_service.mutate_campaign_budgets(
                customer_id=customer_id,
                operations=[budget_operation]
            )

            await db.marketing_actions.insert_one({
                "action_type": action_type,
                "campaign_id": campaign_id,
                "new_budget": value,
                "old_budget": row.campaign_budget.amount_micros / 1_000_000,
                "executed_by": user["username"],
                "executed_at": datetime.now(timezone.utc).isoformat(),
                "status": "success",
            })

            return {"success": True, "message": f"Bütçe {value:.2f} TL olarak güncellendi"}

        else:
            raise HTTPException(status_code=400, detail=f"Bilinmeyen aksiyon tipi: {action_type}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ads action error: {e}")
        await db.marketing_actions.insert_one({
            "action_type": action_type,
            "campaign_id": campaign_id,
            "executed_by": user["username"],
            "executed_at": datetime.now(timezone.utc).isoformat(),
            "status": "error",
            "error": str(e),
        })
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/marketing/actions-log")
async def get_marketing_actions_log(limit: int = 20, user: dict = Depends(get_current_user)):
    """Get log of executed marketing actions."""
    cursor = db.marketing_actions.find({}, {"_id": 0}).sort("executed_at", -1).limit(limit)
    actions = []
    async for doc in cursor:
        actions.append(doc)
    return actions

# ============ REPORT ENDPOINTS ============

@api_router.get("/reports/search-terms")
async def get_search_terms_report(date_from: str = None, date_to: str = None, user: dict = Depends(get_current_user)):
    return fetch_search_terms(date_from, date_to)

@api_router.get("/reports/quality-scores")
async def get_quality_scores_report(user: dict = Depends(get_current_user)):
    return fetch_keyword_quality_scores()

@api_router.get("/reports/ad-assets")
async def get_ad_assets_report(date_from: str = None, date_to: str = None, user: dict = Depends(get_current_user)):
    return fetch_ad_assets(date_from, date_to)

@api_router.get("/reports/competition")
async def get_competition_report(date_from: str = None, date_to: str = None, user: dict = Depends(get_current_user)):
    return fetch_campaign_competition(date_from, date_to)

@api_router.get("/reports/device-performance")
async def get_device_performance_report(date_from: str = None, date_to: str = None, user: dict = Depends(get_current_user)):
    return fetch_device_performance(date_from, date_to)

@api_router.get("/reports/hourly-performance")
async def get_hourly_performance_report(date_from: str = None, date_to: str = None, user: dict = Depends(get_current_user)):
    return fetch_hourly_performance(date_from, date_to)

@api_router.get("/reports/gsc-pages")
async def get_gsc_pages_report(date_from: str = None, date_to: str = None, user: dict = Depends(get_current_user)):
    return fetch_gsc_pages(date_from, date_to)

@api_router.get("/reports/landing-pages")
async def get_landing_pages_report(date_from: str = None, date_to: str = None, user: dict = Depends(get_current_user)):
    return fetch_ga4_landing_pages(date_from, date_to)

@api_router.post("/reports/ai-report")
async def generate_ai_report(request: Request, user: dict = Depends(get_current_user)):
    """Generate deep AI report with web scraping research for a specific category."""
    body = await request.json()
    category = body.get("category", "search_terms")
    date_from = body.get("date_from")
    date_to = body.get("date_to")
    compare_report_id = body.get("compare_report_id")

    if not date_from:
        date_from = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    if not date_to:
        date_to = datetime.now().strftime("%Y-%m-%d")

    openai_key = os.environ.get("OPENAI_API_KEY")
    if not openai_key:
        raise HTTPException(status_code=400, detail="OpenAI API anahtari bulunamadi")

    # Fetch Google Ads/GA4/GSC data
    data_sections = {}
    if category == "search_terms":
        data_sections["search_terms"] = fetch_search_terms(date_from, date_to, limit=150)
        data_sections["quality_scores"] = fetch_keyword_quality_scores(limit=80)
        data_sections["ga4"] = fetch_ga4_overview(date_from, date_to)
        data_sections["ga4_traffic"] = fetch_ga4_traffic_sources(date_from, date_to)
    elif category == "ad_performance":
        data_sections["campaigns"] = fetch_ads_campaigns(date_from, date_to)
        data_sections["competition"] = fetch_campaign_competition(date_from, date_to)
        data_sections["device"] = fetch_device_performance(date_from, date_to)
        data_sections["hourly"] = fetch_hourly_performance(date_from, date_to)
        data_sections["ga4"] = fetch_ga4_overview(date_from, date_to)
    elif category == "ad_assets":
        data_sections["assets"] = fetch_ad_assets(date_from, date_to)
        data_sections["campaigns"] = fetch_ads_campaigns(date_from, date_to)
        data_sections["ga4"] = fetch_ga4_overview(date_from, date_to)
    elif category == "competition":
        data_sections["competition"] = fetch_campaign_competition(date_from, date_to)
        data_sections["keywords"] = fetch_ads_keywords(date_from, date_to)
        data_sections["search_terms"] = fetch_search_terms(date_from, date_to, limit=50)
        data_sections["ga4"] = fetch_ga4_overview(date_from, date_to)
    elif category == "seo":
        data_sections["gsc_queries"] = fetch_gsc_data(date_from, date_to, limit=50)
        data_sections["gsc_pages"] = fetch_gsc_pages(date_from, date_to)
        data_sections["landing_pages"] = fetch_ga4_landing_pages(date_from, date_to)
        data_sections["ga4"] = fetch_ga4_overview(date_from, date_to)
        data_sections["ga4_traffic"] = fetch_ga4_traffic_sources(date_from, date_to)
    elif category == "time_device":
        data_sections["device"] = fetch_device_performance(date_from, date_to)
        data_sections["hourly"] = fetch_hourly_performance(date_from, date_to)
        data_sections["campaigns"] = fetch_ads_campaigns(date_from, date_to)
        data_sections["ga4"] = fetch_ga4_overview(date_from, date_to)
    elif category == "strategy":
        data_sections["campaigns"] = fetch_ads_campaigns(date_from, date_to)
        data_sections["competition"] = fetch_campaign_competition(date_from, date_to)
        data_sections["search_terms"] = fetch_search_terms(date_from, date_to, limit=80)
        data_sections["quality_scores"] = fetch_keyword_quality_scores(limit=50)
        data_sections["gsc_queries"] = fetch_gsc_data(date_from, date_to, limit=30)
        data_sections["ga4"] = fetch_ga4_overview(date_from, date_to)
        data_sections["device"] = fetch_device_performance(date_from, date_to)

    # Run deep analysis with web scraping
    from ai_agents import run_deep_analysis
    research_data = await run_deep_analysis(category, data_sections, {"from": date_from, "to": date_to})

    # If comparing with previous report, fetch it
    prev_report_text = ""
    if compare_report_id:
        prev = await db.marketing_reports.find_one({"_id": ObjectId(compare_report_id)})
        if prev:
            prev_report_text = f"\n\n## ÖNCEKİ RAPOR ({prev.get('date_from', '?')} — {prev.get('date_to', '?')})\n{prev.get('report', '')[:1500]}\n"

    # Build system prompt
    base_prompt = f"""Sen 15 yıllık deneyimli bir dijital pazarlama danışmanısın. Bir e-ticaret sitesi (arigastro.com — endüstriyel mutfak ekipmanları) için {category.replace('_', ' ')} analizi yapıyorsun.

TARİH ARALIĞI: {date_from} — {date_to}

SENİN FARKLIĞIN: Sen sadece veri okuyan bir AI değilsin. Sen:
1. Rakip sayfaları GERÇEKTEN ziyaret edip analiz ettin
2. Google arama sonuçlarını GERÇEKTEN inceledin  
3. Açılış sayfalarını GERÇEKTEN taradın
4. Şimdi bu somut bulgulara dayanarak rapor yazıyorsun

YASAK: "Bu araştırılmalı", "Bu analiz edilmeli", "İncelenmesi gerekir" gibi ifadeler KULLANMA. Sen zaten araştırdın ve inceldin. Bulgularını doğrudan yaz.

YASAK: "Bu kelimeyi kapat", "Bunu negatife ekle" gibi tek cümlelik yüzeysel tavsiyeler verme.

HER TESPİT İÇİN:
1. SORUN: Spesifik olarak ne yanlış (veriyle kanıtla)
2. KÖK NEDEN: Neden böyle? Rakipler ne farklı yapıyor? Sayfa içeriğinde eksik olan ne?
3. ÇÖZÜM PLANI: Adım adım ne yapılmalı, nasıl yapılmalı, tahmini etki ne olacak

FORMAT: Markdown kullan. Her tespit için ayrı başlık. Kısa ve yoğun yaz — gereksiz açıklama yapma, doğrudan sonuçlara geç."""

    if prev_report_text:
        base_prompt += f"\n\nÖNCEKİ RAPORLA KARŞILAŞTIRMA: Önceki rapordaki önerilerin ne kadarı uygulanmış? Hangi metrikler iyileşmiş, hangilerind kötüleşmiş? Spesifik olarak belirt.\n{prev_report_text}"

    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        import json as json_mod

        chat = LlmChat(
            api_key=openai_key,
            session_id=f"report-{category}-{uuid.uuid4().hex[:8]}",
            system_message=base_prompt
        ).with_model("openai", "gpt-4o")

        # Build data text with all sources
        data_text = f"## TARİH ARALIĞI: {date_from} — {date_to}\n\n"

        # Google Ads/GA4/GSC data
        for key, value in data_sections.items():
            if isinstance(value, list):
                clean = [item for item in value if not (isinstance(item, dict) and "error" in item)]
                if clean:
                    data_text += f"\n## {key.upper().replace('_', ' ')} ({len(clean)} kayıt)\n"
                    for item in clean[:60]:
                        data_text += f"- {json_mod.dumps(item, ensure_ascii=False)}\n"
            elif isinstance(value, dict) and "error" not in value:
                data_text += f"\n## {key.upper().replace('_', ' ')}\n{json_mod.dumps(value, ensure_ascii=False)}\n"

        # Deep research data
        if research_data.get("keyword_deep_analyses"):
            data_text += "\n\n# YAPILAN DERİN ARAŞTIRMA SONUÇLARI\n"
            for kw_analysis in research_data["keyword_deep_analyses"]:
                kw = kw_analysis.get("keyword", "")
                data_text += f"\n## ARAŞTIRMA: \"{kw}\"\n"
                if kw_analysis.get("our_page"):
                    p = kw_analysis["our_page"]
                    data_text += f"### BİZİM SAYFAMIZ: {p.get('url','')}\n- Başlık: {p.get('title','')}\n- H1: {p.get('h1',[])}\n- Fiyatlar: {p.get('prices',[])}\n- CTA: {p.get('ctas',[])}\n- Kelime sayısı: {p.get('word_count',0)}\n- Schema: {p.get('has_schema',False)}\n"
                if kw_analysis.get("serp_results"):
                    data_text += f"### GOOGLE ARAMA SONUÇLARI ({kw}):\n"
                    for sr in kw_analysis["serp_results"][:5]:
                        data_text += f"- {sr.get('title','')} | {sr.get('url','')}\n  {sr.get('description','')}\n"
                if kw_analysis.get("competitors"):
                    data_text += f"### RAKİP SAYFA ANALİZLERİ:\n"
                    for comp in kw_analysis["competitors"]:
                        data_text += f"- Rakip: {comp.get('url','')}\n  Başlık: {comp.get('title','')}\n  H1: {comp.get('h1',[])}\n  Fiyatlar: {comp.get('prices',[])}\n  CTA: {comp.get('ctas',[])}\n  Kelime: {comp.get('word_count',0)}\n  Schema: {comp.get('has_schema',False)}\n  İçerik özeti: {comp.get('body_excerpt','')[:200]}\n"

        if research_data.get("scraped_pages"):
            data_text += "\n\n# TARANAN SAYFALAR\n"
            for page in research_data["scraped_pages"]:
                data_text += f"\n## {page.get('url','')}\n- Başlık: {page.get('title','')}\n- Meta: {page.get('meta_description','')}\n- H1: {page.get('h1',[])}\n- H2: {page.get('h2',[])}\n- Fiyatlar: {page.get('prices',[])}\n- CTA: {page.get('ctas',[])}\n- Kelime: {page.get('word_count',0)}\n- Görsel: {page.get('image_count',0)}\n- Schema: {page.get('has_schema',False)}\n"

        if research_data.get("competitor_insights"):
            data_text += "\n\n# RAKİP SERP VERİLERİ\n"
            for ci in research_data["competitor_insights"]:
                data_text += f"- {ci.get('title','')} | {ci.get('url','')}\n"

        response = await chat.send_message(UserMessage(text=data_text))

        # Save report with full metadata
        report_doc = {
            "category": category,
            "date_from": date_from,
            "date_to": date_to,
            "report": response,
            "research_summary": {
                "keywords_researched": len(research_data.get("keyword_deep_analyses", [])),
                "pages_scraped": len(research_data.get("scraped_pages", [])),
                "competitors_analyzed": sum(len(k.get("competitors", [])) for k in research_data.get("keyword_deep_analyses", [])),
            },
            "compared_with": compare_report_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": user["username"],
        }
        result = await db.marketing_reports.insert_one(report_doc)

        return {
            "report": response,
            "category": category,
            "report_id": str(result.inserted_id),
            "date_range": {"from": date_from, "to": date_to},
            "research_summary": report_doc["research_summary"],
        }
    except Exception as e:
        logger.error(f"AI report error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/reports/history")
async def get_report_history(category: str = None, limit: int = 10, user: dict = Depends(get_current_user)):
    query = {}
    if category:
        query["category"] = category
    cursor = db.marketing_reports.find(query).sort("created_at", -1).limit(limit)
    reports = []
    async for doc in cursor:
        doc["report_id"] = str(doc["_id"])
        del doc["_id"]
        reports.append(doc)
    return reports

@api_router.post("/reports/analyze-keyword")
async def analyze_single_keyword(request: Request, user: dict = Depends(get_current_user)):
    """Deep analysis of a single keyword/search term with web scraping."""
    body = await request.json()
    keyword = body.get("keyword", "")
    keyword_data = body.get("data", {})
    analysis_type = body.get("type", "keyword")  # keyword or search_term

    if not keyword:
        raise HTTPException(status_code=400, detail="Anahtar kelime gerekli")

    openai_key = os.environ.get("OPENAI_API_KEY")
    if not openai_key:
        raise HTTPException(status_code=400, detail="OpenAI API anahtari bulunamadi")

    # Deep research: scrape our page + Google SERP + competitors
    from ai_agents import analyze_keyword_deep, scrape_url
    
    # Try to find our landing page for this keyword from the site
    our_landing = f"https://arigastro.com/arama?q={keyword.replace(' ', '+')}"
    deep = await analyze_keyword_deep({"keyword": keyword, "landing_url": our_landing, **keyword_data})

    # Also scrape our main category page if keyword suggests a product category
    extra_pages = []
    slug_guess = keyword.lower().replace(" ", "-").replace("ı", "i").replace("ö", "o").replace("ü", "u").replace("ş", "s").replace("ç", "c").replace("ğ", "g")
    category_url = f"https://arigastro.com/{slug_guess}"
    cat_page = await scrape_url(category_url)
    if "error" not in cat_page:
        extra_pages.append(cat_page)

    # Build comprehensive prompt
    system_prompt = f"""Sen 15 yıllık deneyime sahip bir Google Ads ve dijital pazarlama uzmanısın. 
Arigastro.com (endüstriyel mutfak ekipmanları e-ticaret) için TEK BİR anahtar kelimeyi derinlemesine analiz ediyorsun.

ANALİZ EDİLEN KELİME: "{keyword}"

Sen bu kelime için:
1. Arigastro'nun açılış sayfasını GERÇEKTEN ziyaret edip taradın
2. Google'da bu kelimeyi aratıp ilk sayfa sonuçlarını GERÇEKTEN inceledin
3. Rakip sayfaları GERÇEKTEN ziyaret edip taradın
4. Şimdi tüm bu somut bulgulara dayanarak rapor yazıyorsun

YASAK: "Araştırılmalı", "İncelenmesi gerekir", "Kontrol edilmeli" gibi belirsiz ifadeler. Sen ZATEN araştırdın.
YASAK: "Bu kelimeyi kapat" gibi tek cümlelik tavsiyeler. Derinlemesine analiz et.

RAPOR FORMATI:

### ANAHTAR KELİME PROFİLİ
Bu kelimeyi arayan kişi kim? Ne arıyor? Satın alma niyeti var mı yoksa bilgi mi arıyor? Bu kelime ile hangi ürünler satılmaya çalışılıyor?

### PERFORMANS DURUMU
Mevcut metrikler ne diyor? (tıklama, maliyet, dönüşüm, kalite puanı varsa bileşenleri)

### AÇILIŞ SAYFASI ANALİZİ
Arigastro'nun sayfasında ne var? Eksik olan ne? Sayfa bu kelimeyi arayan kişinin beklentisini karşılıyor mu?
- Başlık ve H1 uyumu
- Fiyat görünürlüğü
- CTA (sepete ekle) net mi?
- İçerik yeterliliği
- Schema markup var mı?

### RAKİP KARŞILAŞTIRMASI
Google'da bu kelimede ilk sıralarda kim var? Onların sayfalarında ne farklı?
- İçerik farkları
- Fiyat karşılaştırması (görebiliyorsan)
- Kullanıcı deneyimi farkları
- SEO avantajları

### KÖK NEDEN ANALİZİ
Bu kelime neden düşük performans gösteriyor? (veya kalite puanı neden düşük?)
Spesifik nedenler:
- Reklam metni ile sayfa uyumu var mı?
- Sayfa hızı/deneyimi yeterli mi?
- Beklenen TO neden düşük/yüksek?

### SOMUT AKSİYON PLANI
Adım adım ne yapılmalı:
1. Açılış sayfasında şunları değiştir: [spesifik]
2. Reklam metninde şunları güncelle: [spesifik]  
3. Alternatif kelime önerileri: Bu ürünleri satmak için bu kelime yerine şu kelimeleri dene: [liste]
4. Tahmini etki: Bu değişikliklerden sonra ne beklenmeli

Kısa, yoğun ve tamamen veriye dayalı yaz. Her tespit somut kanıtla desteklensin."""

    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        import json as json_mod

        chat = LlmChat(
            api_key=openai_key,
            session_id=f"kw-{keyword[:20]}-{uuid.uuid4().hex[:6]}",
            system_message=system_prompt
        ).with_model("openai", "gpt-4o")

        # Build data text
        data_text = f"## ANAHTAR KELİME: \"{keyword}\"\n"
        data_text += f"## MEVCUT METRİKLER:\n{json_mod.dumps(keyword_data, ensure_ascii=False)}\n"

        if deep.get("our_page") and "error" not in deep["our_page"]:
            p = deep["our_page"]
            data_text += f"\n## BİZİM SAYFAMIZ ({p.get('url','')}):\n- Başlık: {p.get('title','')}\n- Meta: {p.get('meta_description','')}\n- H1: {p.get('h1',[])}\n- H2: {p.get('h2',[])}\n- Fiyatlar: {p.get('prices',[])}\n- CTA: {p.get('ctas',[])}\n- Kelime sayısı: {p.get('word_count',0)}\n- Görsel: {p.get('image_count',0)}\n- Schema: {p.get('has_schema',False)}\n- İçerik özeti: {p.get('body_excerpt','')[:300]}\n"

        for ep in extra_pages:
            data_text += f"\n## KATEGORİ SAYFAMIZ ({ep.get('url','')}):\n- Başlık: {ep.get('title','')}\n- H1: {ep.get('h1',[])}\n- Fiyatlar: {ep.get('prices',[])}\n- Kelime: {ep.get('word_count',0)}\n- İçerik: {ep.get('body_excerpt','')[:200]}\n"

        if deep.get("serp_results"):
            data_text += f"\n## GOOGLE ARAMA SONUÇLARI (\"{keyword}\"):\n"
            for sr in deep["serp_results"][:5]:
                data_text += f"- {sr.get('title','')} | {sr.get('url','')}\n  {sr.get('description','')}\n"

        if deep.get("competitors"):
            for comp in deep["competitors"]:
                data_text += f"\n## RAKİP SAYFA: {comp.get('url','')}\n- Başlık: {comp.get('title','')}\n- H1: {comp.get('h1',[])}\n- H2: {comp.get('h2',[])}\n- Fiyatlar: {comp.get('prices',[])}\n- CTA: {comp.get('ctas',[])}\n- Kelime: {comp.get('word_count',0)}\n- Görsel: {comp.get('image_count',0)}\n- Schema: {comp.get('has_schema',False)}\n- İçerik: {comp.get('body_excerpt','')[:300]}\n"

        response = await chat.send_message(UserMessage(text=data_text))

        # Save to DB
        doc = {
            "type": "keyword_analysis",
            "keyword": keyword,
            "keyword_data": keyword_data,
            "analysis": response,
            "research_summary": {
                "our_page_scraped": bool(deep.get("our_page") and "error" not in deep.get("our_page", {})),
                "serp_results": len(deep.get("serp_results", [])),
                "competitors_scraped": len(deep.get("competitors", [])),
                "extra_pages": len(extra_pages),
            },
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": user["username"],
        }
        result = await db.keyword_analyses.insert_one(doc)

        return {
            "analysis": response,
            "keyword": keyword,
            "analysis_id": str(result.inserted_id),
            "research_summary": doc["research_summary"],
        }
    except Exception as e:
        logger.error(f"Keyword analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/reports/keyword-analyses")
async def get_keyword_analyses(keyword: str = None, limit: int = 20, user: dict = Depends(get_current_user)):
    """Get past keyword analyses."""
    query = {"type": "keyword_analysis"}
    if keyword:
        query["keyword"] = {"$regex": keyword, "$options": "i"}
    cursor = db.keyword_analyses.find(query, {"_id": 0}).sort("created_at", -1).limit(limit)
    results = []
    async for doc in cursor:
        results.append(doc)
    return results

# ============ BRAND & CATEGORY SEO ENDPOINTS ============

from brand_category_seo import analyze_competitors, generate_content, build_image_tag, get_product_images

@api_router.get("/ikas/categories")
async def list_ikas_categories(user: dict = Depends(get_current_user)):
    """List all İkas categories with hierarchy."""
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, ikas_graphql, '{ listCategory { id name parentId categoryPath description metaData { pageTitle description } } }', None)
    categories = result.get("listCategory", [])
    
    # Build hierarchy info
    cat_map = {c["id"]: c for c in categories}
    for cat in categories:
        pid = cat.get("parentId")
        cat["parent_name"] = cat_map[pid]["name"] if pid and pid in cat_map else None
        cat["children"] = [c["name"] for c in categories if c.get("parentId") == cat["id"]]
        cat["children_ids"] = [c["id"] for c in categories if c.get("parentId") == cat["id"]]
        # Siblings (same parent)
        if pid:
            cat["siblings"] = [c["name"] for c in categories if c.get("parentId") == pid and c["id"] != cat["id"]]
        else:
            cat["siblings"] = [c["name"] for c in categories if not c.get("parentId") and c["id"] != cat["id"]]

        local = await db.brand_category_seo.find_one({"entity_id": cat["id"], "entity_type": "category"}, {"_id": 0, "status": 1})
        cat["seo_generated"] = bool(local)
        cat["seo_status"] = local.get("status", "") if local else ""
    return categories

@api_router.get("/ikas/brands")
async def list_ikas_brands(user: dict = Depends(get_current_user)):
    """List all İkas brands."""
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, ikas_graphql, '{ listProductBrand { id name description metaData { pageTitle description } } }', None)
    brands = result.get("listProductBrand", [])
    for brand in brands:
        local = await db.brand_category_seo.find_one({"entity_id": brand["id"], "entity_type": "brand"}, {"_id": 0, "status": 1})
        brand["seo_generated"] = bool(local)
        brand["seo_status"] = local.get("status", "") if local else ""
    return brands

@api_router.post("/ikas/bc-seo/generate")
async def generate_bc_seo(request: Request, user: dict = Depends(get_current_user)):
    """Generate SEO content for a single brand or category."""
    body = await request.json()
    entity_type = body.get("type", "category")
    entity_id = body.get("id", "")
    name = body.get("name", "")

    if not entity_id or not name:
        raise HTTPException(status_code=400, detail="id ve name gerekli")

    openai_key = os.environ.get("OPENAI_API_KEY")
    if not openai_key:
        raise HTTPException(status_code=400, detail="OpenAI API anahtari bulunamadi")

    # 1. Analyze competitors
    analysis = await analyze_competitors(name, entity_type)

    # 2. Scrape our site page
    our_site_data = {}
    slug = name.lower().replace(" ", "-").replace("ı", "i").replace("ö", "o").replace("ü", "u").replace("ş", "s").replace("ç", "c").replace("ğ", "g")
    our_url = f"https://arigastro.com/{slug}"
    from brand_category_seo import _scrape_url_sync
    loop = asyncio.get_event_loop()
    our_page = await loop.run_in_executor(None, _scrape_url_sync, our_url)
    if "error" not in our_page:
        our_site_data = {"url": our_url, "body_excerpt": our_page.get("body_text", "")[:1000]}

    # 3. Get product images by scraping site
    product_images = []
    try:
        prods = await loop.run_in_executor(None, ikas_graphql, f'{{ listProduct(search: "{name[:50]}", pagination: {{page:1, limit:6}}) {{ data {{ name }} }} }}', None)
        prod_names = [p["name"] for p in prods.get("listProduct", {}).get("data", [])[:6]]
        product_images = await get_product_images(prod_names, entity_name=name)
    except Exception as e:
        logger.warning(f"Product images fetch error: {e}")

    # 4. Build internal links data
    internal_links = None
    if entity_type == "category":
        # Fetch hierarchy
        cat_result = await loop.run_in_executor(None, ikas_graphql, '{ listCategory { id name parentId } }', None)
        all_cats = cat_result.get("listCategory", [])
        cat_map = {c["id"]: c for c in all_cats}
        current = cat_map.get(entity_id, {})
        pid = current.get("parentId")
        children = [c["name"] for c in all_cats if c.get("parentId") == entity_id]
        siblings = []
        if pid:
            siblings = [c["name"] for c in all_cats if c.get("parentId") == pid and c["id"] != entity_id]
        else:
            siblings = [c["name"] for c in all_cats if not c.get("parentId") and c["id"] != entity_id]
        internal_links = {
            "children": children,
            "siblings": siblings,
            "parent_name": cat_map[pid]["name"] if pid and pid in cat_map else None,
        }

    # 5. Generate content
    result = await generate_content(name, entity_type, entity_id, analysis, product_images[:3], our_site_data, openai_key, internal_links)

    # 5. Save to DB
    doc = {
        "entity_type": entity_type,
        "entity_id": entity_id,
        "entity_name": name,
        "title": result.get("title", ""),
        "description_meta": result.get("description", ""),
        "content": result.get("content", ""),
        "analysis": {
            "competitors_scraped": analysis.get("competitors_scraped", 0),
            "avg_word_count": analysis.get("averages", {}).get("word_count", 0),
            "avg_keyword_density": analysis.get("averages", {}).get("keyword_density", 0),
            "uses_lists_pct": analysis.get("averages", {}).get("uses_lists_pct", 0),
            "uses_tables_pct": analysis.get("averages", {}).get("uses_tables_pct", 0),
            "serp_position": analysis.get("serp_position"),
            "competitor_titles": analysis.get("competitor_titles", []),
            "competitor_descriptions": analysis.get("competitor_descriptions", []),
            "competitor_h2s": analysis.get("competitor_h2s", []),
            "competitor_pages": [{"url": p.get("url",""), "title": p.get("title",""), "word_count": p.get("word_count",0), "keyword_density": p.get("keyword_density",0), "has_lists": p.get("has_lists",False), "has_tables": p.get("has_tables",False)} for p in analysis.get("competitor_pages", [])],
        },
        "product_images_used": len(product_images[:3]),
        "generation_notes": result.get("generation_notes", ""),
        "status": "generated",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": user["username"],
    }
    await db.brand_category_seo.update_one(
        {"entity_id": entity_id, "entity_type": entity_type},
        {"$set": doc}, upsert=True
    )

    return {
        "success": True,
        "title": result.get("title", ""),
        "description": result.get("description", ""),
        "content_length": len(result.get("content", "")),
        "analysis_summary": {
            "competitors_scraped": analysis.get("competitors_scraped", 0),
            "avg_word_count": analysis.get("averages", {}).get("word_count", 0),
            "avg_density": analysis.get("averages", {}).get("keyword_density", 0),
            "our_serp_position": analysis.get("serp_position"),
        }
    }


def _clean_html_for_ikas(html_content: str) -> str:
    """Clean HTML content for İkas WYSIWYG editor compatibility."""
    import re
    # Remove <img> tags (İkas editor doesn't handle external images well)
    content = re.sub(r'<img[^>]*/?>', '', html_content)
    # Remove style attributes
    content = re.sub(r'\s+style="[^"]*"', '', content)
    # Remove <table> structures — convert to simple lists
    content = re.sub(r'<table[^>]*>', '', content)
    content = re.sub(r'</table>', '', content)
    content = re.sub(r'<thead[^>]*>.*?</thead>', '', content, flags=re.DOTALL)
    content = re.sub(r'<tbody[^>]*>', '', content)
    content = re.sub(r'</tbody>', '', content)
    content = re.sub(r'<tr[^>]*>', '', content)
    content = re.sub(r'</tr>', '', content)
    content = re.sub(r'<th[^>]*>(.*?)</th>', r'<strong>\1</strong> ', content)
    content = re.sub(r'<td[^>]*>(.*?)</td>', r'\1 ', content)
    # Clean up extra whitespace
    content = re.sub(r'\n\s*\n\s*\n', '\n\n', content)
    return content.strip()


@api_router.post("/ikas/bc-seo/push")
async def push_bc_seo(request: Request, user: dict = Depends(get_current_user)):
    """Push generated SEO content to İkas."""
    body = await request.json()
    entity_type = body.get("type", "category")
    entity_id = body.get("id", "")

    seo = await db.brand_category_seo.find_one({"entity_id": entity_id, "entity_type": entity_type}, {"_id": 0})
    if not seo:
        raise HTTPException(status_code=404, detail="Once icerik uretmelisiniz")

    loop = asyncio.get_event_loop()
    try:
        if entity_type == "category":
            mutation = """mutation UpdateCategory($input: UpdateCategoryInput!) { updateCategory(input: $input) { id name updatedAt } }"""
        else:
            mutation = """mutation UpdateProductBrand($input: UpdateProductBrandInput!) { updateProductBrand(input: $input) { id name updatedAt } }"""

        variables = {"input": {
            "id": entity_id,
            "metaData": {
                "pageTitle": seo.get("title", "")[:256],
                "description": seo.get("description_meta", "")[:320],
            }
        }}
        
        logger.info(f"BC SEO Push: type={entity_type}, id={entity_id}, title='{seo.get('title','')[:50]}', desc_len={len(seo.get('content',''))}")
        result = await loop.run_in_executor(None, ikas_graphql, mutation, variables)
        logger.info(f"BC SEO Push result: {result}")
        
        await db.brand_category_seo.update_one(
            {"entity_id": entity_id, "entity_type": entity_type},
            {"$set": {"status": "pushed", "pushed_at": datetime.now(timezone.utc).isoformat()}}
        )
        return {"success": True, "message": "Icerik Ikas'a gonderildi"}
    except Exception as e:
        logger.error(f"BC SEO push error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/ikas/bc-seo/analysis/{entity_id}")
async def get_bc_analysis(entity_id: str, user: dict = Depends(get_current_user)):
    """Get saved analysis for a brand/category."""
    doc = await db.brand_category_seo.find_one({"entity_id": entity_id}, {"_id": 0})
    if not doc:
        return {"found": False}
    return doc

@api_router.post("/ikas/bc-seo/bulk-generate")
async def bulk_generate_bc_seo(request: Request, user: dict = Depends(get_current_user)):
    """Start bulk generation for all brands or categories."""
    body = await request.json()
    entity_type = body.get("type", "category")

    status = await db.system_status.find_one({"task": f"bc_seo_bulk_{entity_type}"})
    if status and status.get("running"):
        return {"message": "Toplu uretim zaten devam ediyor", "running": True}

    asyncio.create_task(run_bulk_bc_seo(entity_type, user["username"]))
    return {"message": f"Toplu {'marka' if entity_type == 'brand' else 'kategori'} SEO uretimi baslatildi", "running": True}

async def run_bulk_bc_seo(entity_type: str, username: str):
    """Background: generate + push SEO for all brands or categories."""
    task_key = f"bc_seo_bulk_{entity_type}"
    await db.system_status.update_one(
        {"task": task_key},
        {"$set": {"running": True, "started_at": datetime.now(timezone.utc).isoformat(), "progress": 0, "total": 0, "generated": 0, "pushed": 0, "failed": 0}},
        upsert=True
    )
    try:
        loop = asyncio.get_event_loop()
        if entity_type == "brand":
            result = await loop.run_in_executor(None, ikas_graphql, '{ listProductBrand { id name } }', None)
            entities = result.get("listProductBrand", [])
        else:
            result = await loop.run_in_executor(None, ikas_graphql, '{ listCategory { id name parentId } }', None)
            entities = result.get("listCategory", [])
        
        ent_map = {e["id"]: e for e in entities}
        total = len(entities)
        await db.system_status.update_one({"task": task_key}, {"$set": {"total": total}})

        openai_key = os.environ.get("OPENAI_API_KEY")
        generated = 0
        pushed = 0
        failed = 0

        for i, entity in enumerate(entities):
            eid = entity["id"]
            ename = entity["name"]
            try:
                # Check if already generated
                existing = await db.brand_category_seo.find_one({"entity_id": eid, "entity_type": entity_type, "status": "pushed"})
                if existing:
                    generated += 1
                    pushed += 1
                    await db.system_status.update_one({"task": task_key}, {"$set": {"progress": i+1, "generated": generated, "pushed": pushed, "failed": failed}})
                    continue

                # Analyze competitors
                analysis = await analyze_competitors(ename, entity_type)

                # Get our site data
                slug = ename.lower().replace(" ", "-").replace("ı", "i").replace("ö", "o").replace("ü", "u").replace("ş", "s").replace("ç", "c").replace("ğ", "g")
                from brand_category_seo import _scrape_url_sync
                our_page = await loop.run_in_executor(None, _scrape_url_sync, f"https://arigastro.com/{slug}")
                our_site_data = {}
                if "error" not in our_page:
                    our_site_data = {"url": f"https://arigastro.com/{slug}", "body_excerpt": our_page.get("body_text", "")[:1000]}

                # Get product images by scraping site
                product_images = []
                try:
                    prods = await loop.run_in_executor(None, ikas_graphql, f'{{ listProduct(search: "{ename[:50]}", pagination: {{page:1, limit:6}}) {{ data {{ name }} }} }}', None)
                    prod_names = [p["name"] for p in prods.get("listProduct", {}).get("data", [])[:6]]
                    product_images = await get_product_images(prod_names, entity_name=ename)
                except Exception:
                    pass

                # Build internal links for categories
                bulk_internal_links = None
                if entity_type == "category":
                    current_ent = ent_map.get(eid, {})
                    pid = current_ent.get("parentId")
                    ch = [e["name"] for e in entities if e.get("parentId") == eid]
                    sibs = []
                    if pid:
                        sibs = [e["name"] for e in entities if e.get("parentId") == pid and e["id"] != eid]
                    else:
                        sibs = [e["name"] for e in entities if not e.get("parentId") and e["id"] != eid]
                    bulk_internal_links = {"children": ch, "siblings": sibs, "parent_name": ent_map.get(pid, {}).get("name") if pid else None}

                # Generate content
                content_result = await generate_content(ename, entity_type, eid, analysis, product_images[:3], our_site_data, openai_key, bulk_internal_links)

                # Save
                doc = {
                    "entity_type": entity_type, "entity_id": eid, "entity_name": ename,
                    "title": content_result.get("title", ""), "description_meta": content_result.get("description", ""),
                    "content": content_result.get("content", ""),
                    "analysis": {
                        "competitors_scraped": analysis.get("competitors_scraped", 0),
                        "avg_word_count": analysis.get("averages", {}).get("word_count", 0),
                        "avg_keyword_density": analysis.get("averages", {}).get("keyword_density", 0),
                        "competitor_titles": analysis.get("competitor_titles", []),
                        "competitor_pages": [{"url": p.get("url",""), "word_count": p.get("word_count",0), "keyword_density": p.get("keyword_density",0)} for p in analysis.get("competitor_pages", [])],
                    },
                    "status": "generated", "created_at": datetime.now(timezone.utc).isoformat(), "created_by": username,
                }
                await db.brand_category_seo.update_one({"entity_id": eid, "entity_type": entity_type}, {"$set": doc}, upsert=True)
                generated += 1

                # Push to İkas
                if entity_type == "category":
                    mutation = "mutation UpdateCategory($input: UpdateCategoryInput!) { updateCategory(input: $input) { id } }"
                else:
                    mutation = "mutation UpdateProductBrand($input: UpdateProductBrandInput!) { updateProductBrand(input: $input) { id } }"
                variables = {"input": {"id": eid, "metaData": {"pageTitle": content_result.get("title", "")[:256], "description": content_result.get("description", "")[:320]}}}
                await loop.run_in_executor(None, ikas_graphql, mutation, variables)
                await db.brand_category_seo.update_one({"entity_id": eid, "entity_type": entity_type}, {"$set": {"status": "pushed", "pushed_at": datetime.now(timezone.utc).isoformat()}})
                pushed += 1
            except Exception as e:
                logger.warning(f"Bulk BC SEO failed for {ename}: {e}")
                failed += 1

            await db.system_status.update_one({"task": task_key}, {"$set": {"progress": i+1, "generated": generated, "pushed": pushed, "failed": failed}})
            await asyncio.sleep(3)

        await db.system_status.update_one({"task": task_key}, {"$set": {"running": False, "completed_at": datetime.now(timezone.utc).isoformat(), "progress": total, "generated": generated, "pushed": pushed, "failed": failed}})
    except Exception as e:
        logger.error(f"Bulk BC SEO error: {e}")
        await db.system_status.update_one({"task": task_key}, {"$set": {"running": False, "error": str(e)}})

@api_router.get("/ikas/bc-seo/bulk-status/{entity_type}")
async def bc_seo_bulk_status(entity_type: str, user: dict = Depends(get_current_user)):
    status = await db.system_status.find_one({"task": f"bc_seo_bulk_{entity_type}"}, {"_id": 0})
    return status or {"running": False, "progress": 0, "total": 0}

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
    
    # Reset any stuck background tasks from previous server runs
    stuck_reset = await db.system_status.update_many(
        {"running": True},
        {"$set": {"running": False, "error": "Sunucu yeniden basladi, gorev sifirlandi", "completed_at": datetime.now(timezone.utc).isoformat()}}
    )
    if stuck_reset.modified_count > 0:
        logger.info(f"Startup: {stuck_reset.modified_count} stuck task(s) reset")
    
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
    
    # Start scheduler
    scheduler.add_job(scheduled_feed_sync, CronTrigger(hour=1, minute=0), id="feed_sync", name="Feed Guncelleme (Her gece 01:00)", replace_existing=True)
    scheduler.add_job(scheduled_price_check, CronTrigger(hour=21, minute=0), id="price_check_cron", name="Fiyat Kontrolu (Her gece 00:00 TR)", replace_existing=True)
    scheduler.start()
    logger.info("Scheduler basladi: Feed guncelleme (her gece 01:00), Fiyat kontrolu (her gece 00:00 TR)")

@app.on_event("shutdown")
async def shutdown():
    scheduler.shutdown(wait=False)
    client.close()
