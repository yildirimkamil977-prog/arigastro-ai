"""Category Restoration Script — Restores product-category assignments from Google Feed XML."""
import os
import requests
import xml.etree.ElementTree as ET
import time

IKAS_CLIENT_ID = os.environ.get("IKAS_CLIENT_ID")
IKAS_CLIENT_SECRET = os.environ.get("IKAS_CLIENT_SECRET")
FEED_URL = os.environ.get("FEED_URL")

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

def main():
    print("=== Kategori Kurtarma Scripti ===\n")
    
    token = get_ikas_token()
    print("✅ İkas token alındı")
    
    # 1. Get all İkas categories
    data = ikas_query(token, "{ listCategory { id name parentId } }")
    categories = data.get("listCategory", [])
    cat_name_to_id = {}
    for c in categories:
        cat_name_to_id[c["name"].strip()] = c["id"]
    print(f"✅ {len(categories)} kategori yüklendi")
    
    # 2. Download and parse Google Feed XML (RSS 2.0 format)
    print(f"📥 Feed indiriliyor...")
    resp = requests.get(FEED_URL, timeout=120)
    root = ET.fromstring(resp.content)
    ns = "http://base.google.com/ns/1.0"
    
    feed_products = {}
    for item in root.findall(".//item"):
        title_el = item.find(f"{{{ns}}}title")
        product_type_el = item.find(f"{{{ns}}}product_type")
        
        title = title_el.text.strip() if title_el is not None and title_el.text else ""
        product_type = product_type_el.text.strip() if product_type_el is not None and product_type_el.text else ""
        
        if title and product_type:
            cat_parts = [p.strip() for p in product_type.split(",")]
            feed_products[title] = cat_parts
    
    print(f"✅ Feed'den {len(feed_products)} ürün okundu")
    
    # 3. Get all İkas products with current categories
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
    print(f"✅ {len(all_products)} İkas ürünü yüklendi")
    
    # 4. Compare and find missing categories
    fixes_needed = []
    for ikas_prod in all_products:
        prod_name = ikas_prod["name"].strip()
        current_cats = {c["name"].strip(): c["id"] for c in (ikas_prod.get("categories") or [])}
        
        feed_cats = feed_products.get(prod_name, [])
        if not feed_cats:
            continue
        
        missing = []
        for cat_name in feed_cats:
            if cat_name not in current_cats and cat_name in cat_name_to_id:
                missing.append({"name": cat_name, "id": cat_name_to_id[cat_name]})
        
        if missing:
            all_cat_ids = [{"id": c["id"]} for c in (ikas_prod.get("categories") or [])]
            all_cat_ids += [{"id": m["id"]} for m in missing]
            fixes_needed.append({
                "product_id": ikas_prod["id"],
                "product_name": prod_name,
                "current": list(current_cats.keys()),
                "missing": [m["name"] for m in missing],
                "all_cat_ids": all_cat_ids,
            })
    
    print(f"\n🔍 {len(fixes_needed)} ürünün kategorisi eksik")
    
    if not fixes_needed:
        print("✅ Tüm ürünler doğru kategorilerde!")
        return
    
    for f in fixes_needed[:10]:
        print(f"  {f['product_name'][:40]} | Mevcut: {f['current']} | Eksik: {f['missing']}")
    if len(fixes_needed) > 10:
        print(f"  ... ve {len(fixes_needed) - 10} ürün daha")
    
    # 5. Fix categories
    print(f"\n🔧 {len(fixes_needed)} ürün düzeltiliyor...")
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
        if (fixed + failed) % 50 == 0:
            print(f"  İlerleme: {fixed}/{len(fixes_needed)} düzeltildi")
    
    print(f"\n✅ TAMAMLANDI: {fixed} düzeltildi, {failed} başarısız")

if __name__ == "__main__":
    main()
