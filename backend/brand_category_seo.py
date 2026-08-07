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
    logger.info(f"SERP query: original='{keyword}' -> ascii='{ascii_keyword}'")
    try:
        resp = req_sync.get("https://api.scraperapi.com/structured/google/search", params={
            "api_key": SCRAPERAPI_KEY,
            "query": ascii_keyword,
            "country_code": "tr",
            "tld": "com.tr",
            "num": "10",
        }, timeout=30)
        logger.info(f"SERP API status: {resp.status_code}")
        if resp.status_code != 200:
            logger.warning(f"SERP API returned {resp.status_code}: {resp.text[:200]}")
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
        resp = req_sync.get(f"http://api.scraperapi.com", params={
            "api_key": SCRAPERAPI_KEY,
            "url": url,
            "render": "true",
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

    excluded_domains = ["sahibinden.com", "hepsiburada.com", "trendyol.com", "n11.com", "gittigidiyor.com"]
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
    avg_density = round(sum(s.get("keyword_density", 0) for s in scraped) / max(len(scraped), 1), 2) if scraped else 1.2
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
    """Async wrapper for image scraping."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _get_product_images_sync, product_names, entity_name)


async def generate_content(
    name: str, entity_type: str, entity_id: str,
    analysis: dict, product_images: list, our_site_data: dict,
    openai_key: str, internal_links: dict = None
) -> dict:
    """Generate SEO content using AI based on competitor analysis."""
    from emergentintegrations.llm.chat import LlmChat, UserMessage

    avg = analysis.get("averages", {})
    target_words = max(avg.get("word_count", 800) + 200, 800)
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
        links_instruction = "\n\nSİTE İÇİ LİNKLEME (ZORUNLU — en az 3-5 link olmalı):\nİçeriğin doğal akışı içinde aşağıdaki sayfalara link ver.\n"
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

    if entity_type == "brand":
        title_example = f'"{name} Endüstriyel Mutfak Ürünleri | Arıgastro"'
        title_format_rule = f'Marka title formatı: "{{Marka Adı}} Endüstriyel Mutfak Ürünleri | Arıgastro" veya "{{Marka Adı}} Ürünleri ve Fiyatları | Arıgastro"'
    else:
        title_example = f'"{name} Modelleri ve Fiyatları | Arıgastro"'
        title_format_rule = f'Kategori title formatı: "{{Kategori Adı}} Modelleri ve Fiyatları | Arıgastro"'

    system_prompt = f"""Sen Türkiye'nin en iyi e-ticaret SEO içerik yazarısın. Arıgastro.com (endüstriyel mutfak ekipmanları) için profesyonel {entity_label} sayfası içeriği üretiyorsun.

HEDEF: "{name}" {entity_label}si için Google'da 1. sırada yer alacak, rakiplerden daha kapsamlı ve kaliteli bir sayfa içeriği yaz.

## KESİN KURALLAR:

### TITLE KURALLARI (ÇOK KRİTİK — MUTLAKA UY):
- {title_format_rule}
- Örnek: {title_example}
- MUTLAKA "Arıgastro" kelimesini içermeli (genellikle " | Arıgastro" şeklinde sonda)
- MUTLAKA "{name}" anahtar kelimesini içermeli
- ASLA "Avantajları" kelimesini title'da KULLANMA
- Title MAKSİMUM 60 karakter olmalı (boşluklar dahil)
- Kısa ve net ol, devrik veya yarım cümle YAZMA

### DESCRIPTION KURALLARI (ÇOK KRİTİK — MUTLAKA UY):
- MUTLAKA "Arıgastro" kelimesini içermeli
- MUTLAKA "{name}" anahtar kelimesini içermeli
- MAKSİMUM 150 karakter olmalı (boşluklar dahil)
- Tam ve anlamlı bir cümle olmalı, ASLA yarım cümle bırakma

### İçerik Yapısı:
- H1 KULLANMA (İkas zaten {entity_label} adını H1 olarak gösteriyor)
- H2 ve H3 başlıkları doğal, SEO uyumlu ve ilgi çekici olsun
- En az {target_words} kelime yaz
- Anahtar kelime yoğunluğu yaklaşık %{target_density}
- HTML formatında yaz: <h2>, <h3>, <p>, <ul>, <li>, <strong>, <a href> etiketleri kullan

### GÖRSEL YERLEŞİMİ (ÇOK KRİTİK):
- İçeriğin uygun yerlerine [GORSEL_1], [GORSEL_2], [GORSEL_3], [GORSEL_4] placeholder'larını KOY
- En az 3 görsel placeholder'ı içerikte MUTLAKA olmalı
- Görselleri bölümlere dağıt

### İçerik Bölümleri (hepsini dahil et):
1. **Giriş paragrafı** [GORSEL_1]
2. **{name} Nedir / Neden Önemlidir?**
3. **Arıgastro'da {name} Çeşitleri** [GORSEL_2]
4. **{name} Seçerken Dikkat Edilmesi Gerekenler** [GORSEL_3]
5. **Neden Arıgastro'yu Tercih Etmelisiniz?**
6. **Sıkça Sorulan Sorular** (en az 5 soru-cevap) [GORSEL_4]
7. **Kapanış** (satın almaya yönlendiren kapanış paragrafı — başlıkta ASLA "CTA", "Call to Action" gibi İngilizce/pazarlama jargonu KULLANMA)

### Ürün İsimleri (ÇOK KRİTİK):
- ASLA uydurma ürün isimleri YAZMA
- Sadece verilen gerçek ürün isimlerini kullan

### YASAKLI KELİMELER (başlıklarda ASLA kullanma):
- CTA, Call to Action, FAQ, SEO, KPI gibi İngilizce/teknik terimler
- Başlıklar sade, doğal Türkçe olmalı

### Liste ve Tablo:
- Ürün özelliklerini <ul><li> listeleriyle göster
- {'Uygunsa karşılaştırma tablosu ekle (<table> formatında)' if use_tables else 'Gerekirse özellik listesi kullan'}
{links_instruction}

## YANITINI KESİNLİKLE SADECE BU JSON FORMATINDA VER:
{{"title": "...", "description": "...", "content": "<h2>...</h2><p>...</p>...", "generation_notes": "Bu içeriği hazırlarken şu analizleri yaptım: ..."}}

ÖNEMLİ:
- title MAKSİMUM 60 karakter, description MAKSİMUM 150 karakter
- Her ikisi de TAM CÜMLE olmalı
- Title'da "Avantajları" kelimesi YASAK
- İçerikte en az 3 adet [GORSEL_X] placeholder'ı olmalı
- Tüm içerik TÜRKÇE karakterlerle yazılmalı (ı, ö, ü, ş, ç, ğ)
- "Arıgastro" her zaman "Arıgastro" olarak yazılmalı (ı harfi ile)"""

    chat = LlmChat(
        api_key=openai_key,
        session_id=f"bc-seo-{entity_type}-{name[:15]}",
        system_message=system_prompt
    ).with_model("openai", "gpt-4o")

    data_text = f'## HEDEF: "{name}" ({entity_label})\n\n'
    if our_site_data and our_site_data.get("body_excerpt"):
        data_text += f"## ARİGASTRO SİTESİNDEKİ MEVCUT BİLGİLER:\n{our_site_data.get('body_excerpt','')[:800]}\n\n"
    if product_images:
        data_text += f"## ARİGASTRO'DAKİ ÜRÜNLER (görselleri yazıya eklenecek):\n"
        for img in product_images[:4]:
            data_text += f"- {img.get('product_name','')}\n"
        data_text += "\n"
    if analysis.get("competitors_scraped", 0) > 0:
        data_text += f"## RAKİP ANALİZİ ({analysis['competitors_scraped']} site analiz edildi):\n"
        data_text += f"Ortalama kelime sayısı: {avg.get('word_count',0)}\nOrtalama AK yoğunluğu: %{avg.get('keyword_density',0)}\n\n"
        data_text += "### Rakip Title'ları:\n"
        for t in analysis.get("competitor_titles", []):
            data_text += f"- {t}\n"
        data_text += "\n### Rakip Description'ları:\n"
        for d in analysis.get("competitor_descriptions", []):
            data_text += f"- {d}\n"
        data_text += "\n### Rakiplerde kullanılan H2 başlıkları:\n"
        for h in analysis.get("competitor_h2s", [])[:10]:
            data_text += f"- {h}\n"
    else:
        data_text += "## NOT: Rakip analizi yapılamadı. Endüstriyel mutfak sektörü bilgine dayanarak en profesyonel içeriği üret.\n"

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

    # Enforce title length (max 60 chars)
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

    # Enforce description length (max 150 chars)
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

    # Replace image placeholders with actual HTML
    content = result.get("content", "")
    content = content.replace("Arigastro", "Arıgastro")
    for i, img_data in enumerate(image_html_parts):
        placeholder = f"[GORSEL_{i+1}]"
        content = content.replace(placeholder, img_data["html"])
    content = re.sub(r'\[GORSEL_\d+\]', '', content)

    result["content"] = content
    result["generation_notes"] = result.get("generation_notes", "")
    return result
