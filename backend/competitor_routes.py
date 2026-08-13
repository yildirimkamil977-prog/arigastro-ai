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
        
        # Auto-scrape prices after matching
        if saved > 0:
            all_matches = await db.competitor_matches.find({"product_slug": slug}).to_list(10)
            match_dict = {m["competitor_key"]: m for m in all_matches}
            prices = await loop.run_in_executor(None, scrape_all_competitor_prices, match_dict)
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

            # Merge cheapest competitor data from both systems (new 4-site + old Akakçe)
            if not p.get("cheapest_competitor_price") and p.get("cheapest_price"):
                p["cheapest_competitor_price"] = p["cheapest_price"]
                p["cheapest_competitor_name"] = p.get("cheapest_competitor", "Akakçe")
        
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

                        # Calculate optimal price
                        floor_price = product.get("floor_price")
                        purchase_price = product.get("purchase_price")

                        # Dynamic floor: if no manual floor, use purchase_price + category margin
                        if not floor_price and purchase_price:
                            cp = product.get("category_path", "")
                            top_cat = ""
                            if cp:
                                first_seg = cp.split(",")[0].strip()
                                if first_seg != "Tüm Ürünler":
                                    top_cat = first_seg.split(">")[0].strip()
                            if top_cat:
                                rule = await db.pricing_rules.find_one({"category_name": top_cat})
                                if rule and rule.get("profit_margin_pct"):
                                    floor_price = purchase_price * (1 + rule["profit_margin_pct"] / 100)

                        # Get undercut amount from category rule
                        undercut = 100  # default
                        cp = product.get("category_path", "")
                        if cp:
                            top_cat = cp.split(",")[0].strip().split(">")[0].strip()
                            rule = await db.pricing_rules.find_one({"category_name": top_cat})
                            if rule:
                                undercut = rule.get("undercut_amount", 100)

                        result = calc_fn(prices, product.get("our_price", 0), floor_price or 0, undercut)

                        # Update product
                        update = {
                            "competitor_prices": prices,
                            "cheapest_competitor_price": cheapest["price"],
                            "cheapest_competitor_name": cheapest["competitor_name"],
                            "competitor_prices_checked_at": datetime.now(timezone.utc).isoformat(),
                            "price_recommendation": result,
                        }
                        await db.products.update_one({"slug": slug}, {"$set": update})

                        # Log the price change recommendation
                        if result.get("action") == "update":
                            await db.price_changes.insert_one({
                                "product_slug": slug,
                                "product_name": product.get("name", ""),
                                "action": result["action"],
                                "old_price": result.get("old_price"),
                                "new_price": result.get("new_price"),
                                "cheapest_competitor": result.get("cheapest_competitor"),
                                "cheapest_price": result.get("cheapest_price"),
                                "floor_price": floor_price,
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

        return {
            "total_products": total_products,
            "matched_products": matched_products,
            "cheaper_count": cheaper_count,
            "recommend_count": recommend_count,
            "scan_status": scan_status,
            "recent_changes": recent_changes,
            "category_rules": rules,
        }

    return router
