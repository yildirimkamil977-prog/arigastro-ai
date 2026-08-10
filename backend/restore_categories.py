"""Category Restoration Script v2 — Assigns products to parent categories based on hierarchy."""
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
    return resp.json().get("data", {})

def get_all_parent_ids(cat_id, parent_map):
    """Get all parent category IDs up the hierarchy."""
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
    print("=== Kategori Kurtarma v2 — Üst Kategori Ataması ===\n")
    
    token = get_ikas_token()
    print("✅ İkas token alındı")
    
    # 1. Get all categories with parent info
    data = ikas_query(token, "{ listCategory { id name parentId } }")
    categories = data.get("listCategory", [])
    cat_id_to_name = {c["id"]: c["name"] for c in categories}
    parent_map = {c["id"]: c.get("parentId") for c in categories}
    print(f"✅ {len(categories)} kategori yüklendi")
    
    # Show hierarchy
    root_cats = [c for c in categories if not c.get("parentId")]
    child_cats = [c for c in categories if c.get("parentId")]
    print(f"   Üst kategoriler: {len(root_cats)}, Alt kategoriler: {len(child_cats)}")
    
    # 2. Get all products with current categories
    print("📥 İkas ürünleri yükleniyor...")
    all_products = []
    page = 1
    while True:
        data = ikas_query(token, f'{{ listProduct(pagination: {{page: {page}, limit: 100}}) {{ data {{ id name categories {{ id name }} }} count }} }}')
        prods = data.get("listProduct", {})
        all_products.extend(prods.get("data", []))
        total_count = prods.get("count", 0)
        if page * 100 >= total_count:
            break
        page += 1
        time.sleep(0.3)
    print(f"✅ {len(all_products)} İkas ürünü yüklendi")
    
    # 3. For each product, check if parent categories are missing
    fixes_needed = []
    for prod in all_products:
        current_cat_ids = set(c["id"] for c in (prod.get("categories") or []))
        if not current_cat_ids:
            continue
        
        # Find all parent categories that should be assigned
        needed_parents = set()
        for cat_id in current_cat_ids:
            parent_ids = get_all_parent_ids(cat_id, parent_map)
            for pid in parent_ids:
                if pid not in current_cat_ids:
                    needed_parents.add(pid)
        
        if needed_parents:
            all_ids = list(current_cat_ids | needed_parents)
            fixes_needed.append({
                "product_id": prod["id"],
                "product_name": prod["name"],
                "current_cats": [cat_id_to_name.get(cid, cid) for cid in current_cat_ids],
                "missing_parents": [cat_id_to_name.get(pid, pid) for pid in needed_parents],
                "all_cat_ids": [{"id": cid} for cid in all_ids],
            })
    
    print(f"\n🔍 {len(fixes_needed)} ürünün üst kategorisi eksik")
    
    if not fixes_needed:
        print("✅ Tüm ürünler üst kategorilerine de atanmış!")
        return
    
    # Show preview
    for f in fixes_needed[:10]:
        print(f"  {f['product_name'][:40]} | Eksik üst: {f['missing_parents']}")
    if len(fixes_needed) > 10:
        print(f"  ... ve {len(fixes_needed) - 10} ürün daha")
    
    # 4. Ask for confirmation
    print(f"\n⚠️  {len(fixes_needed)} ürün düzeltilecek. Devam ediliyor...")
    
    # 5. Fix categories
    fixed = 0
    failed = 0
    for fix in fixes_needed:
        try:
            result = ikas_query(token,
                "mutation UpdateProduct($input: UpdateProductInput!) { updateProduct(input: $input) { id } }",
                {"input": {"id": fix["product_id"], "categories": fix["all_cat_ids"]}}
            )
            if result.get("updateProduct"):
                fixed += 1
            else:
                failed += 1
        except Exception as e:
            failed += 1
            print(f"  ❌ {fix['product_name'][:40]}: {e}")
        
        time.sleep(0.5)
        if (fixed + failed) % 100 == 0:
            print(f"  İlerleme: {fixed}/{len(fixes_needed)} düzeltildi, {failed} başarısız")
    
    print(f"\n✅ TAMAMLANDI: {fixed} düzeltildi, {failed} başarısız")

if __name__ == "__main__":
    main()
