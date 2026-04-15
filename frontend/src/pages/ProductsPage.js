import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { getAuthHeaders, API } from "../context/AuthContext";
import { Card, CardContent } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Badge } from "../components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../components/ui/table";
import { Download, Search, Package, Loader2, ExternalLink, Eye, ChevronLeft, ChevronRight, DollarSign, RefreshCw } from "lucide-react";
import { toast } from "sonner";

export default function ProductsPage() {
  const [products, setProducts] = useState([]);
  const [total, setTotal] = useState(0);
  const [pages, setPages] = useState(1);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [importing, setImporting] = useState(false);
  const [fetchingPrices, setFetchingPrices] = useState(false);
  const [editingPrice, setEditingPrice] = useState(null);
  const [priceValue, setPriceValue] = useState("");

  const fetchProducts = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await axios.get(`${API}/products`, {
        params: { search, page, limit: 50 },
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

  const handleImport = async () => {
    setImporting(true);
    try {
      const { data } = await axios.post(`${API}/sitemap/import-products`, {}, { headers: getAuthHeaders(), withCredentials: true });
      toast.success(`${data.imported} yeni urun aktarildi. Toplam: ${data.total}`);
      fetchProducts();
    } catch (err) {
      toast.error("Urun aktarimi basarisiz");
    } finally {
      setImporting(false);
    }
  };

  const handleBulkFetchPrices = async () => {
    setFetchingPrices(true);
    try {
      const { data } = await axios.post(`${API}/feed/sync-prices`, {}, { headers: getAuthHeaders(), withCredentials: true });
      toast.success(`${data.updated} urun guncellendi, ${data.new_products} yeni urun eklendi. Fiyatli: ${data.products_with_price}`);
      fetchProducts();
    } catch (err) {
      toast.error("Feed senkronizasyonu basarisiz");
    } finally {
      setFetchingPrices(false);
    }
  };

  const fetchSinglePrice = async (slug) => {
    try {
      toast.info("Feed'den fiyat senkronizasyonu baslatiliyor...");
      const { data } = await axios.post(`${API}/feed/sync-prices`, {}, { headers: getAuthHeaders(), withCredentials: true });
      toast.success(`${data.updated} urun guncellendi`);
      fetchProducts();
    } catch (err) {
      toast.error("Fiyat senkronizasyonu basarisiz");
    }
  };

  const toggleTracking = async (slug) => {
    try {
      const { data } = await axios.put(`${API}/products/${slug}/toggle-tracking`, {}, { headers: getAuthHeaders(), withCredentials: true });
      setProducts((prev) => prev.map((p) => p.slug === slug ? { ...p, is_tracked: data.is_tracked } : p));
    } catch (err) {
      toast.error("Guncelleme basarisiz");
    }
  };

  const savePrice = async (slug) => {
    if (!priceValue) return;
    try {
      await axios.put(`${API}/products/${slug}`, { our_price: parseFloat(priceValue) }, { headers: getAuthHeaders(), withCredentials: true });
      setProducts((prev) => prev.map((p) => p.slug === slug ? { ...p, our_price: parseFloat(priceValue) } : p));
      setEditingPrice(null);
      setPriceValue("");
      toast.success("Fiyat guncellendi");
    } catch (err) {
      toast.error("Fiyat guncellenemedi");
    }
  };

  const checkAkakce = async (slug) => {
    try {
      toast.info("Akakce kontrol ediliyor...");
      const { data } = await axios.post(`${API}/products/${slug}/check-akakce`, {}, { headers: getAuthHeaders(), withCredentials: true });
      if (data.akakce_result?.success) {
        toast.success("Akakce eslesmesi bulundu!");
      } else {
        toast.warning(data.akakce_result?.error || "Esleme bulunamadi");
      }
      fetchProducts();
    } catch (err) {
      toast.error("Akakce kontrolu basarisiz");
    }
  };

  return (
    <div className="space-y-6" data-testid="products-page">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-slate-900 font-heading">Urunler</h2>
          <p className="text-sm text-slate-500 mt-1">Toplam {total} urun</p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            onClick={handleBulkFetchPrices}
            disabled={fetchingPrices}
            data-testid="bulk-fetch-prices-button"
            className="bg-amber-500 hover:bg-amber-600 text-black text-sm h-9 font-medium"
          >
            {fetchingPrices ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <DollarSign className="h-4 w-4 mr-2" />}
            {fetchingPrices ? "Senkronize ediliyor..." : "Feed'den Fiyat Guncelle"}
          </Button>
          <Button
            onClick={handleImport}
            disabled={importing}
            data-testid="import-products-button"
            className="bg-slate-900 hover:bg-slate-800 text-white text-sm h-9"
          >
            {importing ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Download className="h-4 w-4 mr-2" />}
            Urunleri Aktar
          </Button>
        </div>
      </div>

      <div className="relative max-w-md">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
        <Input
          data-testid="product-search-input"
          placeholder="Urun ara..."
          value={search}
          onChange={(e) => { setSearch(e.target.value); setPage(1); }}
          className="pl-10 h-9 border-slate-300"
        />
      </div>

      <Card className="border-slate-200 shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow className="bg-slate-50">
                <TableHead className="text-[10px] uppercase tracking-wider font-semibold text-slate-500 w-12"></TableHead>
                <TableHead className="text-[10px] uppercase tracking-wider font-semibold text-slate-500">Urun Adi</TableHead>
                <TableHead className="text-[10px] uppercase tracking-wider font-semibold text-slate-500">Marka</TableHead>
                <TableHead className="text-[10px] uppercase tracking-wider font-semibold text-slate-500 text-right">Fiyatimiz</TableHead>
                <TableHead className="text-[10px] uppercase tracking-wider font-semibold text-slate-500 text-right">En Ucuz Rakip</TableHead>
                <TableHead className="text-[10px] uppercase tracking-wider font-semibold text-slate-500">Durum</TableHead>
                <TableHead className="text-[10px] uppercase tracking-wider font-semibold text-slate-500 text-right">Islemler</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading ? (
                <TableRow><TableCell colSpan={6} className="text-center py-12 text-slate-500">Yukleniyor...</TableCell></TableRow>
              ) : products.length === 0 ? (
                <TableRow><TableCell colSpan={6} className="text-center py-12">
                  <Package className="h-8 w-8 mx-auto text-slate-300 mb-2" />
                  <p className="text-sm text-slate-500">Urun bulunamadi</p>
                </TableCell></TableRow>
              ) : (
                products.map((p) => {
                  const isCheaper = p.cheapest_price && p.our_price && p.cheapest_price < p.our_price;
                  return (
                    <TableRow
                      key={p.slug}
                      data-testid={`product-row-${p.slug}`}
                      className={`${isCheaper ? "bg-red-50/50" : ""} hover:bg-slate-50/80 transition-colors`}
                    >
                      <TableCell className="w-12 p-2">
                        {p.image_url && (
                          <img src={p.image_url} alt="" className="w-10 h-10 rounded object-cover bg-slate-100" />
                        )}
                      </TableCell>
                      <TableCell>
                        <p className="text-sm font-medium text-slate-900 line-clamp-1">{p.name}</p>
                        <p className="text-[10px] text-slate-400 mt-0.5 truncate max-w-xs">{p.category_path || p.slug}</p>
                      </TableCell>
                      <TableCell>
                        <p className="text-xs text-slate-600">{p.brand || "-"}</p>
                      </TableCell>
                      <TableCell className="text-right">
                        {editingPrice === p.slug ? (
                          <div className="flex items-center gap-1 justify-end">
                            <Input
                              data-testid={`price-input-${p.slug}`}
                              type="number"
                              value={priceValue}
                              onChange={(e) => setPriceValue(e.target.value)}
                              className="w-24 h-7 text-xs"
                              placeholder="Fiyat"
                              autoFocus
                              onKeyDown={(e) => e.key === "Enter" && savePrice(p.slug)}
                            />
                            <Button size="sm" className="h-7 text-xs px-2" onClick={() => savePrice(p.slug)}>OK</Button>
                          </div>
                        ) : (
                          <button
                            data-testid={`edit-price-${p.slug}`}
                            onClick={() => { setEditingPrice(p.slug); setPriceValue(p.our_price || ""); }}
                            className="text-sm font-mono text-slate-900 hover:text-blue-600 cursor-pointer"
                          >
                            {p.our_price ? `${p.our_price.toLocaleString('tr-TR')} TL` : (
                              <button
                                onClick={(e) => { e.stopPropagation(); fetchSinglePrice(p.slug); }}
                                className="text-amber-600 hover:text-amber-700 text-xs font-medium flex items-center gap-1"
                                data-testid={`fetch-price-${p.slug}`}
                              >
                                <RefreshCw className="h-3 w-3" /> Feed Sync
                              </button>
                            )}
                          </button>
                        )}
                      </TableCell>
                      <TableCell className="text-right">
                        {p.cheapest_price ? (
                          <div>
                            <p className={`text-sm font-mono ${isCheaper ? "text-red-600 font-semibold" : "text-emerald-600"}`}>
                              {p.cheapest_price.toLocaleString('tr-TR')} TL
                            </p>
                            <p className="text-[10px] text-slate-400 truncate max-w-[120px]">{p.cheapest_competitor}</p>
                          </div>
                        ) : (
                          <span className="text-xs text-slate-400">-</span>
                        )}
                      </TableCell>
                      <TableCell>
                        {p.akakce_matched ? (
                          <Badge className="bg-emerald-100 text-emerald-700 border-0 text-[10px]">Eslesti</Badge>
                        ) : (
                          <Badge variant="outline" className="text-[10px] text-slate-500">Eslesmedi</Badge>
                        )}
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex items-center gap-1 justify-end">
                          <Button
                            variant="outline"
                            size="sm"
                            data-testid={`check-akakce-${p.slug}`}
                            onClick={() => checkAkakce(p.slug)}
                            className="h-7 text-[10px] px-2 bg-amber-50 border-amber-200 text-amber-700 hover:bg-amber-100"
                          >
                            Kontrol
                          </Button>
                          {p.is_tracked ? (
                            <Button variant="outline" size="sm" className="h-7 text-[10px] px-2 text-emerald-600 border-emerald-200" onClick={() => toggleTracking(p.slug)}>
                              <Eye className="h-3 w-3" />
                            </Button>
                          ) : (
                            <Button variant="ghost" size="sm" className="h-7 text-[10px] px-2 text-slate-400" onClick={() => toggleTracking(p.slug)}>
                              <Eye className="h-3 w-3" />
                            </Button>
                          )}
                          <a href={p.url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center justify-center h-7 w-7 rounded-md border border-slate-200 text-slate-400 hover:text-slate-600 hover:bg-slate-50">
                            <ExternalLink className="h-3 w-3" />
                          </a>
                        </div>
                      </TableCell>
                    </TableRow>
                  );
                })
              )}
            </TableBody>
          </Table>
        </div>
      </Card>

      {/* Pagination */}
      {pages > 1 && (
        <div className="flex items-center justify-between">
          <p className="text-xs text-slate-500">Sayfa {page} / {pages}</p>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(page - 1)} data-testid="prev-page-button">
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <Button variant="outline" size="sm" disabled={page >= pages} onClick={() => setPage(page + 1)} data-testid="next-page-button">
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
