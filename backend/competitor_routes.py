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
        """Auto-match a product across all competitors. Runs in background."""
        product = await db.products.find_one({"slug": slug})
        if not product:
            raise HTTPException(status_code=404, detail="Ürün bulunamadı")
        
        task_key = f"auto_match_{slug}"
        await db.system_status.update_one(
            {"task": task_key},
            {"$set": {"running": True, "slug": slug, "product_name": product["name"], "started_at": datetime.now(timezone.utc).isoformat(), "matched": 0, "total": len(COMPETITORS), "results": {}}},
            upsert=True
        )
        
        asyncio.create_task(_run_single_product_match(db, slug, product["name"], product.get("brand", ""), product.get("gtin", ""), task_key, COMPETITORS, match_all_competitors_for_product, scrape_all_competitor_prices))
        return {"success": True, "task_key": task_key, "message": f"Eşleştirme başlatıldı: {product['name'][:50]}"}
    
    async def _run_single_product_match(db, slug, product_name, brand, gtin, task_key, competitors, match_fn, scrape_fn):
        loop = asyncio.get_event_loop()
        try:
            results = await loop.run_in_executor(None, match_fn, product_name, brand, gtin)
            
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
                            "match_score": result.get("score", 0),
                            "match_method": result.get("match_method", "text"),
                            "matched_at": datetime.now(timezone.utc).isoformat(),
                            "manual": False,
                        }},
                        upsert=True
                    )
                    saved += 1
            
            # Auto-scrape prices after matching
            if saved > 0:
                all_matches = await db.competitor_matches.find({"product_slug": slug}).to_list(10)
                match_dict = {m["competitor_key"]: m for m in all_matches}
                prices = await loop.run_in_executor(None, scrape_fn, match_dict)
                if prices:
                    await db.price_history.insert_one({
                        "product_slug": slug,
                        "prices": prices,
                        "checked_at": datetime.now(timezone.utc).isoformat(),
                    })
                    cheapest = min(prices.values(), key=lambda x: x["price"]) if prices else None
                    await db.products.update_one({"slug": slug}, {"$set": {
                        "competitor_prices": prices,
                        "cheapest_competitor_price": cheapest["price"] if cheapest else None,
                        "cheapest_competitor_name": cheapest["competitor_name"] if cheapest else None,
                        "competitor_prices_checked_at": datetime.now(timezone.utc).isoformat(),
                    }})
            
            # Serialize results for storage
            clean_results = {}
            for k, v in results.items():
                clean_results[k] = {"matched": v.get("matched", False), "error": v.get("error", ""), "title": v.get("title", "")}
            
            await db.system_status.update_one(
                {"task": task_key},
                {"$set": {"running": False, "matched": saved, "results": clean_results, "completed_at": datetime.now(timezone.utc).isoformat()}}
            )
        except Exception as e:
            logger.error(f"Auto-match error for {slug}: {e}")
            await db.system_status.update_one(
                {"task": task_key},
                {"$set": {"running": False, "matched": 0, "error": str(e), "completed_at": datetime.now(timezone.utc).isoformat()}}
            )
    
    @router.get("/auto-match-status/{task_key}")
    async def get_auto_match_status(task_key: str, user: dict = Depends(get_current_user)):
        status = await db.system_status.find_one({"task": task_key}, {"_id": 0})
        return status or {"running": False}
    
    @router.post("/auto-match-category/{category_name}")
    async def auto_match_category(category_name: str, user: dict = Depends(get_current_user)):
        """Auto-match all products in a category. Runs in background."""
        products = await db.products.find(
            {"category_path": {"$regex": category_name, "$options": "i"}, "inactive": {"$ne": True}},
            {"slug": 1, "name": 1, "brand": 1, "gtin": 1}
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
        products_matched = 0  # Kaç ürün en az 1 eşleşme buldu
        total_matches = 0     # Toplam bireysel eşleşme
        matched_slugs = []    # Fiyat taraması için
        for i, prod in enumerate(products):
            try:
                status = await db.system_status.find_one({"task": task_key})
                if status and status.get("stop_requested"):
                    break
                
                existing = await db.competitor_matches.count_documents({"product_slug": prod["slug"]})
                if existing >= len(COMPETITORS):
                    products_matched += 1
                    matched_slugs.append(prod["slug"])
                    await db.system_status.update_one({"task": task_key}, {"$set": {"progress": i + 1, "products_matched": products_matched, "total_matches": total_matches}})
                    continue
                
                results = await loop.run_in_executor(None, match_all_competitors_for_product, prod["name"], prod.get("brand", ""), prod.get("gtin", ""))
                prod_found = False
                for comp_key, result in results.items():
                    if result.get("matched"):
                        await db.competitor_matches.update_one(
                            {"product_slug": prod["slug"], "competitor_key": comp_key},
                            {"$set": {
                                "url": result["url"], "title": result["title"],
                                "competitor_key": comp_key, "competitor_name": result["competitor_name"],
                                "match_score": result.get("score", 0),
                                "match_method": result.get("match_method", "text"),
                                "matched_at": datetime.now(timezone.utc).isoformat(), "manual": False,
                            }},
                            upsert=True
                        )
                        total_matches += 1
                        prod_found = True
                
                if prod_found:
                    products_matched += 1
                    matched_slugs.append(prod["slug"])
                
                await db.system_status.update_one({"task": task_key}, {"$set": {"progress": i + 1, "products_matched": products_matched, "total_matches": total_matches}})
                await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"Match error for {prod['slug']}: {e}")
        
        # Phase 2: Auto price scan for matched products
        await db.system_status.update_one({"task": task_key}, {"$set": {"phase": "scanning", "scan_progress": 0, "scan_total": len(matched_slugs)}})
        
        scan_progress = 0
        for slug in matched_slugs:
            try:
                matches = await db.competitor_matches.find({"product_slug": slug}).to_list(10)
                match_dict = {m["competitor_key"]: m for m in matches}
                prices = await loop.run_in_executor(None, scrape_all_competitor_prices, match_dict)
                if prices:
                    await db.price_history.insert_one({"product_slug": slug, "prices": prices, "checked_at": datetime.now(timezone.utc).isoformat()})
                    cheapest = min(prices.values(), key=lambda x: x["price"])
                    await db.products.update_one({"slug": slug}, {"$set": {
                        "competitor_prices": prices,
                        "cheapest_competitor_price": cheapest["price"],
                        "cheapest_competitor_name": cheapest["competitor_name"],
                        "competitor_prices_checked_at": datetime.now(timezone.utc).isoformat(),
                    }})
                scan_progress += 1
                await db.system_status.update_one({"task": task_key}, {"$set": {"scan_progress": scan_progress}})
                await asyncio.sleep(0.5)
            except Exception as e:
                logger.error(f"Price scan error for {slug}: {e}")
                scan_progress += 1
        
        await db.system_status.update_one({"task": task_key}, {"$set": {
            "running": False, "stop_requested": False, "phase": "done",
            "products_matched": products_matched, "total_matches": total_matches,
            "completed_at": datetime.now(timezone.utc).isoformat()
        }})
    
    @router.get("/match-status/{task_key}")
    async def get_match_status(task_key: str, user: dict = Depends(get_current_user)):
        status = await db.system_status.find_one({"task": task_key}, {"_id": 0})
        return status or {"running": False}
    
    @router.post("/match-stop/{task_key}")
    async def stop_match(task_key: str, user: dict = Depends(get_current_user)):
        await db.system_status.update_one({"task": task_key}, {"$set": {"stop_requested": True}})
        return {"success": True}
    
    # --- Price checking (background) ---
    @router.post("/check-price/{slug}")
    async def check_product_prices(slug: str, user: dict = Depends(get_current_user)):
        """Check competitor prices for a single product. Runs in background."""
        matches = await db.competitor_matches.find({"product_slug": slug}).to_list(10)
        if not matches:
            raise HTTPException(status_code=404, detail="Eşleştirme bulunamadı")
        
        task_key = f"check_price_{slug}"
        await db.system_status.update_one(
            {"task": task_key},
            {"$set": {"running": True, "slug": slug, "started_at": datetime.now(timezone.utc).isoformat()}},
            upsert=True
        )
        
        asyncio.create_task(_run_price_check(db, slug, matches, scrape_all_competitor_prices, task_key))
        return {"success": True, "task_key": task_key, "message": "Fiyat taraması başlatıldı"}
    
    async def _run_price_check(db, slug, matches, scrape_fn, task_key):
        loop = asyncio.get_event_loop()
        try:
            match_dict = {m["competitor_key"]: m for m in matches}
            prices = await loop.run_in_executor(None, scrape_fn, match_dict)
            
            if prices:
                await db.price_history.insert_one({
                    "product_slug": slug,
                    "prices": prices,
                    "checked_at": datetime.now(timezone.utc).isoformat(),
                })
                cheapest = min(prices.values(), key=lambda x: x["price"])
                await db.products.update_one({"slug": slug}, {"$set": {
                    "competitor_prices": prices,
                    "cheapest_competitor_price": cheapest["price"],
                    "cheapest_competitor_name": cheapest["competitor_name"],
                    "competitor_prices_checked_at": datetime.now(timezone.utc).isoformat(),
                }})
            
            await db.system_status.update_one(
                {"task": task_key},
                {"$set": {"running": False, "prices": prices or {}, "completed_at": datetime.now(timezone.utc).isoformat()}}
            )
        except Exception as e:
            await db.system_status.update_one(
                {"task": task_key},
                {"$set": {"running": False, "error": str(e)}}
            )
    
    @router.get("/check-price-status/{task_key}")
    async def get_price_check_status(task_key: str, user: dict = Depends(get_current_user)):
        status = await db.system_status.find_one({"task": task_key}, {"_id": 0})
        return status or {"running": False}

    @router.post("/retry-failed-prices")
    async def retry_failed_prices(user: dict = Depends(get_current_user)):
        """Re-scan prices for all matched products that don't have prices yet."""
        # Find products with matches but missing some competitor prices
        pipeline = [
            {"$group": {"_id": "$product_slug", "competitors": {"$push": "$competitor_key"}}}
        ]
        match_groups = await db.competitor_matches.aggregate(pipeline).to_list(5000)
        
        retry_slugs = []
        for mg in match_groups:
            slug = mg["_id"]
            prod = await db.products.find_one({"slug": slug}, {"competitor_prices": 1})
            existing_prices = set((prod or {}).get("competitor_prices", {}).keys())
            matched_comps = set(mg["competitors"])
            missing = matched_comps - existing_prices
            if missing:
                retry_slugs.append(slug)
        
        if not retry_slugs:
            return {"started": False, "message": "Eksik fiyat olan ürün yok."}
        
        task_key = "retry_failed_prices"
        await db.system_status.update_one(
            {"task": task_key},
            {"$set": {"running": True, "total": len(retry_slugs), "progress": 0, "started_at": datetime.now(timezone.utc).isoformat()}},
            upsert=True
        )
        
        asyncio.create_task(_run_retry_prices(db, retry_slugs, scrape_all_competitor_prices, task_key))
        return {"started": True, "total": len(retry_slugs), "message": f"{len(retry_slugs)} ürünün eksik fiyatları taranacak."}
    
    async def _run_retry_prices(db, slugs, scrape_fn, task_key):
        loop = asyncio.get_event_loop()
        progress = 0
        for slug in slugs:
            try:
                matches = await db.competitor_matches.find({"product_slug": slug}).to_list(10)
                prod = await db.products.find_one({"slug": slug}, {"competitor_prices": 1})
                existing = (prod or {}).get("competitor_prices", {})
                
                # Only scrape missing competitors
                missing_matches = {m["competitor_key"]: m for m in matches if m["competitor_key"] not in existing}
                if not missing_matches:
                    progress += 1
                    continue
                
                new_prices = await loop.run_in_executor(None, scrape_fn, missing_matches)
                if new_prices:
                    merged = {**existing, **new_prices}
                    cheapest = min(merged.values(), key=lambda x: x["price"])
                    await db.products.update_one({"slug": slug}, {"$set": {
                        "competitor_prices": merged,
                        "cheapest_competitor_price": cheapest["price"],
                        "cheapest_competitor_name": cheapest["competitor_name"],
                        "competitor_prices_checked_at": datetime.now(timezone.utc).isoformat(),
                    }})
                    # Update price history
                    await db.price_history.insert_one({"product_slug": slug, "prices": merged, "checked_at": datetime.now(timezone.utc).isoformat()})
                
                progress += 1
                await db.system_status.update_one({"task": task_key}, {"$set": {"progress": progress}})
                await asyncio.sleep(0.5)
            except Exception as e:
                logger.error(f"Retry price error for {slug}: {e}")
                progress += 1
        
        await db.system_status.update_one({"task": task_key}, {"$set": {"running": False, "progress": progress, "completed_at": datetime.now(timezone.utc).isoformat()}})
    
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
        profit_margin_pct: Optional[float] = None
        auto_update_ikas: bool = False  # Otomatik İkas fiyat güncelleme
    
    @router.post("/category-rules")
    async def set_category_rule(req: CategoryRuleRequest, user: dict = Depends(get_current_user)):
        await db.pricing_rules.update_one(
            {"category_name": req.category_name},
            {"$set": {
                "category_name": req.category_name,
                "enabled": req.enabled,
                "undercut_amount": req.undercut_amount,
                "profit_margin_pct": req.profit_margin_pct,
                "auto_update_ikas": req.auto_update_ikas,
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
    def _parse_categories_from_paths(paths):
        """Parse category_path values into structured top-level and sub-category lists."""
        top_cats = set()
        sub_cats = set()
        for p in paths:
            if not p:
                continue
            for segment in p.split(","):
                segment = segment.strip()
                if segment == "Tüm Ürünler":
                    continue
                parts = [x.strip() for x in segment.split(">")]
                if parts and parts[0]:
                    top_cats.add(parts[0])
                if len(parts) > 1:
                    sub_cats.add(f"{parts[0]} > {parts[1]}")
        return sorted(top_cats), sorted(sub_cats)

    @router.get("/products")
    async def list_products_enhanced(
        user: dict = Depends(get_current_user),
        search: str = "",
        category: str = "",
        brand: str = "",
        match_status: str = "",
        page: int = 1,
        limit: int = 50
    ):
        query = {"inactive": {"$ne": True}}
        if search:
            query["name"] = {"$regex": search, "$options": "i"}
        if category:
            query["category_path"] = {"$regex": category, "$options": "i"}
        if brand:
            query["brand"] = {"$regex": f"^{brand}$", "$options": "i"}
        
        skip = (page - 1) * limit
        total = await db.products.count_documents(query)

        # Get slugs that have competitor matches (ONLY new 4-site system)
        matched_slugs_list = await db.competitor_matches.distinct("product_slug")

        # Priority sort: products with new-system competitor matches first
        pipeline = [
            {"$match": query},
            {"$addFields": {
                "_sort_priority": {"$cond": [
                    {"$in": ["$slug", matched_slugs_list]},
                    0, 1
                ]}
            }},
            {"$sort": {"_sort_priority": 1, "name": 1}},
            {"$skip": skip},
            {"$limit": limit},
            {"$project": {"_id": 0, "_sort_priority": 0}},
        ]
        products = await db.products.aggregate(pipeline).to_list(limit)
        
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
            # Parse top-level category from category_path for display
            cp = p.get("category_path", "")
            if cp:
                first_segment = cp.split(",")[0].strip()
                if first_segment != "Tüm Ürünler":
                    parts = [x.strip() for x in first_segment.split(">")]
                    p["category"] = parts[0] if parts else ""
                    p["subcategory"] = parts[1] if len(parts) > 1 else ""
                else:
                    p["category"] = ""
                    p["subcategory"] = ""
            else:
                p["category"] = ""
                p["subcategory"] = ""
        
        # Filter by match status (post-filter)
        if match_status == "matched":
            products = [p for p in products if p["match_count"] > 0]
        elif match_status == "unmatched":
            products = [p for p in products if p["match_count"] == 0]
        
        # Get unique categories and brands for filters
        all_paths = await db.products.distinct("category_path", {"inactive": {"$ne": True}})
        top_categories, sub_categories = _parse_categories_from_paths(all_paths)
        brands = await db.products.distinct("brand", {"inactive": {"$ne": True}})
        brands = sorted([b for b in brands if b])
        
        return {
            "products": products,
            "total": total,
            "page": page,
            "pages": (total + limit - 1) // limit,
            "categories": top_categories,
            "sub_categories": sub_categories,
            "brands": brands,
        }
    
    # --- İkas price info for a product ---
    @router.get("/ikas-price/{slug}")
    async def get_ikas_price_info(slug: str, user: dict = Depends(get_current_user)):
        """Fetch price list details from İkas for a product."""
        product = await db.products.find_one({"slug": slug})
        if not product:
            raise HTTPException(status_code=404, detail="Ürün bulunamadı")
        
        ikas_id = product.get("ikas_id") or product.get("ikas_product_id")
        if not ikas_id:
            return {"prices": [], "error": "İkas ID bulunamadı"}
        
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, ikas_graphql,
                f'{{ listProduct(id: {{eq: "{ikas_id}"}}) {{ data {{ name variants {{ id prices {{ sellPrice discountPrice currency priceListId }} }} }} }} }}',
                None
            )
            variants = (result.get("listProduct", {}).get("data", []) or [{}])[0].get("variants", [])
            prices = []
            for v in variants[:1]:
                for p in (v.get("prices") or []):
                    if p.get("sellPrice") and p.get("sellPrice") > 0:
                        prices.append({
                            "sell_price": p["sellPrice"],
                            "discount_price": p.get("discountPrice"),
                            "currency": p.get("currency", "TRY"),
                            "price_list_id": p.get("priceListId", ""),
                        })
            return {"prices": prices}
        except Exception as e:
            return {"prices": [], "error": str(e)}

    # ============================================================
    # MODULE 3: Bulk Price Scanning, Comparison & Tracking
    # ============================================================

    @router.post("/scan-all")
    async def scan_all_matched_products(user: dict = Depends(get_current_user)):
        """Start bulk price scan for all matched products. Runs in background."""
        status = await db.system_status.find_one({"task": "competitor_scan"}, {"_id": 0})
        if status and status.get("running"):
            return {"started": False, "message": "Tarama zaten devam ediyor.", "status": status}

        # Count products that have at least one competitor match
        pipeline = [
            {"$group": {"_id": "$product_slug"}},
            {"$count": "total"}
        ]
        count_result = await db.competitor_matches.aggregate(pipeline).to_list(1)
        total = count_result[0]["total"] if count_result else 0

        if total == 0:
            return {"started": False, "message": "Eşleşmiş ürün yok. Önce ürünleri eşleştirin."}

        await db.system_status.update_one(
            {"task": "competitor_scan"},
            {"$set": {
                "running": True,
                "started_at": datetime.now(timezone.utc).isoformat(),
                "total": total,
                "scanned": 0,
                "success": 0,
                "failed": 0,
                "current_product": "",
            }},
            upsert=True
        )

        asyncio.create_task(_run_bulk_competitor_scan(db, COMPETITORS, scrape_all_competitor_prices, calculate_optimal_price))
        return {"started": True, "total": total, "message": f"{total} ürün için fiyat taraması başlatıldı."}

    async def _run_bulk_competitor_scan(db, competitors, scrape_fn, calc_fn):
        """Background: scan all matched products and record price history."""
        loop = asyncio.get_event_loop()
        try:
            # Get all unique slugs with matches
            slugs_cursor = db.competitor_matches.aggregate([
                {"$group": {"_id": "$product_slug"}}
            ])
            slugs = [doc["_id"] async for doc in slugs_cursor]

            scanned = 0
            success = 0
            failed = 0

            for slug in slugs:
                try:
                    # Check stop
                    stop_check = await db.system_status.find_one({"task": "competitor_scan"})
                    if stop_check and stop_check.get("stop_requested"):
                        break

                    product = await db.products.find_one({"slug": slug})
                    if not product:
                        scanned += 1
                        continue

                    await db.system_status.update_one(
                        {"task": "competitor_scan"},
                        {"$set": {"current_product": (product.get("name") or slug)[:50], "scanned": scanned}}
                    )

                    # Get matches
                    matches = await db.competitor_matches.find({"product_slug": slug}).to_list(10)
                    match_dict = {m["competitor_key"]: m for m in matches}

                    # Scrape prices (blocking call in executor)
                    prices = await loop.run_in_executor(None, scrape_fn, match_dict)

                    if prices:
                        # Save to price history
                        await db.price_history.insert_one({
                            "product_slug": slug,
                            "prices": prices,
                            "checked_at": datetime.now(timezone.utc).isoformat(),
                        })

                        # Find cheapest
                        cheapest = min(prices.values(), key=lambda x: x["price"])

                        # ===== SENARYO 1 & 2: Effective Floor =====
                        floor_price = product.get("floor_price")
                        purchase_price = product.get("purchase_price")
                        effective_floor = None

                        if floor_price:
                            effective_floor = floor_price
                        elif purchase_price:
                            cp = product.get("category_path", "")
                            top_cat = ""
                            if cp:
                                first_seg = cp.split(",")[0].strip()
                                if first_seg != "Tüm Ürünler":
                                    top_cat = first_seg.split(">")[0].strip()
                            if top_cat:
                                rule = await db.pricing_rules.find_one({"category_name": top_cat})
                                if rule and rule.get("profit_margin_pct"):
                                    effective_floor = purchase_price * (1 + rule["profit_margin_pct"] / 100)

                        # Get undercut amount from category rule
                        undercut = 100
                        cp = product.get("category_path", "")
                        if cp:
                            top_cat = cp.split(",")[0].strip().split(">")[0].strip()
                            rule = await db.pricing_rules.find_one({"category_name": top_cat})
                            if rule:
                                undercut = rule.get("undercut_amount", 100)

                        result = calc_fn(prices, product.get("our_price", 0), effective_floor or 0, undercut)

                        # Update product
                        update = {
                            "competitor_prices": prices,
                            "cheapest_competitor_price": cheapest["price"],
                            "cheapest_competitor_name": cheapest["competitor_name"],
                            "competitor_prices_checked_at": datetime.now(timezone.utc).isoformat(),
                            "price_recommendation": result,
                        }
                        await db.products.update_one({"slug": slug}, {"$set": update})

                        # Log price changes and floor_hit events
                        if result.get("action") in ("update", "floor_hit"):
                            await db.price_changes.insert_one({
                                "product_slug": slug,
                                "product_name": product.get("name", ""),
                                "action": result["action"],
                                "old_price": result.get("old_price", product.get("our_price")),
                                "new_price": result.get("new_price"),
                                "cheapest_competitor": result.get("cheapest_competitor"),
                                "cheapest_price": result.get("cheapest_price"),
                                "floor_price": effective_floor,
                                "reason": result.get("reason", ""),
                                "applied": False,
                                "can_update": effective_floor is not None,
                                "changed_at": datetime.now(timezone.utc).isoformat(),
                            })

                        success += 1
                    else:
                        failed += 1

                    scanned += 1
                    await asyncio.sleep(0.5)

                except Exception as e:
                    logger.error(f"Scan error for {slug}: {e}")
                    failed += 1
                    scanned += 1

            await db.system_status.update_one(
                {"task": "competitor_scan"},
                {"$set": {
                    "running": False,
                    "stop_requested": False,
                    "scanned": scanned,
                    "success": success,
                    "failed": failed,
                    "current_product": "",
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                }}
            )
        except Exception as e:
            logger.error(f"Bulk competitor scan error: {e}")
            await db.system_status.update_one(
                {"task": "competitor_scan"},
                {"$set": {"running": False, "error": str(e)}}
            )

    @router.get("/scan-status")
    async def get_scan_status(user: dict = Depends(get_current_user)):
        """Get current bulk scan status."""
        status = await db.system_status.find_one({"task": "competitor_scan"}, {"_id": 0})
        return status or {"running": False, "scanned": 0, "total": 0}

    @router.post("/scan-stop")
    async def stop_scan(user: dict = Depends(get_current_user)):
        """Stop the running bulk scan."""
        await db.system_status.update_one({"task": "competitor_scan"}, {"$set": {"stop_requested": True}})
        return {"success": True}

    # --- Dashboard summary ---
    @router.get("/dashboard")
    async def competitor_dashboard(user: dict = Depends(get_current_user)):
        """Get summary stats for the competitor tracking dashboard."""
        total_products = await db.products.count_documents({"inactive": {"$ne": True}})

        # Count matched products (distinct slugs in competitor_matches)
        matched_pipeline = [{"$group": {"_id": "$product_slug"}}, {"$count": "total"}]
        matched_result = await db.competitor_matches.aggregate(matched_pipeline).to_list(1)
        matched_products = matched_result[0]["total"] if matched_result else 0

        # Products where competitor is cheaper
        cheaper_count = await db.products.count_documents({
            "cheapest_competitor_price": {"$exists": True, "$ne": None},
            "$expr": {"$lt": ["$cheapest_competitor_price", "$our_price"]}
        })

        # Products with price recommendations
        recommend_count = await db.products.count_documents({
            "price_recommendation.action": "update"
        })

        # Last scan info
        scan_status = await db.system_status.find_one({"task": "competitor_scan"}, {"_id": 0})

        # Recent price changes (last 10)
        recent_changes = await db.price_changes.find(
            {}, {"_id": 0}
        ).sort("changed_at", -1).limit(10).to_list(10)

        # Category rules
        rules = await db.pricing_rules.find({}, {"_id": 0}).to_list(100)

        # Scheduled scan info
        scheduled_scan = await db.system_status.find_one({"task": "scheduled_competitor_scan"}, {"_id": 0})

        return {
            "total_products": total_products,
            "matched_products": matched_products,
            "cheaper_count": cheaper_count,
            "recommend_count": recommend_count,
            "scan_status": scan_status,
            "recent_changes": recent_changes,
            "category_rules": rules,
            "scheduled_scan": scheduled_scan,
        }

    # ============================================================
    # MODULE 4: İkas Price Update (Original Currency)
    # ============================================================

    IKAS_PRICE_LISTS = {
        "EUR": "db850a77-bfd6-43de-8892-78d16dc01e0e",
        "USD": "28b86f15-34b5-4c49-8d96-678194f4a8ba",
        "TRY": "35b38ca5-9f2d-4482-a9d8-3a6b0df33efd",
        # Nihai fiyat listesi — DOKUNULMAYACAK:
        # "NIHAI": "b8f60257-5b81-44c9-8238-99b18b49e63"
    }

    class ApplyPriceRequest(BaseModel):
        slug: str
        new_price_tl: float
        reason: Optional[str] = ""

    @router.post("/apply-price")
    async def apply_price_to_ikas(req: ApplyPriceRequest, user: dict = Depends(get_current_user)):
        """Apply a recommended price change to İkas, updating the original currency price list."""
        product = await db.products.find_one({"slug": req.slug})
        if not product:
            raise HTTPException(status_code=404, detail="Ürün bulunamadı")

        # SAFETY CHECK: effective floor must be calculable
        floor_price = product.get("floor_price")
        purchase_price = product.get("purchase_price")
        if not floor_price and not purchase_price:
            return {"success": False, "error": "Bu ürünün ne dip fiyatı ne de alış fiyatı girilmiş. Fiyat güncellenmeden önce en az birinin girilmesi zorunludur."}

        ikas_id = product.get("ikas_id") or product.get("ikas_product_id")
        if not ikas_id:
            return {"success": False, "error": "Bu üründe İkas ID bulunamadı. VPS'de İkas senkronizasyonu yapılmalı."}

        try:
            loop = asyncio.get_event_loop()

            # Step 1: Fetch current İkas prices and variant info
            gql_query = f'''{{ listProduct(id: {{eq: "{ikas_id}"}}) {{ data {{
                name
                categories {{ categoryId }}
                brand {{ brandId }}
                variants {{ id prices {{ sellPrice discountPrice currency priceListId }} }}
            }} }} }}'''
            result = await loop.run_in_executor(None, ikas_graphql, gql_query, None)
            product_data = (result.get("listProduct", {}).get("data", []) or [{}])[0]
            variants = product_data.get("variants", [])
            if not variants:
                return {"success": False, "error": "İkas'ta varyant bulunamadı"}

            variant = variants[0]
            existing_prices = variant.get("prices", [])

            # Step 2: Determine which price list to update (original currency, NOT Nihai)
            target_price_list = None
            target_currency = None
            original_sell_price = None

            for p in existing_prices:
                plid = p.get("priceListId", "")
                # Skip Nihai list
                if plid.startswith("b8f60257"):
                    continue
                # Prefer EUR > USD > TRY
                if plid == IKAS_PRICE_LISTS.get("EUR"):
                    target_price_list = plid
                    target_currency = "EUR"
                    original_sell_price = p.get("sellPrice", 0)
                    break
                elif plid == IKAS_PRICE_LISTS.get("USD"):
                    target_price_list = plid
                    target_currency = "USD"
                    original_sell_price = p.get("sellPrice", 0)
                elif plid == IKAS_PRICE_LISTS.get("TRY") and not target_price_list:
                    target_price_list = plid
                    target_currency = "TRY"
                    original_sell_price = p.get("sellPrice", 0)

            if not target_price_list:
                return {"success": False, "error": "Güncellenecek fiyat listesi bulunamadı"}

            # Step 3: Convert TL price to original currency if needed
            if target_currency == "TRY":
                new_price = req.new_price_tl
            else:
                # Calculate ratio from current prices
                tl_price = product.get("our_price", 0)
                if tl_price and original_sell_price and tl_price > 0:
                    ratio = original_sell_price / tl_price
                    new_price = round(req.new_price_tl * ratio, 2)
                else:
                    return {"success": False, "error": f"Kur oranı hesaplanamadı (TL: {tl_price}, {target_currency}: {original_sell_price})"}

            # Step 4: Build prices array preserving ALL existing prices, only changing target
            updated_prices = []
            for p in existing_prices:
                price_entry = {
                    "priceListId": p["priceListId"],
                    "sellPrice": p.get("sellPrice", 0),
                    "currency": p.get("currency", "TRY"),
                }
                if p.get("discountPrice"):
                    price_entry["discountPrice"] = p["discountPrice"]
                # Override target price list
                if p["priceListId"] == target_price_list:
                    price_entry["sellPrice"] = new_price
                updated_prices.append(price_entry)

            # Step 5: Build mutation preserving categories and brand
            existing_cats = [c["categoryId"] for c in (product_data.get("categories") or [])]
            existing_brand = (product_data.get("brand") or {}).get("brandId")

            update_input = {
                "id": ikas_id,
                "variants": [{
                    "id": variant["id"],
                    "prices": updated_prices,
                }],
            }
            if existing_cats:
                update_input["categoryIds"] = existing_cats
            if existing_brand:
                update_input["brandId"] = existing_brand

            mutation = "mutation UpdateProduct($input: UpdateProductInput!) { updateProduct(input: $input) { id } }"
            await loop.run_in_executor(None, ikas_graphql, mutation, {"input": update_input})

            # Step 6: Log the change
            await db.price_changes.update_one(
                {"product_slug": req.slug, "applied": False, "action": "update"},
                {"$set": {
                    "applied": True,
                    "applied_at": datetime.now(timezone.utc).isoformat(),
                    "applied_price_tl": req.new_price_tl,
                    "applied_price_original": new_price,
                    "applied_currency": target_currency,
                    "applied_price_list_id": target_price_list,
                }},
                upsert=False
            )

            # Update local product record
            await db.products.update_one({"slug": req.slug}, {"$set": {
                "our_price": req.new_price_tl,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }})

            return {
                "success": True,
                "message": f"Fiyat güncellendi: {new_price:.2f} {target_currency} ({req.new_price_tl:.2f} TL)",
                "original_currency": target_currency,
                "original_price": new_price,
                "tl_price": req.new_price_tl,
                "price_list_id": target_price_list,
            }

        except Exception as e:
            logger.error(f"İkas price update error for {req.slug}: {e}")
            return {"success": False, "error": str(e)}

    @router.post("/apply-all-recommendations")
    async def apply_all_recommendations(user: dict = Depends(get_current_user)):
        """Apply all pending price recommendations. Runs in background."""
        pending = await db.price_changes.count_documents({"applied": False, "action": "update"})
        if pending == 0:
            return {"started": False, "message": "Bekleyen fiyat önerisi yok."}

        task_key = "apply_recommendations"
        status = await db.system_status.find_one({"task": task_key})
        if status and status.get("running"):
            return {"started": False, "message": "Fiyat güncelleme zaten devam ediyor."}

        await db.system_status.update_one(
            {"task": task_key},
            {"$set": {"running": True, "total": pending, "applied": 0, "failed": 0, "started_at": datetime.now(timezone.utc).isoformat()}},
            upsert=True
        )

        asyncio.create_task(_run_apply_all(db, ikas_graphql, IKAS_PRICE_LISTS, task_key))
        return {"started": True, "total": pending, "message": f"{pending} fiyat önerisi uygulanacak."}

    async def _run_apply_all(db, ikas_fn, price_lists, task_key):
        loop = asyncio.get_event_loop()
        applied = 0
        failed = 0
        try:
            changes = await db.price_changes.find({"applied": False, "action": "update"}).to_list(500)
            for ch in changes:
                try:
                    slug = ch["product_slug"]
                    new_price_tl = ch["new_price"]
                    product = await db.products.find_one({"slug": slug})
                    if not product:
                        failed += 1
                        continue

                    ikas_id = product.get("ikas_id") or product.get("ikas_product_id")
                    if not ikas_id:
                        # No İkas ID — mark as failed with reason
                        await db.price_changes.update_one(
                            {"_id": ch["_id"]},
                            {"$set": {"apply_error": "İkas ID bulunamadı"}}
                        )
                        failed += 1
                        continue

                    # Fetch İkas product for variant + price info
                    gql_query = f'''{{ listProduct(id: {{eq: "{ikas_id}"}}) {{ data {{
                        categories {{ categoryId }}
                        brand {{ brandId }}
                        variants {{ id prices {{ sellPrice discountPrice currency priceListId }} }}
                    }} }} }}'''
                    result = await loop.run_in_executor(None, ikas_fn, gql_query, None)
                    product_data = (result.get("listProduct", {}).get("data", []) or [{}])[0]
                    variants = product_data.get("variants", [])
                    if not variants:
                        failed += 1
                        continue

                    variant = variants[0]
                    existing_prices = variant.get("prices", [])

                    # Determine target price list (prefer EUR > USD > TRY, skip Nihai)
                    target_plid = None
                    target_currency = None
                    original_sell = None
                    for p in existing_prices:
                        plid = p.get("priceListId", "")
                        if plid.startswith("b8f60257"):
                            continue
                        if plid == price_lists.get("EUR"):
                            target_plid, target_currency, original_sell = plid, "EUR", p.get("sellPrice", 0)
                            break
                        elif plid == price_lists.get("USD"):
                            target_plid, target_currency, original_sell = plid, "USD", p.get("sellPrice", 0)
                        elif plid == price_lists.get("TRY") and not target_plid:
                            target_plid, target_currency, original_sell = plid, "TRY", p.get("sellPrice", 0)

                    if not target_plid:
                        failed += 1
                        continue

                    # Convert to original currency
                    if target_currency == "TRY":
                        new_price = new_price_tl
                    else:
                        tl_price = product.get("our_price", 0)
                        if tl_price and original_sell and tl_price > 0:
                            new_price = round(new_price_tl * (original_sell / tl_price), 2)
                        else:
                            failed += 1
                            continue

                    # Build updated prices array
                    updated_prices = []
                    for p in existing_prices:
                        entry = {"priceListId": p["priceListId"], "sellPrice": p.get("sellPrice", 0), "currency": p.get("currency", "TRY")}
                        if p.get("discountPrice"):
                            entry["discountPrice"] = p["discountPrice"]
                        if p["priceListId"] == target_plid:
                            entry["sellPrice"] = new_price
                        updated_prices.append(entry)

                    # Build mutation preserving categories & brand
                    existing_cats = [c["categoryId"] for c in (product_data.get("categories") or [])]
                    existing_brand = (product_data.get("brand") or {}).get("brandId")
                    update_input = {"id": ikas_id, "variants": [{"id": variant["id"], "prices": updated_prices}]}
                    if existing_cats:
                        update_input["categoryIds"] = existing_cats
                    if existing_brand:
                        update_input["brandId"] = existing_brand

                    mutation = "mutation UpdateProduct($input: UpdateProductInput!) { updateProduct(input: $input) { id } }"
                    await loop.run_in_executor(None, ikas_fn, mutation, {"input": update_input})

                    # Mark as applied
                    await db.price_changes.update_one(
                        {"_id": ch["_id"]},
                        {"$set": {
                            "applied": True,
                            "applied_at": datetime.now(timezone.utc).isoformat(),
                            "applied_price_tl": new_price_tl,
                            "applied_price_original": new_price,
                            "applied_currency": target_currency,
                        }}
                    )
                    await db.products.update_one({"slug": slug}, {"$set": {"our_price": new_price_tl, "updated_at": datetime.now(timezone.utc).isoformat()}})
                    applied += 1

                except Exception as e:
                    logger.error(f"Apply price error for {ch.get('product_slug', '?')}: {e}")
                    failed += 1

                await db.system_status.update_one(
                    {"task": task_key},
                    {"$set": {"applied": applied, "failed": failed}}
                )
                await asyncio.sleep(1)

            await db.system_status.update_one(
                {"task": task_key},
                {"$set": {"running": False, "applied": applied, "failed": failed, "completed_at": datetime.now(timezone.utc).isoformat()}}
            )
        except Exception as e:
            await db.system_status.update_one(
                {"task": task_key},
                {"$set": {"running": False, "error": str(e)}}
            )

    # ============================================================
    # MODULE 5: Price Change Logs (Full History)
    # ============================================================

    @router.get("/price-changes-full")
    async def list_price_changes_full(
        user: dict = Depends(get_current_user),
        page: int = 1,
        limit: int = 50,
        status_filter: str = "",
        search: str = "",
    ):
        """Full price change history with filters."""
        query = {}
        if status_filter == "applied":
            query["applied"] = True
        elif status_filter == "pending":
            query["applied"] = False
            query["action"] = "update"
            query["apply_error"] = {"$exists": False}
        elif status_filter == "floor_hit":
            query["action"] = "floor_hit"
        elif status_filter == "error":
            query["apply_error"] = {"$exists": True, "$ne": ""}
        if search:
            query["product_name"] = {"$regex": search, "$options": "i"}

        skip = (page - 1) * limit
        total = await db.price_changes.count_documents(query)
        changes = await db.price_changes.find(query, {"_id": 0}).sort("changed_at", -1).skip(skip).limit(limit).to_list(limit)

        return {
            "changes": changes,
            "total": total,
            "page": page,
            "pages": (total + limit - 1) // limit,
        }

    return router


async def run_scheduled_competitor_scan(db, ikas_graphql=None):
    """Called by APScheduler — scans all matched products, then auto-updates İkas for enabled categories."""
    from competitor_pricing import (
        COMPETITORS, scrape_all_competitor_prices, calculate_optimal_price,
    )
    logger.info("CRON: Rakip fiyat taramasi basladi")
    try:
        # Build rules map by category name
        rules_list = await db.pricing_rules.find({"enabled": True}).to_list(100)
        rules_map = {r["category_name"]: r for r in rules_list}
        # Categories with auto İkas update
        auto_update_cats = {r["category_name"] for r in rules_list if r.get("auto_update_ikas")}

        # Get all matched product slugs
        slugs_cursor = db.competitor_matches.aggregate([{"$group": {"_id": "$product_slug"}}])
        slugs = [doc["_id"] async for doc in slugs_cursor]
        if not slugs:
            logger.info("CRON: Eslesmis urun yok, atlanıyor")
            return

        await db.system_status.update_one(
            {"task": "competitor_scan"},
            {"$set": {
                "running": True,
                "started_at": datetime.now(timezone.utc).isoformat(),
                "total": len(slugs), "scanned": 0, "success": 0, "failed": 0,
                "auto_updated": 0,
                "current_product": "", "triggered_by": "scheduler",
            }},
            upsert=True,
        )

        loop = asyncio.get_event_loop()
        scanned = success = failed = auto_updated = 0

        IKAS_PRICE_LISTS = {
            "EUR": "db850a77-bfd6-43de-8892-78d16dc01e0e",
            "USD": "28b86f15-34b5-4c49-8d96-678194f4a8ba",
            "TRY": "35b38ca5-9f2d-4482-a9d8-3a6b0df33efd",
        }

        for slug in slugs:
            try:
                stop = await db.system_status.find_one({"task": "competitor_scan"})
                if stop and stop.get("stop_requested"):
                    break

                product = await db.products.find_one({"slug": slug})
                if not product:
                    scanned += 1
                    continue

                await db.system_status.update_one(
                    {"task": "competitor_scan"},
                    {"$set": {"current_product": (product.get("name") or slug)[:50], "scanned": scanned}},
                )

                # Determine product's top category
                cp = product.get("category_path", "")
                top_cat = ""
                if cp:
                    first_seg = cp.split(",")[0].strip()
                    if first_seg != "Tüm Ürünler":
                        top_cat = first_seg.split(">")[0].strip()

                rule = rules_map.get(top_cat, {})

                matches = await db.competitor_matches.find({"product_slug": slug}).to_list(10)
                match_dict = {m["competitor_key"]: m for m in matches}
                prices = await loop.run_in_executor(None, scrape_all_competitor_prices, match_dict)

                if prices:
                    await db.price_history.insert_one({
                        "product_slug": slug,
                        "prices": prices,
                        "checked_at": datetime.now(timezone.utc).isoformat(),
                    })

                    cheapest = min(prices.values(), key=lambda x: x["price"])

                    # ===== SENARYO 1 & 2: Effective Floor Hesaplama =====
                    floor_price = product.get("floor_price")        # Manuel dip fiyat
                    purchase_price = product.get("purchase_price")   # Alış fiyatı
                    effective_floor = None

                    if floor_price:
                        # SENARYO 1: Manuel dip fiyat girilmiş
                        effective_floor = floor_price
                    elif purchase_price and rule.get("profit_margin_pct"):
                        # SENARYO 2: Alış fiyatı + kategori kar oranı ile hesapla
                        effective_floor = purchase_price * (1 + rule["profit_margin_pct"] / 100)

                    # SENARYO 3: Ne dip ne alış+marj yok → güncelleme yapılamaz
                    can_update_price = effective_floor is not None

                    undercut = rule.get("undercut_amount", 100)
                    result = calculate_optimal_price(prices, product.get("our_price", 0), effective_floor or 0, undercut)

                    update_fields = {
                        "competitor_prices": prices,
                        "cheapest_competitor_price": cheapest["price"],
                        "cheapest_competitor_name": cheapest["competitor_name"],
                        "competitor_prices_checked_at": datetime.now(timezone.utc).isoformat(),
                        "price_recommendation": result,
                    }
                    await db.products.update_one({"slug": slug}, {"$set": update_fields})

                    # Log & auto-update İkas if category allows
                    if result.get("action") == "update":
                        should_auto = top_cat in auto_update_cats
                        log_entry = {
                            "product_slug": slug,
                            "product_name": product.get("name", ""),
                            "action": "update",
                            "old_price": result.get("old_price"),
                            "new_price": result.get("new_price"),
                            "cheapest_competitor": result.get("cheapest_competitor"),
                            "cheapest_price": result.get("cheapest_price"),
                            "floor_price": effective_floor,
                            "reason": result.get("reason", ""),
                            "applied": False,
                            "auto_update": should_auto,
                            "changed_at": datetime.now(timezone.utc).isoformat(),
                        }

                        if should_auto and ikas_graphql and can_update_price:
                            try:
                                ikas_id = product.get("ikas_id") or product.get("ikas_product_id")
                                if ikas_id:
                                    applied = await _apply_price_to_ikas(
                                        loop, ikas_graphql, db, slug, ikas_id,
                                        result["new_price"], product.get("our_price", 0),
                                        IKAS_PRICE_LISTS
                                    )
                                    if applied:
                                        log_entry["applied"] = True
                                        log_entry["applied_at"] = datetime.now(timezone.utc).isoformat()
                                        await db.products.update_one({"slug": slug}, {"$set": {"our_price": result["new_price"]}})
                                        auto_updated += 1
                            except Exception as e:
                                logger.error(f"CRON auto-update error for {slug}: {e}")
                                log_entry["apply_error"] = str(e)
                        elif should_auto and not can_update_price:
                            log_entry["apply_error"] = "Dip fiyat girilmemiş ve alış fiyatı+kar oranı hesaplanamıyor — güncelleme atlandı"
                            logger.warning(f"CRON: {slug} icin effective floor yok, guncelleme atlanıyor")

                        await db.price_changes.insert_one(log_entry)
                    elif result.get("action") == "floor_hit":
                        # Dip fiyata çarptı — loglayalım
                        await db.price_changes.insert_one({
                            "product_slug": slug,
                            "product_name": product.get("name", ""),
                            "action": "floor_hit",
                            "old_price": product.get("our_price"),
                            "new_price": None,
                            "cheapest_competitor": result.get("cheapest_competitor"),
                            "cheapest_price": result.get("cheapest_price"),
                            "floor_price": effective_floor,
                            "reason": result.get("reason", ""),
                            "applied": False,
                            "changed_at": datetime.now(timezone.utc).isoformat(),
                        })

                    success += 1
                else:
                    failed += 1

                scanned += 1
                await asyncio.sleep(0.5)
            except Exception as e:
                logger.error(f"CRON scan error for {slug}: {e}")
                failed += 1
                scanned += 1

        await db.system_status.update_one(
            {"task": "competitor_scan"},
            {"$set": {
                "running": False, "stop_requested": False,
                "scanned": scanned, "success": success, "failed": failed,
                "auto_updated": auto_updated,
                "current_product": "",
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }},
        )
        await db.system_status.update_one(
            {"task": "scheduled_competitor_scan"},
            {"$set": {"last_run": datetime.now(timezone.utc).isoformat(), "scanned": scanned, "success": success, "failed": failed, "auto_updated": auto_updated}},
            upsert=True,
        )
        logger.info(f"CRON: Rakip tarama tamamlandi. {scanned} urun, {success} basarili, {failed} basarisiz, {auto_updated} ikas guncellendi")
    except Exception as e:
        logger.error(f"CRON: Rakip tarama hatasi: {e}")
        await db.system_status.update_one(
            {"task": "competitor_scan"},
            {"$set": {"running": False, "error": str(e)}},
        )


async def _apply_price_to_ikas(loop, ikas_graphql, db, slug, ikas_id, new_price_tl, current_tl_price, price_lists):
    """Helper: update a product's price in İkas original currency list."""
    gql = f'''{{ listProduct(id: {{eq: "{ikas_id}"}}) {{ data {{
        categories {{ categoryId }}
        brand {{ brandId }}
        variants {{ id prices {{ sellPrice discountPrice currency priceListId }} }}
    }} }} }}'''
    result = await loop.run_in_executor(None, ikas_graphql, gql, None)
    pdata = (result.get("listProduct", {}).get("data", []) or [{}])[0]
    variants = pdata.get("variants", [])
    if not variants:
        return False

    variant = variants[0]
    existing_prices = variant.get("prices", [])

    # Find target price list (EUR > USD > TRY, skip Nihai)
    target_plid = target_currency = original_sell = None
    for p in existing_prices:
        plid = p.get("priceListId", "")
        if plid.startswith("b8f60257"):
            continue
        if plid == price_lists.get("EUR"):
            target_plid, target_currency, original_sell = plid, "EUR", p.get("sellPrice", 0)
            break
        elif plid == price_lists.get("USD"):
            target_plid, target_currency, original_sell = plid, "USD", p.get("sellPrice", 0)
        elif plid == price_lists.get("TRY") and not target_plid:
            target_plid, target_currency, original_sell = plid, "TRY", p.get("sellPrice", 0)

    if not target_plid:
        return False

    # Convert to original currency
    if target_currency == "TRY":
        new_price = new_price_tl
    else:
        if current_tl_price and original_sell and current_tl_price > 0:
            new_price = round(new_price_tl * (original_sell / current_tl_price), 2)
        else:
            return False

    # Build updated prices
    updated_prices = []
    for p in existing_prices:
        entry = {"priceListId": p["priceListId"], "sellPrice": p.get("sellPrice", 0), "currency": p.get("currency", "TRY")}
        if p.get("discountPrice"):
            entry["discountPrice"] = p["discountPrice"]
        if p["priceListId"] == target_plid:
            entry["sellPrice"] = new_price
        updated_prices.append(entry)

    # Preserve categories & brand
    existing_cats = [c["categoryId"] for c in (pdata.get("categories") or [])]
    existing_brand = (pdata.get("brand") or {}).get("brandId")
    update_input = {"id": ikas_id, "variants": [{"id": variant["id"], "prices": updated_prices}]}
    if existing_cats:
        update_input["categoryIds"] = existing_cats
    if existing_brand:
        update_input["brandId"] = existing_brand

    mutation = "mutation UpdateProduct($input: UpdateProductInput!) { updateProduct(input: $input) { id } }"
    await loop.run_in_executor(None, ikas_graphql, mutation, {"input": update_input})
    return True
