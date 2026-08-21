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
    from tcmb_exchange import get_exchange_rates, convert_to_tl, convert_from_tl, get_rate, force_refresh_rates
    
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
        
        asyncio.create_task(_run_single_product_match(db, slug, product["name"], product.get("brand", ""), product.get("gtin", ""), product.get("sku", ""), task_key, COMPETITORS, match_all_competitors_for_product, scrape_all_competitor_prices))
        return {"success": True, "task_key": task_key, "message": f"Eşleştirme başlatıldı: {product['name'][:50]}"}
    
    async def _run_single_product_match(db, slug, product_name, brand, gtin, sku, task_key, competitors, match_fn, scrape_fn):
        loop = asyncio.get_event_loop()
        try:
            # Get existing manual matches to protect them
            existing_matches = await db.competitor_matches.find(
                {"product_slug": slug},
                {"_id": 0, "competitor_key": 1, "manual": 1}
            ).to_list(10)
            manual_keys = {m["competitor_key"] for m in existing_matches if m.get("manual")}
            
            results = await loop.run_in_executor(None, match_fn, product_name, brand, gtin, sku)
            
            saved = 0
            for comp_key, result in results.items():
                # NEVER overwrite manual matches
                if comp_key in manual_keys:
                    continue
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
            {"$or": [
                {"ikas_categories.name": category_name},
                {"category_path": {"$regex": category_name, "$options": "i"}},
            ], "inactive": {"$ne": True}},
            {"slug": 1, "name": 1, "brand": 1, "gtin": 1, "sku": 1}
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
                
                # Get existing manual matches to protect them
                existing_matches = await db.competitor_matches.find(
                    {"product_slug": prod["slug"]},
                    {"_id": 0, "competitor_key": 1, "manual": 1}
                ).to_list(10)
                manual_keys = {m["competitor_key"] for m in existing_matches if m.get("manual")}
                
                results = await loop.run_in_executor(None, match_all_competitors_for_product, prod["name"], prod.get("brand", ""), prod.get("gtin", ""), prod.get("sku", ""))
                prod_found = False
                for comp_key, result in results.items():
                    # NEVER overwrite manual matches
                    if comp_key in manual_keys:
                        continue
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
    
    # --- Product floor price ---
    class PriceSettingsRequest(BaseModel):
        floor_price: Optional[float] = None
        clear_floor: bool = False
    
    @router.put("/price-settings/{slug}")
    async def update_price_settings(slug: str, req: PriceSettingsRequest, user: dict = Depends(get_current_user)):
        if req.clear_floor:
            await db.products.update_one({"slug": slug}, {"$unset": {"floor_price": ""}})
            return {"success": True}
        update = {}
        if req.floor_price is not None:
            update["floor_price"] = req.floor_price
        if update:
            await db.products.update_one({"slug": slug}, {"$set": update})
        return {"success": True}
    
    # --- Category pricing rules ---
    class CategoryRuleRequest(BaseModel):
        category_name: str
        enabled: bool = True
        undercut_amount: float = 100
        auto_update_ikas: bool = False
    
    @router.post("/category-rules")
    async def set_category_rule(req: CategoryRuleRequest, user: dict = Depends(get_current_user)):
        await db.pricing_rules.update_one(
            {"category_name": req.category_name},
            {"$set": {
                "category_name": req.category_name,
                "enabled": req.enabled,
                "undercut_amount": req.undercut_amount,
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
    
    # --- Run full pricing cycle for a single category ---
    @router.post("/run-category-pricing/{category_name}")
    async def run_category_pricing(category_name: str, user: dict = Depends(get_current_user)):
        """Run full cycle for a category: refresh İkas prices → scrape competitors → auto-update."""
        task_key = f"category_pricing_{category_name}"
        status = await db.system_status.find_one({"task": task_key})
        if status and status.get("running"):
            return {"started": False, "message": "Bu kategori için işlem zaten devam ediyor."}

        # Get category rule
        rule = await db.pricing_rules.find_one({"category_name": category_name})
        if not rule:
            raise HTTPException(status_code=404, detail="Kategori kuralı bulunamadı")

        # Find products in this category
        products = await db.products.find(
            {"$or": [
                {"ikas_categories.name": category_name},
                {"category_path": {"$regex": category_name, "$options": "i"}},
            ], "inactive": {"$ne": True}},
            {"_id": 0, "slug": 1, "name": 1, "ikas_product_id": 1, "sku": 1, "brand": 1, "gtin": 1}
        ).to_list(5000)

        if not products:
            return {"started": False, "message": "Bu kategoride aktif ürün bulunamadı."}

        await db.system_status.update_one(
            {"task": task_key},
            {"$set": {
                "running": True, "category": category_name,
                "total": len(products), "phase": "ikas_refresh", "progress": 0,
                "ikas_refreshed": 0, "scanned": 0, "updated": 0, "skipped": 0,
                "started_at": datetime.now(timezone.utc).isoformat(),
            }},
            upsert=True
        )

        asyncio.create_task(_run_category_full_pricing(
            db, ikas_graphql, products, rule, category_name, task_key
        ))
        return {"started": True, "total": len(products), "task_key": task_key, "category": category_name}

    @router.get("/category-pricing-status/{task_key}")
    async def get_category_pricing_status(task_key: str, user: dict = Depends(get_current_user)):
        status = await db.system_status.find_one({"task": task_key}, {"_id": 0})
        return status or {"running": False}

    async def _run_category_full_pricing(db, ikas_fn, products, rule, category_name, task_key):
        """Background: Full pricing cycle for a category."""
        loop = asyncio.get_event_loop()
        undercut = rule.get("undercut_amount", 100)

        PRICE_LISTS_MAP = {
            "db850a77-bfd6-43de-8892-78d16dc01e0e": "EUR",
            "28b86f15-34b5-4c49-8d96-678194f4a8ba": "USD",
            "35b38ca5-9f2d-4482-a9d8-3a6b0df33efd": "TRY",
        }
        IKAS_PRICE_LISTS = {
            "EUR": "db850a77-bfd6-43de-8892-78d16dc01e0e",
            "USD": "28b86f15-34b5-4c49-8d96-678194f4a8ba",
            "TRY": "35b38ca5-9f2d-4482-a9d8-3a6b0df33efd",
        }
        NIHAI_PREFIX = "b8f60257"

        ikas_refreshed = 0
        scanned = 0
        updated_count = 0
        skipped = 0

        try:
            # Force refresh exchange rates before pricing
            force_refresh_rates()
            logger.info(f"Category pricing [{category_name}]: Kur verileri güncellendi")
            # ===== PHASE 1: Refresh İkas prices for each product =====
            await db.system_status.update_one({"task": task_key}, {"$set": {"phase": "ikas_refresh"}})
            logger.info(f"Category pricing [{category_name}]: Phase 1 — İkas fiyat güncelleme ({len(products)} ürün)")

            for i, prod in enumerate(products):
                slug = prod["slug"]
                ikas_id = prod.get("ikas_product_id")
                if not ikas_id:
                    continue
                try:
                    gql = f'{{ listProduct(id: {{eq: "{ikas_id}"}}) {{ data {{ variants {{ prices {{ sellPrice currency priceListId }} }} }} }} }}'
                    result = await loop.run_in_executor(None, ikas_fn, gql, None)
                    variants = (result.get("listProduct", {}).get("data", []) or [{}])[0].get("variants", [])
                    if variants:
                        prices = variants[0].get("prices", [])
                        base_currency = base_price = price_list_id = None
                        for p in prices:
                            plid = p.get("priceListId") or ""
                            if plid.startswith(NIHAI_PREFIX):
                                continue
                            sell = p.get("sellPrice", 0)
                            if not sell or sell <= 0:
                                continue
                            cur = PRICE_LISTS_MAP.get(plid, p.get("currency") or "TRY")
                            if cur == "EUR":
                                base_currency, base_price, price_list_id = "EUR", sell, plid
                                break
                            elif cur == "USD" and base_currency != "EUR":
                                base_currency, base_price, price_list_id = "USD", sell, plid
                            elif cur == "TRY" and not base_currency:
                                base_currency, base_price, price_list_id = "TRY", sell, plid
                        if base_currency and base_price:
                            uf = {
                                "base_currency": base_currency,
                                "base_price": base_price,
                                "price_list_id": price_list_id,
                            }
                            if base_currency != "TRY":
                                uf["our_price"] = convert_to_tl(base_price, base_currency)
                            await db.products.update_one({"slug": slug}, {"$set": uf})
                            ikas_refreshed += 1
                except Exception as e:
                    logger.error(f"İkas refresh error for {slug}: {e}")

                if (i + 1) % 10 == 0:
                    await db.system_status.update_one({"task": task_key}, {"$set": {"progress": i + 1, "ikas_refreshed": ikas_refreshed}})
                await asyncio.sleep(0.15)

            # ===== PHASE 2: Scrape competitor prices =====
            await db.system_status.update_one({"task": task_key}, {"$set": {"phase": "competitor_scan", "progress": 0}})
            logger.info(f"Category pricing [{category_name}]: Phase 2 — Rakip fiyat tarama")

            product_slugs = [p["slug"] for p in products]
            # Get products with competitor matches
            matched_slugs_cursor = db.competitor_matches.aggregate([
                {"$match": {"product_slug": {"$in": product_slugs}}},
                {"$group": {"_id": "$product_slug"}}
            ])
            matched_slugs = [doc["_id"] async for doc in matched_slugs_cursor]

            for i, slug in enumerate(matched_slugs):
                try:
                    product = await db.products.find_one({"slug": slug})
                    if not product:
                        continue

                    matches = await db.competitor_matches.find({"product_slug": slug}).to_list(10)
                    match_dict = {m["competitor_key"]: m for m in matches}

                    # Scrape prices
                    prices = await loop.run_in_executor(None, scrape_all_competitor_prices, match_dict)

                    if prices:
                        await db.price_history.insert_one({
                            "product_slug": slug,
                            "prices": prices,
                            "checked_at": datetime.now(timezone.utc).isoformat(),
                        })
                        cheapest = min(prices.values(), key=lambda x: x["price"])

                        floor_price = product.get("floor_price")
                        base_currency = product.get("base_currency", "TRY")

                        result = calculate_optimal_price(
                            prices, product.get("our_price", 0),
                            floor_price or 0, base_currency, undercut,
                        )

                        update_fields = {
                            "competitor_prices": prices,
                            "cheapest_competitor_price": cheapest["price"],
                            "cheapest_competitor_name": cheapest["competitor_name"],
                            "competitor_prices_checked_at": datetime.now(timezone.utc).isoformat(),
                            "price_recommendation": result,
                        }
                        await db.products.update_one({"slug": slug}, {"$set": update_fields})

                        # ===== PHASE 3 (inline): Auto-update İkas =====
                        if result.get("action") == "update" and floor_price and floor_price > 0:
                            ikas_id = product.get("ikas_id") or product.get("ikas_product_id")
                            new_tl = result["new_price_tl"]

                            # 23-hour protection: skip if already updated recently
                            last_update = product.get("price_updated_at")
                            if last_update:
                                try:
                                    last_dt = datetime.fromisoformat(last_update.replace("Z", "+00:00")) if isinstance(last_update, str) else last_update
                                    hours_since = (datetime.now(timezone.utc) - last_dt).total_seconds() / 3600
                                    if hours_since < 23:
                                        skipped += 1
                                        scanned += 1
                                        continue
                                except Exception:
                                    pass

                            log_entry = {
                                "product_slug": slug,
                                "product_name": product.get("name", ""),
                                "action": "update",
                                "old_price_tl": result.get("old_price_tl"),
                                "new_price_tl": new_tl,
                                "new_price_base": result.get("new_price_base"),
                                "base_currency": base_currency,
                                "cheapest_competitor": result.get("cheapest_competitor"),
                                "cheapest_price": result.get("cheapest_price"),
                                "floor_price": floor_price,
                                "reason": result.get("reason", ""),
                                "applied": False,
                                "auto_update": True,
                                "triggered_by": "manual_category",
                                "changed_at": datetime.now(timezone.utc).isoformat(),
                            }

                            if ikas_id:
                                try:
                                    applied_ok = await _apply_price_to_ikas_inline(
                                        loop, ikas_fn, ikas_id, new_tl,
                                        floor_price, base_currency, IKAS_PRICE_LISTS
                                    )
                                    if applied_ok:
                                        log_entry["applied"] = True
                                        log_entry["applied_at"] = datetime.now(timezone.utc).isoformat()
                                        new_base = convert_from_tl(new_tl, base_currency)
                                        await db.products.update_one({"slug": slug}, {"$set": {
                                            "our_price": new_tl, "base_price": new_base,
                                            "price_updated_at": datetime.now(timezone.utc).isoformat(),
                                        }})
                                        updated_count += 1
                                except Exception as e:
                                    logger.error(f"İkas update error for {slug}: {e}")
                                    log_entry["apply_error"] = str(e)
                            else:
                                log_entry["apply_error"] = "İkas ID bulunamadı"

                            await db.price_changes.insert_one(log_entry)

                        elif result.get("action") == "floor_hit":
                            await db.price_changes.insert_one({
                                "product_slug": slug,
                                "product_name": product.get("name", ""),
                                "action": "floor_hit",
                                "old_price_tl": product.get("our_price"),
                                "base_currency": base_currency,
                                "cheapest_competitor": result.get("cheapest_competitor"),
                                "cheapest_price": result.get("cheapest_price"),
                                "floor_price": floor_price,
                                "reason": result.get("reason", ""),
                                "applied": False,
                                "triggered_by": "manual_category",
                                "changed_at": datetime.now(timezone.utc).isoformat(),
                            })
                            skipped += 1
                        elif result.get("action") == "no_change":
                            pass
                        else:
                            if not floor_price:
                                skipped += 1

                    scanned += 1
                except Exception as e:
                    logger.error(f"Category pricing scan error for {slug}: {e}")
                    scanned += 1

                if (i + 1) % 5 == 0:
                    await db.system_status.update_one({"task": task_key}, {"$set": {
                        "progress": i + 1, "scanned": scanned, "updated": updated_count, "skipped": skipped,
                    }})
                await asyncio.sleep(0.3)

            await db.system_status.update_one({"task": task_key}, {"$set": {
                "running": False, "phase": "done",
                "ikas_refreshed": ikas_refreshed, "scanned": scanned,
                "updated": updated_count, "skipped": skipped,
                "matched_total": len(matched_slugs),
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }})
            logger.info(f"Category pricing [{category_name}] done: {ikas_refreshed} ikas, {scanned} scanned, {updated_count} updated, {skipped} skipped")

        except Exception as e:
            logger.error(f"Category pricing [{category_name}] error: {e}")
            await db.system_status.update_one({"task": task_key}, {"$set": {"running": False, "error": str(e)}})

    async def _apply_price_to_ikas_inline(loop, ikas_fn, ikas_id, new_price_tl, floor_price, base_currency, price_lists):
        """Apply price to İkas — updates BOTH price list AND variant sellPrice."""
        gql = f'''{{ listProduct(id: {{eq: "{ikas_id}"}}) {{ data {{
            variants {{ id prices {{ sellPrice currency priceListId }} }}
        }} }} }}'''
        result = await loop.run_in_executor(None, ikas_fn, gql, None)
        pdata = (result.get("listProduct", {}).get("data", []) or [{}])[0]
        variants = pdata.get("variants", [])
        if not variants:
            return False
        variant = variants[0]
        existing_prices = variant.get("prices", [])

        target_plid = target_currency = None
        for p in existing_prices:
            plid = p.get("priceListId") or ""
            if plid.startswith("b8f60257"):
                continue
            if plid == price_lists.get("EUR"):
                target_plid, target_currency = plid, "EUR"
                break
            elif plid == price_lists.get("USD"):
                target_plid, target_currency = plid, "USD"
            elif plid == price_lists.get("TRY") and not target_plid:
                target_plid, target_currency = plid, "TRY"
        if not target_plid:
            return False

        new_price = convert_from_tl(new_price_tl, target_currency)
        if floor_price and new_price < floor_price:
            return False

        # 1. Update price list (EUR/USD/TL)
        mutation1 = """mutation UpdateVariantPrices($input: UpdateVariantPricesInput!) {
            updateVariantPrices(input: $input) { __typename }
        }"""
        variables1 = {"input": {
            "priceListId": target_plid,
            "variantPriceInputs": [{
                "productId": ikas_id,
                "variantId": variant["id"],
                "price": {"sellPrice": new_price}
            }]
        }}
        await loop.run_in_executor(None, ikas_fn, mutation1, variables1)

        return True
    
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
    
    # --- TCMB Exchange Rates ---
    @router.get("/exchange-rates")
    async def get_tcmb_rates(user: dict = Depends(get_current_user)):
        """Get current TCMB exchange rates."""
        rates = get_exchange_rates()
        return {"rates": rates, "source": "CurrencyAPI"}

    # --- İkas Currency Sync: fetch original prices for products ---
    @router.post("/sync-ikas-currencies")
    async def sync_ikas_currencies(user: dict = Depends(get_current_user)):
        """Fetch original currency prices from İkas for all products (bulk paginated fetch)."""
        task_key = "sync_ikas_currencies"
        status = await db.system_status.find_one({"task": task_key})
        if status and status.get("running"):
            return {"started": False, "message": "Kur senkronizasyonu zaten devam ediyor."}

        total = await db.products.count_documents({"inactive": {"$ne": True}})
        
        await db.system_status.update_one(
            {"task": task_key},
            {"$set": {"running": True, "total": total, "progress": 0, "updated": 0, "started_at": datetime.now(timezone.utc).isoformat()}},
            upsert=True
        )
        asyncio.create_task(_run_ikas_currency_sync_bulk(db, ikas_graphql, task_key))
        return {"started": True, "total": total}

    async def _run_ikas_currency_sync_bulk(db, ikas_fn, task_key):
        """Background: Bulk fetch ALL İkas products with prices+SKU, match to local, add new products."""
        loop = asyncio.get_event_loop()
        updated = 0
        force_refresh_rates()
        logger.info("İkas currency sync: TCMB rates refreshed")

        PRICE_LISTS = {
            "db850a77-bfd6-43de-8892-78d16dc01e0e": "EUR",
            "28b86f15-34b5-4c49-8d96-678194f4a8ba": "USD",
            "35b38ca5-9f2d-4482-a9d8-3a6b0df33efd": "TRY",
        }
        NIHAI_PREFIX = "b8f60257"

        try:
            import re
            def normalize_name(name):
                if not name: return ""
                n = name.lower().strip()
                n = re.sub(r'[^a-z0-9çğıöşü\s]', ' ', n)
                return ' '.join(n.split())

            ikas_page = 1
            ikas_products_map = {}
            ikas_products_by_id = {}
            total_fetched = 0
            logger.info("İkas currency sync: fetching all products...")

            while True:
                query = """query ListProducts($pagination: PaginationInput) {
                    listProduct(pagination: $pagination) {
                        data { id name categories { id name } brand { name } variants { id sku prices { sellPrice currency priceListId } } }
                        count
                    }
                }"""
                try:
                    result = await loop.run_in_executor(None, ikas_fn, query, {"pagination": {"page": ikas_page, "limit": 100}})
                except Exception as e:
                    logger.error(f"İkas fetch page {ikas_page} error: {e}")
                    break
                products_data = result.get("listProduct", {}).get("data", [])
                if not products_data: break

                for ip in products_data:
                    ikas_id = ip.get("id", "")
                    name = ip.get("name", "")
                    variants = ip.get("variants", [])
                    if not ikas_id or not name: continue
                    sku = variants[0].get("sku") or "" if variants else ""
                    prices = variants[0].get("prices", []) if variants else []
                    base_currency = base_price = price_list_id = None
                    for p in prices:
                        plid = p.get("priceListId") or ""
                        if plid.startswith(NIHAI_PREFIX): continue
                        sell = p.get("sellPrice", 0)
                        if not sell or sell <= 0: continue
                        cur = PRICE_LISTS.get(plid, p.get("currency") or "TRY")
                        if cur == "EUR":
                            base_currency, base_price, price_list_id = "EUR", sell, plid; break
                        elif cur == "USD" and base_currency != "EUR":
                            base_currency, base_price, price_list_id = "USD", sell, plid
                        elif cur == "TRY" and not base_currency:
                            base_currency, base_price, price_list_id = "TRY", sell, plid
                    # Extract categories and brand from Ikas
                    ikas_categories = [{"id": c.get("id",""), "name": c.get("name","")} for c in ip.get("categories", []) if c.get("name")]
                    ikas_brand = (ip.get("brand") or {}).get("name", "")
                    info = {"ikas_id": ikas_id, "ikas_name": name, "sku": sku, "base_currency": base_currency, "base_price": base_price, "price_list_id": price_list_id, "ikas_categories": ikas_categories, "ikas_brand": ikas_brand}
                    ikas_products_map[normalize_name(name)] = info
                    ikas_products_by_id[ikas_id] = info
                    total_fetched += 1

                await db.system_status.update_one({"task": task_key}, {"$set": {"phase": "fetching", "ikas_fetched": total_fetched}})
                ikas_page += 1
                await asyncio.sleep(0.2)

            logger.info(f"İkas sync: fetched {total_fetched} products")
            await db.system_status.update_one({"task": task_key}, {"$set": {"phase": "matching", "ikas_total": len(ikas_products_map)}})

            local_products = await db.products.find({}, {"_id": 0, "slug": 1, "name": 1, "our_price": 1, "ikas_product_id": 1}).to_list(10000)
            local_by_ikas_id = {p["ikas_product_id"]: p for p in local_products if p.get("ikas_product_id")}
            local_slugs = {p["slug"] for p in local_products}
            matched_ikas_ids = set()  # Track which İkas IDs have been claimed
            progress = 0
            new_products_added = 0

            # First pass: match by existing ikas_product_id (exact, no duplicates)
            for lp in local_products:
                ikas_id = lp.get("ikas_product_id")
                if ikas_id and ikas_id in ikas_products_by_id:
                    matched_ikas_ids.add(ikas_id)

            for lp in local_products:
                slug = lp["slug"]
                ikas_id = lp.get("ikas_product_id")
                match = ikas_products_by_id.get(ikas_id) if ikas_id else None
                if not match:
                    norm_name = normalize_name(lp.get("name", ""))
                    match = ikas_products_map.get(norm_name)
                    # Only accept if this İkas ID isn't already claimed by another product
                    if match and match["ikas_id"] in matched_ikas_ids:
                        match = None
                    if not match and norm_name:
                        words = norm_name.split()
                        for length in range(len(words), max(2, len(words) - 3), -1):
                            prefix = ' '.join(words[:length])
                            for ik_name, ik_data in ikas_products_map.items():
                                if ik_data["ikas_id"] not in matched_ikas_ids and (ik_name.startswith(prefix) or prefix in ik_name):
                                    match = ik_data; break
                            if match: break
                if match:
                    matched_ikas_ids.add(match["ikas_id"])
                    uf = {"ikas_product_id": match["ikas_id"], "sku": match.get("sku", ""), "inactive": False, "feed_active": True}
                    if match.get("ikas_categories"):
                        uf["ikas_categories"] = match["ikas_categories"]
                    if match.get("ikas_brand"):
                        uf["ikas_brand"] = match["ikas_brand"]
                    if match.get("base_currency") and match.get("base_price"):
                        uf["base_currency"] = match["base_currency"]
                        uf["base_price"] = match["base_price"]
                        uf["price_list_id"] = match["price_list_id"]
                        if match["base_currency"] != "TRY":
                            uf["our_price"] = convert_to_tl(match["base_price"], match["base_currency"])
                    await db.products.update_one({"slug": slug}, {"$set": uf})
                    updated += 1
                progress += 1
                if progress % 100 == 0:
                    await db.system_status.update_one({"task": task_key}, {"$set": {"progress": progress, "updated": updated}})

            # Add NEW İkas products not in local DB
            for ikas_id, info in ikas_products_by_id.items():
                if ikas_id in matched_ikas_ids: continue
                name = info["ikas_name"]
                slug_candidate = re.sub(r'[^a-z0-9]', '-', name.lower().strip())
                slug_candidate = re.sub(r'-+', '-', slug_candidate).strip('-')
                if slug_candidate in local_slugs:
                    slug_candidate = f"{slug_candidate}-{ikas_id[:8]}"
                new_doc = {
                    "slug": slug_candidate, "name": name, "ikas_product_id": ikas_id,
                    "sku": info.get("sku", ""),
                    "ikas_categories": info.get("ikas_categories", []),
                    "ikas_brand": info.get("ikas_brand", ""),
                    "base_currency": info.get("base_currency"), "base_price": info.get("base_price"),
                    "price_list_id": info.get("price_list_id"),
                    "our_price": convert_to_tl(info["base_price"], info["base_currency"]) if info.get("base_price") and info.get("base_currency") and info["base_currency"] != "TRY" else info.get("base_price"),
                    "feed_active": True, "created_at": datetime.now(timezone.utc).isoformat(),
                }
                try:
                    await db.products.insert_one(new_doc); local_slugs.add(slug_candidate); new_products_added += 1
                except Exception: pass

            # Mark products NOT in İkas as inactive
            active_ikas_ids = set(ikas_products_by_id.keys())
            for lp in local_products:
                lid = lp.get("ikas_product_id")
                if lid and lid not in active_ikas_ids:
                    await db.products.update_one({"slug": lp["slug"]}, {"$set": {"inactive": True, "feed_active": False}})

            # Also sync Ikas category tree to local DB
            try:
                cat_result = await loop.run_in_executor(None, ikas_fn, "{ listCategory { id name parentId } }", None)
                ikas_cats = cat_result.get("listCategory", [])
                if ikas_cats:
                    await db.ikas_categories.delete_many({})
                    await db.ikas_categories.insert_many([
                        {"cat_id": c["id"], "name": c["name"], "parentId": c.get("parentId"), "synced_at": datetime.now(timezone.utc).isoformat()}
                        for c in ikas_cats
                    ])
                    logger.info(f"İkas category sync: {len(ikas_cats)} categories synced")
            except Exception as e:
                logger.error(f"İkas category sync error: {e}")

            await db.system_status.update_one({"task": task_key}, {"$set": {
                "running": False, "phase": "done", "progress": progress, "updated": updated,
                "new_products": new_products_added, "ikas_total": len(ikas_products_map),
                "completed_at": datetime.now(timezone.utc).isoformat()
            }})
            logger.info(f"İkas sync done: {updated} matched, {new_products_added} new, {total_fetched} İkas total")
        except Exception as e:
            logger.error(f"İkas currency sync error: {e}")
            await db.system_status.update_one({"task": task_key}, {"$set": {"running": False, "error": str(e), "completed_at": datetime.now(timezone.utc).isoformat()}})


    @router.get("/sync-ikas-currencies-status")
    async def get_currency_sync_status(user: dict = Depends(get_current_user)):
        status = await db.system_status.find_one({"task": "sync_ikas_currencies"}, {"_id": 0})
        return status or {"running": False}

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
            query["$or"] = [
                {"name": {"$regex": search, "$options": "i"}},
                {"sku": {"$regex": search, "$options": "i"}},
            ]
        if category:
            if "$and" not in query:
                query["$and"] = []
            query["$and"].append({"$or": [
                {"ikas_categories.name": category},
                {"category_path": {"$regex": category, "$options": "i"}},
            ]})
        if brand:
            if "$and" not in query:
                query["$and"] = []
            query["$and"].append({"$or": [
                {"ikas_brand": {"$regex": f"^{brand}$", "$options": "i"}},
                {"brand": {"$regex": f"^{brand}$", "$options": "i"}},
            ]})
        
        skip = (page - 1) * limit

        # Get slugs that have competitor matches (ONLY new 4-site system)
        matched_slugs_list = await db.competitor_matches.distinct("product_slug")
        matched_slugs_set = set(matched_slugs_list)

        # Apply match_status filter at query level
        if match_status == "matched":
            query["slug"] = {"$in": matched_slugs_list}
        elif match_status == "unmatched":
            query["slug"] = {"$nin": matched_slugs_list}

        total = await db.products.count_documents(query)

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
            # Add converted competitor prices in product's base currency
            base_cur = p.get("base_currency", "TRY")
            if base_cur and base_cur != "TRY" and p.get("cheapest_competitor_price"):
                p["cheapest_price_in_base"] = convert_from_tl(p["cheapest_competitor_price"], base_cur)
            comp_prices = p.get("competitor_prices", {})
            if comp_prices and base_cur and base_cur != "TRY":
                converted = {}
                for ck, cv in comp_prices.items():
                    if isinstance(cv, dict) and cv.get("price"):
                        converted[ck] = convert_from_tl(cv["price"], base_cur)
                p["competitor_prices_in_base"] = converted
            # Use ikas_categories for category display (fallback to category_path)
            ikas_cats = p.get("ikas_categories", [])
            if ikas_cats:
                cat_names = [c["name"] for c in ikas_cats if c.get("name") and c["name"] != "Tüm Ürünler"]
                p["category"] = cat_names[0] if cat_names else ""
                p["subcategory"] = cat_names[1] if len(cat_names) > 1 else ""
            else:
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

            # Use ikas_brand for brand display (fallback to brand)
            if p.get("ikas_brand"):
                p["brand"] = p["ikas_brand"]
        
        # Get unique categories and brands from ikas data (with fallback to old fields)
        ikas_cat_names = set()
        ikas_brand_names = set()
        async for doc in db.products.find({"inactive": {"$ne": True}}, {"ikas_categories": 1, "ikas_brand": 1, "category_path": 1, "brand": 1}):
            for c in doc.get("ikas_categories", []):
                if c.get("name") and c["name"] != "Tüm Ürünler":
                    ikas_cat_names.add(c["name"])
            if doc.get("ikas_brand"):
                ikas_brand_names.add(doc["ikas_brand"])
            # Fallback for products without ikas data
            if not doc.get("ikas_categories"):
                cp = doc.get("category_path", "")
                if cp:
                    for seg in cp.split(","):
                        for part in seg.strip().split(">"):
                            part = part.strip()
                            if part and part != "Tüm Ürünler":
                                ikas_cat_names.add(part)
            if not doc.get("ikas_brand") and doc.get("brand"):
                ikas_brand_names.add(doc["brand"])

        top_categories = sorted(ikas_cat_names)
        sub_categories = []  # Flat list from ikas, no sub needed
        brands = sorted(ikas_brand_names)
        
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
            rates = get_exchange_rates()
            for v in variants[:1]:
                for p in (v.get("prices") or []):
                    if p.get("sellPrice") and p.get("sellPrice") > 0:
                        currency = p.get("currency", "TRY")
                        sell = p["sellPrice"]
                        tl_equivalent = convert_to_tl(sell, currency)
                        prices.append({
                            "sell_price": sell,
                            "discount_price": p.get("discountPrice"),
                            "currency": currency,
                            "price_list_id": p.get("priceListId", ""),
                            "tl_equivalent": tl_equivalent,
                        })
            return {"prices": prices, "rates": {"EUR": rates.get("EUR", 0), "USD": rates.get("USD", 0)}}
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
            slugs_cursor = db.competitor_matches.aggregate([
                {"$group": {"_id": "$product_slug"}}
            ])
            slugs = [doc["_id"] async for doc in slugs_cursor]

            scanned = 0
            success = 0
            failed = 0

            for slug in slugs:
                try:
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

                    matches = await db.competitor_matches.find({"product_slug": slug}).to_list(10)
                    match_dict = {m["competitor_key"]: m for m in matches}
                    prices = await loop.run_in_executor(None, scrape_fn, match_dict)

                    if prices:
                        await db.price_history.insert_one({
                            "product_slug": slug,
                            "prices": prices,
                            "checked_at": datetime.now(timezone.utc).isoformat(),
                        })

                        cheapest = min(prices.values(), key=lambda x: x["price"])

                        # Floor price is in the product's base currency
                        floor_price = product.get("floor_price")
                        base_currency = product.get("base_currency", "TRY")

                        # Get undercut amount from category rule
                        undercut = 100
                        product_cats = set()
                        ikas_cats = product.get("ikas_categories", [])
                        for c in ikas_cats:
                            if c.get("name") and c["name"] != "Tüm Ürünler":
                                product_cats.add(c["name"])
                        if not product_cats:
                            cp = product.get("category_path", "")
                            if cp:
                                for seg in cp.split(","):
                                    for part in seg.strip().split(">"):
                                        part = part.strip()
                                        if part and part != "Tüm Ürünler":
                                            product_cats.add(part)
                        for cat in product_cats:
                            rule = await db.pricing_rules.find_one({"category_name": cat})
                            if rule:
                                undercut = rule.get("undercut_amount", 100)
                                break

                        result = calc_fn(
                            prices,
                            product.get("our_price", 0),
                            floor_price or 0,
                            base_currency,
                            undercut,
                        )

                        update = {
                            "competitor_prices": prices,
                            "cheapest_competitor_price": cheapest["price"],
                            "cheapest_competitor_name": cheapest["competitor_name"],
                            "competitor_prices_checked_at": datetime.now(timezone.utc).isoformat(),
                            "price_recommendation": result,
                        }
                        await db.products.update_one({"slug": slug}, {"$set": update})

                        if result.get("action") in ("update", "floor_hit"):
                            await db.price_changes.insert_one({
                                "product_slug": slug,
                                "product_name": product.get("name", ""),
                                "action": result["action"],
                                "old_price_tl": result.get("old_price_tl", product.get("our_price")),
                                "new_price_tl": result.get("new_price_tl"),
                                "new_price_base": result.get("new_price_base"),
                                "base_currency": base_currency,
                                "cheapest_competitor": result.get("cheapest_competitor"),
                                "cheapest_price": result.get("cheapest_price"),
                                "floor_price": floor_price,
                                "reason": result.get("reason", ""),
                                "applied": False,
                                "can_update": floor_price is not None and floor_price > 0,
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

        # SAFETY CHECK: floor price must exist
        floor_price = product.get("floor_price")
        if not floor_price:
            return {"success": False, "error": "Bu ürünün dip fiyatı girilmemiş. Fiyat güncellenmeden önce dip fiyat girilmesi zorunludur."}

        ikas_id = product.get("ikas_id") or product.get("ikas_product_id")
        if not ikas_id:
            return {"success": False, "error": "Bu üründe İkas ID bulunamadı."}

        try:
            loop = asyncio.get_event_loop()
            base_currency = product.get("base_currency", "TRY")

            # Step 1: Fetch current İkas prices and variant info
            gql_query = f'''{{ listProduct(id: {{eq: "{ikas_id}"}}) {{ data {{
                name
                variants {{ id prices {{ sellPrice currency priceListId }} }}
            }} }} }}'''
            result = await loop.run_in_executor(None, ikas_graphql, gql_query, None)
            product_data = (result.get("listProduct", {}).get("data", []) or [{}])[0]
            variants = product_data.get("variants", [])
            if not variants:
                return {"success": False, "error": "İkas'ta varyant bulunamadı"}

            variant = variants[0]
            existing_prices = variant.get("prices", [])

            # Step 2: Determine target price list
            target_price_list = None
            target_currency = None

            for p in existing_prices:
                plid = p.get("priceListId") or ""
                if plid.startswith("b8f60257"):
                    continue
                if plid == IKAS_PRICE_LISTS.get("EUR"):
                    target_price_list = plid
                    target_currency = "EUR"
                    break
                elif plid == IKAS_PRICE_LISTS.get("USD"):
                    target_price_list = plid
                    target_currency = "USD"
                elif plid == IKAS_PRICE_LISTS.get("TRY") and not target_price_list:
                    target_price_list = plid
                    target_currency = "TRY"

            if not target_price_list:
                return {"success": False, "error": "Güncellenecek fiyat listesi bulunamadı"}

            # Step 3: Convert TL price to original currency using TCMB
            new_price = convert_from_tl(req.new_price_tl, target_currency)

            # Step 4: Safety check — new price must not be below floor
            if new_price < floor_price:
                return {"success": False, "error": f"Yeni fiyat ({new_price:.2f} {target_currency}) dip fiyatın ({floor_price:.2f} {target_currency}) altında."}

            # Step 5: Use saveVariantPrices — SAFE, no category/brand risk
            mutation = """mutation UpdateVariantPrices($input: UpdateVariantPricesInput!) {
                updateVariantPrices(input: $input) { __typename }
            }"""
            variables = {"input": {
                "priceListId": target_price_list,
                "variantPriceInputs": [{
                    "productId": ikas_id,
                    "variantId": variant["id"],
                    "price": {"sellPrice": new_price}
                }]
            }}
            await loop.run_in_executor(None, ikas_graphql, mutation, variables)

            # Step 6: Log + update local
            cur_label = "TL" if target_currency in ("TRY", "TL") else target_currency
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

            await db.products.update_one({"slug": req.slug}, {"$set": {
                "our_price": req.new_price_tl,
                "base_price": new_price,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }})

            return {
                "success": True,
                "message": f"Fiyat güncellendi: {new_price:.2f} {cur_label} ({req.new_price_tl:,.2f} TL)",
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
                    new_price_tl = ch.get("new_price_tl") or ch.get("new_price")
                    if not new_price_tl:
                        failed += 1
                        continue
                    product = await db.products.find_one({"slug": slug})
                    if not product:
                        failed += 1
                        continue

                    # Safety: floor_price must exist
                    floor_price = product.get("floor_price")
                    if not floor_price:
                        await db.price_changes.update_one({"_id": ch["_id"]}, {"$set": {"apply_error": "Dip fiyat girilmemiş"}})
                        failed += 1
                        continue

                    ikas_id = product.get("ikas_id") or product.get("ikas_product_id")
                    if not ikas_id:
                        await db.price_changes.update_one({"_id": ch["_id"]}, {"$set": {"apply_error": "İkas ID bulunamadı"}})
                        failed += 1
                        continue

                    gql_query = f'''{{ listProduct(id: {{eq: "{ikas_id}"}}) {{ data {{
                        variants {{ id prices {{ sellPrice currency priceListId }} }}
                    }} }} }}'''
                    result = await loop.run_in_executor(None, ikas_fn, gql_query, None)
                    product_data = (result.get("listProduct", {}).get("data", []) or [{}])[0]
                    variants = product_data.get("variants", [])
                    if not variants:
                        failed += 1
                        continue

                    variant = variants[0]
                    existing_prices = variant.get("prices", [])

                    target_plid = target_currency = None
                    for p in existing_prices:
                        plid = p.get("priceListId") or ""
                        if plid.startswith("b8f60257"):
                            continue
                        if plid == price_lists.get("EUR"):
                            target_plid, target_currency = plid, "EUR"
                            break
                        elif plid == price_lists.get("USD"):
                            target_plid, target_currency = plid, "USD"
                        elif plid == price_lists.get("TRY") and not target_plid:
                            target_plid, target_currency = plid, "TRY"

                    if not target_plid:
                        failed += 1
                        continue

                    # Convert using TCMB
                    new_price = convert_from_tl(new_price_tl, target_currency)

                    # Floor check
                    if new_price < floor_price:
                        await db.price_changes.update_one({"_id": ch["_id"]}, {"$set": {"apply_error": f"Dip fiyat altı ({new_price:.2f} < {floor_price:.2f} {target_currency})"}})
                        failed += 1
                        continue

                    # Use saveVariantPrices — SAFE
                    mutation = """mutation UpdateVariantPrices($input: UpdateVariantPricesInput!) {
                        updateVariantPrices(input: $input) { __typename }
                    }"""
                    variables = {"input": {
                        "priceListId": target_plid,
                        "variantPriceInputs": [{
                            "productId": ikas_id,
                            "variantId": variant["id"],
                            "price": {"sellPrice": new_price}
                        }]
                    }}
                    await loop.run_in_executor(None, ikas_fn, mutation, variables)

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
                    await db.products.update_one({"slug": slug}, {"$set": {
                        "our_price": new_price_tl,
                        "base_price": new_price,
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    }})
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
    from tcmb_exchange import convert_from_tl, convert_to_tl, force_refresh_rates
    logger.info("CRON: Rakip fiyat taramasi basladi")
    try:
        # Force refresh exchange rates before scan
        force_refresh_rates()
        logger.info("CRON: Kur verileri güncellendi")
        rules_list = await db.pricing_rules.find({"enabled": True}).to_list(100)
        rules_map = {r["category_name"]: r for r in rules_list}
        auto_update_cats = {r["category_name"] for r in rules_list if r.get("auto_update_ikas")}

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

                # Determine product categories from ikas_categories (with category_path fallback)
                product_cats = set()
                ikas_cats = product.get("ikas_categories", [])
                for c in ikas_cats:
                    if c.get("name") and c["name"] != "Tüm Ürünler":
                        product_cats.add(c["name"])
                if not product_cats:
                    cp = product.get("category_path", "")
                    if cp:
                        for seg in cp.split(","):
                            for part in seg.strip().split(">"):
                                part = part.strip()
                                if part and part != "Tüm Ürünler":
                                    product_cats.add(part)

                # Find matching rule from any of the product's categories
                rule = {}
                for cat in product_cats:
                    if cat in rules_map:
                        rule = rules_map[cat]
                        break
                should_auto = any(cat in auto_update_cats for cat in product_cats)
                base_currency = product.get("base_currency", "TRY")
                floor_price = product.get("floor_price")

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
                    can_update_price = floor_price is not None and floor_price > 0

                    undercut = rule.get("undercut_amount", 100)
                    result = calculate_optimal_price(
                        prices,
                        product.get("our_price", 0),
                        floor_price or 0,
                        base_currency,
                        undercut,
                    )

                    update_fields = {
                        "competitor_prices": prices,
                        "cheapest_competitor_price": cheapest["price"],
                        "cheapest_competitor_name": cheapest["competitor_name"],
                        "competitor_prices_checked_at": datetime.now(timezone.utc).isoformat(),
                        "price_recommendation": result,
                    }
                    await db.products.update_one({"slug": slug}, {"$set": update_fields})

                    if result.get("action") == "update":
                        log_entry = {
                            "product_slug": slug,
                            "product_name": product.get("name", ""),
                            "action": "update",
                            "old_price_tl": result.get("old_price_tl"),
                            "new_price_tl": result.get("new_price_tl"),
                            "new_price_base": result.get("new_price_base"),
                            "base_currency": base_currency,
                            "cheapest_competitor": result.get("cheapest_competitor"),
                            "cheapest_price": result.get("cheapest_price"),
                            "floor_price": floor_price,
                            "reason": result.get("reason", ""),
                            "applied": False,
                            "auto_update": should_auto,
                            "changed_at": datetime.now(timezone.utc).isoformat(),
                        }

                        if should_auto and ikas_graphql and can_update_price:
                            # 23-hour protection
                            last_update = product.get("price_updated_at")
                            skip_23h = False
                            if last_update:
                                try:
                                    last_dt = datetime.fromisoformat(last_update.replace("Z", "+00:00")) if isinstance(last_update, str) else last_update
                                    hours_since = (datetime.now(timezone.utc) - last_dt).total_seconds() / 3600
                                    if hours_since < 23:
                                        skip_23h = True
                                        log_entry["apply_error"] = f"Son güncelleme {hours_since:.0f} saat önce — 23 saat koruması"
                                except Exception:
                                    pass
                            
                            if not skip_23h:
                                try:
                                    ikas_id = product.get("ikas_id") or product.get("ikas_product_id")
                                    if ikas_id:
                                        new_tl = result["new_price_tl"]
                                        applied_ok = await _apply_price_to_ikas(
                                            loop, ikas_graphql, db, slug, ikas_id,
                                            new_tl, floor_price, base_currency,
                                            IKAS_PRICE_LISTS
                                        )
                                        if applied_ok:
                                            log_entry["applied"] = True
                                            log_entry["applied_at"] = datetime.now(timezone.utc).isoformat()
                                            new_base = convert_from_tl(new_tl, base_currency)
                                            await db.products.update_one({"slug": slug}, {"$set": {"our_price": new_tl, "base_price": new_base}})
                                            auto_updated += 1
                                except Exception as e:
                                    logger.error(f"CRON auto-update error for {slug}: {e}")
                                    log_entry["apply_error"] = str(e)
                        elif should_auto and not can_update_price:
                            log_entry["apply_error"] = "Dip fiyat girilmemiş — güncelleme atlandı"

                        await db.price_changes.insert_one(log_entry)
                    elif result.get("action") == "floor_hit":
                        await db.price_changes.insert_one({
                            "product_slug": slug,
                            "product_name": product.get("name", ""),
                            "action": "floor_hit",
                            "old_price_tl": product.get("our_price"),
                            "new_price_tl": None,
                            "base_currency": base_currency,
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


async def _apply_price_to_ikas(loop, ikas_graphql, db, slug, ikas_id, new_price_tl, floor_price, base_currency, price_lists):
    """Helper: update a product's price in İkas using saveVariantPrices — SAFE."""
    from tcmb_exchange import convert_from_tl

    gql = f'''{{ listProduct(id: {{eq: "{ikas_id}"}}) {{ data {{
        variants {{ id prices {{ sellPrice currency priceListId }} }}
    }} }} }}'''
    result = await loop.run_in_executor(None, ikas_graphql, gql, None)
    pdata = (result.get("listProduct", {}).get("data", []) or [{}])[0]
    variants = pdata.get("variants", [])
    if not variants:
        return False

    variant = variants[0]
    existing_prices = variant.get("prices", [])

    target_plid = target_currency = None
    for p in existing_prices:
        plid = p.get("priceListId") or ""
        if plid.startswith("b8f60257"):
            continue
        if plid == price_lists.get("EUR"):
            target_plid, target_currency = plid, "EUR"
            break
        elif plid == price_lists.get("USD"):
            target_plid, target_currency = plid, "USD"
        elif plid == price_lists.get("TRY") and not target_plid:
            target_plid, target_currency = plid, "TRY"

    if not target_plid:
        return False

    new_price = convert_from_tl(new_price_tl, target_currency)
    if floor_price and new_price < floor_price:
        return False

    # 1. Update price list
    mutation1 = """mutation UpdateVariantPrices($input: UpdateVariantPricesInput!) {
        updateVariantPrices(input: $input) { __typename }
    }"""
    variables1 = {"input": {
        "priceListId": target_plid,
        "variantPriceInputs": [{
            "productId": ikas_id,
            "variantId": variant["id"],
            "price": {"sellPrice": new_price}
        }]
    }}
    await loop.run_in_executor(None, ikas_graphql, mutation1, variables1)

    # Update price_updated_at for 23-hour protection
    await db.products.update_one({"ikas_product_id": ikas_id}, {"$set": {"price_updated_at": datetime.now(timezone.utc).isoformat()}})
    return True
