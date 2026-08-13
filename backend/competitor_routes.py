"""Competitor pricing API routes — matching, price tracking, auto-pricing."""
import os
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List

logger = logging.getLogger("competitor_routes")

router = APIRouter(prefix="/competitor", tags=["competitor"])


def setup_competitor_routes(db, get_current_user, ikas_graphql):
    """Initialize routes with DB and auth dependencies."""
    
    from competitor_pricing import (
        COMPETITORS, search_competitor_product, scrape_competitor_price,
        match_all_competitors_for_product, scrape_all_competitor_prices,
        calculate_optimal_price,
    )
    
    # --- Competitor info ---
    @router.get("/list")
    async def list_competitors(user: dict = Depends(get_current_user)):
        return {"competitors": COMPETITORS}
    
    # --- Product matching ---
    class MatchRequest(BaseModel):
        competitor_key: str
        url: str
        title: Optional[str] = ""
    
    @router.post("/match/{slug}")
    async def match_product_single(slug: str, req: MatchRequest, user: dict = Depends(get_current_user)):
        """Manually set a competitor match for a product."""
        product = await db.products.find_one({"slug": slug})
        if not product:
            raise HTTPException(status_code=404, detail="Ürün bulunamadı")
        
        match_data = {
            "url": req.url,
            "title": req.title,
            "competitor_key": req.competitor_key,
            "competitor_name": COMPETITORS.get(req.competitor_key, {}).get("name", ""),
            "matched_at": datetime.now(timezone.utc).isoformat(),
            "manual": True,
        }
        
        await db.competitor_matches.update_one(
            {"product_slug": slug, "competitor_key": req.competitor_key},
            {"$set": match_data},
            upsert=True
        )
        return {"success": True, "match": match_data}
    
    @router.delete("/match/{slug}/{competitor_key}")
    async def remove_match(slug: str, competitor_key: str, user: dict = Depends(get_current_user)):
        """Remove a competitor match."""
        await db.competitor_matches.delete_one({"product_slug": slug, "competitor_key": competitor_key})
        return {"success": True}
    
    @router.post("/auto-match/{slug}")
    async def auto_match_product(slug: str, user: dict = Depends(get_current_user)):
        """Auto-match a product across all competitors using Google search."""
        product = await db.products.find_one({"slug": slug})
        if not product:
            raise HTTPException(status_code=404, detail="Ürün bulunamadı")
        
        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(None, match_all_competitors_for_product, product["name"])
        
        saved = 0
        for comp_key, result in results.items():
            if result.get("matched"):
                await db.competitor_matches.update_one(
                    {"product_slug": slug, "competitor_key": comp_key},
                    {"$set": {
                        "url": result["url"],
                        "title": result["title"],
                        "competitor_key": comp_key,
                        "competitor_name": result["competitor_name"],
                        "matched_at": datetime.now(timezone.utc).isoformat(),
                        "manual": False,
                    }},
                    upsert=True
                )
                saved += 1
        
        return {"success": True, "matched": saved, "total": len(COMPETITORS), "results": results}
    
    @router.post("/auto-match-category/{category_name}")
    async def auto_match_category(category_name: str, user: dict = Depends(get_current_user)):
        """Auto-match all products in a category. Runs in background."""
        products = await db.products.find(
            {"category": {"$regex": category_name, "$options": "i"}},
            {"slug": 1, "name": 1}
        ).to_list(5000)
        
        if not products:
            raise HTTPException(status_code=404, detail="Kategoride ürün bulunamadı")
        
        task_key = f"auto_match_{category_name}"
        await db.system_status.update_one(
            {"task": task_key},
            {"$set": {"running": True, "total": len(products), "progress": 0, "matched": 0, "started_at": datetime.now(timezone.utc).isoformat()}},
            upsert=True
        )
        
        asyncio.create_task(_run_category_match(db, products, task_key))
        return {"success": True, "total": len(products), "task_key": task_key}
    
    async def _run_category_match(db, products, task_key):
        loop = asyncio.get_event_loop()
        matched_total = 0
        for i, prod in enumerate(products):
            try:
                # Check stop
                status = await db.system_status.find_one({"task": task_key})
                if status and status.get("stop_requested"):
                    break
                
                # Skip already matched
                existing = await db.competitor_matches.count_documents({"product_slug": prod["slug"]})
                if existing >= len(COMPETITORS):
                    matched_total += 1
                    await db.system_status.update_one({"task": task_key}, {"$set": {"progress": i + 1, "matched": matched_total}})
                    continue
                
                results = await loop.run_in_executor(None, match_all_competitors_for_product, prod["name"])
                for comp_key, result in results.items():
                    if result.get("matched"):
                        await db.competitor_matches.update_one(
                            {"product_slug": prod["slug"], "competitor_key": comp_key},
                            {"$set": {
                                "url": result["url"], "title": result["title"],
                                "competitor_key": comp_key, "competitor_name": result["competitor_name"],
                                "matched_at": datetime.now(timezone.utc).isoformat(), "manual": False,
                            }},
                            upsert=True
                        )
                        matched_total += 1
                
                await db.system_status.update_one({"task": task_key}, {"$set": {"progress": i + 1, "matched": matched_total}})
                await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"Match error for {prod['slug']}: {e}")
        
        await db.system_status.update_one({"task": task_key}, {"$set": {"running": False, "stop_requested": False, "completed_at": datetime.now(timezone.utc).isoformat()}})
    
    @router.get("/match-status/{task_key}")
    async def get_match_status(task_key: str, user: dict = Depends(get_current_user)):
        status = await db.system_status.find_one({"task": task_key}, {"_id": 0})
        return status or {"running": False}
    
    @router.post("/match-stop/{task_key}")
    async def stop_match(task_key: str, user: dict = Depends(get_current_user)):
        await db.system_status.update_one({"task": task_key}, {"$set": {"stop_requested": True}})
        return {"success": True}
    
    # --- Price checking ---
    @router.post("/check-price/{slug}")
    async def check_product_prices(slug: str, user: dict = Depends(get_current_user)):
        """Check competitor prices for a single product."""
        matches = await db.competitor_matches.find({"product_slug": slug}).to_list(10)
        if not matches:
            raise HTTPException(status_code=404, detail="Eşleştirme bulunamadı")
        
        loop = asyncio.get_event_loop()
        match_dict = {m["competitor_key"]: m for m in matches}
        prices = await loop.run_in_executor(None, scrape_all_competitor_prices, match_dict)
        
        # Save price history
        if prices:
            await db.price_history.insert_one({
                "product_slug": slug,
                "prices": prices,
                "checked_at": datetime.now(timezone.utc).isoformat(),
            })
            # Update product with latest prices
            cheapest = min(prices.values(), key=lambda x: x["price"]) if prices else None
            await db.products.update_one({"slug": slug}, {"$set": {
                "competitor_prices": prices,
                "cheapest_competitor_price": cheapest["price"] if cheapest else None,
                "cheapest_competitor_name": cheapest["competitor_name"] if cheapest else None,
                "competitor_prices_checked_at": datetime.now(timezone.utc).isoformat(),
            }})
        
        return {"success": True, "prices": prices}
    
    # --- Product floor price & purchase price ---
    class PriceSettingsRequest(BaseModel):
        floor_price: Optional[float] = None
        purchase_price: Optional[float] = None
    
    @router.put("/price-settings/{slug}")
    async def update_price_settings(slug: str, req: PriceSettingsRequest, user: dict = Depends(get_current_user)):
        update = {}
        if req.floor_price is not None:
            update["floor_price"] = req.floor_price
        if req.purchase_price is not None:
            update["purchase_price"] = req.purchase_price
        
        if update:
            await db.products.update_one({"slug": slug}, {"$set": update})
        return {"success": True}
    
    # --- Category pricing rules ---
    class CategoryRuleRequest(BaseModel):
        category_name: str
        enabled: bool = True
        undercut_amount: float = 100
        profit_margin_pct: Optional[float] = None  # e.g. 15 for 15%
        scan_hour: int = 3  # Default 03:00 Turkey time
    
    @router.post("/category-rules")
    async def set_category_rule(req: CategoryRuleRequest, user: dict = Depends(get_current_user)):
        await db.pricing_rules.update_one(
            {"category_name": req.category_name},
            {"$set": {
                "category_name": req.category_name,
                "enabled": req.enabled,
                "undercut_amount": req.undercut_amount,
                "profit_margin_pct": req.profit_margin_pct,
                "scan_hour": req.scan_hour,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }},
            upsert=True
        )
        return {"success": True}
    
    @router.get("/category-rules")
    async def list_category_rules(user: dict = Depends(get_current_user)):
        rules = await db.pricing_rules.find({}, {"_id": 0}).to_list(200)
        return {"rules": rules}
    
    @router.delete("/category-rules/{category_name}")
    async def delete_category_rule(category_name: str, user: dict = Depends(get_current_user)):
        await db.pricing_rules.delete_one({"category_name": category_name})
        return {"success": True}
    
    # --- Get matches for a product ---
    @router.get("/matches/{slug}")
    async def get_product_matches(slug: str, user: dict = Depends(get_current_user)):
        matches = await db.competitor_matches.find({"product_slug": slug}, {"_id": 0}).to_list(10)
        return {"matches": matches}
    
    # --- Price history ---
    @router.get("/price-history/{slug}")
    async def get_price_history(slug: str, days: int = 30, user: dict = Depends(get_current_user)):
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        history = await db.price_history.find(
            {"product_slug": slug, "checked_at": {"$gte": cutoff}},
            {"_id": 0}
        ).sort("checked_at", -1).to_list(100)
        return {"history": history}
    
    # --- Price change log ---
    @router.get("/price-changes")
    async def list_price_changes(page: int = 1, limit: int = 50, user: dict = Depends(get_current_user)):
        skip = (page - 1) * limit
        total = await db.price_changes.count_documents({})
        changes = await db.price_changes.find({}, {"_id": 0}).sort("changed_at", -1).skip(skip).limit(limit).to_list(limit)
        return {"changes": changes, "total": total, "page": page, "pages": (total + limit - 1) // limit}
    
    # --- Products enhanced list (with competitor data) ---
    @router.get("/products")
    async def list_products_enhanced(
        user: dict = Depends(get_current_user),
        search: str = "",
        category: str = "",
        price_list: str = "",
        match_status: str = "",
        page: int = 1,
        limit: int = 50
    ):
        query = {"inactive": {"$ne": True}}
        if search:
            query["name"] = {"$regex": search, "$options": "i"}
        if category:
            query["$or"] = [
                {"category": {"$regex": category, "$options": "i"}},
                {"category_path": {"$regex": category, "$options": "i"}},
            ]
        
        skip = (page - 1) * limit
        total = await db.products.count_documents(query)
        products = await db.products.find(query, {"_id": 0}).sort("name", 1).skip(skip).limit(limit).to_list(limit)
        
        # Enrich with competitor matches
        slugs = [p["slug"] for p in products]
        matches = await db.competitor_matches.find({"product_slug": {"$in": slugs}}, {"_id": 0}).to_list(1000)
        match_map = {}
        for m in matches:
            if m["product_slug"] not in match_map:
                match_map[m["product_slug"]] = {}
            match_map[m["product_slug"]][m["competitor_key"]] = m
        
        for p in products:
            p["competitor_matches"] = match_map.get(p["slug"], {})
            p["match_count"] = len(p["competitor_matches"])
        
        # Filter by match status
        if match_status == "matched":
            products = [p for p in products if p["match_count"] > 0]
        elif match_status == "unmatched":
            products = [p for p in products if p["match_count"] == 0]
        
        # Get unique categories for filter
        categories = await db.products.distinct("category", {"inactive": {"$ne": True}})
        categories = sorted([c for c in categories if c])
        
        return {
            "products": products,
            "total": total,
            "page": page,
            "pages": (total + limit - 1) // limit,
            "categories": categories,
        }
    
    return router
