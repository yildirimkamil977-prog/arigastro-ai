#!/usr/bin/env python3
"""
Ikas Kategori Tam Duzeltme Script'i
======================================
1. Ghost kategorileri devre disi birakir (rename)
2. Hiyerarsiyi PDF/CSV'ye gore duzeltir (sadece parentId, aciklama/SEO korunur)
3. Tum urunlerin kategorilerini CSV'ye gore duzeltir

Kullanim:
  python3 full_category_fix.py                # DRY-RUN
  python3 full_category_fix.py --execute      # Gercek
"""

import os, csv, sys, json, time, re, requests
from collections import defaultdict
from dotenv import load_dotenv

load_dotenv()

CSV_PATH = "/tmp/ikas-urunler.csv"
IKAS_TOKEN_URL = "https://api.myikas.com/api/admin/oauth/token"
IKAS_GRAPHQL_URL = "https://api.myikas.com/api/v2/admin/graphql"
IKAS_CLIENT_ID = os.environ.get("IKAS_CLIENT_ID")
IKAS_CLIENT_SECRET = os.environ.get("IKAS_CLIENT_SECRET")

DRY_RUN = "--execute" not in sys.argv
NAME_MAP = {"Buzdolabı ve Derindondurucular": "Buzdolabı ve Derin Dondurucular"}

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


def gql(query, variables=None, timeout=30):
    token = get_token()
    resp = requests.post(IKAS_GRAPHQL_URL,
        json={"query": query, "variables": variables or {}},
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        timeout=timeout)
    data = resp.json()
    if data.get("errors"):
        return {"_errors": data["errors"]}
    return data.get("data", {})


def load_ikas_categories():
    data = gql("{ listCategory { id name parentId } }")
    cats = data.get("listCategory", [])
    return cats


def identify_ghost_categories(cats):
    """Ghost = categories whose parent chain contains UUID-like names (from path bug)."""
    id_to_cat = {c["id"]: c for c in cats}
    uuid_re = re.compile(r"^[a-f0-9]{8}-[a-f0-9]{4}")
    ghosts = []
    for c in cats:
        chain_names = []
        cur = c
        visited = set()
        while cur and cur["id"] not in visited:
            visited.add(cur["id"])
            chain_names.append(cur["name"])
            cur = id_to_cat.get(cur.get("parentId"))
        if any(uuid_re.match(n) for n in chain_names):
            ghosts.append(c["id"])
    return ghosts


def phase1_disable_ghosts(cats):
    """Rename ghost categories so they don't interfere with name matching."""
    ghost_ids = identify_ghost_categories(cats)
    if not ghost_ids:
        print("   Ghost kategori yok.")
        return 0

    print(f"   {len(ghost_ids)} ghost kategori devre disi birakilacak")
    disabled = 0
    for gid in ghost_ids:
        cat = next((c for c in cats if c["id"] == gid), None)
        if not cat:
            continue
        new_name = f"_SLINECEK_{cat['name']}_{gid[:8]}"
        if DRY_RUN:
            disabled += 1
            continue

        result = gql(
            """mutation U($input: UpdateCategoryInput!) { updateCategory(input: $input) { id name } }""",
            {"input": {"id": gid, "name": new_name}},
        )
        if result.get("_errors"):
            print(f"     X Rename hatasi: {cat['name'][:30]}: {result['_errors'][0].get('message','')[:60]}")
        else:
            disabled += 1
        time.sleep(0.3)

    print(f"   {disabled} ghost devre disi birakildi")
    return disabled


def phase2_fix_hierarchy(cats):
    """Fix parent-child relationships based on CSV hierarchy. Only changes parentId."""
    id_to_cat = {c["id"]: c for c in cats}
    name_to_cats = defaultdict(list)
    for c in cats:
        if not c["name"].startswith("_SLINECEK_"):
            name_to_cats[c["name"].strip()].append(c)

    # Parse CSV hierarchy
    expected_relations = set()
    with open(CSV_PATH, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            raw = row.get("Kategoriler", "").strip()
            for chain in raw.split(";"):
                parts = [p.strip() for p in chain.strip().split(">")]
                for i in range(1, len(parts)):
                    child = NAME_MAP.get(parts[i], parts[i])
                    parent = NAME_MAP.get(parts[i - 1], parts[i - 1])
                    expected_relations.add((child, parent))

    fixes = []
    for child_name, parent_name in expected_relations:
        child_cats = name_to_cats.get(child_name, [])
        parent_cats = name_to_cats.get(parent_name, [])
        if not child_cats or not parent_cats:
            continue

        parent_ids = {p["id"] for p in parent_cats}
        # Find root-level child that needs a parent
        for cc in child_cats:
            if not cc.get("parentId") and cc["id"] not in {f["child_id"] for f in fixes}:
                target_parent = parent_cats[0]["id"]
                for p in parent_cats:
                    if not p.get("parentId"):
                        target_parent = p["id"]
                        break
                fixes.append({
                    "child_id": cc["id"],
                    "child_name": cc["name"],
                    "parent_id": target_parent,
                    "parent_name": parent_name,
                })
                break

    print(f"   {len(fixes)} hiyerarsi duzeltmesi")
    if DRY_RUN:
        for f in fixes[:10]:
            print(f"     \"{f['child_name']}\" -> \"{f['parent_name']}\"")
        return len(fixes)

    done = 0
    for f in fixes:
        result = gql(
            """mutation U($input: UpdateCategoryInput!) { updateCategory(input: $input) { id } }""",
            {"input": {"id": f["child_id"], "parentId": f["parent_id"]}},
        )
        if result.get("_errors"):
            err = result["_errors"][0].get("message", "")
            if "duplicate" not in err.lower():
                print(f"     X {f['child_name']}: {err[:60]}")
        else:
            done += 1
        time.sleep(0.3)

    print(f"   {done} hiyerarsi duzeltildi")
    return done


def phase3_fix_products(cats):
    """Fix product-category assignments based on CSV. Only changes categories field."""
    id_to_cat = {c["id"]: c for c in cats}
    name_to_cats = defaultdict(list)
    for c in cats:
        if not c["name"].startswith("_SLINECEK_"):
            name_to_cats[c["name"].strip()].append(c)

    def resolve_id(cat_name, parent_name):
        mapped = NAME_MAP.get(cat_name, cat_name)
        mapped_parent = NAME_MAP.get(parent_name, parent_name) if parent_name else None
        cands = name_to_cats.get(mapped, [])
        if not cands:
            return None
        if len(cands) == 1:
            return cands[0]["id"]
        if mapped_parent:
            p_cands = name_to_cats.get(mapped_parent, [])
            p_ids = {p["id"] for p in p_cands}
            for c in cands:
                if c.get("parentId") in p_ids:
                    return c["id"]
        for c in cands:
            if not c.get("parentId"):
                return c["id"]
        return cands[0]["id"]

    # Parse CSV products
    csv_products = {}
    with open(CSV_PATH, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            gid = row.get("Ürün Grup ID", "").strip()
            raw = row.get("Kategoriler", "").strip()
            brand = row.get("Marka", "").strip()
            if not gid or not raw or gid in csv_products:
                continue
            expected_ids = set()
            for chain in raw.split(";"):
                parts = [p.strip() for p in chain.strip().split(">")]
                for i, part in enumerate(parts):
                    parent = parts[i - 1] if i > 0 else None
                    cid = resolve_id(part, parent)
                    if cid:
                        expected_ids.add(cid)
            csv_products[gid] = {"name": row.get("İsim", ""), "expected": expected_ids, "brand": brand}

    # Fetch all Ikas products
    all_ikas = {}
    page = 1
    while True:
        data = gql(
            """query L($p:Int!){ listProduct(pagination:{page:$p,limit:100}){
                data { id categories { id name } brand { name } } count } }""",
            {"p": page},
        )
        prods = data.get("listProduct", {})
        for p in prods.get("data", []):
            cat_ids = {c["id"] for c in (p.get("categories") or [])}
            # Filter out ghost categories
            cat_ids = {cid for cid in cat_ids if not (id_to_cat.get(cid, {}).get("name", "").startswith("_SLINECEK_"))}
            all_ikas[p["id"]] = {
                "cats": cat_ids,
                "brand": (p.get("brand") or {}).get("name", ""),
            }
        total = prods.get("count", 0)
        if page * 100 >= total:
            break
        page += 1
        time.sleep(0.2)

    # Compare
    needs_fix = []
    perfect = 0
    for gid, csv_data in csv_products.items():
        if gid not in all_ikas:
            continue
        ikas_data = all_ikas[gid]
        expected = csv_data["expected"]
        current = ikas_data["cats"]
        missing = expected - current
        if not missing:
            perfect += 1
            continue
        # Merge: keep current (non-ghost) + add missing
        merged_ids = current | expected
        merged_names = []
        for cid in merged_ids:
            cat = id_to_cat.get(cid)
            if cat and not cat["name"].startswith("_SLINECEK_"):
                merged_names.append(cat["name"])
        needs_fix.append({
            "id": gid,
            "name": csv_data["name"],
            "brand": csv_data.get("brand", ikas_data.get("brand", "")),
            "merged_names": list(set(merged_names)),
            "missing_count": len(missing),
        })

    print(f"   Dogru: {perfect}, Duzeltme gereken: {len(needs_fix)}")

    if DRY_RUN:
        for f in needs_fix[:10]:
            print(f"     {f['name'][:45]} (+{f['missing_count']} kategori)")
        return len(needs_fix)

    # Execute
    updated = 0
    failed = 0
    for i, fix in enumerate(needs_fix):
        cat_input = [{"name": n} for n in fix["merged_names"]]
        input_data = {"id": fix["id"], "categories": cat_input}
        if fix.get("brand"):
            input_data["brand"] = {"name": fix["brand"]}

        result = gql(
            """mutation U($input: UpdateProductInput!) { updateProduct(input: $input) { id } }""",
            {"input": input_data},
        )
        if result.get("_errors"):
            failed += 1
            if failed <= 5:
                print(f"     X {fix['name'][:40]}: {result['_errors'][0].get('message','')[:60]}")
        elif result.get("updateProduct"):
            updated += 1
        else:
            failed += 1

        time.sleep(0.3)
        if (i + 1) % 100 == 0 or (i + 1) == len(needs_fix):
            print(f"     Ilerleme: {i+1}/{len(needs_fix)} ({updated} OK, {failed} hata)")

    print(f"   {updated} urun duzeltildi, {failed} hata")
    return updated


def main():
    mode = "DRY-RUN" if DRY_RUN else "GERCEK GUNCELLEME"
    print(f"=== Ikas Kategori Tam Duzeltme ===")
    print(f"Mod: {mode}\n")

    # Load categories
    print("Kategoriler yukleniyor...")
    cats = load_ikas_categories()
    print(f"   {len(cats)} kategori")

    # Phase 1: Disable ghosts
    print("\nFAZ 1: Ghost kategorileri devre disi birak...")
    phase1_disable_ghosts(cats)

    # Reload after ghost rename
    if not DRY_RUN:
        cats = load_ikas_categories()

    # Phase 2: Fix hierarchy
    print("\nFAZ 2: Hiyerarsi duzelt (sadece parentId, aciklama/SEO korunur)...")
    phase2_fix_hierarchy(cats)

    # Phase 3: Fix products
    print("\nFAZ 3: Urun kategorilerini duzelt...")
    phase3_fix_products(cats)

    print("\n=== TAMAMLANDI ===")
    if DRY_RUN:
        print("Gercek guncelleme icin: python3 full_category_fix.py --execute")


if __name__ == "__main__":
    main()
