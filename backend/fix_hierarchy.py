#!/usr/bin/env python3
"""
Ikas Kategori Hiyerarsi Duzeltme Script'i
==========================================
CSV'den dogru parent-child iliskilerini okur,
Ikas'taki bozuk hiyerarsiyi duzeltir.

Kullanim:
  python3 fix_hierarchy.py                 # DRY-RUN
  python3 fix_hierarchy.py --execute       # Gercek guncelleme
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


def main():
    mode = "DRY-RUN" if DRY_RUN else "GERCEK GUNCELLEME"
    print(f"=== Ikas Kategori Hiyerarsi Duzeltme ===")
    print(f"Mod: {mode}\n")

    # 1. Load Ikas categories
    print("1. Ikas kategorileri yukleniyor...")
    cat_data = gql("{ listCategory { id name parentId } }")
    ikas_cats = cat_data.get("listCategory", [])
    id_to_cat = {c["id"]: c for c in ikas_cats}
    name_to_cats = defaultdict(list)
    for c in ikas_cats:
        name_to_cats[c["name"].strip()].append(c)
    print(f"   {len(ikas_cats)} kategori yuklendi")

    # 2. Parse CSV — build expected hierarchy: child -> parent
    print("\n2. CSV'den hiyerarsi okunuyor...")
    # For each (child_name, parent_name), we need ONE mapping
    # If child has multiple parents (ambiguous like Fritozler under 600/700/900),
    # we handle each separately
    expected_relations = []  # list of (child_name, parent_name)
    seen = set()

    with open(CSV_PATH, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            cats = row.get("Kategoriler", "").strip()
            for chain in cats.split(";"):
                parts = [p.strip() for p in chain.strip().split(">")]
                for i in range(1, len(parts)):
                    child = parts[i]
                    parent = parts[i - 1]
                    key = (child, parent)
                    if key not in seen:
                        seen.add(key)
                        expected_relations.append(key)

    print(f"   {len(expected_relations)} benzersiz child->parent iliski bulundu")

    # 3. Check each relation against Ikas
    print("\n3. Hiyerarsi kontrol ediliyor...")
    fixes = []

    for child_name, parent_name in expected_relations:
        # Map names
        mapped_child = NAME_MAP.get(child_name, child_name)
        mapped_parent = NAME_MAP.get(parent_name, parent_name)

        child_cats = name_to_cats.get(mapped_child, [])
        parent_cats = name_to_cats.get(mapped_parent, [])

        if not child_cats or not parent_cats:
            continue

        parent_ids = {p["id"] for p in parent_cats}

        # Find the child category that SHOULD have this parent but doesn't
        # For ambiguous names: look for a root-level child (no parentId)
        # that should be under this specific parent
        for cc in child_cats:
            if cc.get("parentId") in parent_ids:
                # Already correct
                continue

            if not cc.get("parentId"):
                # Root-level child that should have a parent
                # Pick the first matching parent
                target_parent_id = parent_cats[0]["id"]

                # For ambiguous parents (e.g., "600 Seri" might exist multiple times)
                # prefer root-level parent
                for p in parent_cats:
                    if not p.get("parentId"):
                        target_parent_id = p["id"]
                        break

                fixes.append({
                    "child_id": cc["id"],
                    "child_name": cc["name"],
                    "new_parent_id": target_parent_id,
                    "new_parent_name": mapped_parent,
                    "current_parent": cc.get("parentId"),
                })
                break  # Only fix one root-level child per relation

    # Deduplicate: same child might appear in multiple relations
    seen_children = set()
    unique_fixes = []
    for f in fixes:
        if f["child_id"] not in seen_children:
            seen_children.add(f["child_id"])
            unique_fixes.append(f)

    print(f"   Dogru hiyerarsi: {len(expected_relations) - len(unique_fixes)}")
    print(f"   Duzeltme gereken: {len(unique_fixes)}")

    if not unique_fixes:
        print("\n   Tum hiyerarsi dogru!")
        return

    # Preview
    print(f"\n   Onizleme:")
    for f in unique_fixes[:20]:
        print(f"      \"{f['child_name']}\" -> ust: \"{f['new_parent_name']}\"")
    if len(unique_fixes) > 20:
        print(f"      ... ve {len(unique_fixes) - 20} tane daha")

    if DRY_RUN:
        with open("/tmp/hierarchy_fixes.json", "w") as fp:
            json.dump(unique_fixes, fp, indent=2, ensure_ascii=False)
        print(f"\n=== DRY-RUN tamamlandi ===")
        print(f"Rapor: /tmp/hierarchy_fixes.json")
        print(f"Gercek guncelleme icin: python3 fix_hierarchy.py --execute")
        return

    # 4. Execute fixes
    print(f"\n4. {len(unique_fixes)} kategori hiyerarsisi duzeltiliyor...")
    mutation = """
    mutation UpdateCategory($input: UpdateCategoryInput!) {
        updateCategory(input: $input) { id name parentId }
    }
    """

    updated = 0
    failed = 0
    errors = []

    for i, fix in enumerate(unique_fixes):
        result = gql(mutation, {
            "input": {
                "id": fix["child_id"],
                "parentId": fix["new_parent_id"],
            }
        })

        if result.get("_errors"):
            failed += 1
            err = result["_errors"][0].get("message", "")
            errors.append({"child": fix["child_name"], "parent": fix["new_parent_name"], "error": err})
            if failed <= 10:
                print(f"  X {fix['child_name']}: {err[:80]}")
        elif result.get("updateCategory"):
            updated += 1
        else:
            failed += 1

        time.sleep(0.3)
        if (i + 1) % 50 == 0 or (i + 1) == len(unique_fixes):
            print(f"  Ilerleme: {i+1}/{len(unique_fixes)} ({updated} basarili, {failed} basarisiz)")

    print(f"\n=== TAMAMLANDI ===")
    print(f"   Basarili: {updated}")
    print(f"   Basarisiz: {failed}")

    if errors:
        with open("/tmp/hierarchy_errors.json", "w") as fp:
            json.dump(errors, fp, indent=2, ensure_ascii=False)
        print(f"   Hata detaylari: /tmp/hierarchy_errors.json")


if __name__ == "__main__":
    main()
