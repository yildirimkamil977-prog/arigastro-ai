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
        # Strategy 1: Scrape the category page via ScraperAPI
        if SCRAPERAPI_KEY and entity_name:
            slug = entity_name.lower()
            for old, new in [("ö","o"),("ü","u"),("ş","s"),("ç","c"),("ğ","g"),("ı","i"),(" ","-")]:
                slug = slug.replace(old, new)
            cat_url = f"https://{site_domain}/{slug}"
            api_url = f"http://api.scraperapi.com?api_key={SCRAPERAPI_KEY}&url={cat_url}&render=true"

            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(api_url)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                for img in soup.find_all("img"):
                    src = img.get("src", "") or img.get("data-src", "")
                    alt = (img.get("alt", "") or "").strip()
                    if not src or "theme-images" not in src:
                        continue
                    if any(ex in alt.lower() for ex in EXCLUDE_WORDS):
                        continue
                    if any(ex in src.lower() for ex in EXCLUDE_WORDS):
                        continue
                    if len(alt) > 5 and src not in [i["url"] for i in images]:
                        images.append({"url": src, "alt": alt, "product_name": alt})
                    if len(images) >= 4:
                        break

        # Strategy 2: Scrape individual product pages
        if len(images) < 3 and SCRAPERAPI_KEY:
            for name in product_names[:5]:
                if len(images) >= 4:
                    break
                slug = name.lower()
                for old, new in [("ö","o"),("ü","u"),("ş","s"),("ç","c"),("ğ","g"),("ı","i"),(" ","-"),(",",""),(".",""),("+","")]:
                    slug = slug.replace(old, new)
                slug = slug.strip("-")
                prod_url = f"https://{site_domain}/{slug}"
                api_url = f"http://api.scraperapi.com?api_key={SCRAPERAPI_KEY}&url={prod_url}&render=true"

                try:
                    async with httpx.AsyncClient(timeout=25) as client:
                        resp = await client.get(api_url)
                    if resp.status_code == 200:
                        soup = BeautifulSoup(resp.text, "html.parser")
                        og = soup.find("meta", property="og:image")
                        if og and og.get("content") and "theme-images" in og["content"]:
                            src = og["content"]
                            if src not in [i["url"] for i in images]:
                                images.append({"url": src, "alt": name, "product_name": name})
                                continue
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
                if len(images) >= 4:
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


async def scrape_url_basic(url: str, timeout: int = 25) -> dict:
    """Scrape URL and extract key SEO elements."""
    import httpx
    from bs4 import BeautifulSoup
    if not SCRAPERAPI_KEY:
        return {"error": "ScraperAPI key missing"}
    try:
        api_url = f"http://api.scraperapi.com?api_key={SCRAPERAPI_KEY}&url={url}&render=true"
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
    """Search Google Turkey using ScraperAPI structured endpoint."""
    import httpx
    if not SCRAPERAPI_KEY:
        return []
    try:
        # Use ScraperAPI's structured Google Search endpoint for reliable JSON results
        params = {
            "api_key": SCRAPERAPI_KEY,
            "query": keyword,
            "country_code": "tr",
            "tld": "com.tr",
            "num": "10",
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get("https://api.scraperapi.com/structured/google/search", params=params)
            if resp.status_code != 200:
                logger.warning(f"SERP structured API returned {resp.status_code}, falling back to HTML scrape")
                return await _scrape_google_serp_html(keyword)
            data = resp.json()

        results = []
        for item in data.get("organic_results", []):
            url = item.get("link", "")
            title = item.get("title", "")
            snippet = item.get("snippet", "")
            if url and title:
                results.append({"title": title, "url": url, "description": snippet})
        return results
    except Exception as e:
        logger.error(f"SERP structured error: {e}, falling back to HTML scrape")
        return await _scrape_google_serp_html(keyword)


async def _scrape_google_serp_html(keyword: str) -> list:
    """Fallback: Scrape Google SERP via HTML parsing."""
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
        for item in soup.select("div.g"):
            link = item.find("a")
            title_el = item.find("h3")
            desc_el = item.select_one("div[data-sncf], div.VwiC3b, span.aCOpRe")
            if link and title_el:
                href = link.get("href", "")
                if href.startswith("http"):
                    results.append({
                        "title": title_el.get_text(strip=True),
                        "url": href,
                        "description": desc_el.get_text(strip=True) if desc_el else ""
                    })
        return results
    except Exception as e:
        logger.error(f"SERP HTML fallback error: {e}")
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
    logger.info(f"SERP results for '{search_query}': {len(serp_results)} found")

    competitors = [r for r in serp_results if "arigastro" not in r.get("url", "")]
    our_result = [r for r in serp_results if "arigastro" in r.get("url", "")]

    scraped = []
    for comp in competitors[:6]:
        if len(scraped) >= 3:
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
    for img in product_images[:4]:
        tag = build_image_tag(img.get("url", ""), img.get("alt", name))
        if tag:
            image_html_parts.append({"html": tag, "product_name": img.get("product_name", "")})

    # Build internal links instruction
    links_instruction = ""
    if internal_links:
        children = internal_links.get("children", [])
        siblings = internal_links.get("siblings", [])
        parent = internal_links.get("parent_name", "")

        links_instruction = "\n\nSITE ICI LINKLEME (ZORUNLU — en az 3-5 link olmali):\nIcerigin dogal akisi icinde asagidaki sayfalara link ver. Linkleri cumle icinde dogal sekilde yerlestir.\n"

        if children:
            links_instruction += "\nAlt kategoriler (MUTLAKA hepsine link ver):\n"
            for ch in children[:8]:
                slug = ch.lower().replace(" ", "-").replace("ı", "i").replace("ö", "o").replace("ü", "u").replace("ş", "s").replace("ç", "c").replace("ğ", "g")
                links_instruction += f'- {ch}: https://arigastro.com/{slug}\n'

        if parent:
            parent_slug = parent.lower().replace(" ", "-").replace("ı", "i").replace("ö", "o").replace("ü", "u").replace("ş", "s").replace("ç", "c").replace("ğ", "g")
            links_instruction += f'\nUst kategori: {parent}: https://arigastro.com/{parent_slug}\n'

        if siblings:
            links_instruction += "\nIlgili kategoriler (en az 2-3 tanesine link ver):\n"
            for sib in siblings[:5]:
                slug = sib.lower().replace(" ", "-").replace("ı", "i").replace("ö", "o").replace("ü", "u").replace("ş", "s").replace("ç", "c").replace("ğ", "g")
                links_instruction += f'- {sib}: https://arigastro.com/{slug}\n'

        links_instruction += '\nLinkler <a href="URL">dogal anchor metin</a> formatinda olsun. "Tiklayin" gibi genel anchor kullanma, her linkin anchor metni o kategoriyi tanimlayan dogal bir ifade olsun.\n'

    entity_label = "marka" if entity_type == "brand" else "kategori"

    # Build title examples based on type
    if entity_type == "brand":
        title_example = f'"{name} Endustriyel Mutfak Urunleri | Arigastro"'
        title_format_rule = f'Marka title formati: "{{Marka Adi}} Endustriyel Mutfak Urunleri | Arigastro" veya "{{Marka Adi}} Urunleri ve Fiyatlari | Arigastro"'
    else:
        title_example = f'"{name} Modelleri ve Fiyatlari | Arigastro"'
        title_format_rule = f'Kategori title formati: "{{Kategori Adi}} Modelleri ve Fiyatlari | Arigastro"'

    system_prompt = f"""Sen Turkiye'nin en iyi e-ticaret SEO icerik yazarisin. Arigastro.com (endustriyel mutfak ekipmanlari) icin profesyonel {entity_label} sayfasi icerigi uretiyorsun.

HEDEF: "{name}" {entity_label}si icin Google'da 1. sirada yer alacak, rakiplerden daha kapsamli ve kaliteli bir sayfa icerigi yaz.

## KESIN KURALLAR:

### TITLE KURALLARI (COK KRITIK — MUTLAKA UY):
- {title_format_rule}
- Ornek: {title_example}
- MUTLAKA "Arigastro" kelimesini icermeli (genellikle " | Arigastro" seklinde sonda)
- MUTLAKA "{name}" anahtar kelimesini icermeli
- ASLA "Avantajlari" kelimesini title'da KULLANMA
- Title MAKSIMUM 55 karakter olmali (bosluklar dahil)
- Kisa ve net ol, devrik veya yarim cumle YAZMA
- Rakip sitelerin title'larindan esinlen ama daha iyi yaz

### DESCRIPTION KURALLARI (COK KRITIK — MUTLAKA UY):
- MUTLAKA "Arigastro" kelimesini icermeli
- MUTLAKA "{name}" anahtar kelimesini icermeli
- MAKSIMUM 150 karakter olmali (bosluklar dahil)
- Tam ve anlamli bir cumle olmali, ASLA yarim cumle birakma
- Avantaj vurgulayan, tiklamaya tesvik eden aciklama
- Karakter limitine uygunlugu kontrol et, gerekirse cumleyi kisalt ama ASLA devrik birakma

### Icerik Yapisi:
- H1 KULLANMA (Ikas zaten {entity_label} adini H1 olarak gosteriyor)
- H2 ve H3 basliklari dogal, SEO uyumlu ve ilgi cekici olsun
- "Bar Buzdolaplari Kategorisi" gibi robotik basliklar YAZMA. Yerine "Profesyonel Bar Buzdolaplari ile Isletmenizi Donatin" gibi dogal basliklar yaz
- En az {target_words} kelime yaz
- Anahtar kelime yogunlugu yaklasik %{target_density}
- HTML formatinda yaz: <h2>, <h3>, <p>, <ul>, <li>, <strong>, <a href>, <table> etiketleri kullan

### GORSEL YERLESIMI (COK KRITIK):
- Icerigin uygun yerlerine [GORSEL_1], [GORSEL_2], [GORSEL_3], [GORSEL_4] placeholder'larini KOY
- Her gorsel bir paragrafin altina veya urun cesitleri anlatilirken yerlestirilmeli
- En az 3 gorsel placeholder'i icerikte MUTLAKA olmali
- Gorselleri bolumlere dagit — hepsini bir yere yigma

### Ton ve Uslup:
- Profesyonel, kurumsal ama sicak ve guven veren
- E-ticaret odakli — okuyucuyu satin almaya tesvik et
- Gercek bilgi ver, genel/bos laflar yazma
- Fiyat bilgisi YAZMA

### Icerik Bolumleri (hepsini dahil et):
1. **Giris paragrafi** (2-3 cumle, anahtar kelimeyi dogal sekilde iceren guclu acilis)
   [GORSEL_1]
2. **{name} Nedir / Neden Onemlidir?** (sektorel bilgi, kullanim alanlari)
3. **Arigastro'da {name} Cesitleri** (urun gruplarini, ozelliklerini anlat — sitede bulunan gercek urun isimlerini kullan)
   [GORSEL_2]
4. **{name} Secerken Dikkat Edilmesi Gerekenler** (kapasite, malzeme, enerji verimliligi vb. satin alma rehberi)
   [GORSEL_3]
5. **Neden Arigastro'yu Tercih Etmelisiniz?** (ucretsiz kargo, guvenli odeme, genis urun yelpazesi, teknik destek, kurumsal guvenilirlik)
6. **Sikca Sorulan Sorular** (en az 5 soru-cevap, <h3> ile baslikladir)
   [GORSEL_4]
7. **Sonuc / CTA** (satin almaya yonlendiren kapanis paragrafi)

### Urun Isimleri (COK KRITIK):
- ASLA "Model X1", "Model Y2", "Model Z3" gibi uydurma urun isimleri YAZMA
- Sadece asagida sana verilen gercek urun isimlerini kullan
- Eger urun ismi verilmemisse, genel ifadeler kullan: "farkli kapasite secenekleri", "cesitli modeller" gibi
- Hicbir zaman var olmayan bir urun modeli uydurma

### Baslik Formati:
- Basliklar kesinlikle <h2> ve <h3> HTML etiketleri icinde olmali
- Alt basliklar icin <h3> kullan

### Rakip Analiz Notu:
- Icerikte AYRI olarak, yaptigin analizle ilgili kisa bir not hazirla
- Hangi siteleri inceledigin, title ve description'da nelere dikkat ettigin, rakiplerden hangi noktalari referans aldigin
- Bu notu "generation_notes" alaninda JSON'da ver

### Liste ve Tablo:
- Urun ozelliklerini veya karsilastirmalari <ul><li> listeleriyle goster
- {'Uygunsa ozellik karsilastirma tablosu ekle (<table> formatinda)' if use_tables else 'Gerekirse ozellik listesi kullan'}
{links_instruction}

## YANITINI KESINLIKLE SADECE BU JSON FORMATINDA VER:
{{"title": "...", "description": "...", "content": "<h2>...</h2><p>...</p>...", "generation_notes": "Bu icerigi hazirlarken su analizleri yaptim: ..."}}

ONEMLI HATIRLATMA:
- title MAKSIMUM 55 karakter (bosluklar dahil)
- description MAKSIMUM 150 karakter (bosluklar dahil)
- Her ikisi de TAM CUMLE olmali, ASLA devrik veya yarim birakma
- Title'da "Avantajlari" kelimesi YASAK
- Icerikte en az 3 adet [GORSEL_X] placeholder'i olmali"""

    chat = LlmChat(
        api_key=openai_key,
        session_id=f"bc-seo-{entity_type}-{name[:15]}",
        system_message=system_prompt
    ).with_model("openai", "gpt-4o")

    # Build data text
    data_text = f'## HEDEF: "{name}" ({entity_label})\n\n'

    # Our site data
    if our_site_data and our_site_data.get("body_excerpt"):
        data_text += f"## ARIGASTRO SITESINDEKI MEVCUT BILGILER:\n{our_site_data.get('body_excerpt','')[:800]}\n\n"

    # Product info
    if product_images:
        data_text += f"## ARIGASTRO'DAKI URUNLER (gorselleri yaziya eklenecek):\n"
        for img in product_images[:4]:
            data_text += f"- {img.get('product_name','')}\n"
        data_text += "\n"

    # Competitor analysis
    if analysis.get("competitors_scraped", 0) > 0:
        data_text += f"## RAKIP ANALIZI ({analysis['competitors_scraped']} site analiz edildi):\n"
        data_text += f"Ortalama kelime sayisi: {avg.get('word_count',0)}\nOrtalama AK yogunlugu: %{avg.get('keyword_density',0)}\n\n"
        data_text += "### Rakip Title'lari:\n"
        for t in analysis.get("competitor_titles", []):
            data_text += f"- {t}\n"
        data_text += "\n### Rakip Description'lari:\n"
        for d in analysis.get("competitor_descriptions", []):
            data_text += f"- {d}\n"
        data_text += "\n### Rakiplerde kullanilan H2 basliklari:\n"
        for h in analysis.get("competitor_h2s", [])[:10]:
            data_text += f"- {h}\n"
    else:
        data_text += "## NOT: Rakip analizi yapilamadi. Endustriyel mutfak sektoru bilgine dayanarak en profesyonel icerigi uret.\n"

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
                result = {"title": f"{name} Modelleri ve Fiyatlari | Arigastro", "description": "", "content": clean}
        else:
            result = {"title": f"{name} Modelleri ve Fiyatlari | Arigastro", "description": "", "content": clean}

    # Enforce title length (max 55 chars)
    title = result.get("title", "")
    if len(title) > 55:
        # Try to shorten while keeping "| Arigastro"
        if "| Arigastro" in title:
            prefix = title.split("| Arigastro")[0].strip()
            # Trim prefix to fit
            while len(f"{prefix} | Arigastro") > 55 and " " in prefix:
                prefix = prefix.rsplit(" ", 1)[0]
            title = f"{prefix} | Arigastro"
        else:
            title = title[:52] + "..."
    result["title"] = title

    # Enforce description length (max 150 chars)
    desc = result.get("description", "")
    if len(desc) > 150:
        # Find last complete sentence within limit
        truncated = desc[:150]
        last_period = truncated.rfind(".")
        if last_period > 80:
            desc = truncated[:last_period + 1]
        else:
            # Find last space and add period
            last_space = truncated.rfind(" ")
            if last_space > 80:
                desc = truncated[:last_space] + "."
    result["description"] = desc

    # Replace image placeholders with actual HTML
    content = result.get("content", "")
    for i, img_data in enumerate(image_html_parts):
        placeholder = f"[GORSEL_{i+1}]"
        content = content.replace(placeholder, img_data["html"])
    # Remove remaining placeholders
    content = re.sub(r'\[GORSEL_\d+\]', '', content)

    result["content"] = content
    result["generation_notes"] = result.get("generation_notes", "")
    return result
