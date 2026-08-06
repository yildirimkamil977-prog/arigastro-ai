"""Brand & Category SEO — Competitor analysis + AI content generation."""
import os
import re
import json
import logging
import asyncio
from datetime import datetime, timezone

logger = logging.getLogger("brand_category_seo")

SCRAPERAPI_KEY = os.environ.get("SCRAPERAPI_KEY", "")


def build_image_tag(image_url: str, alt: str) -> str:
    """Build HTML img tag from a full image URL."""
    if not image_url:
        return ""
    return f'<img src="{image_url}" alt="{alt}" style="max-width:100%;height:auto;border-radius:8px;margin:16px 0;" />'


async def get_product_images_from_site(product_names: list, entity_name: str = "", site_domain: str = "arigastro.com") -> list:
    """Get real product image URLs by scraping the site category/product pages."""
    import httpx
    from bs4 import BeautifulSoup
    
    EXCLUDE_WORDS = ["logo", "qr kod", "qr code", "arigato", "favicon", "icon", "banner", "slider", "payment", "cargo", "kargo", "whatsapp"]
    images = []
    
    try:
        # Strategy 1: Scrape the category page via ScraperAPI (renders JS)
        if SCRAPERAPI_KEY and entity_name:
            slug = entity_name.lower()
            for old, new in [("ö","o"),("ü","u"),("ş","s"),("ç","c"),("ğ","g"),("ı","i"),(" ","-")]:
                slug = slug.replace(old, new)
            cat_url = f"https://{site_domain}/{slug}"
            api_url = f"http://api.scraperapi.com?api_key={SCRAPERAPI_KEY}&url={cat_url}"
            
            async with httpx.AsyncClient(timeout=25) as client:
                resp = await client.get(api_url)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                for img in soup.find_all("img"):
                    src = img.get("src", "") or img.get("data-src", "")
                    alt = (img.get("alt", "") or "").strip()
                    if not src or "theme-images" not in src:
                        continue
                    # Filter out logos and non-product images
                    if any(ex in alt.lower() for ex in EXCLUDE_WORDS):
                        continue
                    if any(ex in src.lower() for ex in EXCLUDE_WORDS):
                        continue
                    # Must have meaningful alt text (product name)
                    if len(alt) > 5 and src not in [i["url"] for i in images]:
                        images.append({"url": src, "alt": alt, "product_name": alt})
                    if len(images) >= 3:
                        break
        
        # Strategy 2: Scrape individual product pages
        if len(images) < 3 and SCRAPERAPI_KEY:
            for name in product_names[:5]:
                if len(images) >= 3:
                    break
                # Try product page via slug
                slug = name.lower()
                for old, new in [("ö","o"),("ü","u"),("ş","s"),("ç","c"),("ğ","g"),("ı","i"),(" ","-"),(",",""),(".",""),("+","")]:
                    slug = slug.replace(old, new)
                slug = slug.strip("-")
                prod_url = f"https://{site_domain}/{slug}"
                api_url = f"http://api.scraperapi.com?api_key={SCRAPERAPI_KEY}&url={prod_url}"
                
                try:
                    async with httpx.AsyncClient(timeout=20) as client:
                        resp = await client.get(api_url)
                    if resp.status_code == 200:
                        soup = BeautifulSoup(resp.text, "html.parser")
                        # Try og:image first
                        og = soup.find("meta", property="og:image")
                        if og and og.get("content") and "theme-images" in og["content"]:
                            src = og["content"]
                            if src not in [i["url"] for i in images]:
                                images.append({"url": src, "alt": name, "product_name": name})
                                continue
                        # Fallback: find product images
                        for img in soup.find_all("img"):
                            src = img.get("src", "")
                            alt = img.get("alt", "")
                            if "theme-images" in src and not any(ex in alt.lower() for ex in EXCLUDE_WORDS) and len(alt) > 5:
                                if src not in [i["url"] for i in images]:
                                    images.append({"url": src, "alt": alt, "product_name": name})
                                    break
                except Exception:
                    pass
                await asyncio.sleep(0.5)
        
        # Strategy 3: Direct site search (no ScraperAPI needed)
        if len(images) < 3:
            for name in product_names[:4]:
                if len(images) >= 3:
                    break
                search_term = "+".join(name.split()[:3])
                search_url = f"https://{site_domain}/arama?q={search_term}"
                try:
                    async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
                        resp = await client.get(search_url)
                    soup = BeautifulSoup(resp.text, "html.parser")
                    for img in soup.find_all("img"):
                        src = img.get("src", "")
                        alt = (img.get("alt", "") or "").strip()
                        if "theme-images" in src and not any(ex in alt.lower() for ex in EXCLUDE_WORDS) and len(alt) > 5:
                            if src not in [i["url"] for i in images]:
                                images.append({"url": src, "alt": alt, "product_name": alt})
                                break
                except Exception:
                    pass
                await asyncio.sleep(0.3)
    except Exception as e:
        logger.warning(f"Product image scrape error: {e}")
    
    return images


async def scrape_url_basic(url: str, timeout: int = 20) -> dict:
    """Scrape URL and extract key SEO elements."""
    import httpx
    from bs4 import BeautifulSoup
    if not SCRAPERAPI_KEY:
        return {"error": "ScraperAPI key missing"}
    try:
        api_url = f"http://api.scraperapi.com?api_key={SCRAPERAPI_KEY}&url={url}"
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(api_url)
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


async def scrape_google_serp_tr(keyword: str) -> list:
    """Search Google Turkey for a keyword."""
    import httpx
    from bs4 import BeautifulSoup
    if not SCRAPERAPI_KEY:
        return []
    try:
        search_url = f"https://www.google.com.tr/search?q={keyword}&hl=tr&gl=tr&num=10"
        api_url = f"http://api.scraperapi.com?api_key={SCRAPERAPI_KEY}&url={search_url}"
        async with httpx.AsyncClient(timeout=25) as client:
            resp = await client.get(api_url)
            if resp.status_code != 200:
                return []
        soup = BeautifulSoup(resp.text, "html.parser")
        results = []
        for item in soup.select("div.g")[:10]:
            link = item.find("a")
            title_el = item.find("h3")
            desc_el = item.select_one("div[data-sncf], div.VwiC3b, span.aCOpRe")
            if link and title_el:
                href = link.get("href", "")
                if href.startswith("http"):
                    results.append({"title": title_el.get_text(strip=True), "url": href, "description": desc_el.get_text(strip=True) if desc_el else ""})
        return results
    except Exception as e:
        logger.error(f"SERP error: {e}")
        return []


def calc_keyword_density(text: str, keyword: str) -> float:
    """Calculate keyword density percentage."""
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

    serp_results = await scrape_google_serp_tr(search_query)

    competitors = [r for r in serp_results if "arigastro" not in r.get("url", "")]
    our_result = [r for r in serp_results if "arigastro" in r.get("url", "")]

    scraped = []
    for comp in competitors[:8]:
        if len(scraped) >= 5:
            break
        page_data = await scrape_url_basic(comp["url"])
        if "error" not in page_data:
            page_data["serp_title"] = comp.get("title", "")
            page_data["serp_description"] = comp.get("description", "")
            page_data["keyword_density"] = calc_keyword_density(page_data.get("body_text", ""), name)
            scraped.append(page_data)
        await asyncio.sleep(0.5)

    our_page = None
    if our_result:
        our_page = await scrape_url_basic(our_result[0]["url"])

    avg_word_count = round(sum(s.get("word_count", 0) for s in scraped) / max(len(scraped), 1)) if scraped else 800
    avg_density = round(sum(s.get("keyword_density", 0) for s in scraped) / max(len(scraped), 1), 2) if scraped else 1.2
    uses_lists = sum(1 for s in scraped if s.get("has_lists")) if scraped else 3
    uses_tables = sum(1 for s in scraped if s.get("has_tables")) if scraped else 1

    common_h2s = []
    for s in scraped:
        common_h2s.extend(s.get("h2", []))

    analysis = {
        "search_query": search_query,
        "competitors_scraped": len(scraped),
        "serp_position": None,
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

    for i, r in enumerate(serp_results):
        if "arigastro" in r.get("url", ""):
            analysis["serp_position"] = i + 1
            break

    return analysis


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
    use_lists = avg.get("uses_lists_pct", 0) > 30
    use_tables = avg.get("uses_tables_pct", 0) > 30

    # Build image HTML
    image_html_parts = []
    for img in product_images[:3]:
        tag = build_image_tag(img.get("url", ""), img.get("alt", name))
        if tag:
            image_html_parts.append({"html": tag, "product_name": img.get("product_name", "")})

    # Build internal links instruction
    links_instruction = ""
    if internal_links:
        children = internal_links.get("children", [])
        siblings = internal_links.get("siblings", [])
        parent = internal_links.get("parent_name", "")

        links_instruction = "\n\nSİTE İÇİ LİNKLEME (ZORUNLU — en az 3-5 link olmalı):\nİçeriğin doğal akışı içinde aşağıdaki sayfalara link ver. Linkleri cümle içinde doğal şekilde yerleştir.\n"

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

        links_instruction += '\nLinkler <a href="URL">doğal anchor metin</a> formatında olsun. "Tıklayın" gibi genel anchor kullanma, her linkin anchor metni o kategoriyi tanımlayan doğal bir ifade olsun.\n'

    entity_label = "marka" if entity_type == "brand" else "kategori"

    system_prompt = f"""Sen Türkiye'nin en iyi e-ticaret SEO içerik yazarısın. Arıgastro.com (endüstriyel mutfak ekipmanları) için profesyonel {entity_label} sayfası içeriği üretiyorsun.

HEDEF: "{name}" {entity_label}si için Google'da 1. sırada yer alacak, rakiplerden daha kapsamlı ve kaliteli bir sayfa içeriği yaz.

## KESİN KURALLAR:

### İçerik Yapısı:
- H1 KULLANMA (İkas zaten {entity_label} adını H1 olarak gösteriyor)
- H2 ve H3 başlıkları doğal, SEO uyumlu ve ilgi çekici olsun
- "Bar Buzdolapları Kategorisi" gibi robotik başlıklar YAZMA. Yerine "Profesyonel Bar Buzdolapları ile İşletmenizi Donatın" gibi doğal başlıklar yaz
- En az {target_words} kelime yaz
- Anahtar kelime yoğunluğu yaklaşık %{target_density}
- HTML formatında yaz: <h2>, <h3>, <p>, <ul>, <li>, <strong>, <a href>, <table> etiketleri kullan

### Ton ve Üslup:
- Profesyonel, kurumsal ama sıcak ve güven veren
- E-ticaret odaklı — okuyucuyu satın almaya teşvik et
- Gerçek bilgi ver, genel/boş laflar yazma
- Fiyat bilgisi YAZMA

### İçerik Bölümleri (hepsini dahil et):
1. **Giriş paragrafı** (2-3 cümle, anahtar kelimeyi doğal şekilde içeren güçlü açılış)
2. **{name} Nedir / Neden Önemlidir?** (sektörel bilgi, kullanım alanları)
3. **Arıgastro'da {name} Çeşitleri** (ürün gruplarını, özelliklerini anlat — sitede bulunan gerçek ürün isimlerini kullan)
4. **{name} Seçerken Dikkat Edilmesi Gerekenler** (kapasite, malzeme, enerji verimliliği vb. satın alma rehberi)
5. **Neden Arıgastro'yu Tercih Etmelisiniz?** (ücretsiz kargo, güvenli ödeme, geniş ürün yelpazesi, teknik destek, kurumsal güvenilirlik)
6. **Sıkça Sorulan Sorular** (en az 5 soru-cevap, <h3> ile başlıklandır)
7. **Sonuç / CTA** (satın almaya yönlendiren kapanış paragrafı)

### Görsel Yerleşimi:
- İçeriğin uygun yerlerine [GORSEL_1], [GORSEL_2], [GORSEL_3] placeholder'ları koy
- Görselleri bölümler arasına veya ürün çeşitleri anlatılırken yerleştir
- Eğer ürün görseli bilgisi verilmişse, görselin hangi ürüne ait olduğunu yazıda doğal şekilde belirt

### Liste ve Tablo:
- Ürün özelliklerini veya karşılaştırmaları <ul><li> listeleriyle göster
- {'Uygunsa özellik karşılaştırma tablosu ekle (<table> formatında)' if use_tables else 'Gerekirse özellik listesi kullan'}
{links_instruction}

## TITLE KURALLARI:
- MUTLAKA "Arıgastro" kelimesini içermeli (genellikle " | Arıgastro" şeklinde sonda)
- MUTLAKA "{name}" anahtar kelimesini içermeli
- Rakip sitelerin title'larından esinlen ama daha iyi yaz
- Marka ise örnek: "Öztiryakiler Endüstriyel Mutfak Ürünleri | Arıgastro"
- Kategori ise örnek: "Bar Buzdolapları Modelleri ve Çeşitleri | Arıgastro"
- Maximum 60 karakter

## DESCRIPTION KURALLARI:
- MUTLAKA "Arıgastro" kelimesini içermeli
- MUTLAKA "{name}" anahtar kelimesini içermeli
- Avantaj vurgulayan, tıklamaya teşvik eden açıklama
- Maximum 160 karakter

## YANITINI KESİNLİKLE SADECE BU JSON FORMATINDA VER:
{{"title": "...", "description": "...", "content": "<h2>...</h2><p>...</p>..."}}"""

    chat = LlmChat(
        api_key=openai_key,
        session_id=f"bc-seo-{entity_type}-{name[:15]}",
        system_message=system_prompt
    ).with_model("openai", "gpt-4o")

    # Build data text
    data_text = f'## HEDEF: "{name}" ({entity_label})\n\n'

    # Our site data
    if our_site_data and our_site_data.get("body_excerpt"):
        data_text += f"## ARİGASTRO SİTESİNDEKİ MEVCUT BİLGİLER:\n{our_site_data.get('body_excerpt','')[:800]}\n\n"

    # Product info
    if product_images:
        data_text += f"## ARİGASTRO'DAKİ ÜRÜNLER (görselleri yazıya eklenecek):\n"
        for img in product_images[:3]:
            data_text += f"- {img.get('product_name','')}\n"
        data_text += "\n"

    # Competitor analysis
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

    # Parse JSON response
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
                result = {"title": f"{name} | Arıgastro", "description": "", "content": clean}
        else:
            result = {"title": f"{name} | Arıgastro", "description": "", "content": clean}

    # Replace image placeholders with actual HTML
    content = result.get("content", "")
    for i, img_data in enumerate(image_html_parts):
        placeholder = f"[GORSEL_{i+1}]"
        content = content.replace(placeholder, img_data["html"])
    # Remove remaining placeholders
    content = re.sub(r'\[GORSEL_\d+\]', '', content)

    result["content"] = content
    return result
