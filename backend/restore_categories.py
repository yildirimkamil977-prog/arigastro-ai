"""Category Restoration Script — Restores product-category assignments from Google Feed XML."""
import os
import requests
import xml.etree.ElementTree as ET
import time
import json

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
    
    # 1. Get İkas token
    token = get_ikas_token()
    print("✅ İkas token alındı")
    
    # 2. Get all İkas categories
    data = ikas_query(token, "{ listCategory { id name parentId } }")
    categories = data.get("listCategory", [])
    cat_name_to_id = {}
    for c in categories:
        cat_name_to_id[c["name"].strip()] = c["id"]
    print(f"✅ {len(categories)} kategori yüklendi")
    
    # 3. Download and parse Google Feed XML
    print(f"📥 Feed indiriliyor: {FEED_URL[:60]}...")
    resp = requests.get(FEED_URL, timeout=60)
    root = ET.fromstring(resp.content)
    ns = {"g": "http://base.google.com/ns/1.0", "atom": "http://www.w3.org/2005/Atom"}
    
    # Parse feed entries
    feed_products = {}
    for entry in root.findall(".//atom:entry", ns) or root.findall(".//{http://www.w3.org/2005/Atom}entry"):
        title_el = entry.find("{http://www.w3.org/2005/Atom}title")
        product_type_el = entry.find("{http://base.google.com/ns/1.0}product_type")
        gtin_el = entry.find("{http://base.google.com/ns/1.0}gtin")
        id_el = entry.find("{http://www.w3.org/2005/Atom}id")
        
        title = title_el.text.strip() if title_el is not None and title_el.text else ""
        product_type = product_type_el.text.strip() if product_type_el is not None and product_type_el.text else ""
        gtin = gtin_el.text.strip() if gtin_el is not None and gtin_el.text else ""
        
        if title and product_type:
            # Parse category hierarchy: "Ana Kategori > Alt Kategori > Alt Alt Kategori"
            cat_parts = [p.strip() for p in product_type.split(">")]
            feed_products[title] = {
                "categories": cat_parts,
                "gtin": gtin,
            }
    
    print(f"✅ Feed'den {len(feed_products)} ürün okundu")
    
    # 4. Get all İkas products with current categories
    print("📥 İkas ürünleri yükleniyor...")
    all_products = []
    page = 1
    while True:
        data = ikas_query(token, f'{{ listProduct(pagination: {{page: {page}, limit: 100}}) {{ data {{ id name categories {{ id name }} }} count }} }}')
        products = data.get("listProduct", {}).get("data", [])
        count = data.get("listProduct", {}).get("count", 0)
        all_products.extend(products)
        if page * 100 >= count:
            break
        page += 1
        time.sleep(0.5)
    print(f"✅ {len(all_products)} İkas ürünü yüklendi")
    
    # 5. Compare and find missing categories
    fixes_needed = []
    for ikas_prod in all_products:
        prod_name = ikas_prod["name"].strip()
        current_cats = {c["name"]: c["id"] for c in (ikas_prod.get("categories") or [])}
        
        # Find in feed
        feed_data = feed_products.get(prod_name)
        if not feed_data:
            continue
        
        # Find missing categories
        missing = []
        for cat_name in feed_data["categories"]:
            cat_name = cat_name.strip()
            if cat_name not in current_cats and cat_name in cat_name_to_id:
                missing.append({"name": cat_name, "id": cat_name_to_id[cat_name]})
        
        if missing:
            fixes_needed.append({
                "product_id": ikas_prod["id"],
                "product_name": prod_name,
                "current_cats": list(current_cats.keys()),
                "missing_cats": [m["name"] for m in missing],
                "all_cat_ids": [{"id": c["id"]} for c in (ikas_prod.get("categories") or [])] + [{"id": m["id"]} for m in missing]
            })
    
    print(f"\n🔍 {len(fixes_needed)} ürünün kategorisi eksik")
    
    if not fixes_needed:
        print("✅ Tüm ürünler doğru kategorilerde!")
        return
    
    # Show preview
    for f in fixes_needed[:10]:
        print(f"  {f['product_name'][:45]} | Eksik: {f['missing_cats']}")
    if len(fixes_needed) > 10:
        print(f"  ... ve {len(fixes_needed) - 10} ürün daha")
    
    # 6. Fix categories
    print(f"\n🔧 {len(fixes_needed)} ürün düzeltiliyor...")
    fixed = 0
    failed = 0
    for fix in fixes_needed:
        try:
            mutation = """mutation UpdateProduct($input: UpdateProductInput!) { 
                updateProduct(input: $input) { id name } 
            }"""
            variables = {"input": {
                "id": fix["product_id"],
                "categories": fix["all_cat_ids"]
            }}
            result = ikas_query(token, mutation, variables)
            if result.get("updateProduct"):
                fixed += 1
            else:
                failed += 1
                print(f"  ❌ {fix['product_name'][:40]}: {result}")
        except Exception as e:
            failed += 1
            print(f"  ❌ {fix['product_name'][:40]}: {e}")
        
        time.sleep(1)  # Rate limit
        
        if (fixed + failed) % 50 == 0:
            print(f"  İlerleme: {fixed} düzeltildi, {failed} başarısız / {len(fixes_needed)} toplam")
    
    print(f"\n✅ TAMAMLANDI: {fixed} düzeltildi, {failed} başarısız")

if __name__ == "__main__":
    main()
