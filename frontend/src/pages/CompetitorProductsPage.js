import { useState, useEffect, useCallback, useRef } from "react";
import { API, getAuthHeaders } from "../context/AuthContext";
import axios from "axios";
import { toast } from "sonner";
import {
  Search, ExternalLink, RefreshCw, Link2, Unlink, TrendingDown,
  ChevronLeft, ChevronRight, Loader2, Eye, Tag, ShoppingCart,
  ArrowUpDown, X, Check, AlertTriangle
} from "lucide-react";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../components/ui/dialog";

const COMPETITOR_ICONS = {
  mutfak10: { name: "M10", color: "#f97316", domain: "mutfak10.com" },
  cafemarkt: { name: "CM", color: "#3b82f6", domain: "cafemarkt.com" },
  mutbex: { name: "MX", color: "#22c55e", domain: "mutbex.com" },
  hakbilenler: { name: "HB", color: "#a855f7", domain: "hakbilenler.com.tr" },
};

const CURRENCY_STYLES = {
  EUR: { bg: "bg-blue-50 text-blue-700 border-blue-200", label: "EUR" },
  USD: { bg: "bg-emerald-50 text-emerald-700 border-emerald-200", label: "USD" },
  TRY: { bg: "bg-amber-50 text-amber-700 border-amber-200", label: "TL" },
  TL: { bg: "bg-amber-50 text-amber-700 border-amber-200", label: "TL" },
};

export default function CompetitorProductsPage() {
  const [products, setProducts] = useState([]);
  const [categories, setCategories] = useState([]);
  const [subCategories, setSubCategories] = useState([]);
  const [brands, setBrands] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(0);
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("");
  const [brand, setBrand] = useState("");
  const [matchStatus, setMatchStatus] = useState("");
  const [loading, setLoading] = useState(false);
  const [matchingSlug, setMatchingSlug] = useState(null);
  const [checkingSlug, setCheckingSlug] = useState(null);
  const [detailProduct, setDetailProduct] = useState(null);
  const [matchDetail, setMatchDetail] = useState(null);
  const [priceHistory, setPriceHistory] = useState([]);
  const [ikasPrice, setIkasPrice] = useState([]);
  const [categoryMatchStatus, setCategoryMatchStatus] = useState(null);
  const [editingSlug, setEditingSlug] = useState(null);
  const [editFloor, setEditFloor] = useState("");
  const [editPurchase, setEditPurchase] = useState("");
  const [editingMatchKey, setEditingMatchKey] = useState(null);
  const searchTimer = useRef(null);

  const fetchProducts = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ page, limit: 30 });
      if (search) params.set("search", search);
      if (category) params.set("category", category);
      if (brand) params.set("brand", brand);
      if (matchStatus) params.set("match_status", matchStatus);
      const { data } = await axios.get(`${API}/competitor/products?${params}`, { headers: getAuthHeaders(), withCredentials: true });
      setProducts(data.products || []);
      setTotal(data.total || 0);
      setPages(data.pages || 0);
      if (data.categories) setCategories(data.categories);
      if (data.sub_categories) setSubCategories(data.sub_categories);
      if (data.brands) setBrands(data.brands);
    } catch (err) {
      toast.error("Ürünler yüklenemedi");
    }
    setLoading(false);
  }, [page, search, category, brand, matchStatus]);

  useEffect(() => { fetchProducts(); }, [fetchProducts]);

  const handleSearch = (val) => {
    if (searchTimer.current) clearTimeout(searchTimer.current);
    searchTimer.current = setTimeout(() => { setSearch(val); setPage(1); }, 400);
  };

  const autoMatchProduct = async (slug) => {
    setMatchingSlug(slug);
    try {
      const { data } = await axios.post(`${API}/competitor/auto-match/${slug}`, {}, { headers: getAuthHeaders(), withCredentials: true });
      toast.info(data.message || "Eşleştirme başlatıldı...");
      
      // Poll for completion
      if (data.task_key) {
        const pollInterval = setInterval(async () => {
          try {
            const { data: status } = await axios.get(`${API}/competitor/auto-match-status/${data.task_key}`, { headers: getAuthHeaders(), withCredentials: true });
            if (!status.running) {
              clearInterval(pollInterval);
              setMatchingSlug(null);
              if (status.error) {
                toast.error(`Eşleştirme hatası: ${status.error.substring(0, 100)}`);
              } else {
                toast.success(`${status.matched}/${Object.keys(status.results || {}).length} rakipte eşleşme bulundu`);
              }
              fetchProducts();
            }
          } catch {
            clearInterval(pollInterval);
            setMatchingSlug(null);
          }
        }, 2000);
      } else {
        setMatchingSlug(null);
      }
    } catch (err) {
      toast.error(err.response?.data?.detail || "Eşleştirme başlatılamadı");
      setMatchingSlug(null);
    }
  };

  const checkPrices = async (slug) => {
    setCheckingSlug(slug);
    try {
      const { data } = await axios.post(`${API}/competitor/check-price/${slug}`, {}, { headers: getAuthHeaders(), withCredentials: true });
      toast.info("Fiyat taraması başlatıldı...");
      if (data.task_key) {
        const poll = setInterval(async () => {
          try {
            const { data: st } = await axios.get(`${API}/competitor/check-price-status/${data.task_key}`, { headers: getAuthHeaders(), withCredentials: true });
            if (!st.running) {
              clearInterval(poll);
              setCheckingSlug(null);
              const priceCount = Object.keys(st.prices || {}).length;
              if (st.error) toast.error(`Tarama hatası: ${st.error.substring(0, 80)}`);
              else toast.success(`${priceCount} rakipten fiyat alındı`);
              fetchProducts();
            }
          } catch { clearInterval(poll); setCheckingSlug(null); }
        }, 3000);
      } else { setCheckingSlug(null); }
    } catch (err) {
      toast.error("Fiyat kontrolü başarısız");
      setCheckingSlug(null);
    }
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

  const startEditing = (p) => {
    setEditingSlug(p.slug);
    setEditFloor(p.floor_price || "");
    setEditPurchase(p.purchase_price || "");
  };

  const savePriceSettings = async (slug) => {
    try {
      await axios.put(`${API}/competitor/price-settings/${slug}`, {
        floor_price: editFloor ? parseFloat(editFloor) : null,
        purchase_price: editPurchase ? parseFloat(editPurchase) : null,
      }, { headers: getAuthHeaders(), withCredentials: true });
      toast.success("Fiyat ayarları kaydedildi");
      setEditingSlug(null);
      fetchProducts();
    } catch { toast.error("Kaydetme başarısız"); }
  };

  const openDetail = async (product) => {
    setDetailProduct(product);
    setIkasPrice([]);
    try {
      const [matchRes, histRes, ikasRes] = await Promise.all([
        axios.get(`${API}/competitor/matches/${product.slug}`, { headers: getAuthHeaders(), withCredentials: true }),
        axios.get(`${API}/competitor/price-history/${product.slug}`, { headers: getAuthHeaders(), withCredentials: true }),
        axios.get(`${API}/competitor/ikas-price/${product.slug}`, { headers: getAuthHeaders(), withCredentials: true }).catch(() => ({ data: { prices: [] } })),
      ]);
      setMatchDetail(matchRes.data.matches || []);
      setPriceHistory(histRes.data.history || []);
      setIkasPrice(ikasRes.data.prices || []);
    } catch {}
  };

  const formatPrice = (price) => {
    if (!price && price !== 0) return "-";
    return new Intl.NumberFormat("tr-TR", { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(price);
  };

  const clearFilters = () => {
    setCategory("");
    setBrand("");
    setMatchStatus("");
    setSearch("");
    setPage(1);
  };

  const hasFilters = category || brand || matchStatus || search;

  return (
    <div className="space-y-4" data-testid="competitor-products-page">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h1 className="text-xl font-bold text-slate-900" data-testid="page-title">Rakip Fiyat Takibi</h1>
          <p className="text-sm text-slate-500">{total} ürün listeleniyor</p>
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

      {/* Category Match Progress */}
      {categoryMatchStatus?.running && (
        <div className="bg-violet-50 border border-violet-200 rounded-xl p-4" data-testid="category-match-progress">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <Loader2 className="h-4 w-4 animate-spin text-violet-600" />
              <span className="font-medium text-sm text-violet-900">Kategori eşleştirme devam ediyor...</span>
            </div>
            <span className="text-sm text-violet-700 font-mono">{categoryMatchStatus.progress || 0}/{categoryMatchStatus.total || 0}</span>
          </div>
          <div className="w-full bg-violet-200 rounded-full h-2">
            <div className="bg-violet-600 h-2 rounded-full transition-all duration-500" style={{ width: `${categoryMatchStatus.total ? (categoryMatchStatus.progress / categoryMatchStatus.total * 100) : 0}%` }} />
          </div>
          <p className="text-xs text-violet-600 mt-1.5">Eşleşme bulunan: {categoryMatchStatus.matched || 0} ürün</p>
        </div>
      )}

      {/* Filters */}
      <div className="bg-white rounded-xl border p-3 shadow-sm" data-testid="filters">
        <div className="flex gap-2 flex-wrap items-center">
          {/* Search */}
          <div className="relative flex-1 min-w-[200px]">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
            <Input
              placeholder="Ürün ara..."
              defaultValue={search}
              onChange={e => handleSearch(e.target.value)}
              className="pl-9 h-9"
              data-testid="search-input"
            />
          </div>
          {/* Category */}
          <select
            value={category}
            onChange={e => { setCategory(e.target.value); setPage(1); }}
            className="border rounded-lg px-3 h-9 text-sm bg-white min-w-[180px] focus:ring-2 focus:ring-violet-200 focus:border-violet-400 outline-none"
            data-testid="category-filter"
          >
            <option value="">{`Tüm Kategoriler (${categories.length})`}</option>
            {categories.map(c => <option key={c} value={c}>{c}</option>)}
            {subCategories.length > 0 && (
              <>
                <option disabled>── Alt Kategoriler ──</option>
                {subCategories.map(c => <option key={c} value={c}>{c}</option>)}
              </>
            )}
          </select>
          {/* Brand */}
          <select
            value={brand}
            onChange={e => { setBrand(e.target.value); setPage(1); }}
            className="border rounded-lg px-3 h-9 text-sm bg-white min-w-[150px] focus:ring-2 focus:ring-violet-200 focus:border-violet-400 outline-none"
            data-testid="brand-filter"
          >
            <option value="">{`Tüm Markalar (${brands.length})`}</option>
            {brands.map(b => <option key={b} value={b}>{b}</option>)}
          </select>
          {/* Match Status */}
          <select
            value={matchStatus}
            onChange={e => { setMatchStatus(e.target.value); setPage(1); }}
            className="border rounded-lg px-3 h-9 text-sm bg-white min-w-[140px] focus:ring-2 focus:ring-violet-200 focus:border-violet-400 outline-none"
            data-testid="match-status-filter"
          >
            <option value="">Tüm Durum</option>
            <option value="matched">Eşleşmiş</option>
            <option value="unmatched">Eşleşmemiş</option>
          </select>
          {/* Clear Filters */}
          {hasFilters && (
            <Button size="sm" variant="ghost" onClick={clearFilters} className="h-9 px-2 text-slate-500" data-testid="clear-filters-btn">
              <X className="h-4 w-4" />
            </Button>
          )}
        </div>
      </div>

      {/* Products Table */}
      <div className="bg-white rounded-xl border shadow-sm overflow-hidden" data-testid="products-table">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 border-b">
              <tr>
                <th className="text-left px-4 py-3 font-semibold text-slate-600 text-xs uppercase tracking-wide">Ürün</th>
                <th className="text-center px-3 py-3 font-semibold text-slate-600 text-xs uppercase tracking-wide">Fiyat (TL)</th>
                <th className="text-center px-3 py-3 font-semibold text-slate-600 text-xs uppercase tracking-wide">Alış Fiyatı</th>
                <th className="text-center px-3 py-3 font-semibold text-slate-600 text-xs uppercase tracking-wide">Dip Fiyat</th>
                <th className="text-center px-3 py-3 font-semibold text-slate-600 text-xs uppercase tracking-wide">Rakipler</th>
                <th className="text-center px-3 py-3 font-semibold text-slate-600 text-xs uppercase tracking-wide">En Ucuz Rakip</th>
                <th className="text-center px-3 py-3 font-semibold text-slate-600 text-xs uppercase tracking-wide w-[100px]">İşlemler</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {loading ? (
                <tr><td colSpan={7} className="text-center py-16"><Loader2 className="h-6 w-6 animate-spin mx-auto text-slate-400" /></td></tr>
              ) : products.length === 0 ? (
                <tr><td colSpan={7} className="text-center py-16 text-slate-400">Ürün bulunamadı</td></tr>
              ) : products.map(p => (
                <ProductRow
                  key={p.slug}
                  p={p}
                  editingSlug={editingSlug}
                  editFloor={editFloor}
                  editPurchase={editPurchase}
                  setEditFloor={setEditFloor}
                  setEditPurchase={setEditPurchase}
                  startEditing={startEditing}
                  savePriceSettings={savePriceSettings}
                  setEditingSlug={setEditingSlug}
                  matchingSlug={matchingSlug}
                  checkingSlug={checkingSlug}
                  autoMatchProduct={autoMatchProduct}
                  checkPrices={checkPrices}
                  openDetail={openDetail}
                  formatPrice={formatPrice}
                />
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
              {Array.from({ length: Math.min(5, pages) }, (_, i) => {
                const startPage = Math.max(1, Math.min(page - 2, pages - 4));
                const pageNum = startPage + i;
                if (pageNum > pages) return null;
                return (
                  <Button key={pageNum} size="sm" variant={pageNum === page ? "default" : "outline"} onClick={() => setPage(pageNum)} className="w-8 h-8 p-0">
                    {pageNum}
                  </Button>
                );
              })}
              <Button size="sm" variant="outline" disabled={page >= pages} onClick={() => setPage(p => p + 1)} data-testid="next-page">
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          </div>
        )}
      </div>

      {/* Product Detail Modal */}
      <Dialog open={!!detailProduct} onOpenChange={() => { setDetailProduct(null); setMatchDetail(null); setPriceHistory([]); setIkasPrice([]); }}>
        <DialogContent className="max-w-lg max-h-[85vh] overflow-y-auto p-0">
          <DialogHeader className="px-6 pt-6 pb-4 border-b bg-slate-50 sticky top-0 z-10">
            <DialogTitle className="text-lg font-bold text-slate-900 pr-8" data-testid="detail-modal-title">{detailProduct?.name}</DialogTitle>
          </DialogHeader>
          {detailProduct && (
            <div className="px-6 pb-6 space-y-5">
              {/* Quick Actions */}
              <div className="flex gap-2 pt-4 flex-wrap" data-testid="detail-actions">
                <Button size="sm" variant="outline" onClick={async () => {
                  try {
                    toast.info("Rakip fiyatları taranıyor...");
                    await axios.post(`${API}/competitor/check-price/${detailProduct.slug}`, {}, { headers: getAuthHeaders(), withCredentials: true });
                    toast.success("Fiyatlar güncellendi");
                    openDetail(detailProduct);
                    fetchProducts();
                  } catch { toast.error("Tarama başarısız"); }
                }} disabled={!detailProduct.match_count} data-testid="detail-scan-btn">
                  <TrendingDown className="h-3.5 w-3.5 mr-1.5" /> Rakip Fiyat Tara
                </Button>
                <Button size="sm" variant="outline" onClick={async () => {
                  toast.info("Eşleştirme başlatıldı...");
                  autoMatchProduct(detailProduct.slug);
                }} data-testid="detail-match-btn">
                  <Link2 className="h-3.5 w-3.5 mr-1.5" /> Eşleştir
                </Button>
              </div>

              {/* Price Overview Cards */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <PriceCard label="Satış Fiyatı" value={formatPrice(detailProduct.our_price)} suffix="₺" color="text-slate-900" />
                <PriceCard label="Alış Fiyatı" value={detailProduct.purchase_price ? formatPrice(detailProduct.purchase_price) : "-"} suffix={detailProduct.purchase_price ? "₺" : ""} color="text-blue-700" />
                <PriceCard label="Dip Fiyat" value={detailProduct.floor_price ? formatPrice(detailProduct.floor_price) : "-"} suffix={detailProduct.floor_price ? "₺" : ""} color="text-orange-700" />
                <PriceCard label="En Ucuz Rakip" value={detailProduct.cheapest_competitor_price ? formatPrice(detailProduct.cheapest_competitor_price) : "-"} suffix={detailProduct.cheapest_competitor_price ? "₺" : ""} sub={detailProduct.cheapest_competitor_name || ""} color={detailProduct.cheapest_competitor_price && detailProduct.cheapest_competitor_price < detailProduct.our_price ? "text-red-600" : "text-emerald-700"} />
              </div>

              {/* Safety warning if no floor/purchase */}
              {!detailProduct.floor_price && !detailProduct.purchase_price && (
                <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-xs text-red-700 flex items-center gap-2">
                  <AlertTriangle className="h-4 w-4 shrink-0" />
                  <span><strong>Dip fiyat ve alış fiyatı girilmemiş.</strong> Bu ürünün fiyatı otomatik olarak güncellenmez. Lütfen tabloda alış fiyatı veya dip fiyat girin.</span>
                </div>
              )}

              {/* İkas Price Lists */}
              {ikasPrice.length > 0 && (
                <div>
                  <h3 className="text-sm font-semibold text-slate-700 mb-2 flex items-center gap-1.5">
                    <ArrowUpDown className="h-4 w-4" /> İkas Fiyat Listeleri
                  </h3>
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                    {ikasPrice.map((ip, i) => {
                      const cs = CURRENCY_STYLES[ip.currency] || CURRENCY_STYLES.TRY;
                      return (
                        <div key={i} className={`rounded-lg border px-3 py-2 ${cs.bg}`}>
                          <div className="text-xs opacity-70">{cs.label} Fiyat Listesi</div>
                          <div className="font-bold text-lg">{formatPrice(ip.sell_price)} {cs.label}</div>
                          {ip.discount_price && <div className="text-xs line-through opacity-60">{formatPrice(ip.discount_price)} {cs.label}</div>}
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Product Info */}
              <div className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm bg-slate-50 rounded-lg p-3">
                <div><span className="text-slate-500">Marka:</span> <strong>{detailProduct.brand || "-"}</strong></div>
                <div><span className="text-slate-500">Kategori:</span> <strong>{detailProduct.category || "-"}</strong></div>
                {detailProduct.subcategory && (
                  <div className="col-span-2"><span className="text-slate-500">Alt Kategori:</span> <strong>{detailProduct.subcategory}</strong></div>
                )}
                {detailProduct.gtin && (
                  <div><span className="text-slate-500">GTIN:</span> <strong>{detailProduct.gtin}</strong></div>
                )}
              </div>

              {/* Competitor Matches */}
              <div>
                <h3 className="text-sm font-semibold text-slate-700 mb-2 flex items-center gap-1.5">
                  <Link2 className="h-4 w-4" /> Rakip Eşleştirmeleri ({matchDetail?.length || 0}/4)
                </h3>
                <div className="space-y-2">
                  {Object.entries(COMPETITOR_ICONS).map(([key, comp]) => {
                    const match = matchDetail?.find(m => m.competitor_key === key);
                    const price = detailProduct.competitor_prices?.[key];
                    const isEditing = editingMatchKey === key;
                    if (match && !isEditing) {
                      return (
                        <div key={key} className="flex items-center gap-2 p-2.5 bg-white border border-emerald-200 rounded-lg">
                          <div className="w-8 h-8 rounded-full flex items-center justify-center text-[10px] font-bold text-white shrink-0" style={{ backgroundColor: comp.color }}>
                            {comp.name}
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="font-medium text-xs truncate">{match.title || "Eşleşmiş"}</div>
                            <a href={match.url} target="_blank" rel="noopener noreferrer" className="text-[11px] text-blue-500 hover:underline truncate block">{match.url}</a>
                          </div>
                          {price && <div className="font-bold text-xs shrink-0">{formatPrice(price.price)} ₺</div>}
                          <div className="flex gap-0.5 shrink-0">
                            <button onClick={() => setEditingMatchKey(key)} className="text-slate-400 hover:text-blue-600 p-1 rounded hover:bg-blue-50" title="Düzenle"><Eye className="h-3 w-3" /></button>
                            <button onClick={async () => {
                              try {
                                await axios.delete(`${API}/competitor/match/${detailProduct.slug}/${key}`, { headers: getAuthHeaders(), withCredentials: true });
                                toast.success(`${comp.name} eşleşmesi kaldırıldı`);
                                openDetail(detailProduct); fetchProducts();
                              } catch { toast.error("Silme başarısız"); }
                            }} className="text-slate-400 hover:text-red-600 p-1 rounded hover:bg-red-50" title="Sil"><X className="h-3 w-3" /></button>
                          </div>
                        </div>
                      );
                    }
                    // Unmatched or editing — show URL input
                    return (
                      <div key={key} className={`flex items-center gap-2 p-2.5 border rounded-lg ${match ? "bg-blue-50 border-blue-200" : "bg-slate-50 border-dashed border-slate-300"}`}>
                        <div className={`w-8 h-8 rounded-full flex items-center justify-center text-[10px] font-bold text-white shrink-0 ${match ? "" : "opacity-40"}`} style={{ backgroundColor: comp.color }}>
                          {comp.name}
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="text-[11px] text-slate-400 mb-1">{comp.domain} {match ? "— Link düzenle" : "— Eşleşme yok"}</div>
                          <form className="flex gap-1" onSubmit={async (e) => {
                            e.preventDefault();
                            const url = e.target.url.value.trim();
                            if (!url) return;
                            try {
                              await axios.post(`${API}/competitor/match/${detailProduct.slug}`, {
                                competitor_key: key, url, title: ""
                              }, { headers: getAuthHeaders(), withCredentials: true });
                              toast.success(`${comp.name} eşleştirildi`);
                              setEditingMatchKey(null);
                              openDetail(detailProduct); fetchProducts();
                            } catch { toast.error("Eşleştirme başarısız"); }
                          }}>
                            <input name="url" defaultValue={match?.url || ""} placeholder={`${comp.domain} ürün URL'si`} className="flex-1 text-xs border rounded px-2 py-1 focus:ring-1 focus:ring-violet-300 outline-none" />
                            <Button type="submit" size="sm" variant="outline" className="h-7 text-xs px-2">Kaydet</Button>
                            {match && <Button type="button" size="sm" variant="ghost" className="h-7 text-xs px-1" onClick={() => setEditingMatchKey(null)}>İptal</Button>}
                          </form>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Price History */}
              {priceHistory.length > 0 && (
                <div>
                  <h3 className="text-sm font-semibold text-slate-700 mb-2 flex items-center gap-1.5">
                    <TrendingDown className="h-4 w-4" /> Fiyat Geçmişi
                  </h3>
                  <div className="space-y-1.5 max-h-48 overflow-y-auto">
                    {priceHistory.map((h, i) => (
                      <div key={i} className="flex items-center gap-2 text-xs p-2 bg-slate-50 rounded-lg border">
                        <span className="text-slate-500 shrink-0">{new Date(h.checked_at).toLocaleDateString("tr-TR")} {new Date(h.checked_at).toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" })}</span>
                        <div className="flex gap-1.5 flex-wrap">
                          {Object.entries(h.prices || {}).map(([k, v]) => (
                            <span key={k} className="px-2 py-0.5 rounded text-white font-medium" style={{ backgroundColor: COMPETITOR_ICONS[k]?.color || "#888" }}>
                              {COMPETITOR_ICONS[k]?.name}: {formatPrice(v.price)} ₺
                            </span>
                          ))}
                        </div>
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

/* --- Sub-components --- */

function PriceCard({ label, value, suffix, color, sub }) {
  return (
    <div className="bg-white border rounded-lg p-3 text-center">
      <div className="text-[11px] text-slate-500 uppercase tracking-wide mb-1">{label}</div>
      <div className={`font-bold text-lg ${color}`}>{value} <span className="text-xs font-normal">{suffix}</span></div>
      {sub && <div className="text-[10px] text-slate-400 mt-0.5">{sub}</div>}
    </div>
  );
}

function ProductRow({
  p, editingSlug, editFloor, editPurchase, setEditFloor, setEditPurchase,
  startEditing, savePriceSettings, setEditingSlug,
  matchingSlug, checkingSlug, autoMatchProduct, checkPrices, openDetail, formatPrice
}) {
  const isEditing = editingSlug === p.slug;

  return (
    <tr className="hover:bg-slate-50/70 transition-colors" data-testid={`product-row-${p.slug}`}>
      {/* Product Info */}
      <td className="px-4 py-2.5">
        <div className="font-medium text-slate-900 text-sm leading-snug max-w-[300px] truncate" title={p.name}>{p.name}</div>
        <div className="flex gap-1.5 mt-1 items-center flex-wrap">
          {p.brand && <span className="text-[11px] text-slate-500 font-medium">{p.brand}</span>}
          {p.brand && p.category && <span className="text-slate-300">·</span>}
          {p.category && (
            <span className="text-[11px] bg-violet-50 text-violet-600 px-1.5 py-0.5 rounded font-medium" data-testid={`category-tag-${p.slug}`}>
              {p.subcategory ? `${p.category} > ${p.subcategory}` : p.category}
            </span>
          )}
        </div>
      </td>

      {/* Our TL Price + Base Currency */}
      <td className="text-center px-3 py-2.5">
        <div className="font-semibold text-slate-900">{formatPrice(p.our_price)} ₺</div>
        {p.base_price && p.base_currency && p.base_currency !== "TRY" && (
          <div className="mt-0.5">
            <span className={`text-[11px] px-1.5 py-0.5 rounded border font-medium ${(CURRENCY_STYLES[p.base_currency] || CURRENCY_STYLES.TRY).bg}`}>
              {formatPrice(p.base_price)} {p.base_currency}
            </span>
          </div>
        )}
      </td>

      {/* Purchase Price (Alış Fiyatı) */}
      <td className="text-center px-3 py-2.5">
        {isEditing ? (
          <input
            type="number"
            value={editPurchase}
            onChange={e => setEditPurchase(e.target.value)}
            className="w-24 border rounded px-2 py-1 text-xs text-center focus:ring-2 focus:ring-blue-200 focus:border-blue-400 outline-none"
            placeholder="Alış ₺"
            data-testid={`purchase-price-input-${p.slug}`}
          />
        ) : (
          <button
            onClick={() => startEditing(p)}
            className="text-xs hover:bg-blue-50 px-2 py-1 rounded transition-colors"
            data-testid={`purchase-price-${p.slug}`}
          >
            {p.purchase_price ? (
              <span className="text-blue-700 font-medium">{formatPrice(p.purchase_price)} ₺</span>
            ) : (
              <span className="text-slate-300 italic">Gir</span>
            )}
          </button>
        )}
      </td>

      {/* Floor Price (Dip Fiyat) */}
      <td className="text-center px-3 py-2.5">
        {isEditing ? (
          <div className="flex flex-col gap-1 items-center">
            <input
              type="number"
              value={editFloor}
              onChange={e => setEditFloor(e.target.value)}
              className="w-24 border rounded px-2 py-1 text-xs text-center focus:ring-2 focus:ring-orange-200 focus:border-orange-400 outline-none"
              placeholder="Dip ₺"
              data-testid={`floor-price-input-${p.slug}`}
            />
            <div className="flex gap-1">
              <button onClick={() => savePriceSettings(p.slug)} className="text-emerald-600 hover:bg-emerald-50 rounded p-0.5" data-testid={`save-prices-${p.slug}`}><Check className="h-3.5 w-3.5" /></button>
              <button onClick={() => setEditingSlug(null)} className="text-slate-400 hover:bg-slate-100 rounded p-0.5"><X className="h-3.5 w-3.5" /></button>
            </div>
          </div>
        ) : (
          <button
            onClick={() => startEditing(p)}
            className="text-xs hover:bg-orange-50 px-2 py-1 rounded transition-colors"
            data-testid={`floor-price-${p.slug}`}
          >
            {p.floor_price ? (
              <span className="text-orange-700 font-medium">{formatPrice(p.floor_price)} ₺</span>
            ) : (
              <span className="text-slate-300 italic">Ayarla</span>
            )}
          </button>
        )}
      </td>

      {/* Competitor Icons */}
      <td className="text-center px-3 py-2.5">
        <div className="flex gap-1 justify-center">
          {Object.entries(COMPETITOR_ICONS).map(([key, comp]) => {
            const match = (p.competitor_matches || {})[key];
            const price = p.competitor_prices?.[key];
            return (
              <a
                key={key}
                href={match?.url || "#"}
                target={match ? "_blank" : undefined}
                rel="noopener noreferrer"
                className={`w-7 h-7 rounded-full flex items-center justify-center text-[10px] font-bold text-white transition-all ${match ? "ring-2 ring-offset-1 hover:scale-110 cursor-pointer" : "opacity-20 cursor-default"}`}
                style={{ backgroundColor: comp.color, ringColor: match ? comp.color : "transparent" }}
                title={match ? `${comp.name}: ${price ? formatPrice(price.price) + " ₺" : "Fiyat yok"} — ${match.title || match.url}` : `${comp.name}: Eşleşme yok`}
                data-testid={`competitor-icon-${key}-${p.slug}`}
              >
                {comp.name}
              </a>
            );
          })}
        </div>
      </td>

      {/* Cheapest Competitor */}
      <td className="text-center px-3 py-2.5">
        {p.cheapest_competitor_price ? (
          <div>
            <div className={`font-bold text-sm ${p.cheapest_competitor_price < (p.our_price || 0) ? "text-red-600" : "text-emerald-600"}`}>
              {formatPrice(p.cheapest_competitor_price)} ₺
            </div>
            <div className="text-[10px] text-slate-400 mt-0.5">{p.cheapest_competitor_name}</div>
            {p.cheapest_competitor_price < (p.our_price || 0) && (
              <div className="text-[10px] text-red-500 font-medium flex items-center justify-center gap-0.5 mt-0.5">
                <AlertTriangle className="h-3 w-3" />
                -{formatPrice((p.our_price || 0) - p.cheapest_competitor_price)} ₺
              </div>
            )}
          </div>
        ) : (
          <span className="text-xs text-slate-300">—</span>
        )}
      </td>

      {/* Actions */}
      <td className="text-center px-3 py-2.5">
        <div className="flex gap-0.5 justify-center">
          <Button size="sm" variant="ghost" className="h-7 w-7 p-0" title="Otomatik Eşleştir" onClick={() => autoMatchProduct(p.slug)} disabled={matchingSlug === p.slug} data-testid={`match-btn-${p.slug}`}>
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
  );
}
