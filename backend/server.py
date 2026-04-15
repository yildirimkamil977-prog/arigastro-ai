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
    cheaper_only: bool = False,
    unmatched_only: bool = False,
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
    if cheaper_only:
        query["$and"] = [
            {"cheapest_price": {"$ne": None}},
            {"our_price": {"$ne": None}},
            {"$expr": {"$lt": ["$cheapest_price", "$our_price"]}}
        ]
    if unmatched_only:
        query["akakce_matched"] = False

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

# ============ AKAKCE SCRAPING ============

AKAKCE_SEARCH_URL = "https://www.akakce.com/arama/?q={query}"
AKAKCE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
}

async def search_akakce(product_name: str) -> dict:
    """Search Akakçe for a product and extract prices."""
    try:
        search_query = product_name.replace(" ", "+")
        url = AKAKCE_SEARCH_URL.format(query=search_query)
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as http_client:
            resp = await http_client.get(url, headers=AKAKCE_HEADERS)
            if resp.status_code != 200:
                return {"success": False, "error": f"HTTP {resp.status_code}", "competitors": []}
        
        soup = BeautifulSoup(resp.text, "html.parser")
        results = []
        
        # Try to parse Akakçe search results
        # Akakçe uses various list structures for search results
        product_items = soup.select("li.p") or soup.select("div.p") or soup.select("[class*='product']")
        
        for item in product_items[:10]:
            try:
                name_el = item.select_one("h3, .pn, [class*='name'], a[title]")
                price_el = item.select_one(".pt, .pb, [class*='price'], span.pt")
                
                name = name_el.get_text(strip=True) if name_el else ""
                price_text = price_el.get_text(strip=True) if price_el else ""
                
                # Parse Turkish price format (1.234,56 TL)
                price = parse_turkish_price(price_text)
                
                if name and price:
                    link = item.select_one("a")
                    href = link.get("href", "") if link else ""
                    if href and not href.startswith("http"):
                        href = f"https://www.akakce.com{href}"
                    results.append({"name": name, "price": price, "url": href})
            except Exception:
                continue
        
        # Also try to find the first product detail page result
        if not results:
            # Try alternate selectors
            for sel in ["ul.products li", "div.result-item", ".search-result"]:
                items = soup.select(sel)
                for item in items[:10]:
                    try:
                        name = item.get_text(strip=True)[:100]
                        price_match = re.search(r'([\d.]+,\d{2})\s*TL', item.get_text())
                        if price_match:
                            price = parse_turkish_price(price_match.group(0))
                            if price:
                                results.append({"name": name[:80], "price": price, "url": ""})
                    except Exception:
                        continue
                if results:
                    break
        
        return {
            "success": len(results) > 0,
            "search_url": url,
            "competitors": sorted(results, key=lambda x: x["price"])[:10],
            "error": None if results else "No results found or page structure changed"
        }
    except httpx.TimeoutException:
        return {"success": False, "error": "Timeout - Akakçe may be blocking requests", "competitors": []}
    except Exception as e:
        logger.error(f"Akakçe search error: {e}")
        return {"success": False, "error": str(e), "competitors": []}

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
    """Search Akakçe for product and update competitor prices."""
    product = await db.products.find_one({"slug": slug})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    result = await search_akakce(product["name"])
    
    update_data = {
        "last_price_check": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "akakce_matched": result["success"],
    }
    
    if result["success"] and result["competitors"]:
        cheapest = result["competitors"][0]
        update_data["cheapest_competitor"] = cheapest["name"]
        update_data["cheapest_price"] = cheapest["price"]
        update_data["competitors"] = result["competitors"]
        update_data["akakce_url"] = result.get("search_url", "")
        
        if product.get("our_price"):
            update_data["price_difference"] = round(product["our_price"] - cheapest["price"], 2)
        
        # Save to price history
        await db.price_history.insert_one({
            "product_slug": slug,
            "our_price": product.get("our_price"),
            "cheapest_competitor": cheapest["name"],
            "cheapest_price": cheapest["price"],
            "all_competitors": result["competitors"],
            "checked_at": datetime.now(timezone.utc).isoformat()
        })
    
    await db.products.update_one({"slug": slug}, {"$set": update_data})
    
    return {
        "slug": slug,
        "akakce_result": result,
        "updated": True
    }

# ============ SEO GENERATION ============

class SeoGenerateRequest(BaseModel):
    product_name: str
    product_url: Optional[str] = ""
    current_title: Optional[str] = ""
    current_description: Optional[str] = ""
    category: Optional[str] = ""

@api_router.post("/seo/generate/{slug}")
async def generate_seo(slug: str, user: dict = Depends(get_current_user)):
    """Generate SEO content for a product using OpenAI."""
    product = await db.products.find_one({"slug": slug})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    openai_key = os.environ.get("OPENAI_API_KEY")
    if not openai_key:
        raise HTTPException(status_code=500, detail="OpenAI API key not configured")
    
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        
        chat = LlmChat(
            api_key=openai_key,
            session_id=f"seo-{slug}-{uuid.uuid4().hex[:8]}",
            system_message="""Sen bir SEO uzmanısın. Endüstriyel mutfak ekipmanları için SEO içerikleri oluşturuyorsun.
Arıgastro Endüstriyel Mutfak Ekipmanları firması için çalışıyorsun.
Türkçe içerik üreteceksin. İçerikler özgün, SEO uyumlu ve profesyonel olmalı.
Yanıtını tam olarak şu JSON formatında ver, başka hiçbir şey ekleme:
{"seo_title": "...", "seo_description": "...", "product_description": "..."}"""
        ).with_model("openai", "gpt-4o")
        
        prompt = f"""Aşağıdaki ürün için SEO içerikleri oluştur:

Ürün Adı: {product['name']}
Ürün URL: {product.get('url', '')}
Kategori: {product.get('category_slug', 'Endüstriyel Mutfak Ekipmanı')}

Lütfen şunları oluştur:
1. SEO Title (max 60 karakter, anahtar kelime odaklı)
2. SEO Description (max 160 karakter, çekici ve bilgilendirici)
3. Ürün Açıklaması (300-500 kelime, detaylı, SEO uyumlu, özellikler ve faydalar içeren)

JSON formatında yanıt ver."""

        response = await chat.send_message(UserMessage(text=prompt))
        
        # Parse JSON response
        import json
        # Clean response - extract JSON from potential markdown code blocks
        response_text = response.strip()
        if response_text.startswith("```"):
            response_text = re.sub(r'^```(?:json)?\s*', '', response_text)
            response_text = re.sub(r'\s*```$', '', response_text)
        
        seo_data = json.loads(response_text)
        
        # Save to database
        seo_record = {
            "product_slug": slug,
            "seo_title": seo_data.get("seo_title", ""),
            "seo_description": seo_data.get("seo_description", ""),
            "product_description": seo_data.get("product_description", ""),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "status": "draft"
        }
        
        # Upsert - update if exists, insert if not
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
    """Check Akakçe prices for all tracked products. Rate limited."""
    tracked = await db.products.find({"is_tracked": True}, {"_id": 0, "slug": 1, "name": 1}).to_list(100)
    results = {"checked": 0, "matched": 0, "failed": 0}
    
    for product in tracked[:20]:  # Limit to 20 per batch to avoid blocking
        try:
            result = await search_akakce(product["name"])
            update_data = {
                "last_price_check": datetime.now(timezone.utc).isoformat(),
                "akakce_matched": result["success"],
                "updated_at": datetime.now(timezone.utc).isoformat()
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
            
            # Rate limiting - wait between requests
            await asyncio.sleep(3)
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
