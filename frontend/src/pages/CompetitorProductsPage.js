import { useState, useEffect, useCallback } from "react";
import { API, getAuthHeaders } from "../context/AuthContext";
import axios from "axios";
import { toast } from "sonner";
import { Search, Filter, ExternalLink, RefreshCw, Link2, Unlink, DollarSign, TrendingDown, ChevronLeft, ChevronRight, Loader2, Settings2, Eye } from "lucide-react";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../components/ui/dialog";

const COMPETITOR_ICONS = {
  mutfak10: { name: "M10", color: "#f97316", domain: "mutfak10.com" },
  cafemarkt: { name: "CM", color: "#3b82f6", domain: "cafemarkt.com" },
  mutbex: { name: "MX", color: "#22c55e", domain: "mutbex.com" },
  hakbilenler: { name: "HB", color: "#a855f7", domain: "hakbilenler.com.tr" },
};

export default function CompetitorProductsPage() {
  const [products, setProducts] = useState([]);
  const [categories, setCategories] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(0);
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("");
  const [loading, setLoading] = useState(false);
  const [matchingSlug, setMatchingSlug] = useState(null);
  const [checkingSlug, setCheckingSlug] = useState(null);
  const [detailProduct, setDetailProduct] = useState(null);
  const [matchDetail, setMatchDetail] = useState(null);
  const [priceHistory, setPriceHistory] = useState([]);
  const [categoryMatchStatus, setCategoryMatchStatus] = useState(null);
  const [editFloorPrice, setEditFloorPrice] = useState(null);

  const fetchProducts = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ page, limit: 30 });
      if (search) params.set("search", search);
      if (category) params.set("category", category);
      const { data } = await axios.get(`${API}/competitor/products?${params}`, { headers: getAuthHeaders(), withCredentials: true });
      setProducts(data.products || []);
      setTotal(data.total || 0);
      setPages(data.pages || 0);
      if (data.categories) setCategories(data.categories);
    } catch (err) {
      toast.error("Ürünler yüklenemedi");
    }
    setLoading(false);
  }, [page, search, category]);

  useEffect(() => { fetchProducts(); }, [fetchProducts]);

  const autoMatchProduct = async (slug) => {
    setMatchingSlug(slug);
    try {
      const { data } = await axios.post(`${API}/competitor/auto-match/${slug}`, {}, { headers: getAuthHeaders(), withCredentials: true });
      toast.success(`${data.matched}/${data.total} rakipte eşleşme bulundu`);
      fetchProducts();
    } catch (err) {
      toast.error("Eşleştirme başarısız");
    }
    setMatchingSlug(null);
  };

  const checkPrices = async (slug) => {
    setCheckingSlug(slug);
    try {
      const { data } = await axios.post(`${API}/competitor/check-price/${slug}`, {}, { headers: getAuthHeaders(), withCredentials: true });
      const count = Object.keys(data.prices || {}).length;
      toast.success(`${count} rakipten fiyat alındı`);
      fetchProducts();
    } catch (err) {
      toast.error("Fiyat kontrolü başarısız");
    }
    setCheckingSlug(null);
  };

  const autoMatchCategory = async () => {
    if (!category) { toast.error("Önce bir kategori seçin"); return; }
    try {
      const { data } = await axios.post(`${API}/competitor/auto-match-category/${encodeURIComponent(category)}`, {}, { headers: getAuthHeaders(), withCredentials: true });
      toast.success(`${data.total} ürün için eşleştirme başlatıldı`);
      setCategoryMatchStatus({ task_key: data.task_key, running: true, total: data.total, progress: 0 });
    } catch (err) {
      toast.error(err.response?.data?.detail || "Kategori eşleştirme başarısız");
    }
  };

  // Poll category match status
  useEffect(() => {
    if (!categoryMatchStatus?.running) return;
    const interval = setInterval(async () => {
      try {
        const { data } = await axios.get(`${API}/competitor/match-status/${categoryMatchStatus.task_key}`, { headers: getAuthHeaders(), withCredentials: true });
        setCategoryMatchStatus(prev => ({ ...prev, ...data }));
        if (!data.running) { clearInterval(interval); fetchProducts(); toast.success("Kategori eşleştirme tamamlandı"); }
      } catch {}
    }, 5000);
    return () => clearInterval(interval);
  }, [categoryMatchStatus?.running]);

  const openDetail = async (product) => {
    setDetailProduct(product);
    try {
      const [matchRes, histRes] = await Promise.all([
        axios.get(`${API}/competitor/matches/${product.slug}`, { headers: getAuthHeaders(), withCredentials: true }),
        axios.get(`${API}/competitor/price-history/${product.slug}`, { headers: getAuthHeaders(), withCredentials: true }),
      ]);
      setMatchDetail(matchRes.data.matches || []);
      setPriceHistory(histRes.data.history || []);
    } catch {}
  };

  const saveFloorPrice = async (slug, floorPrice, purchasePrice) => {
    try {
      await axios.put(`${API}/competitor/price-settings/${slug}`, {
        floor_price: floorPrice ? parseFloat(floorPrice) : null,
        purchase_price: purchasePrice ? parseFloat(purchasePrice) : null,
      }, { headers: getAuthHeaders(), withCredentials: true });
      toast.success("Fiyat ayarları kaydedildi");
      setEditFloorPrice(null);
      fetchProducts();
    } catch { toast.error("Kaydetme başarısız"); }
  };

  const formatPrice = (price) => {
    if (!price && price !== 0) return "-";
    return new Intl.NumberFormat("tr-TR", { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(price) + " ₺";
  };

  return (
    <div className="space-y-4" data-testid="competitor-products-page">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-slate-900" data-testid="page-title">Ürünler & Rakip Fiyat Takibi</h1>
          <p className="text-sm text-slate-500">{total} ürün</p>
        </div>
        <div className="flex gap-2">
          {category && (
            <Button size="sm" onClick={autoMatchCategory} disabled={categoryMatchStatus?.running} data-testid="match-category-btn" className="bg-violet-600 hover:bg-violet-700 text-white">
              {categoryMatchStatus?.running ? (
                <><Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />{categoryMatchStatus.progress}/{categoryMatchStatus.total}</>
              ) : (
                <><Link2 className="h-3.5 w-3.5 mr-1.5" />Kategoriyi Eşleştir</>
              )}
            </Button>
          )}
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-3 flex-wrap" data-testid="filters">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
          <Input placeholder="Ürün ara..." value={search} onChange={e => { setSearch(e.target.value); setPage(1); }} className="pl-9" data-testid="search-input" />
        </div>
        <select value={category} onChange={e => { setCategory(e.target.value); setPage(1); }} className="border rounded-md px-3 py-2 text-sm bg-white min-w-[180px]" data-testid="category-filter">
          <option value="">Tüm Kategoriler</option>
          {categories.map(c => <option key={c} value={c}>{c}</option>)}
        </select>
      </div>

      {/* Products Table */}
      <div className="bg-white rounded-xl border shadow-sm overflow-hidden" data-testid="products-table">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 border-b">
              <tr>
                <th className="text-left px-4 py-3 font-semibold text-slate-700">Ürün</th>
                <th className="text-center px-3 py-3 font-semibold text-slate-700">Fiyat</th>
                <th className="text-center px-3 py-3 font-semibold text-slate-700">Dip Fiyat</th>
                <th className="text-center px-3 py-3 font-semibold text-slate-700">Rakipler</th>
                <th className="text-center px-3 py-3 font-semibold text-slate-700">En Ucuz Rakip</th>
                <th className="text-center px-3 py-3 font-semibold text-slate-700">İşlemler</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {loading ? (
                <tr><td colSpan={6} className="text-center py-12"><Loader2 className="h-6 w-6 animate-spin mx-auto text-slate-400" /></td></tr>
              ) : products.length === 0 ? (
                <tr><td colSpan={6} className="text-center py-12 text-slate-400">Ürün bulunamadı</td></tr>
              ) : products.map(p => (
                <tr key={p.slug} className="hover:bg-slate-50 transition-colors" data-testid={`product-row-${p.slug}`}>
                  {/* Product Name + Category */}
                  <td className="px-4 py-3">
                    <div className="font-medium text-slate-900 text-sm leading-tight max-w-[280px] truncate">{p.name}</div>
                    <div className="flex gap-1.5 mt-1">
                      <span className="text-xs text-slate-400">{p.brand || ""}</span>
                      {p.category && <span className="text-xs bg-slate-100 text-slate-500 px-1.5 py-0.5 rounded">{p.category}</span>}
                    </div>
                  </td>
                  {/* Our Price */}
                  <td className="text-center px-3 py-3">
                    <div className="font-semibold text-slate-900">{formatPrice(p.price || p.our_price)}</div>
                    {p.price_list_currency && (
                      <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${p.price_list_currency === 'EUR' ? 'bg-blue-100 text-blue-700' : p.price_list_currency === 'USD' ? 'bg-green-100 text-green-700' : 'bg-amber-100 text-amber-700'}`}>
                        {p.price_list_currency}
                      </span>
                    )}
                  </td>
                  {/* Floor Price */}
                  <td className="text-center px-3 py-3">
                    {editFloorPrice === p.slug ? (
                      <div className="flex gap-1 items-center justify-center">
                        <input type="number" defaultValue={p.floor_price || ""} id={`floor-${p.slug}`} className="w-20 border rounded px-1 py-0.5 text-xs" placeholder="Dip" />
                        <Button size="sm" variant="ghost" className="h-6 text-xs px-1" onClick={() => {
                          const val = document.getElementById(`floor-${p.slug}`).value;
                          saveFloorPrice(p.slug, val, p.purchase_price);
                        }}>✓</Button>
                        <Button size="sm" variant="ghost" className="h-6 text-xs px-1" onClick={() => setEditFloorPrice(null)}>✕</Button>
                      </div>
                    ) : (
                      <button onClick={() => setEditFloorPrice(p.slug)} className="text-xs text-slate-500 hover:text-slate-800 hover:bg-slate-100 px-2 py-1 rounded transition-colors" data-testid={`floor-price-${p.slug}`}>
                        {p.floor_price ? formatPrice(p.floor_price) : <span className="text-slate-300">Ayarla</span>}
                      </button>
                    )}
                  </td>
                  {/* Competitor Icons */}
                  <td className="text-center px-3 py-3">
                    <div className="flex gap-1 justify-center">
                      {Object.entries(COMPETITOR_ICONS).map(([key, comp]) => {
                        const match = (p.competitor_matches || {})[key];
                        return (
                          <a key={key} href={match?.url || "#"} target={match ? "_blank" : undefined} rel="noopener noreferrer"
                            className={`w-7 h-7 rounded-full flex items-center justify-center text-[10px] font-bold text-white transition-all ${match ? "opacity-100 hover:scale-110 cursor-pointer" : "opacity-20 cursor-default"}`}
                            style={{ backgroundColor: comp.color }}
                            title={match ? `${comp.name}: ${match.title || match.url}` : `${comp.name}: Eşleşme yok`}
                            data-testid={`competitor-icon-${key}-${p.slug}`}>
                            {comp.name}
                          </a>
                        );
                      })}
                    </div>
                  </td>
                  {/* Cheapest Competitor */}
                  <td className="text-center px-3 py-3">
                    {p.cheapest_competitor_price ? (
                      <div>
                        <div className={`font-semibold text-sm ${p.cheapest_competitor_price < (p.price || p.our_price || 0) ? "text-red-600" : "text-emerald-600"}`}>
                          {formatPrice(p.cheapest_competitor_price)}
                        </div>
                        <div className="text-[10px] text-slate-400">{p.cheapest_competitor_name}</div>
                      </div>
                    ) : (
                      <span className="text-xs text-slate-300">-</span>
                    )}
                  </td>
                  {/* Actions */}
                  <td className="text-center px-3 py-3">
                    <div className="flex gap-1 justify-center">
                      <Button size="sm" variant="ghost" className="h-7 w-7 p-0" title="Eşleştir" onClick={() => autoMatchProduct(p.slug)} disabled={matchingSlug === p.slug} data-testid={`match-btn-${p.slug}`}>
                        {matchingSlug === p.slug ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Link2 className="h-3.5 w-3.5" />}
                      </Button>
                      <Button size="sm" variant="ghost" className="h-7 w-7 p-0" title="Fiyat Kontrol" onClick={() => checkPrices(p.slug)} disabled={checkingSlug === p.slug || !p.match_count} data-testid={`check-btn-${p.slug}`}>
                        {checkingSlug === p.slug ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <TrendingDown className="h-3.5 w-3.5" />}
                      </Button>
                      <Button size="sm" variant="ghost" className="h-7 w-7 p-0" title="Detay" onClick={() => openDetail(p)} data-testid={`detail-btn-${p.slug}`}>
                        <Eye className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        
        {/* Pagination */}
        {pages > 1 && (
          <div className="flex items-center justify-between px-4 py-3 border-t bg-slate-50">
            <span className="text-sm text-slate-500">Sayfa {page}/{pages} ({total} ürün)</span>
            <div className="flex gap-1">
              <Button size="sm" variant="outline" disabled={page <= 1} onClick={() => setPage(p => p - 1)} data-testid="prev-page">
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <Button size="sm" variant="outline" disabled={page >= pages} onClick={() => setPage(p => p + 1)} data-testid="next-page">
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          </div>
        )}
      </div>

      {/* Product Detail Modal */}
      <Dialog open={!!detailProduct} onOpenChange={() => { setDetailProduct(null); setMatchDetail(null); setPriceHistory([]); }}>
        <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="text-lg">{detailProduct?.name}</DialogTitle>
          </DialogHeader>
          {detailProduct && (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-3 text-sm">
                <div><span className="text-slate-500">Marka:</span> <strong>{detailProduct.brand || "-"}</strong></div>
                <div><span className="text-slate-500">Kategori:</span> <strong>{detailProduct.category || "-"}</strong></div>
                <div><span className="text-slate-500">Fiyat:</span> <strong>{formatPrice(detailProduct.price || detailProduct.our_price)}</strong></div>
                <div><span className="text-slate-500">Dip Fiyat:</span> <strong>{detailProduct.floor_price ? formatPrice(detailProduct.floor_price) : "Ayarlanmadı"}</strong></div>
                <div><span className="text-slate-500">Alış Fiyatı:</span> <strong>{detailProduct.purchase_price ? formatPrice(detailProduct.purchase_price) : "Girilmedi"}</strong></div>
              </div>
              
              {/* Competitor Matches */}
              <div>
                <h3 className="font-semibold text-sm mb-2">Rakip Eşleştirmeleri</h3>
                <div className="space-y-2">
                  {matchDetail?.length ? matchDetail.map(m => (
                    <div key={m.competitor_key} className="flex items-center gap-2 p-2 bg-slate-50 rounded-lg text-sm">
                      <div className="w-8 h-8 rounded-full flex items-center justify-center text-[10px] font-bold text-white" style={{ backgroundColor: COMPETITOR_ICONS[m.competitor_key]?.color || "#888" }}>
                        {COMPETITOR_ICONS[m.competitor_key]?.name || "?"}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="font-medium truncate">{m.title || m.url}</div>
                        <a href={m.url} target="_blank" rel="noopener noreferrer" className="text-xs text-blue-500 hover:underline truncate block">{m.url}</a>
                      </div>
                      <span className={`text-xs px-2 py-0.5 rounded ${m.manual ? "bg-amber-100 text-amber-700" : "bg-emerald-100 text-emerald-700"}`}>
                        {m.manual ? "Manuel" : "Otomatik"}
                      </span>
                    </div>
                  )) : <p className="text-sm text-slate-400">Henüz eşleştirme yok</p>}
                </div>
              </div>
              
              {/* Price History */}
              {priceHistory.length > 0 && (
                <div>
                  <h3 className="font-semibold text-sm mb-2">Fiyat Geçmişi</h3>
                  <div className="space-y-1 max-h-40 overflow-y-auto">
                    {priceHistory.map((h, i) => (
                      <div key={i} className="flex items-center gap-2 text-xs p-1.5 bg-slate-50 rounded">
                        <span className="text-slate-400">{new Date(h.checked_at).toLocaleDateString("tr-TR")}</span>
                        {Object.entries(h.prices || {}).map(([k, v]) => (
                          <span key={k} className="px-1.5 py-0.5 rounded text-white text-[10px] font-medium" style={{ backgroundColor: COMPETITOR_ICONS[k]?.color || "#888" }}>
                            {COMPETITOR_ICONS[k]?.name}: {formatPrice(v.price)}
                          </span>
                        ))}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
