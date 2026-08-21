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

TEKNIK_OZELLIKLER_ATTR_ID = "0e243181-b2d4-4b4c-aed6-c79a953f3208"

_mongo_client = None


def build_specs_html(filter_values):
    """Build a clean HTML table from filter name-value pairs for Teknik Özellikler."""
    if not filter_values:
        return ""
    rows = ""
    for i, fv in enumerate(filter_values):
        bg = "#f8f9fa" if i % 2 == 0 else "#ffffff"
        rows += (
            f'<tr style="background:{bg}">'
            f'<td style="padding:10px 14px;border:1px solid #e2e8f0;font-weight:600;color:#334155;width:40%">{fv["name"]}</td>'
            f'<td style="padding:10px 14px;border:1px solid #e2e8f0;color:#475569">{fv["value"]}</td>'
            f'</tr>'
        )
    return (
        '<table style="width:100%;border-collapse:collapse;font-size:14px;font-family:inherit">'
        '<thead><tr style="background:#1e293b">'
        '<th style="padding:10px 14px;text-align:left;color:#fff;border:1px solid #1e293b">Özellik</th>'
        '<th style="padding:10px 14px;text-align:left;color:#fff;border:1px solid #1e293b">Değer</th>'
        f'</tr></thead><tbody>{rows}</tbody></table>'
    )


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
                    '{listProduct(id:{eq:"' + ikas_id + '"}){data{name description shortDescription}}}')
                prod = (data.get("listProduct", {}).get("data", []) or [{}])[0]
                desc = prod.get("description", "") or ""
                short_desc = prod.get("shortDescription", "") or ""
                full = f"{desc}\n{short_desc}".strip()
                if full and len(full) > 30:
                    sample_descs.append({"name": prod.get("name", p.get("name", "")), "description": full[:2000], "sku": p.get("sku", "")})
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
            descs_text += f"\n--- Ürün {i}: {sd['name']} (SKU: {sd.get('sku','')}) ---\n{sd['description'][:1500]}\n"

        prompt = f"""Aşağıda "{category}" kategorisindeki {len(sample_descs)} endüstriyel mutfak ekipmanı ürününün bilgileri var.

Bu ürünlerin teknik özelliklerini analiz et ve bu kategori için uygun FİLTRE ÖNERİLERİ çıkar.

KURALLAR:
1. Bu kategoriye özgü, müşterinin satın alma kararını kolaylaştıracak filtreler öner
2. Her filtre için 3-8 örnek değer belirt
3. Ürün adlarından, açıklamalardan ve teknik tablolardan veri çıkar
4. Boyut, ağırlık, güç, kapasite, malzeme gibi somut teknik filtreleri öncelikle öner
5. Tüm ürünlere uygulanamayacak filtreler de olabilir
6. Mevcut İkas filtreleri: Materyal, Çalışma Tipi, Çalışma Teknolojisi, Voltaj, Kapasite, Boyutlar — bunları tekrar önerme, sadece YENİ filtreler öner
7. Filtre isimleri Türkçe ve profesyonel olmalı
8. En az 4, en fazla 12 filtre öner

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
            try:
                if f["name"] in existing_map:
                    attr = existing_map[f["name"]]
                    filter_map[f["name"]] = {
                        "id": attr["id"],
                        "options": {o["name"]: o["id"] for o in attr.get("options", [])},
                    }
                else:
                    # Create new attribute — options must not be empty for MULTIPLE_CHOICE
                    options = [{"name": v} for v in f.get("sample_values", []) if v and v.strip()]
                    create_input = {"name": f["name"], "type": f.get("type", "MULTIPLE_CHOICE")}
                    if options:
                        create_input["options"] = options
                    else:
                        # İkas requires at least one option for MULTIPLE_CHOICE
                        create_input["options"] = [{"name": "-"}]
                    res = ikas_gql(
                        "mutation C($i:CreateProductAttributeInput!){createProductAttribute(input:$i){id name options{id name}}}",
                        {"i": create_input},
                    )
                    new_attr = res.get("createProductAttribute", {})
                    filter_map[f["name"]] = {
                        "id": new_attr["id"],
                        "options": {o["name"]: o["id"] for o in new_attr.get("options", [])},
                    }
                    logger.info(f"Created filter: {f['name']} with {len(options)} options")
            except Exception as e:
                logger.error(f"Filter create/lookup error for '{f['name']}': {e}")
                continue

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
                # Get description + shortDescription from Ikas
                pdata = ikas_gql('{listProduct(id:{eq:"' + ikas_id + '"}){data{name description shortDescription}}}')
                pinfo = (pdata.get("listProduct", {}).get("data", []) or [{}])[0]
                desc = pinfo.get("description", "") or ""
                short_desc = pinfo.get("shortDescription", "") or ""
                pname = pinfo.get("name", prod.get("name", ""))
                sku = prod.get("sku", "")

                # Combine all available text
                full_text = f"{desc}\n{short_desc}".strip()
                if not full_text or len(full_text) < 10:
                    await _update_job_progress(db, job_id, idx + 1, pname, [], "Açıklama yok")
                    continue

                # AI extraction — two parts: (1) filter values, (2) ALL technical specs for table
                prompt = f"""Bu endüstriyel mutfak ekipmanı ürününü analiz et.

ÜRÜN ADI: {pname}
SKU: {sku}
AÇIKLAMA: {full_text[:3000]}

İKİ GÖREV:

GÖREV 1 — FİLTRELER:
Aşağıdaki filtrelerden bu ürüne uygun olanları doldur:
{json.dumps(filter_names, ensure_ascii=False)}

GÖREV 2 — TEKNİK ÖZELLİKLER TABLOSU:
Açıklamada ve ürün adında geçen TÜM teknik özellikleri çıkar (Kapasite, Boyutlar, Ağırlık, Güç, Model, Voltaj, vb.)

KRİTİK KURALLAR:
1. SADECE metinde birebir yazan bilgileri kullan
2. KESİNLİKLE tahmin yapma, bilgiyi değiştirme veya uydurmma
3. Metinde "Krom Çelik" yazıyorsa "Krom Çelik" yaz, "304 Paslanmaz Çelik" diye değiştirme
4. Değerler metindeki orijinal ifadeyle aynı olmalı
5. Metinde olmayan bilgiyi hiçbir alana EKLEME

CEVABINI SADECE JSON OLARAK VER:
{{
  "filters": {{"Filtre Adı": "Değer"}},
  "specs": {{"Özellik Adı": "Değer", "Kapasite": "400 litre", "Net Ağırlık": "163 kg"}}
}}
"filters" sadece yukarıdaki filtre listesinden, "specs" ise açıklamadaki TÜM teknik bilgileri içermeli."""

                ai_result = await ai_analyze(prompt)
                ai_result = ai_result.strip()
                if ai_result.startswith("```"):
                    ai_result = ai_result.split("\n", 1)[1] if "\n" in ai_result else ai_result
                    ai_result = ai_result.rsplit("```", 1)[0]

                parsed = json.loads(ai_result)
                # Support both new format {filters, specs} and old format {key: value}
                if "filters" in parsed and "specs" in parsed:
                    filter_values = parsed["filters"]
                    spec_values = parsed["specs"]
                else:
                    filter_values = parsed
                    spec_values = parsed

                # Build Ikas attribute update from filter values
                attr_updates = []
                added_filters = []
                for fname, fvalue in filter_values.items():
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
                if attr_updates or added_filters:
                    # Get existing attributes first to preserve them
                    existing = ikas_gql('{listProduct(id:{eq:"' + ikas_id + '"}){data{attributes{productAttributeId productAttributeOptionId value}}}}')
                    existing_attrs_prod = (existing.get("listProduct", {}).get("data", []) or [{}])[0].get("attributes", [])

                    # Merge: keep existing + add new
                    merged = {}
                    for ea in existing_attrs_prod:
                        aid = ea["productAttributeId"]
                        if aid == TEKNIK_OZELLIKLER_ATTR_ID:
                            # Preserve existing Teknik Özellikler for merging
                            continue
                        if aid not in merged:
                            merged[aid] = {"productAttributeId": aid, "productAttributeOptionIds": []}
                        if ea.get("productAttributeOptionId"):
                            merged[aid]["productAttributeOptionIds"].append(ea["productAttributeOptionId"])

                    for au in attr_updates:
                        aid = au["productAttributeId"]
                        merged[aid] = au

                    # Build Teknik Özellikler HTML table from ALL extracted specs
                    all_specs = []
                    # First add spec_values (comprehensive technical specs)
                    for sname, svalue in spec_values.items():
                        svalue_str = str(svalue).strip()
                        if svalue_str:
                            all_specs.append({"name": sname, "value": svalue_str})
                    # Add any filter values not already in specs
                    spec_names = {s["name"] for s in all_specs}
                    for af in added_filters:
                        if af["name"] not in spec_names:
                            all_specs.append(af)

                    if all_specs:
                        specs_html = build_specs_html(all_specs)
                        merged[TEKNIK_OZELLIKLER_ATTR_ID] = {
                            "productAttributeId": TEKNIK_OZELLIKLER_ATTR_ID,
                            "value": specs_html,
                        }

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
