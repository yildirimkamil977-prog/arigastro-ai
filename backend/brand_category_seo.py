"""Brand & Category SEO — Competitor analysis + AI content generation."""
import os
import re
import json
import logging
import asyncio
from datetime import datetime, timezone

logger = logging.getLogger("brand_category_seo")

SCRAPERAPI_KEY = os.environ.get("SCRAPERAPI_KEY", "")
IKAS_IMAGE_BASE = "https://cdn.myikas.com/images/theme-images"


def build_image_tag(image_url: str, alt: str) -> str:
    """Build HTML img tag from a full image URL."""
    if not image_url:
        return ""
    return f'<img src="{image_url}" alt="{alt}" style="max-width:100%;height:auto;border-radius:8px;margin:16px 0;" />'


async def get_product_images_from_site(product_names: list, site_domain: str = "arigastro.com") -> list:
    """Get real product image URLs by scraping the site's search or product pages."""
    import httpx
    from bs4 import BeautifulSoup
    images = []
    try:
        for name in product_names[:4]:
            search_url = f"https://{site_domain}/arama?q={name.split()[0]}"
            async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
                resp = await client.get(search_url)
            soup = BeautifulSoup(resp.text, "html.parser")
            for img in soup.find_all("img"):
                src = img.get("src", "")
                if "theme-images" in src and src not in [i["url"] for i in images]:
                    alt_text = img.get("alt", name)
                    images.append({"url": src, "alt": alt_text, "product_name": name})
                    break
            if len(images) >= 3:
                break
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

        # Check for lists and tables
        lists = len(soup.find_all(["ul", "ol"]))
        tables = len(soup.find_all("table"))

        # Keyword density helper
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
    """Search Google Turkey for a keyword and get organic results."""
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
                    results.append({
                        "title": title_el.get_text(strip=True),
                        "url": href,
                        "description": desc_el.get_text(strip=True) if desc_el else "",
                    })
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

    # Filter out arigastro from competitors, keep at least 5
    competitors = [r for r in serp_results if "arigastro" not in r.get("url", "")]
    our_result = [r for r in serp_results if "arigastro" in r.get("url", "")]

    # Scrape top sites (try up to 8 to get at least 5 successful)
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

    # Scrape our own page if in results
    our_page = None
    if our_result:
        our_page = await scrape_url_basic(our_result[0]["url"])

    # Calculate averages
    avg_word_count = round(sum(s.get("word_count", 0) for s in scraped) / max(len(scraped), 1))
    avg_density = round(sum(s.get("keyword_density", 0) for s in scraped) / max(len(scraped), 1), 2)
    uses_lists = sum(1 for s in scraped if s.get("has_lists"))
    uses_tables = sum(1 for s in scraped if s.get("has_tables"))

    # Collect common title/description words
    all_titles = " ".join(s.get("serp_title", "") for s in scraped)
    all_descs = " ".join(s.get("serp_description", "") for s in scraped)
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
            "uses_lists_pct": round(uses_lists / max(len(scraped), 1) * 100),
            "uses_tables_pct": round(uses_tables / max(len(scraped), 1) * 100),
        },
        "competitor_titles": [s.get("serp_title", "") for s in scraped],
        "competitor_descriptions": [s.get("serp_description", "") for s in scraped],
        "competitor_h2s": list(set(common_h2s))[:15],
        "all_title_words": all_titles,
        "all_desc_words": all_descs,
    }

    # Find our SERP position
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
    target_density = avg.get("keyword_density", 1.0)
    use_lists = avg.get("uses_lists_pct", 0) > 40
    use_tables = avg.get("uses_tables_pct", 0) > 40

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
        
        links_instruction = "\n\nSİTE İÇİ LİNKLEME (ÇOK ÖNEMLİ):\nİçerikte aşağıdaki sayfalara doğal şekilde link ver. Linkler <a href=\"URL\">metin</a> formatında olsun.\n"
        
        if children:
            links_instruction += "\nAlt kategoriler (MUTLAKA link ver):\n"
            for ch in children:
                slug = ch.lower().replace(" ", "-").replace("ı", "i").replace("ö", "o").replace("ü", "u").replace("ş", "s").replace("ç", "c").replace("ğ", "g")
                links_instruction += f'- <a href="https://arigastro.com/{slug}">{ch}</a>\n'
        
        if parent:
            parent_slug = parent.lower().replace(" ", "-").replace("ı", "i").replace("ö", "o").replace("ü", "u").replace("ş", "s").replace("ç", "c").replace("ğ", "g")
            links_instruction += f'\nÜst kategori: <a href="https://arigastro.com/{parent_slug}">{parent}</a>\n'
        
        if siblings and not children:
            links_instruction += "\nİlgili kategoriler (en az 2-3 tanesine link ver):\n"
            for sib in siblings[:5]:
                slug = sib.lower().replace(" ", "-").replace("ı", "i").replace("ö", "o").replace("ü", "u").replace("ş", "s").replace("ç", "c").replace("ğ", "g")
                links_instruction += f'- <a href="https://arigastro.com/{slug}">{sib}</a>\n'
        elif siblings:
            links_instruction += "\nKardeş kategoriler (uygun olanlara link ver):\n"
            for sib in siblings[:3]:
                slug = sib.lower().replace(" ", "-").replace("ı", "i").replace("ö", "o").replace("ü", "u").replace("ş", "s").replace("ç", "c").replace("ğ", "g")
                links_instruction += f'- <a href="https://arigastro.com/{slug}">{sib}</a>\n'
        
        links_instruction += "\nLinkleri doğal cümleler içinde kullan, liste halinde sıralama."

    system_prompt = f"""Sen profesyonel bir e-ticaret SEO içerik yazarısın. Arıgastro.com (endüstriyel mutfak ekipmanları) için {'marka' if entity_type == 'brand' else 'kategori'} sayfası içeriği yazıyorsun.

İÇERİK: "{name}" {'markası' if entity_type == 'brand' else 'kategorisi'} için sayfa açıklaması

KURALLAR:
1. Profesyonel ve kurumsal ton. Satın almaya yönlendirici.
2. En az {target_words} kelime yaz.
3. Anahtar kelime yoğunluğu yaklaşık %{target_density} olsun ("{name}" kelimesi).
4. H1 ETİKETİ KULLANMA — İkas zaten {'marka' if entity_type == 'brand' else 'kategori'} adını H1 olarak gösteriyor. H2'den başla.
5. Fiyat bilgisi YAZMA.
6. Sadece Arıgastro'da bulunan ürünlerden bahset, uydurma ürün ekleme.
7. {"Liste (ul/li) kullan." if use_lists else ""}
8. {"Tablo kullan (karşılaştırma veya özellik tablosu)." if use_tables else ""}
9. İçeriğin arasına ürün görselleri eklenecek yer bırak — [GORSEL_1], [GORSEL_2], [GORSEL_3] placeholder'larını kullan.
10. HTML formatında yaz (h2, h3, p, ul, li, strong, table, a).
{links_instruction}

TITLE KURALLARI (ÇOK ÖNEMLİ):
- Title mutlaka "Arıgastro" kelimesini içermeli (genellikle sonda " | Arıgastro" şeklinde)
- Title mutlaka "{name}" anahtar kelimesini içermeli
- Rakip sitelerin title'larını analiz et ve onlardan esinlen
- Marka ise: "Marka Adı Ürünleri ve Modelleri | Arıgastro" veya "Marka Adı Endüstriyel Mutfak Ürünleri | Arıgastro" gibi
- Kategori ise: "Kategori Adı Çeşitleri | Arıgastro" veya "Kategori Adı Modelleri ve Fiyatları | Arıgastro" gibi
- Rakiplerin title'larında dikkat çeken ortak kelimeler varsa (çeşitleri, modelleri, fiyatları vb.) sen de kullan
- Maximum 60 karakter

DESCRIPTION KURALLARI:
- Description mutlaka "Arıgastro" kelimesini içermeli
- Description mutlaka "{name}" anahtar kelimesini içermeli
- Rakip sitelerin description'larını analiz et ve onlardan esinlen
- Satın almaya teşvik eden, avantajları vurgulayan (ücretsiz kargo, güvenli alışveriş vb.)
- Maximum 160 karakter

İÇERİK YAPISI:
- {'Marka' if entity_type == 'brand' else 'Kategori'} tanıtımı
- Arıgastro neden tercih edilmeli (ücretsiz kargo, güvenli alışveriş vb.)
- Ürün çeşitleri ve özellikleri
- Sıkça Sorulan Sorular (en az 4 soru)
- Satın alma rehberi / sonuç

TITLE (max 60 karakter): SEO uyumlu sayfa başlığı
DESCRIPTION (max 160 karakter): SEO uyumlu meta açıklama

Yanıtını JSON formatında ver:
{{"title": "...", "description": "...", "content": "HTML içerik..."}}"""

    chat = LlmChat(
        api_key=openai_key,
        session_id=f"bc-seo-{entity_type}-{name[:15]}",
        system_message=system_prompt
    ).with_model("openai", "gpt-4o")

    # Build data text
    data_text = f"## HEDEF: {name}\n\n"

    # Our site data
    if our_site_data:
        data_text += f"## ARİGASTRO SAYFA BİLGİLERİ:\n"
        data_text += f"URL: {our_site_data.get('url','')}\n"
        data_text += f"İçerik özeti: {our_site_data.get('body_excerpt','')[:500]}\n\n"

    # Product info
    if product_images:
        data_text += f"## ARİGASTRO'DAKİ ÜRÜNLER (görsel eklenecekler):\n"
        for img in product_images[:3]:
            data_text += f"- {img.get('product_name','')}\n"

    # Competitor analysis
    data_text += f"\n## RAKİP ANALİZİ ({analysis.get('competitors_scraped',0)} site analiz edildi):\n"
    data_text += f"Ortalama kelime sayısı: {avg.get('word_count',0)}\n"
    data_text += f"Ortalama anahtar kelime yoğunluğu: %{avg.get('keyword_density',0)}\n"
    data_text += f"Liste kullanan site oranı: %{avg.get('uses_lists_pct',0)}\n"
    data_text += f"Tablo kullanan site oranı: %{avg.get('uses_tables_pct',0)}\n\n"

    data_text += "### Rakip Title'ları:\n"
    for t in analysis.get("competitor_titles", []):
        data_text += f"- {t}\n"

    data_text += "\n### Rakip Description'ları:\n"
    for d in analysis.get("competitor_descriptions", []):
        data_text += f"- {d}\n"

    data_text += "\n### Rakiplerde kullanılan H2 başlıkları:\n"
    for h in analysis.get("competitor_h2s", [])[:10]:
        data_text += f"- {h}\n"

    response_text = await chat.send_message(UserMessage(text=data_text))

    # Parse JSON response
    clean = response_text.strip()
    if clean.startswith("```"):
        clean = clean.split("\n", 1)[1] if "\n" in clean else clean[3:]
        clean = clean.rsplit("```", 1)[0]
    try:
        result = json.loads(clean)
    except json.JSONDecodeError:
        # Try to extract JSON from text
        match = re.search(r'\{.*\}', clean, re.DOTALL)
        if match:
            result = json.loads(match.group())
        else:
            result = {"title": name, "description": "", "content": clean}

    # Replace image placeholders with actual HTML
    content = result.get("content", "")
    for i, img_data in enumerate(image_html_parts):
        placeholder = f"[GORSEL_{i+1}]"
        content = content.replace(placeholder, img_data["html"])
    # Remove any remaining placeholders
    content = re.sub(r'\[GORSEL_\d+\]', '', content)

    result["content"] = content
    return result
