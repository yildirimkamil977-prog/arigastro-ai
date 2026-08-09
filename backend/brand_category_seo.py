"""Brand & Category SEO — Competitor analysis + AI content generation."""
import os
import re
import json
import logging
import asyncio
import requests as req_sync
from datetime import datetime, timezone

logger = logging.getLogger("brand_category_seo")

SCRAPERAPI_KEY = os.environ.get("SCRAPERAPI_KEY", "")
TR_TO_ASCII = str.maketrans("ıİşŞğĞüÜöÖçÇ", "iIsSgGuUoOcC")


def build_image_tag(image_url: str, alt: str) -> str:
    if not image_url:
        return ""
    return f'<img src="{image_url}" alt="{alt}" style="max-width:100%;height:auto;border-radius:8px;margin:16px 0;" />'


def _is_product_image(src: str, alt: str) -> bool:
    EXCLUDE_WORDS = ["logo", "qr kod", "qr code", "arigato", "favicon", "icon", "banner", "slider", "payment", "cargo", "kargo", "whatsapp", "freeship", "ucretsiz"]
    if not src:
        return False
    if "cdn.myikas.com/images/" not in src:
        return False
    if "theme-images" in src:
        return False
    alt_lower = alt.lower() if alt else ""
    if any(ex in alt_lower for ex in EXCLUDE_WORDS):
        return False
    if any(ex in src.lower() for ex in EXCLUDE_WORDS):
        return False
    if len(alt) < 10:
        return False
    return True


def _scrape_google_serp_sync(keyword: str) -> list:
    """Search Google Turkey using ScraperAPI structured endpoint (sync)."""
    if not SCRAPERAPI_KEY:
        return []
    ascii_keyword = keyword.translate(TR_TO_ASCII)
    logger.info(f"SERP query: '{keyword}' -> '{ascii_keyword}'")
    try:
        resp = req_sync.get("https://api.scraperapi.com/structured/google/search", params={
            "api_key": SCRAPERAPI_KEY,
            "query": ascii_keyword,
            "country_code": "tr",
            "tld": "com.tr",
            "num": "10",
        }, timeout=30)
        if resp.status_code != 200:
            logger.warning(f"SERP API returned {resp.status_code}")
            return []
        data = resp.json()
        results = []
        for item in data.get("organic_results", []):
            url = item.get("link", "")
            title = item.get("title", "")
            snippet = item.get("snippet", "")
            if url and title:
                results.append({"title": title, "url": url, "description": snippet})
        logger.info(f"SERP results for '{keyword}': {len(results)} found")
        return results
    except Exception as e:
        logger.error(f"SERP error: {e}")
        return []


def _scrape_url_sync(url: str) -> dict:
    """Scrape URL and extract key SEO elements (sync)."""
    from bs4 import BeautifulSoup
    if not SCRAPERAPI_KEY:
        return {"error": "ScraperAPI key missing"}
    try:
        resp = req_sync.get("http://api.scraperapi.com", params={
            "api_key": SCRAPERAPI_KEY, "url": url, "render": "true",
        }, timeout=30)
        if resp.status_code != 200:
            return {"error": f"HTTP {resp.status_code}"}
        soup = BeautifulSoup(resp.text, "html.parser")
        title = soup.title.string.strip() if soup.title and soup.title.string else ""
        meta_desc = ""
        mt = soup.find("meta", attrs={"name": "description"})
        if mt:
            meta_desc = mt.get("content", "")
        h1s = [h.get_text(strip=True) for h in soup.find_all("h1")][:3]
        h2s = [h.get_text(strip=True) for h in soup.find_all("h2")][:10]
        body = soup.find("body")
        body_text = body.get_text(" ", strip=True) if body else ""
        word_count = len(body_text.split())
        lists = len(soup.find_all(["ul", "ol"]))
        tables = len(soup.find_all("table"))
        return {
            "url": url, "title": title[:200], "meta_description": meta_desc[:300],
            "h1": h1s, "h2": h2s, "word_count": word_count,
            "has_lists": lists > 0, "list_count": lists,
            "has_tables": tables > 0, "table_count": tables,
            "body_text": body_text[:3000],
        }
    except Exception as e:
        return {"url": url, "error": str(e)}


def _get_product_images_sync(product_names: list, entity_name: str = "", site_domain: str = "arigastro.com") -> list:
    """Get real product image URLs by scraping the site (sync)."""
    from bs4 import BeautifulSoup
    images = []
    try:
        if SCRAPERAPI_KEY and entity_name:
            slug = entity_name.lower()
            for old, new in [("ö","o"),("ü","u"),("ş","s"),("ç","c"),("ğ","g"),("ı","i"),(" ","-")]:
                slug = slug.replace(old, new)
            cat_url = f"https://{site_domain}/{slug}"
            resp = req_sync.get("http://api.scraperapi.com", params={
                "api_key": SCRAPERAPI_KEY, "url": cat_url, "render": "true"
            }, timeout=30)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                for img in soup.find_all("img"):
                    src = img.get("src", "") or img.get("data-src", "")
                    alt = (img.get("alt", "") or "").strip()
                    if _is_product_image(src, alt) and src not in [i["url"] for i in images]:
                        images.append({"url": src, "alt": alt, "product_name": alt})
                    if len(images) >= 4:
                        break
                logger.info(f"Category page {cat_url}: {len(images)} product images found")
    except Exception as e:
        logger.warning(f"Product image scrape error: {e}")
    return images


def calc_keyword_density(text: str, keyword: str) -> float:
    if not text or not keyword:
        return 0
    words = text.lower().split()
    kw_words = keyword.lower().split()
    total = len(words)
    if total == 0:
        return 0
    count = 0
    for i in range(len(words) - len(kw_words) + 1):
        if words[i:i+len(kw_words)] == kw_words:
            count += 1
    return round((count * len(kw_words) / total) * 100, 2)


async def analyze_competitors(name: str, entity_type: str = "category") -> dict:
    """Full competitor analysis: Google SERP + scrape top 5 sites."""
    search_query = f"{name} endüstriyel mutfak" if entity_type == "brand" else name
    loop = asyncio.get_event_loop()

    serp_results = await loop.run_in_executor(None, _scrape_google_serp_sync, search_query)

    excluded_domains = ["sahibinden.com", "hepsiburada.com", "trendyol.com", "n11.com", "gittigidiyor.com", "amazon.com", "ciceksepeti.com"]
    competitors = [r for r in serp_results if "arigastro" not in r.get("url", "") and not any(d in r.get("url", "") for d in excluded_domains)]
    our_result = [r for r in serp_results if "arigastro" in r.get("url", "")]

    scraped = []
    for comp in competitors[:10]:
        if len(scraped) >= 5:
            break
        page_data = await loop.run_in_executor(None, _scrape_url_sync, comp["url"])
        if "error" not in page_data:
            page_data["serp_title"] = comp.get("title", "")
            page_data["serp_description"] = comp.get("description", "")
            page_data["keyword_density"] = calc_keyword_density(page_data.get("body_text", ""), name)
            scraped.append(page_data)
        await asyncio.sleep(0.3)

    our_page = None
    if our_result:
        our_page = await loop.run_in_executor(None, _scrape_url_sync, our_result[0]["url"])

    avg_word_count = round(sum(s.get("word_count", 0) for s in scraped) / max(len(scraped), 1)) if scraped else 800
    non_zero_densities = [s.get("keyword_density", 0) for s in scraped if s.get("keyword_density", 0) > 0]
    avg_density = round(sum(non_zero_densities) / max(len(non_zero_densities), 1), 2) if non_zero_densities else 1.2
    uses_lists = sum(1 for s in scraped if s.get("has_lists")) if scraped else 3
    uses_tables = sum(1 for s in scraped if s.get("has_tables")) if scraped else 1

    common_h2s = []
    for s in scraped:
        common_h2s.extend(s.get("h2", []))

    return {
        "search_query": search_query,
        "competitors_scraped": len(scraped),
        "serp_position": next((i + 1 for i, r in enumerate(serp_results) if "arigastro" in r.get("url", "")), None),
        "our_page": our_page,
        "competitor_pages": scraped,
        "averages": {
            "word_count": avg_word_count,
            "keyword_density": avg_density,
            "uses_lists_pct": round(uses_lists / max(len(scraped), 1) * 100) if scraped else 80,
            "uses_tables_pct": round(uses_tables / max(len(scraped), 1) * 100) if scraped else 40,
        },
        "competitor_titles": [s.get("serp_title", "") for s in scraped],
        "competitor_descriptions": [s.get("serp_description", "") for s in scraped],
        "competitor_h2s": list(set(common_h2s))[:15],
    }


async def get_product_images(product_names: list, entity_name: str = "") -> list:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _get_product_images_sync, product_names, entity_name)


async def generate_content(
    name: str, entity_type: str, entity_id: str,
    analysis: dict, product_images: list, our_site_data: dict,
    openai_key: str, internal_links: dict = None,
    real_products: list = None, real_brands: list = None
) -> dict:
    """Generate SEO content using AI based on competitor analysis."""
    from emergentintegrations.llm.chat import LlmChat, UserMessage

    avg = analysis.get("averages", {})
    target_words = max(avg.get("word_count", 1200) + 300, 1200)
    target_density = avg.get("keyword_density", 1.2)
    use_tables = avg.get("uses_tables_pct", 0) > 30

    image_html_parts = []
    for img in product_images[:4]:
        tag = build_image_tag(img.get("url", ""), img.get("alt", name))
        if tag:
            image_html_parts.append({"html": tag, "product_name": img.get("product_name", "")})

    links_instruction = ""
    if internal_links:
        children = internal_links.get("children", [])
        siblings = internal_links.get("siblings", [])
        parent = internal_links.get("parent_name", "")
        links_instruction = "\n\nSİTE İÇİ LİNKLEME (ZORUNLU — en az 3-5 link olmalı):\n"
        if children:
            links_instruction += "\nAlt kategoriler (MUTLAKA hepsine link ver):\n"
            for ch in children[:8]:
                slug = ch.lower().replace(" ", "-").replace("ı", "i").replace("ö", "o").replace("ü", "u").replace("ş", "s").replace("ç", "c").replace("ğ", "g")
                links_instruction += f'- {ch}: https://arigastro.com/{slug}\n'
        if parent:
            parent_slug = parent.lower().replace(" ", "-").replace("ı", "i").replace("ö", "o").replace("ü", "u").replace("ş", "s").replace("ç", "c").replace("ğ", "g")
            links_instruction += f'\nÜst kategori: {parent}: https://arigastro.com/{parent_slug}\n'
        if siblings:
            links_instruction += "\nİlgili kategoriler (en az 2-3 tanesine link ver):\n"
            for sib in siblings[:5]:
                slug = sib.lower().replace(" ", "-").replace("ı", "i").replace("ö", "o").replace("ü", "u").replace("ş", "s").replace("ç", "c").replace("ğ", "g")
                links_instruction += f'- {sib}: https://arigastro.com/{slug}\n'
        links_instruction += '\nLinkler <a href="URL">doğal anchor metin</a> formatında olsun.\n'

    entity_label = "marka" if entity_type == "brand" else "kategori"

    # Build product/brand context
    products_text = ""
    if real_products:
        products_text = "\n".join(f"- {p}" for p in real_products[:15])
    brands_text = ""
    if real_brands:
        brands_text = ", ".join(real_brands)

    if entity_type == "brand":
        title_example = f'"{name} Endüstriyel Mutfak Ürünleri | Arıgastro"'
        title_format_rule = f'Marka title formatı: "{{Marka Adı}} Endüstriyel Mutfak Ürünleri | Arıgastro"'
    else:
        title_example = f'"{name} Modelleri ve Fiyatları | Arıgastro"'
        title_format_rule = f'Kategori title formatı: "{{Kategori Adı}} Modelleri ve Fiyatları | Arıgastro"'

    system_prompt = f"""Sen Türkiye'nin en deneyimli e-ticaret SEO içerik uzmanısın. Arıgastro.com (endüstriyel mutfak ekipmanları) için "{name}" {entity_label} sayfası üretiyorsun.

## FİRMA BİLGİSİ:
Arıgastro, endüstriyel mutfak ekipmanları satıcısıdır. Müşteri kitlesi: kafe, restoran, otel, kiralık villa, pizzacı, dönerci, pastane, fırın, catering firmaları ve toplu yemek üretim tesisleri gibi İŞLETMELERdir. Bireysel/ev kullanıcıları DEĞİL.

## MUTLAK KURALLAR:

### ÜRÜN VE MARKA BİLGİLERİ (EN KRİTİK KURAL):
- Arıgastro'da satılan GERÇEK markalar YALNIZCA şunlardır: {brands_text if brands_text else 'Bilgi verilmedi — marka adı UYDURMA'}
- ASLA Arıgastro'da OLMAYAN bir marka adı yazma (örn: Bosch, Siemens, Samsung gibi)
- ASLA uydurma ürün modeli yazma
- Marka/ürün ismi verilmemişse, genel ifadeler kullan

### ÖDEME VE KARGO BİLGİLERİ (KRİTİK):
- ASLA "kapıda ödeme", "taksit imkanı", "ücretsiz kargo" gibi belirli ödeme/kargo vaatleri YAZMA — bunların doğruluğunu bilemezsin
- Bunun yerine şunu yaz: "Detaylı bilgi ve güncel kampanyalar için Arıgastro.com'u ziyaret edin"
- Genel ifade kullan: "uygun ödeme seçenekleri", "hızlı teslimat"

### TITLE (MAKSİMUM 60 KARAKTER):
- {title_format_rule}
- Örnek: {title_example}
- "Arıgastro" (ı harfi ile) MUTLAKA olmalı
- "Avantajları" kelimesi YASAK

### DESCRIPTION (MAKSİMUM 150 KARAKTER):
- "Arıgastro" ve "{name}" MUTLAKA olmalı
- Tam cümle, yarım bırakma

### İÇERİK KALİTESİ:
- MİNİMUM {target_words} kelime — bu çok önemli, kısa yazı KABUL EDİLMEZ
- Her bölüm en az 3-4 paragraf olmalı
- Anahtar kelime yoğunluğu ~%{target_density}
- Rakip sitelerden daha UZUN ve KAPSAMLI olmalı
- E-ticaret ve işletme odaklı yaz — hedef kitle işletme sahipleri

### HTML YAPISI:
- H1 KULLANMA
- <h2>, <h3>, <p>, <ul>, <li>, <strong>, <a href> kullan

### YASAKLI BAŞLIKLAR (ASLA KULLANMA):
- "Giriş", "Kapanış", "Sonuç", "Sonuç / CTA", "CTA", "FAQ", "Genel Bakış" gibi başlıklar YASAK
- Her başlık konuya özel ve SEO anahtar kelime içermeli
- Başlıklar insanların Google'da aradığı ifadeler olmalı

### GÖRSEL YERLEŞİMİ:
- İçeriğin HTML kodunda şu placeholder'ları MUTLAKA yerleştir: [GORSEL_1], [GORSEL_2], [GORSEL_3], [GORSEL_4]
- Placeholder'lar kendi satırında, </p> etiketinden sonra olmalı
- Örnek: <p>...metin...</p>\n[GORSEL_1]\n<h2>...başlık...</h2>
- EN AZ 3 placeholder ZORUNLU

### İÇERİK YAPISI VE ALT BAŞLIKLAR:
Alt başlıklar insanların Google'da aradığı ikincil anahtar kelimeleri hedeflemeli. Örneğin "{name}" kategorisi için:
- "{name} fiyatları" — fiyat aralığı hakkında (rakam vermeden)
- "{name} modelleri" — çeşitler ve farklı tipler
- "İşletme için {name} seçimi" — işletme tipine göre rehber
- "{name} teknik özellikleri" — kapasite, güç, boyut karşılaştırma

Yapı:
1. Açılış paragrafı (başlık YOK, direkt paragrafla başla, {name} anahtar kelimesi ilk cümlede) ardından [GORSEL_1]
2. <h2>{name} Nedir ve Neden Önemlidir?</h2>
3. <h2>{name} Modelleri ve Çeşitleri</h2> — GERÇEK ürün isimleriyle, ardından [GORSEL_2]
4. <h2>{name} Fiyatları ve Fiyat Karşılaştırması</h2> — fiyat RAKAMI vermeden genel bilgi
5. <h2>İşletmeniz İçin {name} Seçim Rehberi</h2> — kapasite, malzeme, enerji, ardından [GORSEL_3]
6. <h2>Arıgastro'da {name} Satın Almanın Avantajları</h2>
7. <h2>{name} Hakkında Sıkça Sorulan Sorular</h2> — en az 5 soru (<h3>), ardından [GORSEL_4]
8. Kapanış paragrafı (başlık YOK, direkt paragrafla bitir)
{'9. Ürün karşılaştırma tablosu' if use_tables else ''}
{links_instruction}

## JSON FORMATI:
{{"title": "...", "description": "...", "content": "<h2>...</h2><p>...</p>...", "generation_notes": "Analiz özeti..."}}

## SON HATIRLATMALAR:
- MİNİMUM {target_words} kelime
- SADECE verilen gerçek ürün ve markaları kullan
- Tüm metin TÜRKÇE karakterlerle
- "Arıgastro" her zaman ı harfi ile
- İçerikte EN AZ 3 adet [GORSEL_1], [GORSEL_2], [GORSEL_3] placeholder'ı OLMALI
- "Giriş", "Kapanış", "Sonuç" başlıkları YASAK
- Kapıda ödeme, ücretsiz kargo gibi vaatler YAZMA
- İlk ve son bölümde başlık yok, direkt paragraf"""

    chat = LlmChat(
        api_key=openai_key,
        session_id=f"bc-seo-{entity_type}-{name[:15]}",
        system_message=system_prompt
    ).with_model("openai", "gpt-4o")

    # Build comprehensive data text
    data_text = f'## HEDEF: "{name}" ({entity_label})\n\n'

    # Real products from İkas
    if real_products:
        data_text += f"## GERÇEK ÜRÜNLER (Arıgastro'da satılan — SADECE bunları kullan):\n{products_text}\n\n"
    if real_brands:
        data_text += f"## GERÇEK MARKALAR (Arıgastro'da satılan — SADECE bunları kullan):\n{brands_text}\n\n"

    # Our site data
    if our_site_data and our_site_data.get("body_excerpt"):
        data_text += f"## ARİGASTRO SİTESİNDEKİ MEVCUT BİLGİLER:\n{our_site_data.get('body_excerpt','')[:1200]}\n\n"

    # Product images info
    if product_images:
        data_text += f"## ÜRÜN GÖRSELLERİ ({len(product_images)} adet — içeriğe yerleştirilecek):\n"
        for img in product_images[:4]:
            data_text += f"- {img.get('product_name','')}\n"
        data_text += "\n"

    # Competitor analysis
    if analysis.get("competitors_scraped", 0) > 0:
        data_text += f"## RAKİP ANALİZİ ({analysis['competitors_scraped']} site analiz edildi):\n"
        data_text += f"- Ortalama kelime sayısı: {avg.get('word_count',0)}\n"
        data_text += f"- Ortalama anahtar kelime yoğunluğu: %{avg.get('keyword_density',0)}\n"
        data_text += f"- Liste kullanan: %{avg.get('uses_lists_pct',0)}\n"
        data_text += f"- Tablo kullanan: %{avg.get('uses_tables_pct',0)}\n\n"

        data_text += "### Rakip Title'ları:\n"
        for t in analysis.get("competitor_titles", []):
            data_text += f"- {t}\n"
        data_text += "\n### Rakip Description'ları:\n"
        for d in analysis.get("competitor_descriptions", []):
            data_text += f"- {d}\n"

        # Competitor page details
        data_text += "\n### Rakip Sayfa Detayları:\n"
        for p in analysis.get("competitor_pages", []):
            data_text += f"- {p.get('url','')[:80]}: {p.get('word_count',0)} kelime, AK yoğunluğu: %{p.get('keyword_density',0)}\n"

        if analysis.get("competitor_h2s"):
            data_text += "\n### Rakiplerde Kullanılan H2 Başlıkları:\n"
            for h in analysis.get("competitor_h2s", [])[:10]:
                data_text += f"- {h}\n"
    else:
        data_text += "## NOT: Rakip analizi yapılamadı. Endüstriyel mutfak sektörü bilgine dayanarak en profesyonel içeriği üret.\n"

    data_text += f"\n\n## HEDEF: Rakiplerden daha uzun ({target_words}+ kelime), daha detaylı, daha profesyonel bir içerik yaz. KISA YAZMA!"

    response_text = await chat.send_message(UserMessage(text=data_text))

    clean = response_text.strip()
    if clean.startswith("```"):
        clean = clean.split("\n", 1)[1] if "\n" in clean else clean[3:]
        clean = clean.rsplit("```", 1)[0]
    try:
        result = json.loads(clean)
    except json.JSONDecodeError:
        match = re.search(r'\{.*\}', clean, re.DOTALL)
        if match:
            try:
                result = json.loads(match.group())
            except:
                result = {"title": f"{name} Modelleri ve Fiyatları | Arıgastro", "description": "", "content": clean}
        else:
            result = {"title": f"{name} Modelleri ve Fiyatları | Arıgastro", "description": "", "content": clean}

    # Enforce title
    title = result.get("title", "")
    if len(title) > 60:
        if "| Arıgastro" in title:
            prefix = title.split("| Arıgastro")[0].strip()
            while len(f"{prefix} | Arıgastro") > 60 and " " in prefix:
                prefix = prefix.rsplit(" ", 1)[0].strip()
            for conj in ["ve", "ile", "veya", ",", "-"]:
                if prefix.endswith(conj):
                    prefix = prefix[:-len(conj)].strip()
            title = f"{prefix} | Arıgastro"
        else:
            title = title[:57] + "..."
    title = title.replace("Arigastro", "Arıgastro")
    result["title"] = title

    # Enforce description
    desc = result.get("description", "")
    desc = desc.replace("Arigastro", "Arıgastro")
    if len(desc) > 150:
        truncated = desc[:150]
        last_period = truncated.rfind(".")
        if last_period > 80:
            desc = truncated[:last_period + 1]
        else:
            last_space = truncated.rfind(" ")
            if last_space > 80:
                desc = truncated[:last_space] + "."
    result["description"] = desc

    # Replace image placeholders
    content = result.get("content", "")
    content = content.replace("Arigastro", "Arıgastro")
    
    # Count placeholders found in AI output
    placeholders_in_content = len(re.findall(r'\[GORSEL_\d+\]', content))
    logger.info(f"Image replacement: {len(image_html_parts)} images available, {placeholders_in_content} placeholders in content")
    
    for i, img_data in enumerate(image_html_parts):
        placeholder = f"[GORSEL_{i+1}]"
        if placeholder in content:
            content = content.replace(placeholder, img_data["html"])
            logger.info(f"Replaced {placeholder} with image: {img_data['product_name'][:40]}")
        else:
            logger.warning(f"{placeholder} NOT found in content — injecting after first <h2>")
    
    # If AI didn't place any placeholders, inject images manually
    if placeholders_in_content == 0 and image_html_parts:
        logger.info("No placeholders found — injecting images manually into content")
        h2_positions = [m.end() for m in re.finditer(r'</h2>', content)]
        for i, img_data in enumerate(image_html_parts[:min(len(h2_positions), 4)]):
            if i < len(h2_positions):
                # Find end of next paragraph after h2
                next_p_end = content.find("</p>", h2_positions[i])
                if next_p_end != -1:
                    insert_pos = next_p_end + 4
                    content = content[:insert_pos] + "\n" + img_data["html"] + "\n" + content[insert_pos:]
                    # Update positions for subsequent inserts
                    offset = len(img_data["html"]) + 2
                    h2_positions = [p + offset if p > insert_pos else p for p in h2_positions]
    
    # Remove remaining unreplaced placeholders
    content = re.sub(r'\[GORSEL_\d+\]', '', content)

    result["content"] = content
    result["generation_notes"] = result.get("generation_notes", "")
    return result
