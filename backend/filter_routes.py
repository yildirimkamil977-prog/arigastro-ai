"""
Filter Management Routes — AI-powered product attribute filling.
Uses Ikas Product Attributes API (updateProductAndVariantAttributes)
which is completely isolated from product categories/descriptions/prices.
"""

import os
import json
import asyncio
import logging
import uuid
import traceback
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from motor.motor_asyncio import AsyncIOMotorClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/filters", tags=["filters"])

MONGO_URL = os.environ.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME", "arigastro")
EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
IKAS_CLIENT_ID = os.environ.get("IKAS_CLIENT_ID")
IKAS_CLIENT_SECRET = os.environ.get("IKAS_CLIENT_SECRET")

_mongo_client = None


def get_db():
    global _mongo_client
    if not _mongo_client:
        _mongo_client = AsyncIOMotorClient(MONGO_URL)
    return _mongo_client[DB_NAME]


# --- Ikas helpers ---
import requests

_ikas_token_cache = {}


def ikas_token():
    now = __import__("time").time()
    if _ikas_token_cache.get("t") and _ikas_token_cache.get("exp", 0) > now:
        return _ikas_token_cache["t"]
    r = requests.post("https://api.myikas.com/api/admin/oauth/token", json={
        "grant_type": "client_credentials",
        "client_id": IKAS_CLIENT_ID,
        "client_secret": IKAS_CLIENT_SECRET,
    }, timeout=15)
    data = r.json()
    _ikas_token_cache["t"] = data["access_token"]
    _ikas_token_cache["exp"] = now + data.get("expires_in", 14400) - 60
    return _ikas_token_cache["t"]


def ikas_gql(q, v=None):
    r = requests.post("https://api.myikas.com/api/v2/admin/graphql",
        json={"query": q, "variables": v or {}},
        headers={"Authorization": f"Bearer {ikas_token()}", "Content-Type": "application/json"},
        timeout=30)
    data = r.json()
    if data.get("errors"):
        raise Exception(data["errors"][0].get("message", "Ikas API error"))
    return data.get("data", {})


# --- AI helper ---
async def ai_analyze(prompt, system_msg="Sen endüstriyel mutfak ekipmanları uzmanısın."):
    from openai import OpenAI
    api_key = OPENAI_API_KEY
    if not api_key:
        raise Exception("AI API anahtarı bulunamadı (OPENAI_API_KEY)")
    client = OpenAI(api_key=api_key)
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(None, lambda: client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
    ))
    return response.choices[0].message.content


# --- Auth dependency (reuse from server) ---
from server import get_current_user


# --- Models ---
class FilterSuggestion(BaseModel):
    name: str
    type: str = "MULTIPLE_CHOICE"
    sample_values: List[str] = []


class ApproveRequest(BaseModel):
    filters: List[FilterSuggestion]


# --- Routes ---

@router.get("/categories")
async def list_filter_categories(user: dict = Depends(get_current_user)):
    """List categories with product counts for filter management."""
    db = get_db()
    pipeline = [
        {"$match": {"inactive": {"$ne": True}, "ikas_categories": {"$exists": True, "$ne": []}}},
        {"$unwind": "$ikas_categories"},
        {"$group": {"_id": "$ikas_categories.name", "count": {"$sum": 1}}},
        {"$sort": {"_id": 1}},
    ]
    cats = []
    async for doc in db.products.aggregate(pipeline):
        if doc["_id"] and doc["_id"] != "Tüm Ürünler":
            cats.append({"name": doc["_id"], "product_count": doc["count"]})
    return {"categories": cats}


@router.post("/analyze-category")
async def analyze_category(req: dict, user: dict = Depends(get_current_user)):
    """AI analyzes products in a category and suggests filters."""
    category = req.get("category", "")
    if not category:
        raise HTTPException(400, "Kategori belirtilmedi")

    db = get_db()
    job_id = uuid.uuid4().hex[:12]

    # Get products in this category
    products = []
    async for p in db.products.find(
        {"inactive": {"$ne": True}, "ikas_categories.name": category},
        {"_id": 0, "name": 1, "ikas_product_id": 1, "sku": 1, "description": 1}
    ).limit(500):
        products.append(p)

    if not products:
        raise HTTPException(404, f"'{category}' kategorisinde ürün bulunamadı")

    # Create job
    await db.filter_jobs.insert_one({
        "job_id": job_id,
        "category": category,
        "status": "analyzing",
        "total_products": len(products),
        "processed": 0,
        "suggested_filters": [],
        "approved_filters": [],
        "results": [],
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    # Run analysis in background
    asyncio.create_task(_analyze_background(job_id, category, products))

    return {"job_id": job_id, "status": "analyzing", "total_products": len(products)}


async def _analyze_background(job_id, category, products):
    db = get_db()
    try:
        # Get product descriptions from Ikas for better data
        sample_descs = []
        for p in products[:20]:
            ikas_id = p.get("ikas_product_id", "")
            if not ikas_id:
                continue
            try:
                data = ikas_gql(
                    '{listProduct(id:{eq:"' + ikas_id + '"}){data{name description}}}')
                prod = (data.get("listProduct", {}).get("data", []) or [{}])[0]
                desc = prod.get("description", "")
                if desc and len(desc) > 50:
                    sample_descs.append({"name": prod.get("name", p.get("name", "")), "description": desc[:2000]})
            except Exception:
                pass
            if len(sample_descs) >= 15:
                break

        if not sample_descs:
            await db.filter_jobs.update_one(
                {"job_id": job_id},
                {"$set": {"status": "error", "error": "Ürün açıklamaları bulunamadı"}}
            )
            return

        # Build prompt
        descs_text = ""
        for i, sd in enumerate(sample_descs, 1):
            descs_text += f"\n--- Ürün {i}: {sd['name']} ---\n{sd['description'][:1500]}\n"

        prompt = f"""Aşağıda "{category}" kategorisindeki {len(sample_descs)} ürünün açıklamaları var.

Bu ürünlerin teknik özelliklerini analiz et ve bu kategori için uygun FİLTRE ÖNERİLERİ çıkar.

KURALLAR:
1. Sadece bu kategoriye özgü, anlamlı filtreler öner (genel filtreler değil)
2. Her filtre için 3-8 örnek değer belirt
3. Tüm ürünlere uygulanamayacak filtreler de olabilir (örn: çekmeceli ürünlere "Çekmece Sayısı", kapılı ürünlere "Kapı Sayısı")
4. Mevcut İkas filtreleri: Materyal, Çalışma Tipi, Çalışma Teknolojisi, Voltaj, Kapasite, Boyutlar — bunları tekrar önerme, sadece YENİ filtreler öner
5. Filtre isimleri Türkçe ve profesyonel olmalı

CEVABINI SADECE JSON OLARAK VER, başka hiçbir şey yazma:
[
  {{"name": "Filtre Adı", "type": "MULTIPLE_CHOICE", "sample_values": ["Değer1", "Değer2", "Değer3"]}},
  ...
]

{descs_text}"""

        result = await ai_analyze(prompt)

        # Parse JSON
        result = result.strip()
        if result.startswith("```"):
            result = result.split("\n", 1)[1] if "\n" in result else result
            result = result.rsplit("```", 1)[0]
        suggestions = json.loads(result)

        await db.filter_jobs.update_one(
            {"job_id": job_id},
            {"$set": {
                "status": "awaiting_review",
                "suggested_filters": suggestions,
                "sample_products": [sd["name"] for sd in sample_descs],
            }}
        )

    except Exception as e:
        logger.error(f"Filter analysis error: {traceback.format_exc()}")
        await db.filter_jobs.update_one(
            {"job_id": job_id},
            {"$set": {"status": "error", "error": str(e)[:500]}}
        )


@router.get("/job/{job_id}")
async def get_job_status(job_id: str, user: dict = Depends(get_current_user)):
    """Get filter job status and results."""
    db = get_db()
    job = await db.filter_jobs.find_one({"job_id": job_id}, {"_id": 0})
    if not job:
        raise HTTPException(404, "İş bulunamadı")
    return job


@router.post("/execute/{job_id}")
async def execute_filters(job_id: str, req: ApproveRequest, user: dict = Depends(get_current_user)):
    """User approves filters and starts execution."""
    db = get_db()
    job = await db.filter_jobs.find_one({"job_id": job_id})
    if not job:
        raise HTTPException(404, "İş bulunamadı")
    if job["status"] not in ("awaiting_review", "error"):
        raise HTTPException(400, f"İş durumu uygun değil: {job['status']}")

    filters = [f.dict() for f in req.filters]
    await db.filter_jobs.update_one(
        {"job_id": job_id},
        {"$set": {
            "status": "executing",
            "approved_filters": filters,
            "processed": 0,
            "results": [],
            "error": None,
        }}
    )

    asyncio.create_task(_execute_background(job_id))
    return {"status": "executing", "job_id": job_id}


async def _execute_background(job_id):
    db = get_db()
    job = await db.filter_jobs.find_one({"job_id": job_id})
    category = job["category"]
    approved = job["approved_filters"]

    try:
        # 1. Ensure all filters exist in Ikas
        existing_attrs = ikas_gql("{listProductAttribute{id name type options{id name}}}").get("listProductAttribute", [])
        existing_map = {a["name"]: a for a in existing_attrs}

        filter_map = {}  # filter_name -> {id, options: {value: option_id}}
        for f in approved:
            if f["name"] in existing_map:
                attr = existing_map[f["name"]]
                filter_map[f["name"]] = {
                    "id": attr["id"],
                    "options": {o["name"]: o["id"] for o in attr.get("options", [])},
                }
            else:
                # Create new attribute
                options = [{"name": v} for v in f.get("sample_values", [])]
                res = ikas_gql(
                    "mutation C($i:CreateProductAttributeInput!){createProductAttribute(input:$i){id name options{id name}}}",
                    {"i": {"name": f["name"], "type": f.get("type", "MULTIPLE_CHOICE"), "options": options}},
                )
                new_attr = res.get("createProductAttribute", {})
                filter_map[f["name"]] = {
                    "id": new_attr["id"],
                    "options": {o["name"]: o["id"] for o in new_attr.get("options", [])},
                }
                logger.info(f"Created filter: {f['name']} with {len(options)} options")

        # 2. Get all products in category
        products = []
        async for p in db.products.find(
            {"inactive": {"$ne": True}, "ikas_categories.name": category},
            {"_id": 0, "name": 1, "ikas_product_id": 1, "sku": 1}
        ).limit(500):
            products.append(p)

        filter_names = [f["name"] for f in approved]

        # 3. Process each product
        for idx, prod in enumerate(products):
            ikas_id = prod.get("ikas_product_id", "")
            if not ikas_id:
                continue

            try:
                # Get description from Ikas
                pdata = ikas_gql('{listProduct(id:{eq:"' + ikas_id + '"}){data{name description}}}')
                pinfo = (pdata.get("listProduct", {}).get("data", []) or [{}])[0]
                desc = pinfo.get("description", "")
                pname = pinfo.get("name", prod.get("name", ""))

                if not desc or len(desc) < 30:
                    await _update_job_progress(db, job_id, idx + 1, pname, [], "Açıklama yok")
                    continue

                # AI extraction
                prompt = f"""Bu ürünün açıklamasını analiz et ve aşağıdaki filtrelerden SADECE bu ürüne uygun olanları doldur.

ÜRÜN: {pname}
AÇIKLAMA: {desc[:3000]}

MEVCUT FİLTRELER: {json.dumps(filter_names, ensure_ascii=False)}

KURALLAR:
1. Sadece ürüne GERÇEKTEN uygun filtreleri doldur
2. Uygun olmayan filtreleri ATLAMA (örn: çekmeceli ürüne "Kapı Sayısı" yazma)
3. Açıklamada bilgi yoksa o filtreyi ATLAMA
4. Değerler kısa ve net olsun (örn: "220V", "Paslanmaz Çelik", "150 Litre")

CEVABINI SADECE JSON OLARAK VER:
{{"Filtre Adı": "Değer", "Başka Filtre": "Değer"}}
Uygun olmayan filtreler için anahtar EKLEME."""

                ai_result = await ai_analyze(prompt)
                ai_result = ai_result.strip()
                if ai_result.startswith("```"):
                    ai_result = ai_result.split("\n", 1)[1] if "\n" in ai_result else ai_result
                    ai_result = ai_result.rsplit("```", 1)[0]

                values = json.loads(ai_result)

                # Build Ikas attribute update
                attr_updates = []
                added_filters = []
                for fname, fvalue in values.items():
                    if fname not in filter_map:
                        continue
                    fdata = filter_map[fname]
                    fvalue_str = str(fvalue).strip()
                    if not fvalue_str:
                        continue

                    # Check if option exists, if not create it
                    if fvalue_str not in fdata["options"]:
                        try:
                            res = ikas_gql(
                                "mutation U($i:UpdateProductAttributeInput!){updateProductAttribute(input:$i){id options{id name}}}",
                                {"i": {"id": fdata["id"], "options": [{"name": fvalue_str}]}},
                            )
                            updated = res.get("updateProductAttribute", {})
                            new_opt = next((o for o in updated.get("options", []) if o["name"] == fvalue_str), None)
                            if new_opt:
                                fdata["options"][fvalue_str] = new_opt["id"]
                        except Exception:
                            continue

                    opt_id = fdata["options"].get(fvalue_str)
                    if opt_id:
                        attr_updates.append({
                            "productAttributeId": fdata["id"],
                            "productAttributeOptionIds": [opt_id],
                        })
                        added_filters.append({"name": fname, "value": fvalue_str})

                # Apply to Ikas
                if attr_updates:
                    # Get existing attributes first to preserve them
                    existing = ikas_gql('{listProduct(id:{eq:"' + ikas_id + '"}){data{attributes{productAttributeId productAttributeOptionId}}}}')
                    existing_attrs_prod = (existing.get("listProduct", {}).get("data", []) or [{}])[0].get("attributes", [])

                    # Merge: keep existing + add new
                    merged = {}
                    for ea in existing_attrs_prod:
                        aid = ea["productAttributeId"]
                        if aid not in merged:
                            merged[aid] = {"productAttributeId": aid, "productAttributeOptionIds": []}
                        if ea.get("productAttributeOptionId"):
                            merged[aid]["productAttributeOptionIds"].append(ea["productAttributeOptionId"])

                    for au in attr_updates:
                        aid = au["productAttributeId"]
                        merged[aid] = au

                    ikas_gql(
                        "mutation U($i:UpdateProductAndVariantAttributesInput!){updateProductAndVariantAttributes(input:$i){id}}",
                        {"i": {"productId": ikas_id, "productAttributes": list(merged.values())}},
                    )

                await _update_job_progress(db, job_id, idx + 1, pname, added_filters, "OK")

            except Exception as e:
                await _update_job_progress(db, job_id, idx + 1, prod.get("name", ""), [], str(e)[:200])

            await asyncio.sleep(0.5)

        await db.filter_jobs.update_one(
            {"job_id": job_id},
            {"$set": {"status": "completed", "completed_at": datetime.now(timezone.utc).isoformat()}}
        )

    except Exception as e:
        logger.error(f"Filter execution error: {traceback.format_exc()}")
        await db.filter_jobs.update_one(
            {"job_id": job_id},
            {"$set": {"status": "error", "error": str(e)[:500]}}
        )


async def _update_job_progress(db, job_id, processed, product_name, filters, status):
    await db.filter_jobs.update_one(
        {"job_id": job_id},
        {
            "$set": {"processed": processed},
            "$push": {"results": {
                "product": product_name,
                "filters": filters,
                "status": status,
            }},
        }
    )


@router.get("/jobs")
async def list_jobs(user: dict = Depends(get_current_user)):
    """List all filter jobs."""
    db = get_db()
    jobs = []
    async for j in db.filter_jobs.find({}, {"_id": 0, "results": 0}).sort("created_at", -1).limit(20):
        jobs.append(j)
    return {"jobs": jobs}
