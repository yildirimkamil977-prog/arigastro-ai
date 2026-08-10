"""Category Restoration Script v4 — Restores from İkas CSV export with full hierarchy."""
import os
import csv
import requests
import time

IKAS_CLIENT_ID = os.environ.get("IKAS_CLIENT_ID")
IKAS_CLIENT_SECRET = os.environ.get("IKAS_CLIENT_SECRET")
CSV_PATH = "/tmp/ikas.csv"

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

def main():
    print("=== Kategori Kurtarma v4 — İkas CSV'den ===\n")
    
    token = get_ikas_token()
    print("✅ İkas token alındı")
    
    # 1. Get all İkas categories (to validate names)
    data = ikas_query(token, "{ listCategory { id name } }")
    ikas_categories = set(c["name"].strip() for c in data.get("listCategory", []))
    print(f"✅ İkas'ta {len(ikas_categories)} kategori mevcut")
    
    # 2. Parse CSV — build product_group_id → required categories mapping
    csv_data = {}
    with open(CSV_PATH, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            group_id = row.get("Ürün Grup ID", "").strip()
            name = row.get("İsim", "").strip()
            cats_raw = row.get("Kategoriler", "").strip()
            
            if not group_id or not cats_raw:
                continue
            
            # Split hierarchy: "A>B>C" means product should be in A, B, AND C
            required_cats = set()
            for cat_path in cats_raw.split(","):
                parts = [p.strip() for p in cat_path.strip().split(">")]
                for part in parts:
                    if part and part in ikas_categories:
                        required_cats.add(part)
            
            # Only keep first variant per product group
            if group_id not in csv_data:
                csv_data[group_id] = {
                    "name": name,
                    "required_cats": required_cats,
                }
    
    print(f"✅ CSV'den {len(csv_data)} benzersiz ürün okundu")
    
    # 3. Get all current İkas products with categories
    print("📥 İkas ürünleri yükleniyor...")
    all_products = []
    page = 1
    while True:
        data = ikas_query(token, f'{{ listProduct(pagination: {{page: {page}, limit: 100}}) {{ data {{ id name categories {{ id name }} }} count }} }}')
        prods = data.get("listProduct", {})
        all_products.extend(prods.get("data", []))
        total = prods.get("count", 0)
        if page * 100 >= total:
            break
        page += 1
        time.sleep(0.3)
    print(f"✅ Sitede {len(all_products)} ürün mevcut")
    
    # 4. Compare and find products with missing categories
    fixes_needed = []
    not_in_csv = 0
    already_ok = 0
    
    for prod in all_products:
        prod_name = prod["name"].strip()
        current_cats = set(c["name"].strip() for c in (prod.get("categories") or []))
        
        # Find in CSV by name (since product IDs might differ)
        csv_entry = None
        for gid, entry in csv_data.items():
            if entry["name"] == prod_name:
                csv_entry = entry
                break
        
        if not csv_entry:
            not_in_csv += 1
            continue
        
        # Find missing categories
        missing = csv_entry["required_cats"] - current_cats
        
        if not missing:
            already_ok += 1
            continue
        
        # Combine current + missing
        all_cat_names = list(current_cats | csv_entry["required_cats"])
        fixes_needed.append({
            "product_id": prod["id"],
            "product_name": prod_name,
            "current": list(current_cats),
            "missing": list(missing),
            "all_cats": [{"name": n} for n in all_cat_names],
        })
    
    print(f"\n📊 Sonuç:")
    print(f"   ✅ Kategorileri doğru: {already_ok}")
    print(f"   ⚠️  Kategorisi eksik: {len(fixes_needed)}")
    print(f"   ℹ️  CSV'de bulunamayan: {not_in_csv}")
    
    if not fixes_needed:
        print("\n✅ Tüm ürünler doğru kategorilerde!")
        return
    
    # Preview
    print(f"\nÖnizleme (ilk 15):")
    for f in fixes_needed[:15]:
        print(f"  {f['product_name'][:40]} | Eksik: {f['missing']}")
    if len(fixes_needed) > 15:
        print(f"  ... ve {len(fixes_needed) - 15} ürün daha")
    
    # 5. Fix categories
    print(f"\n🔧 {len(fixes_needed)} ürün düzeltiliyor (SADECE kategori, başka hiçbir şey değişmiyor)...")
    fixed = 0
    failed = 0
    for fix in fixes_needed:
        try:
            result = ikas_query(token,
                "mutation UpdateProduct($input: UpdateProductInput!) { updateProduct(input: $input) { id } }",
                {"input": {"id": fix["product_id"], "categories": fix["all_cats"]}}
            )
            if result.get("_errors"):
                failed += 1
                if failed <= 5:
                    print(f"  ❌ {fix['product_name'][:30]}: {result['_errors'][0].get('message','')[:80]}")
            elif result.get("updateProduct"):
                fixed += 1
            else:
                failed += 1
        except Exception as e:
            failed += 1
        
        time.sleep(0.5)
        if (fixed + failed) % 100 == 0:
            print(f"  İlerleme: {fixed}/{len(fixes_needed)} düzeltildi, {failed} başarısız")
    
    print(f"\n✅ TAMAMLANDI: {fixed} düzeltildi, {failed} başarısız")

if __name__ == "__main__":
    main()
