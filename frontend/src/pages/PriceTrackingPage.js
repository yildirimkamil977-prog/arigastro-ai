import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { getAuthHeaders, API } from "../context/AuthContext";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Badge } from "../components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../components/ui/table";
import { Tabs, TabsList, TabsTrigger } from "../components/ui/tabs";
import { Search, TrendingDown, Loader2, RefreshCw, ChevronLeft, ChevronRight, ExternalLink } from "lucide-react";
import { toast } from "sonner";

export default function PriceTrackingPage() {
  const [products, setProducts] = useState([]);
  const [total, setTotal] = useState(0);
  const [pages, setPages] = useState(1);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("all");
  const [loading, setLoading] = useState(true);
  const [bulkChecking, setBulkChecking] = useState(false);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await axios.get(`${API}/price-tracking`, {
        params: { filter_type: filter, search, page, limit: 50 },
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
  }, [filter, search, page]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const handleBulkCheck = async () => {
    setBulkChecking(true);
    try {
      const { data } = await axios.post(`${API}/products/bulk-check-akakce`, {}, { headers: getAuthHeaders(), withCredentials: true });
      toast.success(`${data.checked} urun kontrol edildi. ${data.matched} eslesti, ${data.failed} basarisiz.`);
      fetchData();
    } catch (err) {
      toast.error("Toplu kontrol basarisiz");
    } finally {
      setBulkChecking(false);
    }
  };

  return (
    <div className="space-y-6" data-testid="price-tracking-page">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-slate-900 font-heading">Fiyat Takip</h2>
          <p className="text-sm text-slate-500 mt-1">
            Akakce uzerindeki rakip fiyatlarini karsilastirin
          </p>
        </div>
        <Button
          onClick={handleBulkCheck}
          disabled={bulkChecking}
          data-testid="bulk-check-button"
          className="bg-amber-500 hover:bg-amber-600 text-black text-sm h-9 font-medium"
        >
          {bulkChecking ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <RefreshCw className="h-4 w-4 mr-2" />}
          Toplu Fiyat Kontrolu
        </Button>
      </div>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center gap-4">
        <Tabs value={filter} onValueChange={(v) => { setFilter(v); setPage(1); }}>
          <TabsList className="bg-slate-100">
            <TabsTrigger value="all" data-testid="filter-all" className="text-xs">Tumu ({total})</TabsTrigger>
            <TabsTrigger value="cheaper" data-testid="filter-cheaper" className="text-xs">Rakip Daha Ucuz</TabsTrigger>
            <TabsTrigger value="expensive" data-testid="filter-expensive" className="text-xs">Biz Daha Ucuz</TabsTrigger>
          </TabsList>
        </Tabs>
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
          <Input
            data-testid="price-search-input"
            placeholder="Urun ara..."
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1); }}
            className="pl-10 h-9 border-slate-300"
          />
        </div>
      </div>

      {/* Table */}
      <Card className="border-slate-200 shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow className="bg-slate-50">
                <TableHead className="text-[10px] uppercase tracking-wider font-semibold text-slate-500 w-10"></TableHead>
                <TableHead className="text-[10px] uppercase tracking-wider font-semibold text-slate-500">Urun</TableHead>
                <TableHead className="text-[10px] uppercase tracking-wider font-semibold text-slate-500 text-right">Bizim Fiyat</TableHead>
                <TableHead className="text-[10px] uppercase tracking-wider font-semibold text-slate-500 text-right">En Ucuz Rakip</TableHead>
                <TableHead className="text-[10px] uppercase tracking-wider font-semibold text-slate-500 text-right">Fark</TableHead>
                <TableHead className="text-[10px] uppercase tracking-wider font-semibold text-slate-500">En Ucuz Firma</TableHead>
                <TableHead className="text-[10px] uppercase tracking-wider font-semibold text-slate-500">Son Kontrol</TableHead>
                <TableHead className="text-[10px] uppercase tracking-wider font-semibold text-slate-500 w-10"></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading ? (
                <TableRow><TableCell colSpan={8} className="text-center py-12 text-slate-500">Yukleniyor...</TableCell></TableRow>
              ) : products.length === 0 ? (
                <TableRow><TableCell colSpan={8} className="text-center py-12">
                  <TrendingDown className="h-8 w-8 mx-auto text-slate-300 mb-2" />
                  <p className="text-sm text-slate-500">Fiyat verisi bulunamadi</p>
                  <p className="text-xs text-slate-400 mt-1">Urunler sayfasindan Akakce kontrolu baslatabilirsiniz</p>
                </TableCell></TableRow>
              ) : (
                products.map((p) => {
                  const isCheaper = p.cheapest_price && p.our_price && p.cheapest_price < p.our_price;
                  const diff = p.price_difference;
                  return (
                    <TableRow
                      key={p.slug}
                      data-testid={`price-row-${p.slug}`}
                      className={`${isCheaper ? "bg-red-50/60" : "bg-emerald-50/30"} hover:bg-slate-50 transition-colors`}
                    >
                      <TableCell className="p-2 w-10">
                        {p.image_url && <img src={p.image_url} alt="" className="w-8 h-8 rounded object-cover" />}
                      </TableCell>
                      <TableCell>
                        <p className="text-sm font-medium text-slate-900 line-clamp-1">{p.name}</p>
                      </TableCell>
                      <TableCell className="text-right font-mono text-sm">
                        {p.our_price ? `${p.our_price.toLocaleString('tr-TR')} TL` : <span className="text-slate-400">-</span>}
                      </TableCell>
                      <TableCell className="text-right">
                        <span className={`font-mono text-sm font-semibold ${isCheaper ? "text-red-600" : "text-emerald-600"}`}>
                          {p.cheapest_price?.toLocaleString('tr-TR')} TL
                        </span>
                      </TableCell>
                      <TableCell className="text-right">
                        {diff != null ? (
                          <Badge className={`border-0 text-xs font-mono ${diff > 0 ? "bg-red-100 text-red-700" : "bg-emerald-100 text-emerald-700"}`}>
                            {diff > 0 ? `+${diff.toLocaleString('tr-TR')}` : diff.toLocaleString('tr-TR')} TL
                          </Badge>
                        ) : "-"}
                      </TableCell>
                      <TableCell>
                        <p className="text-xs text-slate-600 truncate max-w-[150px]">{p.cheapest_competitor || "-"}</p>
                      </TableCell>
                      <TableCell>
                        <p className="text-[10px] text-slate-400">
                          {p.last_price_check ? new Date(p.last_price_check).toLocaleDateString('tr-TR') : "-"}
                        </p>
                      </TableCell>
                      <TableCell>
                        {p.akakce_url && (
                          <a href={p.akakce_url} target="_blank" rel="noopener noreferrer" className="text-slate-400 hover:text-blue-600">
                            <ExternalLink className="h-3.5 w-3.5" />
                          </a>
                        )}
                      </TableCell>
                    </TableRow>
                  );
                })
              )}
            </TableBody>
          </Table>
        </div>
      </Card>

      {pages > 1 && (
        <div className="flex items-center justify-between">
          <p className="text-xs text-slate-500">Sayfa {page} / {pages} (Toplam {total} urun)</p>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(page - 1)} data-testid="price-prev-page"><ChevronLeft className="h-4 w-4" /></Button>
            <Button variant="outline" size="sm" disabled={page >= pages} onClick={() => setPage(page + 1)} data-testid="price-next-page"><ChevronRight className="h-4 w-4" /></Button>
          </div>
        </div>
      )}
    </div>
  );
}
