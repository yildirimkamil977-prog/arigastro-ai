#!/usr/bin/env python3
"""
Ikas Kategori Kurtarma v5 — Additive Restoration
==================================================
CSV'den eksik kategorileri bulup Ikas'a ekler. Mevcut kategorileri KORUR.

Kullanim:
  python3 restore_categories.py                      # DRY-RUN
  python3 restore_categories.py --execute            # Gercek guncelleme
  python3 restore_categories.py --execute --limit 5  # Ilk 5 urunle test
"""

import os
import csv
import sys
import json
import time
import requests
from collections import defaultdict
from dotenv import load_dotenv

load_dotenv()

CSV_PATH = "/tmp/ikas-urunler.csv"
IKAS_TOKEN_URL = "https://api.myikas.com/api/admin/oauth/token"
IKAS_GRAPHQL_URL = "https://api.myikas.com/api/v2/admin/graphql"
IKAS_CLIENT_ID = os.environ.get("IKAS_CLIENT_ID")
IKAS_CLIENT_SECRET = os.environ.get("IKAS_CLIENT_SECRET")

DRY_RUN = "--execute" not in sys.argv
LIMIT = None
for _i, _arg in enumerate(sys.argv):
    if _arg == "--limit" and _i + 1 < len(sys.argv):
        LIMIT = int(sys.argv[_i + 1])

# Name mapping: CSV name -> Ikas name (for known mismatches)
NAME_MAP = {
    "Buzdolabı ve Derindondurucular": "Buzdolabı ve Derin Dondurucular",
}

_token_cache = {}


def get_token():
    now = time.time()
    if _token_cache.get("token") and _token_cache.get("expires_at", 0) > now:
        return _token_cache["token"]
    resp = requests.post(IKAS_TOKEN_URL, json={
        "grant_type": "client_credentials",
        "client_id": IKAS_CLIENT_ID,
        "client_secret": IKAS_CLIENT_SECRET,
    }, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    _token_cache["token"] = data["access_token"]
    _token_cache["expires_at"] = now + data.get("expires_in", 14400) - 60
    return _token_cache["token"]


def gql(query, variables=None):
    token = get_token()
    resp = requests.post(IKAS_GRAPHQL_URL,
        json={"query": query, "variables": variables or {}},
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        timeout=30,
    )
    data = resp.json()
    if data.get("errors"):
        return {"_errors": data["errors"]}
    return data.get("data", {})


# ─── Phase 1: Create missing categories ───
def create_missing_categories(csv_cat_names, ikas_cat_names, ikas_name_to_id, csv_chains):
    """Create categories that exist in CSV but not in Ikas."""
    missing = csv_cat_names - ikas_cat_names - set(NAME_MAP.keys())
    if not missing:
        print("   Tum kategoriler Ikas'ta mevcut.")
        return {}

    print(f"   {len(missing)} eksik kategori olusturulacak:")
    created = {}

    # Determine parent for each missing category from CSV chains
    cat_parent_map = {}
    for chain in csv_chains:
        parts = [p.strip() for p in chain.split(">")]
        for i, part in enumerate(parts):
            if part in missing and part not in cat_parent_map:
                parent = parts[i - 1] if i > 0 else None
                if parent:
                    parent = NAME_MAP.get(parent, parent)
                cat_parent_map[part] = parent

    # Topological sort: create parents before children
    # Level 0: root (no parent) or parent already exists in Ikas
    # Level 1+: parent is another missing category (created earlier)
    existing = set(ikas_cat_names)
    ordered = []
    remaining = dict(cat_parent_map)
    max_rounds = 10
    for _ in range(max_rounds):
        if not remaining:
            break
        batch = []
        for name, parent in list(remaining.items()):
            if not parent or parent in existing:
                batch.append((name, parent))
        for name, parent in batch:
            ordered.append((name, parent))
            existing.add(name)
            del remaining[name]
    # Add any remaining (shouldn't happen, but safety net)
    for name, parent in remaining.items():
        ordered.append((name, parent))

    for cat_name, parent_name in ordered:
        parent_id = None
        if parent_name:
            parent_id = ikas_name_to_id.get(parent_name) or created.get(parent_name)

        if DRY_RUN:
            print(f"      [DRY] Olusturulacak: \"{cat_name}\" (ust: \"{parent_name or 'KOK'}\")")
            created[cat_name] = f"dry-run-{cat_name}"
            continue

        result = gql(
            """mutation CreateCategory($input: CreateCategoryInput!) {
                createCategory(input: $input) { id name }
            }""",
            {"input": {"name": cat_name, **({"parentId": parent_id} if parent_id else {})}},
        )

        if result.get("_errors"):
            err = result["_errors"][0].get("message", "")
            print(f"      X Hata: \"{cat_name}\": {err[:80]}")
        elif result.get("createCategory"):
            new_id = result["createCategory"]["id"]
            created[cat_name] = new_id
            ikas_name_to_id[cat_name] = new_id
            print(f"      + Olusturuldu: \"{cat_name}\" (ID: {new_id[:12]}...)")
        time.sleep(0.3)

    return created


# ─── Phase 2: Fetch all Ikas products with categories ───
def fetch_all_ikas_products():
    """Fetch all products from Ikas with their current categories."""
    all_products = {}
    page = 1
    while True:
        data = gql(
            """query ListProducts($page: Int!) {
                listProduct(pagination: {page: $page, limit: 100}) {
                    data { id name categories { id name } brand { id name } }
                    count
                }
            }""",
            {"page": page},
        )
        prods = data.get("listProduct", {})
        for p in prods.get("data", []):
            all_products[p["id"]] = {
                "name": p["name"],
                "categories": {c["name"] for c in (p.get("categories") or [])},
                "brand": (p.get("brand") or {}).get("name", ""),
            }
        total = prods.get("count", 0)
        if page * 100 >= total:
            break
        page += 1
        time.sleep(0.3)
    return all_products


# ─── Phase 3: Compare and build update list ───
def build_update_list(csv_products, ikas_products, ikas_cat_names):
    """Compare CSV vs Ikas and find products that need category updates."""
    updates = []
    not_in_ikas = 0
    already_ok = 0
    partial_fix = 0

    for group_id, csv_data in csv_products.items():
        ikas_prod = ikas_products.get(group_id)
        if not ikas_prod:
            not_in_ikas += 1
            continue

        current_cats = ikas_prod["categories"]
        expected_cats = csv_data["expected_cats"]

        # Apply name mapping
        mapped_expected = set()
        for c in expected_cats:
            mapped_expected.add(NAME_MAP.get(c, c))

        # Find what's missing (only add categories that exist in Ikas)
        missing = mapped_expected - current_cats
        # Filter: only add categories that actually exist in Ikas now
        missing = {c for c in missing if c in ikas_cat_names}

        if not missing:
            already_ok += 1
            continue

        partial_fix += 1
        # ADDITIVE: merge current + missing
        merged = list(current_cats | missing)
        updates.append({
            "id": group_id,
            "name": csv_data["name"],
            "current": sorted(current_cats),
            "adding": sorted(missing),
            "merged": sorted(merged),
            "brand": csv_data.get("brand", ""),
        })

    return updates, not_in_ikas, already_ok, partial_fix


# ─── Phase 4: Execute updates ───
def execute_updates(updates):
    """Push additive category updates to Ikas."""
    mutation = """
    mutation UpdateProduct($input: UpdateProductInput!) {
        updateProduct(input: $input) { id name }
    }
    """
    updated = 0
    failed = 0
    errors = []

    items = updates[:LIMIT] if LIMIT else updates
    total = len(items)

    for i, upd in enumerate(items):
        cat_input = [{"name": c} for c in upd["merged"]]
        input_data = {"id": upd["id"], "categories": cat_input}
        if upd.get("brand"):
            input_data["brand"] = {"name": upd["brand"]}

        result = gql(mutation, {"input": input_data})

        if result.get("_errors"):
            failed += 1
            err = result["_errors"][0].get("message", "")
            errors.append({"product": upd["name"], "id": upd["id"], "error": err})
            if failed <= 10:
                print(f"  X {upd['name'][:40]}: {err[:80]}")
        elif result.get("updateProduct"):
            updated += 1
        else:
            failed += 1

        time.sleep(0.3)
        if (i + 1) % 100 == 0 or (i + 1) == total:
            print(f"  Ilerleme: {i+1}/{total} ({updated} basarili, {failed} basarisiz)")

    return updated, failed, errors


# ─── Main ───
def main():
    mode = "DRY-RUN" if DRY_RUN else "GERCEK GUNCELLEME"
    print(f"=== Ikas Kategori Kurtarma v5 (Additive) ===")
    print(f"Mod: {mode}")
    if LIMIT:
        print(f"Limit: {LIMIT} urun")
    print()

    if not IKAS_CLIENT_ID or not IKAS_CLIENT_SECRET:
        print("HATA: IKAS_CLIENT_ID / IKAS_CLIENT_SECRET eksik!")
        sys.exit(1)

    # 1. Load Ikas categories
    print("1. Ikas kategorileri yukleniyor...")
    cat_data = gql("{ listCategory { id name parentId } }")
    ikas_cats = cat_data.get("listCategory", [])
    ikas_cat_names = {c["name"].strip() for c in ikas_cats}
    ikas_name_to_id = {}
    for c in ikas_cats:
        name = c["name"].strip()
        if name not in ikas_name_to_id:
            ikas_name_to_id[name] = c["id"]
    print(f"   {len(ikas_cats)} kategori yuklendi")

    # 2. Parse CSV
    print("\n2. CSV okunuyor...")
    csv_products = {}
    all_csv_cat_names = set()
    all_csv_chains = set()

    with open(CSV_PATH, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            gid = row.get("Ürün Grup ID", "").strip()
            name = row.get("İsim", "").strip()
            cats_raw = row.get("Kategoriler", "").strip()
            brand = row.get("Marka", "").strip()

            if not gid or not cats_raw or gid in csv_products:
                continue

            expected = set()
            for chain in cats_raw.split(";"):
                chain = chain.strip()
                if not chain:
                    continue
                all_csv_chains.add(chain)
                for part in chain.split(">"):
                    part = part.strip()
                    if part:
                        expected.add(part)
                        all_csv_cat_names.add(part)

            csv_products[gid] = {
                "name": name,
                "expected_cats": expected,
                "brand": brand,
            }

    print(f"   {len(csv_products)} benzersiz urun, {len(all_csv_cat_names)} benzersiz kategori ismi")

    # 3. Create missing categories
    print("\n3. Eksik kategoriler kontrol ediliyor...")
    created = create_missing_categories(all_csv_cat_names, ikas_cat_names, ikas_name_to_id, all_csv_chains)
    # Update ikas_cat_names with newly created
    ikas_cat_names.update(created.keys())

    # 4. Fetch all Ikas products
    print("\n4. Ikas urunleri yukleniyor (bulk)...")
    ikas_products = fetch_all_ikas_products()
    print(f"   {len(ikas_products)} urun yuklendi")

    # 5. Compare and build update list
    print("\n5. Karsilastirma yapiliyor...")
    updates, not_in_ikas, already_ok, partial_fix = build_update_list(
        csv_products, ikas_products, ikas_cat_names
    )

    print(f"   Kategorileri dogru: {already_ok}")
    print(f"   Guncelleme gereken: {partial_fix}")
    print(f"   Ikas'ta bulunamayan: {not_in_ikas}")

    if not updates:
        print("\n   Tum urunlerin kategorileri dogru! Guncelleme gerekmiyor.")
        return

    # Preview
    print(f"\n   Onizleme (ilk 10):")
    for upd in updates[:10]:
        print(f"      {upd['name'][:45]}")
        print(f"        Eklenecek: {upd['adding']}")

    if DRY_RUN:
        report = {
            "mode": "DRY-RUN",
            "total_csv_products": len(csv_products),
            "total_ikas_products": len(ikas_products),
            "already_correct": already_ok,
            "needs_update": partial_fix,
            "not_in_ikas": not_in_ikas,
            "categories_to_create": list(created.keys()),
            "sample_updates": [
                {"name": u["name"], "adding": u["adding"]}
                for u in updates[:20]
            ],
        }
        with open("/tmp/restore_dryrun_report.json", "w") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"\n=== DRY-RUN tamamlandi ===")
        print(f"Rapor: /tmp/restore_dryrun_report.json")
        print(f"Gercek guncelleme icin: python3 restore_categories.py --execute")
        return

    # 6. Execute updates
    print(f"\n6. {len(updates)} urun guncelleniyor...")
    updated, failed, errors = execute_updates(updates)

    print(f"\n=== TAMAMLANDI ===")
    print(f"   Basarili: {updated}")
    print(f"   Basarisiz: {failed}")

    if errors:
        with open("/tmp/restore_errors.json", "w") as f:
            json.dump(errors, f, indent=2, ensure_ascii=False)
        print(f"   Hata detaylari: /tmp/restore_errors.json")


if __name__ == "__main__":
    main()
