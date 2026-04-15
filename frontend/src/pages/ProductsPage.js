import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { getAuthHeaders, API } from "../context/AuthContext";
import { Card, CardContent } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Badge } from "../components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../components/ui/table";
import { Tabs, TabsList, TabsTrigger } from "../components/ui/tabs";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "../components/ui/dialog";
import { Label } from "../components/ui/label";
import { Download, Search, Package, Loader2, ExternalLink, ChevronLeft, ChevronRight, DollarSign, RefreshCw, Link2, Check, X, Pencil, TrendingDown } from "lucide-react";
import { toast } from "sonner";

export default function ProductsPage() {
  const [products, setProducts] = useState([]);
  const [total, setTotal] = useState(0);
  const [pages, setPages] = useState(1);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("all");
  const [loading, setLoading] = useState(true);
  const [importing, setImporting] = useState(false);
  const [fetchingPrices, setFetchingPrices] = useState(false);
  const [editingPrice, setEditingPrice] = useState(null);
  const [priceValue, setPriceValue] = useState("");
  const [matchDialog, setMatchDialog] = useState(null);
  const [akakceUrl, setAkakceUrl] = useState("");
  const [checkingSlug, setCheckingSlug] = useState(null);

  const fetchProducts = useCallback(async () => {
    setLoading(true);
    try {
      const params = { search, page, limit: 50 };
      if (filter === "tracked") params.tracked_categories_only = true;
      if (filter === "matched") params.matched_only = true;
      if (filter === "unmatched") { params.tracked_categories_only = true; params.unmatched_only = true; }
      const { data } = await axios.get(`${API}/products`, { params, headers: getAuthHeaders(), withCredentials: true });
      setProducts(data.products);
      setTotal(data.total);
      setPages(data.pages);
    } catch (err) { console.error(err); }
    finally { setLoading(false); }
  }, [search, page, filter]);

  useEffect(() => { fetchProducts(); }, [fetchProducts]);

  const handleImport = async () => {
    setImporting(true);
    try {
      const { data } = await axios.post(`${API}/sitemap/import-products`, {}, { headers: getAuthHeaders(), withCredentials: true });
      toast.success(`${data.imported} yeni urun aktarildi. Toplam: ${data.total}`);
      fetchProducts();
    } catch { toast.error("Urun aktarimi basarisiz"); }
    finally { setImporting(false); }
  };

  const handleBulkFetchPrices = async () => {
    setFetchingPrices(true);
    try {
      const { data } = await axios.post(`${API}/feed/sync-prices`, {}, { headers: getAuthHeaders(), withCredentials: true });
      toast.success(`${data.updated} urun guncellendi. Fiyatli: ${data.products_with_price}`);
      fetchProducts();
    } catch { toast.error("Feed senkronizasyonu basarisiz"); }
    finally { setFetchingPrices(false); }
  };

  const savePrice = async (slug) => {
    if (!priceValue) return;
    try {
      await axios.put(`${API}/products/${slug}`, { our_price: parseFloat(priceValue) }, { headers: getAuthHeaders(), withCredentials: true });
      setProducts(prev => prev.map(p => p.slug === slug ? { ...p, our_price: parseFloat(priceValue) } : p));
      setEditingPrice(null);
      toast.success("Fiyat guncellendi");
    } catch { toast.error("Fiyat guncellenemedi"); }
  };

  const openMatchDialog = (product) => {
    setMatchDialog(product);
    setAkakceUrl(product.akakce_product_url || "");
  };

  const saveAkakceMatch = async () => {
    if (!matchDialog || !akakceUrl) return;
    try {
      await axios.post(`${API}/products/${matchDialog.slug}/set-akakce-match`,
        { akakce_product_url: akakceUrl, akakce_product_name: "" },
        { headers: getAuthHeaders(), withCredentials: true });
      toast.success("Akakce eslestirmesi kaydedildi. Fiyat kontrolu baslatiliyor...");
      setMatchDialog(null);
      // Auto-trigger price check after manual match
      try {
        const { data } = await axios.post(`${API}/products/${matchDialog.slug}/check-akakce`, {}, { headers: getAuthHeaders(), withCredentials: true, timeout: 90000 });
        if (data.success) {
          toast.success(`Fiyat guncellendi! ${data.sellers?.length || 0} satici bulundu.`);
        }
      } catch {}
      fetchProducts();
    } catch { toast.error("Eslestirme kaydedilemedi"); }
  };

  const checkAkakce = async (slug) => {
    const product = products.find(p => p.slug === slug);
    if (!product?.akakce_product_url) {
      toast.error("Once Akakce eslestirmesi yapilmali. Eslestir butonuna tiklayarak URL girin.");
      return;
    }
    setCheckingSlug(slug);
    try {
      toast.info("Akakce fiyatlari kontrol ediliyor...", { duration: 10000 });
      const { data } = await axios.post(`${API}/products/${slug}/check-akakce`, {}, { headers: getAuthHeaders(), withCredentials: true, timeout: 90000 });
      if (data.success) {
        toast.success(`${data.sellers?.length || 0} satici bulundu!`);
      } else {
        toast.warning(data.error || "Fiyat kontrolu basarisiz");
      }
      fetchProducts();
    } catch { toast.error("Akakce kontrolu basarisiz"); }
    finally { setCheckingSlug(null); }
  };

  return (
    <div className="space-y-6" data-testid="products-page">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-slate-900 font-heading">Urunler</h2>
          <p className="text-sm text-slate-500 mt-1">Toplam {total} urun</p>
        </div>
        <div className="flex items-center gap-2">
          <Button onClick={handleBulkFetchPrices} disabled={fetchingPrices} data-testid="bulk-fetch-prices-button" className="bg-amber-500 hover:bg-amber-600 text-black text-sm h-9 font-medium">
            {fetchingPrices ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <DollarSign className="h-4 w-4 mr-2" />}
            {fetchingPrices ? "Senkronize ediliyor..." : "Feed'den Fiyat Guncelle"}
          </Button>
          <Button onClick={handleImport} disabled={importing} data-testid="import-products-button" className="bg-slate-900 hover:bg-slate-800 text-white text-sm h-9">
            {importing ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Download className="h-4 w-4 mr-2" />}
            Urunleri Aktar
          </Button>
        </div>
      </div>

      <div className="flex flex-col sm:flex-row items-start sm:items-center gap-4">
        <Tabs value={filter} onValueChange={(v) => { setFilter(v); setPage(1); }}>
          <TabsList className="bg-slate-100">
            <TabsTrigger value="all" data-testid="filter-all" className="text-xs">Tum Urunler</TabsTrigger>
            <TabsTrigger value="tracked" data-testid="filter-tracked" className="text-xs">Aktif Kategoriler</TabsTrigger>
            <TabsTrigger value="matched" data-testid="filter-matched" className="text-xs">Eslesmis</TabsTrigger>
            <TabsTrigger value="unmatched" data-testid="filter-unmatched" className="text-xs">Eslesmemis</TabsTrigger>
          </TabsList>
        </Tabs>
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
          <Input data-testid="product-search-input" placeholder="Urun ara..." value={search} onChange={(e) => { setSearch(e.target.value); setPage(1); }} className="pl-10 h-9 border-slate-300" />
        </div>
      </div>

      <Card className="border-slate-200 shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow className="bg-slate-50">
                <TableHead className="text-[10px] uppercase tracking-wider font-semibold text-slate-500 w-12"></TableHead>
                <TableHead className="text-[10px] uppercase tracking-wider font-semibold text-slate-500">Urun Adi</TableHead>
                <TableHead className="text-[10px] uppercase tracking-wider font-semibold text-slate-500 text-right">Fiyatimiz</TableHead>
                <TableHead className="text-[10px] uppercase tracking-wider font-semibold text-slate-500 text-right">En Ucuz Rakip</TableHead>
                <TableHead className="text-[10px] uppercase tracking-wider font-semibold text-slate-500">Akakce Durumu</TableHead>
                <TableHead className="text-[10px] uppercase tracking-wider font-semibold text-slate-500 text-right">Islemler</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading ? (
                <TableRow><TableCell colSpan={6} className="text-center py-12 text-slate-500">Yukleniyor...</TableCell></TableRow>
              ) : products.length === 0 ? (
                <TableRow><TableCell colSpan={6} className="text-center py-12">
                  <Package className="h-8 w-8 mx-auto text-slate-300 mb-2" />
                  <p className="text-sm text-slate-500">{filter === "tracked" ? "Aktif kategorilerde urun yok." : "Urun bulunamadi"}</p>
                </TableCell></TableRow>
              ) : products.map((p) => {
                const isCheaper = p.cheapest_price && p.our_price && p.cheapest_price < p.our_price;
                return (
                  <TableRow key={p.slug} data-testid={`product-row-${p.slug}`} className={`${isCheaper ? "bg-red-50/40" : ""} hover:bg-slate-50/80 transition-colors`}>
                    <TableCell className="w-12 p-2">
                      {p.image_url && <img src={p.image_url} alt="" className="w-10 h-10 rounded object-cover bg-slate-100" />}
                    </TableCell>
                    <TableCell>
                      <p className="text-sm font-medium text-slate-900 line-clamp-1">{p.name}</p>
                      <p className="text-[10px] text-slate-400 mt-0.5 truncate max-w-xs">{p.brand ? `${p.brand} - ` : ""}{p.category_path || ""}</p>
                    </TableCell>
                    <TableCell className="text-right">
                      {editingPrice === p.slug ? (
                        <div className="flex items-center gap-1 justify-end">
                          <Input type="number" value={priceValue} onChange={(e) => setPriceValue(e.target.value)} className="w-24 h-7 text-xs" autoFocus onKeyDown={(e) => e.key === "Enter" && savePrice(p.slug)} />
                          <Button size="sm" className="h-7 text-xs px-2" onClick={() => savePrice(p.slug)}>OK</Button>
                          <Button size="sm" variant="ghost" className="h-7 px-1" onClick={() => setEditingPrice(null)}><X className="h-3 w-3" /></Button>
                        </div>
                      ) : (
                        <button onClick={() => { setEditingPrice(p.slug); setPriceValue(p.our_price || ""); }} className="text-sm font-mono text-slate-900 hover:text-blue-600">
                          {p.our_price ? `${p.our_price.toLocaleString('tr-TR')} TL` : <span className="text-slate-400 text-xs">-</span>}
                        </button>
                      )}
                    </TableCell>
                    <TableCell className="text-right">
                      {p.cheapest_price ? (
                        <div>
                          <span className={`text-sm font-mono font-semibold ${isCheaper ? "text-red-600" : "text-emerald-600"}`}>
                            {p.cheapest_price.toLocaleString('tr-TR')} TL
                          </span>
                          <p className="text-[10px] text-slate-400 truncate max-w-[100px]">{p.cheapest_competitor}</p>
                        </div>
                      ) : (
                        <span className="text-xs text-slate-400">-</span>
                      )}
                    </TableCell>
                    <TableCell>
                      {p.akakce_matched ? (
                        <div className="flex items-center gap-1.5">
                          <Badge className="bg-emerald-100 text-emerald-700 border-0 text-[10px]"><Check className="h-3 w-3 mr-0.5" />Eslesti</Badge>
                          <button onClick={() => openMatchDialog(p)} className="text-blue-500 hover:text-blue-700" title="Duzenle"><Pencil className="h-3 w-3" /></button>
                          {p.our_position && <span className="text-[10px] text-slate-500">{p.our_position}/{p.total_sellers}</span>}
                        </div>
                      ) : p.akakce_match_confidence === "not_found" ? (
                        <div className="flex items-center gap-1.5">
                          <Badge className="bg-orange-100 text-orange-700 border-0 text-[10px]">Bulunamadi</Badge>
                          <button onClick={() => openMatchDialog(p)} className="text-blue-500 hover:text-blue-700"><Pencil className="h-3 w-3" /></button>
                        </div>
                      ) : p.akakce_match_confidence === "ai_uncertain" ? (
                        <div className="flex items-center gap-1.5">
                          <Badge className="bg-amber-100 text-amber-700 border-0 text-[10px]">Belirsiz</Badge>
                          <button onClick={() => openMatchDialog(p)} className="text-blue-500 hover:text-blue-700"><Pencil className="h-3 w-3" /></button>
                        </div>
                      ) : (
                        <button onClick={() => openMatchDialog(p)} className="flex items-center gap-1 text-amber-600 hover:text-amber-700 text-xs font-medium">
                          <Link2 className="h-3 w-3" /> Eslesir
                        </button>
                      )}
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex items-center gap-1 justify-end">
                        {p.akakce_product_url && (
                          <Button variant="outline" size="sm" disabled={checkingSlug === p.slug} onClick={() => checkAkakce(p.slug)} className="h-7 text-[10px] px-2 bg-amber-50 border-amber-200 text-amber-700 hover:bg-amber-100">
                            {checkingSlug === p.slug ? <Loader2 className="h-3 w-3 animate-spin" /> : <RefreshCw className="h-3 w-3 mr-1" />}
                            Fiyat
                          </Button>
                        )}
                        <a href={p.url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center justify-center h-7 w-7 rounded-md border border-slate-200 text-slate-400 hover:text-slate-600 hover:bg-slate-50">
                          <ExternalLink className="h-3 w-3" />
                        </a>
                      </div>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </div>
      </Card>

      {pages > 1 && (
        <div className="flex items-center justify-between">
          <p className="text-xs text-slate-500">Sayfa {page} / {pages}</p>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(page - 1)}><ChevronLeft className="h-4 w-4" /></Button>
            <Button variant="outline" size="sm" disabled={page >= pages} onClick={() => setPage(page + 1)}><ChevronRight className="h-4 w-4" /></Button>
          </div>
        </div>
      )}

      <Dialog open={!!matchDialog} onOpenChange={(open) => !open && setMatchDialog(null)}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle className="font-heading text-lg">Akakce Urun Eslestirmesi</DialogTitle>
          </DialogHeader>
          {matchDialog && (
            <div className="space-y-4">
              <div className="bg-slate-50 rounded-lg p-3">
                <p className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold">Bizim Urun</p>
                <p className="text-sm font-medium text-slate-900 mt-1">{matchDialog.name}</p>
                <a href={matchDialog.url} target="_blank" rel="noopener noreferrer" className="text-xs text-blue-600 hover:underline">{matchDialog.url}</a>
              </div>
              <div className="space-y-2">
                <Label className="text-sm font-medium text-slate-700">Akakce Urun Sayfasi URL'si</Label>
                <Input data-testid="akakce-url-input" value={akakceUrl} onChange={(e) => setAkakceUrl(e.target.value)} placeholder="https://www.akakce.com/...fiyati,123456.html" className="text-sm" />
                <p className="text-[10px] text-slate-400">Akakce'de urun sayfasini acip URL'yi yapisirin. Kaydettikten sonra fiyatlar otomatik cekilir.</p>
              </div>
              {matchDialog.akakce_product_url && (
                <div className="bg-emerald-50 rounded-lg p-3">
                  <p className="text-[10px] uppercase tracking-wider text-emerald-600 font-semibold">Mevcut Eslestirme</p>
                  <a href={matchDialog.akakce_product_url} target="_blank" rel="noopener noreferrer" className="text-xs text-emerald-800 break-all hover:underline">{matchDialog.akakce_product_url}</a>
                </div>
              )}
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setMatchDialog(null)}>Iptal</Button>
            <Button onClick={saveAkakceMatch} disabled={!akakceUrl} className="bg-slate-900 hover:bg-slate-800 text-white" data-testid="save-match-button">Kaydet ve Fiyat Kontrol Et</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
