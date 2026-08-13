import { useState, useEffect, useCallback } from "react";
import { API, getAuthHeaders } from "../context/AuthContext";
import axios from "axios";
import { toast } from "sonner";
import {
  Search, ChevronLeft, ChevronRight, Loader2, RefreshCw, ArrowRight,
  CheckCircle2, Clock, Filter
} from "lucide-react";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";

export default function PriceChangesPage() {
  const [changes, setChanges] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(0);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [loading, setLoading] = useState(true);

  const fetchChanges = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ page, limit: 50 });
      if (search) params.set("search", search);
      if (statusFilter) params.set("status_filter", statusFilter);
      const { data } = await axios.get(`${API}/competitor/price-changes-full?${params}`, { headers: getAuthHeaders(), withCredentials: true });
      setChanges(data.changes || []);
      setTotal(data.total || 0);
      setPages(data.pages || 0);
    } catch {
      toast.error("Fiyat değişiklikleri yüklenemedi");
    }
    setLoading(false);
  }, [page, search, statusFilter]);

  useEffect(() => { fetchChanges(); }, [fetchChanges]);

  const formatPrice = (price) => {
    if (!price && price !== 0) return "-";
    return new Intl.NumberFormat("tr-TR", { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(price);
  };

  const formatDate = (d) => {
    if (!d) return "-";
    const dt = new Date(d);
    return dt.toLocaleDateString("tr-TR") + " " + dt.toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" });
  };

  return (
    <div className="space-y-4" data-testid="price-changes-page">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h1 className="text-xl font-bold text-slate-900" data-testid="page-title">Fiyat Değişiklik Logları</h1>
          <p className="text-sm text-slate-500">{total} kayıt</p>
        </div>
        <Button size="sm" variant="outline" onClick={fetchChanges} data-testid="refresh-btn">
          <RefreshCw className="h-3.5 w-3.5 mr-1.5" /> Yenile
        </Button>
      </div>

      <div className="bg-white rounded-xl border p-3 shadow-sm flex gap-2 flex-wrap items-center" data-testid="filters">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
          <Input placeholder="Ürün ara..." value={search} onChange={e => { setSearch(e.target.value); setPage(1); }} className="pl-9 h-9" data-testid="search-input" />
        </div>
        <select
          value={statusFilter}
          onChange={e => { setStatusFilter(e.target.value); setPage(1); }}
          className="border rounded-lg px-3 h-9 text-sm bg-white min-w-[140px] focus:ring-2 focus:ring-violet-200 focus:border-violet-400 outline-none"
          data-testid="status-filter"
        >
          <option value="">Tüm Durum</option>
          <option value="applied">Uygulanmış</option>
          <option value="pending">Bekliyor</option>
        </select>
      </div>

      <div className="bg-white rounded-xl border shadow-sm overflow-hidden" data-testid="changes-table">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 border-b">
              <tr>
                <th className="text-left px-4 py-3 font-semibold text-slate-600 text-xs uppercase tracking-wide">Ürün</th>
                <th className="text-center px-3 py-3 font-semibold text-slate-600 text-xs uppercase tracking-wide">Eski Fiyat</th>
                <th className="text-center px-1 py-3"></th>
                <th className="text-center px-3 py-3 font-semibold text-slate-600 text-xs uppercase tracking-wide">Yeni Fiyat</th>
                <th className="text-center px-3 py-3 font-semibold text-slate-600 text-xs uppercase tracking-wide">En Ucuz Rakip</th>
                <th className="text-center px-3 py-3 font-semibold text-slate-600 text-xs uppercase tracking-wide">Durum</th>
                <th className="text-center px-3 py-3 font-semibold text-slate-600 text-xs uppercase tracking-wide">Tarih</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {loading ? (
                <tr><td colSpan={7} className="text-center py-16"><Loader2 className="h-6 w-6 animate-spin mx-auto text-slate-400" /></td></tr>
              ) : changes.length === 0 ? (
                <tr><td colSpan={7} className="text-center py-16 text-slate-400">Fiyat değişikliği bulunamadı</td></tr>
              ) : changes.map((ch, i) => (
                <tr key={i} className="hover:bg-slate-50/70 transition-colors">
                  <td className="px-4 py-3">
                    <div className="font-medium text-slate-900 text-sm truncate max-w-[250px]">{ch.product_name}</div>
                    {ch.reason && <div className="text-[11px] text-slate-400 mt-0.5 truncate max-w-[250px]">{ch.reason}</div>}
                  </td>
                  <td className="text-center px-3 py-3">
                    <span className="text-slate-500 line-through">{formatPrice(ch.old_price)} ₺</span>
                  </td>
                  <td className="text-center px-1 py-3"><ArrowRight className="h-3.5 w-3.5 text-slate-300 mx-auto" /></td>
                  <td className="text-center px-3 py-3">
                    <span className="font-bold text-blue-700">{formatPrice(ch.new_price)} ₺</span>
                    <div className="text-[11px] text-emerald-600 font-medium">-{formatPrice((ch.old_price || 0) - (ch.new_price || 0))} ₺</div>
                  </td>
                  <td className="text-center px-3 py-3">
                    <div className="text-sm">{formatPrice(ch.cheapest_price)} ₺</div>
                    <div className="text-[11px] text-slate-400">{ch.cheapest_competitor}</div>
                  </td>
                  <td className="text-center px-3 py-3">
                    {ch.applied ? (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-emerald-100 text-emerald-700">
                        <CheckCircle2 className="h-3 w-3" /> Uygulandı
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-amber-100 text-amber-700">
                        <Clock className="h-3 w-3" /> Bekliyor
                      </span>
                    )}
                  </td>
                  <td className="text-center px-3 py-3 text-xs text-slate-500">{formatDate(ch.changed_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {pages > 1 && (
          <div className="flex items-center justify-between px-4 py-3 border-t bg-slate-50">
            <span className="text-sm text-slate-500">Sayfa {page}/{pages} ({total} kayıt)</span>
            <div className="flex gap-1">
              <Button size="sm" variant="outline" disabled={page <= 1} onClick={() => setPage(p => p - 1)} data-testid="prev-page"><ChevronLeft className="h-4 w-4" /></Button>
              <Button size="sm" variant="outline" disabled={page >= pages} onClick={() => setPage(p => p + 1)} data-testid="next-page"><ChevronRight className="h-4 w-4" /></Button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
