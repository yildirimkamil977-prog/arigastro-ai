import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { getAuthHeaders, API } from "../context/AuthContext";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Badge } from "../components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../components/ui/table";
import { Textarea } from "../components/ui/textarea";
import { Search, Sparkles, FileText, Loader2, Copy, Check, X, ChevronLeft, ChevronRight } from "lucide-react";
import { toast } from "sonner";

export default function SeoGeneratorPage() {
  const [products, setProducts] = useState([]);
  const [total, setTotal] = useState(0);
  const [pages, setPages] = useState(1);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [selectedSlug, setSelectedSlug] = useState(null);
  const [seoContent, setSeoContent] = useState(null);
  const [generating, setGenerating] = useState(false);
  const [copied, setCopied] = useState("");

  const fetchProducts = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await axios.get(`${API}/products`, {
        params: { search, page, limit: 30 },
        headers: getAuthHeaders(),
        withCredentials: true,
      });
      setProducts(data.products);
      setTotal(data.total);
      setPages(data.pages);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [search, page]);

  useEffect(() => { fetchProducts(); }, [fetchProducts]);

  const selectProduct = async (slug) => {
    setSelectedSlug(slug);
    setSeoContent(null);
    try {
      const { data } = await axios.get(`${API}/seo/${slug}`, { headers: getAuthHeaders(), withCredentials: true });
      if (data && data.seo_title) {
        setSeoContent(data);
      }
    } catch {
      // No existing SEO content
    }
  };

  const generateSeo = async () => {
    if (!selectedSlug) return;
    setGenerating(true);
    try {
      const { data } = await axios.post(`${API}/seo/generate/${selectedSlug}`, {}, { headers: getAuthHeaders(), withCredentials: true });
      setSeoContent(data);
      toast.success("SEO icerigi olusturuldu!");
    } catch (err) {
      toast.error(err.response?.data?.detail || "SEO uretimi basarisiz");
    } finally {
      setGenerating(false);
    }
  };

  const copyToClipboard = (text, field) => {
    navigator.clipboard.writeText(text);
    setCopied(field);
    setTimeout(() => setCopied(""), 2000);
    toast.success("Panoya kopyalandi");
  };

  const selectedProduct = products.find((p) => p.slug === selectedSlug);

  return (
    <div className="space-y-6" data-testid="seo-page">
      <div>
        <h2 className="text-2xl font-bold tracking-tight text-slate-900 font-heading">SEO Icerik Uretici</h2>
        <p className="text-sm text-slate-500 mt-1">AI ile urunleriniz icin SEO uyumlu baslik, aciklama ve urun icerigi uretin</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
        {/* Product List */}
        <div className="lg:col-span-2 space-y-4">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
            <Input
              data-testid="seo-search-input"
              placeholder="Urun ara..."
              value={search}
              onChange={(e) => { setSearch(e.target.value); setPage(1); }}
              className="pl-10 h-9 border-slate-300"
            />
          </div>

          <Card className="border-slate-200 shadow-sm overflow-hidden">
            <div className="max-h-[60vh] overflow-y-auto">
              {loading ? (
                <div className="p-4 space-y-2">
                  {[1,2,3].map((i) => <div key={i} className="h-12 bg-slate-100 rounded animate-pulse" />)}
                </div>
              ) : products.length === 0 ? (
                <div className="p-8 text-center text-slate-500 text-sm">Urun bulunamadi</div>
              ) : (
                <div className="divide-y divide-slate-100">
                  {products.map((p) => (
                    <button
                      key={p.slug}
                      data-testid={`seo-product-${p.slug}`}
                      onClick={() => selectProduct(p.slug)}
                      className={`w-full text-left px-4 py-3 hover:bg-slate-50 transition-colors flex items-center gap-3
                        ${selectedSlug === p.slug ? "bg-amber-50 border-l-2 border-amber-500" : ""}`}
                    >
                      {p.image_url && <img src={p.image_url} alt="" className="w-8 h-8 rounded object-cover flex-shrink-0" />}
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-medium text-slate-900 truncate">{p.name}</p>
                        <p className="text-[10px] text-slate-400 truncate">{p.slug}</p>
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </div>
          </Card>

          {pages > 1 && (
            <div className="flex items-center justify-between">
              <p className="text-xs text-slate-500">Sayfa {page}/{pages}</p>
              <div className="flex gap-1">
                <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(page - 1)} className="h-7"><ChevronLeft className="h-3 w-3" /></Button>
                <Button variant="outline" size="sm" disabled={page >= pages} onClick={() => setPage(page + 1)} className="h-7"><ChevronRight className="h-3 w-3" /></Button>
              </div>
            </div>
          )}
        </div>

        {/* SEO Content Panel */}
        <div className="lg:col-span-3 space-y-4">
          {selectedSlug ? (
            <>
              <Card className="border-slate-200 shadow-sm">
                <CardHeader className="pb-3">
                  <div className="flex items-center justify-between">
                    <div>
                      <CardTitle className="text-base font-semibold tracking-tight font-heading">{selectedProduct?.name}</CardTitle>
                      <p className="text-xs text-slate-500 mt-1">{selectedProduct?.url}</p>
                    </div>
                    <Button
                      onClick={generateSeo}
                      disabled={generating}
                      data-testid="generate-seo-button"
                      className="bg-amber-500 hover:bg-amber-600 text-black font-medium text-sm h-9"
                    >
                      {generating ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Sparkles className="h-4 w-4 mr-2" />}
                      {seoContent ? "Yeniden Uret" : "AI ile Uret"}
                    </Button>
                  </div>
                </CardHeader>
              </Card>

              {generating && (
                <Card className="border-amber-200 bg-amber-50">
                  <CardContent className="py-8 text-center">
                    <Loader2 className="h-8 w-8 animate-spin text-amber-500 mx-auto mb-3" />
                    <p className="text-sm font-medium text-amber-800">AI icerik uretiyor...</p>
                    <p className="text-xs text-amber-600 mt-1">Bu islem birkaç saniye surebilir</p>
                  </CardContent>
                </Card>
              )}

              {seoContent && !generating && (
                <div className="space-y-4">
                  {/* SEO Title */}
                  <Card className="border-slate-200 shadow-sm">
                    <CardHeader className="pb-2">
                      <div className="flex items-center justify-between">
                        <p className="text-[10px] uppercase tracking-wider font-semibold text-slate-500">SEO Baslik</p>
                        <Button
                          variant="ghost"
                          size="sm"
                          data-testid="copy-seo-title"
                          onClick={() => copyToClipboard(seoContent.seo_title, "title")}
                          className="h-7 text-xs text-slate-500"
                        >
                          {copied === "title" ? <Check className="h-3 w-3 text-emerald-500" /> : <Copy className="h-3 w-3" />}
                        </Button>
                      </div>
                    </CardHeader>
                    <CardContent className="pt-0">
                      <p className="text-sm font-medium text-slate-900" data-testid="seo-title-content">{seoContent.seo_title}</p>
                      <p className="text-[10px] text-slate-400 mt-1">{seoContent.seo_title?.length || 0} / 60 karakter</p>
                    </CardContent>
                  </Card>

                  {/* SEO Description */}
                  <Card className="border-slate-200 shadow-sm">
                    <CardHeader className="pb-2">
                      <div className="flex items-center justify-between">
                        <p className="text-[10px] uppercase tracking-wider font-semibold text-slate-500">Meta Aciklama</p>
                        <Button
                          variant="ghost"
                          size="sm"
                          data-testid="copy-seo-description"
                          onClick={() => copyToClipboard(seoContent.seo_description, "desc")}
                          className="h-7 text-xs text-slate-500"
                        >
                          {copied === "desc" ? <Check className="h-3 w-3 text-emerald-500" /> : <Copy className="h-3 w-3" />}
                        </Button>
                      </div>
                    </CardHeader>
                    <CardContent className="pt-0">
                      <p className="text-sm text-slate-700" data-testid="seo-description-content">{seoContent.seo_description}</p>
                      <p className="text-[10px] text-slate-400 mt-1">{seoContent.seo_description?.length || 0} / 160 karakter</p>
                    </CardContent>
                  </Card>

                  {/* SERP Preview */}
                  <Card className="border-slate-200 shadow-sm">
                    <CardHeader className="pb-2">
                      <p className="text-[10px] uppercase tracking-wider font-semibold text-slate-500">Google Onizleme</p>
                    </CardHeader>
                    <CardContent className="pt-0">
                      <div className="bg-white rounded-lg p-4 border border-slate-100">
                        <p className="text-xs text-emerald-700 truncate">{selectedProduct?.url}</p>
                        <p className="text-blue-800 text-base font-medium mt-1 hover:underline cursor-pointer line-clamp-1">{seoContent.seo_title}</p>
                        <p className="text-sm text-slate-600 mt-0.5 line-clamp-2">{seoContent.seo_description}</p>
                      </div>
                    </CardContent>
                  </Card>

                  {/* Product Description */}
                  <Card className="border-slate-200 shadow-sm">
                    <CardHeader className="pb-2">
                      <div className="flex items-center justify-between">
                        <p className="text-[10px] uppercase tracking-wider font-semibold text-slate-500">Urun Aciklamasi</p>
                        <Button
                          variant="ghost"
                          size="sm"
                          data-testid="copy-product-description"
                          onClick={() => copyToClipboard(seoContent.product_description, "prodDesc")}
                          className="h-7 text-xs text-slate-500"
                        >
                          {copied === "prodDesc" ? <Check className="h-3 w-3 text-emerald-500" /> : <Copy className="h-3 w-3" />}
                        </Button>
                      </div>
                    </CardHeader>
                    <CardContent className="pt-0">
                      <div className="prose prose-sm max-w-none text-slate-700 text-sm leading-relaxed whitespace-pre-wrap" data-testid="product-description-content">
                        {seoContent.product_description}
                      </div>
                    </CardContent>
                  </Card>

                  {seoContent.generated_at && (
                    <p className="text-[10px] text-slate-400 text-right">
                      Olusturulma: {new Date(seoContent.generated_at).toLocaleString('tr-TR')}
                    </p>
                  )}
                </div>
              )}

              {!seoContent && !generating && (
                <Card className="border-dashed border-slate-300">
                  <CardContent className="py-12 text-center">
                    <FileText className="h-10 w-10 mx-auto text-slate-300 mb-3" />
                    <p className="text-sm text-slate-500">Bu urun icin henuz SEO icerigi olusturulmamis</p>
                    <p className="text-xs text-slate-400 mt-1">"AI ile Uret" butonuna tiklayarak baslayabilirsiniz</p>
                  </CardContent>
                </Card>
              )}
            </>
          ) : (
            <Card className="border-dashed border-slate-300">
              <CardContent className="py-16 text-center">
                <Sparkles className="h-12 w-12 mx-auto text-amber-300 mb-4" />
                <p className="text-lg font-semibold text-slate-700 font-heading">SEO Icerik Uretici</p>
                <p className="text-sm text-slate-500 mt-2">Soldaki listeden bir urun secin ve AI ile SEO icerigi uretin</p>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
