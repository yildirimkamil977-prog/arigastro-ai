"""Category Restoration Script v3 — Uses category NAMES (not IDs) as İkas requires."""
import os
import requests
import time

IKAS_CLIENT_ID = os.environ.get("IKAS_CLIENT_ID")
IKAS_CLIENT_SECRET = os.environ.get("IKAS_CLIENT_SECRET")

def get_ikas_token():
    resp = requests.post("https://api.myikas.com/api/admin/oauth/token", json={
        "grant_type": "client_credentials",
        "client_id": IKAS_CLIENT_ID,
        "client_secret": IKAS_CLIENT_SECRET,
    })
    return resp.json()["access_token"]

def ikas_query(token, query, variables=None):
    resp = requests.post("https://api.myikas.com/api/v2/admin/graphql",
        json={"query": query, "variables": variables or {}},
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    data = resp.json()
    if data.get("errors"):
        return {"_errors": data["errors"]}
    return data.get("data", {})

def get_all_parent_ids(cat_id, parent_map):
    parents = []
    current = cat_id
    seen = set()
    while current in parent_map and current not in seen:
        seen.add(current)
        parent_id = parent_map[current]
        if parent_id:
            parents.append(parent_id)
            current = parent_id
        else:
            break
    return parents

def main():
    print("=== Kategori Kurtarma v3 ===\n")
    
    token = get_ikas_token()
    print("✅ İkas token alındı")
    
    # 1. Get all categories
    data = ikas_query(token, "{ listCategory { id name parentId } }")
    categories = data.get("listCategory", [])
    cat_id_to_name = {c["id"]: c["name"] for c in categories}
    parent_map = {c["id"]: c.get("parentId") for c in categories}
    print(f"✅ {len(categories)} kategori yüklendi")
    
    # 2. Get all products
    print("📥 İkas ürünleri yükleniyor...")
    all_products = []
    page = 1
    while True:
        data = ikas_query(token, f'{{ listProduct(pagination: {{page: {page}, limit: 100}}) {{ data {{ id name categories {{ id name }} }} count }} }}')
        prods = data.get("listProduct", {})
        all_products.extend(prods.get("data", []))
        if page * 100 >= prods.get("count", 0):
            break
        page += 1
        time.sleep(0.3)
    print(f"✅ {len(all_products)} ürün yüklendi")
    
    # 3. Find products missing parent categories
    fixes_needed = []
    for prod in all_products:
        current_cat_ids = set(c["id"] for c in (prod.get("categories") or []))
        current_cat_names = set(c["name"] for c in (prod.get("categories") or []))
        if not current_cat_ids:
            continue
        
        needed_parent_names = set()
        for cat_id in current_cat_ids:
            for pid in get_all_parent_ids(cat_id, parent_map):
                if pid not in current_cat_ids:
                    pname = cat_id_to_name.get(pid, "")
                    if pname:
                        needed_parent_names.add(pname)
        
        if needed_parent_names:
            all_names = list(current_cat_names | needed_parent_names)
            fixes_needed.append({
                "product_id": prod["id"],
                "product_name": prod["name"],
                "missing": list(needed_parent_names),
                "all_cat_names": [{"name": n} for n in all_names],
            })
    
    print(f"\n🔍 {len(fixes_needed)} ürünün üst kategorisi eksik")
    
    if not fixes_needed:
        print("✅ Tüm ürünler doğru!")
        return
    
    for f in fixes_needed[:10]:
        print(f"  {f['product_name'][:40]} | Eksik: {f['missing']}")
    if len(fixes_needed) > 10:
        print(f"  ... ve {len(fixes_needed) - 10} ürün daha")
    
    # 4. Fix
    print(f"\n🔧 {len(fixes_needed)} ürün düzeltiliyor...")
    fixed = 0
    failed = 0
    for fix in fixes_needed:
        try:
            result = ikas_query(token,
                "mutation UpdateProduct($input: UpdateProductInput!) { updateProduct(input: $input) { id } }",
                {"input": {"id": fix["product_id"], "categories": fix["all_cat_names"]}}
            )
            if result.get("_errors"):
                failed += 1
                if failed <= 3:
                    print(f"  ❌ {fix['product_name'][:30]}: {result['_errors'][0]['message'][:80]}")
            elif result.get("updateProduct"):
                fixed += 1
            else:
                failed += 1
        except Exception as e:
            failed += 1
        
        time.sleep(0.5)
        if (fixed + failed) % 50 == 0:
            print(f"  İlerleme: {fixed}/{len(fixes_needed)} düzeltildi, {failed} başarısız")
    
    print(f"\n✅ TAMAMLANDI: {fixed} düzeltildi, {failed} başarısız")

if __name__ == "__main__":
    main()
