import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { Button } from "../components/ui/button";
import { Loader2, ChevronDown, ChevronUp, CheckCircle2, XCircle, AlertTriangle, Clock, ArrowDown } from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL + "/api";
const getAuthHeaders = () => ({ Authorization: `Bearer ${localStorage.getItem("token")}` });

const formatPrice = (p) => p ? new Intl.NumberFormat("tr-TR", { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(p) : "-";
const formatDate = (d) => d ? new Date(d).toLocaleString("tr-TR", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" }) : "-";

export default function PriceChangesPage() {
  const [operations, setOperations] = useState([]);
  const [selectedOp, setSelectedOp] = useState(null);
  const [opDetails, setOpDetails] = useState(null);
  const [recentChanges, setRecentChanges] = useState([]);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [view, setView] = useState("operations"); // "operations" or "all"

  const fetchOps = useCallback(async () => {
    try {
      const { data } = await axios.get(`${API}/competitor/operations?page=${page}&limit=15`, { headers: getAuthHeaders() });
      setOperations(data.operations || []);
      setTotalPages(data.pages || 1);
    } catch {}
    setLoading(false);
  }, [page]);

  const fetchAllChanges = useCallback(async () => {
    try {
      const { data } = await axios.get(`${API}/competitor/price-changes?page=${page}&limit=30`, { headers: getAuthHeaders() });
      setRecentChanges(data.changes || []);
      setTotalPages(data.pages || 1);
    } catch {}
    setLoading(false);
  }, [page]);

  useEffect(() => {
    setLoading(true);
    if (view === "operations") fetchOps();
    else fetchAllChanges();
  }, [view, page, fetchOps, fetchAllChanges]);

  const loadOpDetail = async (opId) => {
    if (selectedOp === opId) { setSelectedOp(null); return; }
    setSelectedOp(opId);
    setDetailLoading(true);
    try {
      const { data } = await axios.get(`${API}/competitor/operations/${opId}`, { headers: getAuthHeaders() });
      setOpDetails(data);
    } catch { setOpDetails(null); }
    setDetailLoading(false);
  };

  if (loading) return <div className="flex items-center justify-center h-64"><Loader2 className="h-8 w-8 animate-spin text-slate-400" /></div>;

  return (
    <div className="space-y-4" data-testid="price-changes-page">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-slate-900">Islem Loglari</h1>
          <p className="text-sm text-slate-500">Fiyat tarama ve guncelleme islemlerinin kayitlari</p>
        </div>
        <div className="flex gap-2">
          <Button size="sm" variant={view === "operations" ? "default" : "outline"} onClick={() => { setView("operations"); setPage(1); }} data-testid="view-operations">
            Islemler
          </Button>
          <Button size="sm" variant={view === "all" ? "default" : "outline"} onClick={() => { setView("all"); setPage(1); }} data-testid="view-all">
            Tum Degisiklikler
          </Button>
        </div>
      </div>

      {view === "operations" ? (
        /* Operations View */
        <div className="space-y-3">
          {operations.length === 0 ? (
            <div className="bg-white border rounded-xl p-12 text-center">
              <Clock className="h-10 w-10 text-slate-300 mx-auto mb-3" />
              <p className="text-slate-500">Henuz islem kaydi yok</p>
              <p className="text-slate-400 text-sm mt-1">Otomasyon sayfasindan bir kategori calistirdiginizda burada gorunecek</p>
            </div>
          ) : operations.map(op => (
            <div key={op.operation_id} className="bg-white border rounded-xl overflow-hidden" data-testid={`op-${op.operation_id}`}>
              {/* Operation Summary */}
              <button onClick={() => loadOpDetail(op.operation_id)} className="w-full p-4 text-left hover:bg-slate-50 transition-colors">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    {op.status === "completed" ? <CheckCircle2 className="h-5 w-5 text-emerald-500" /> :
                     op.status === "running" ? <Loader2 className="h-5 w-5 text-blue-500 animate-spin" /> :
                     <XCircle className="h-5 w-5 text-red-500" />}
                    <div>
                      <h3 className="font-semibold text-slate-800">{op.category}</h3>
                      <p className="text-xs text-slate-500">
                        {formatDate(op.started_at)} | {op.triggered_by === "manual" ? "Manuel" : "Otomatik"} | {op.total_products} urun
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-4">
                    {op.updated > 0 && <span className="text-sm font-medium text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded">{op.updated} guncellendi</span>}
                    {op.skipped > 0 && <span className="text-sm text-amber-600 bg-amber-50 px-2 py-0.5 rounded">{op.skipped} atlandi</span>}
                    {selectedOp === op.operation_id ? <ChevronUp className="h-4 w-4 text-slate-400" /> : <ChevronDown className="h-4 w-4 text-slate-400" />}
                  </div>
                </div>
              </button>

              {/* Operation Detail (expanded) */}
              {selectedOp === op.operation_id && (
                <div className="border-t bg-slate-50 p-4">
                  {detailLoading ? (
                    <div className="flex items-center justify-center py-6"><Loader2 className="h-5 w-5 animate-spin text-slate-400" /></div>
                  ) : opDetails?.changes?.length > 0 ? (
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="border-b text-left text-xs text-slate-500">
                            <th className="pb-2 pr-3">Durum</th>
                            <th className="pb-2 pr-3">Urun</th>
                            <th className="pb-2 pr-3 text-right">Eski Fiyat</th>
                            <th className="pb-2 pr-3 text-right">Yeni Fiyat</th>
                            <th className="pb-2 pr-3 text-right">Rakip Fiyat</th>
                            <th className="pb-2 pr-3">Rakip</th>
                            <th className="pb-2 pr-3 text-right">Dip Fiyat</th>
                            <th className="pb-2">Sebep</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-200">
                          {opDetails.changes.map((ch, i) => (
                            <tr key={i} className="hover:bg-white">
                              <td className="py-2 pr-3">
                                {ch.applied ? <CheckCircle2 className="h-4 w-4 text-emerald-500" /> :
                                 ch.action === "floor_hit" ? <AlertTriangle className="h-4 w-4 text-amber-500" /> :
                                 <XCircle className="h-4 w-4 text-red-400" />}
                              </td>
                              <td className="py-2 pr-3 max-w-[220px]">
                                <div className="font-medium text-slate-700 truncate">{ch.product_name}</div>
                                {ch.sku && <div className="text-xs text-slate-400">{ch.sku}</div>}
                              </td>
                              <td className="py-2 pr-3 text-right">
                                <div className="text-slate-500">{formatPrice(ch.old_price_tl)} TL</div>
                                {ch.base_currency && ch.base_currency !== "TRY" && ch.old_price_base && (
                                  <div className="text-xs text-slate-400">{formatPrice(ch.old_price_base)} {ch.base_currency}</div>
                                )}
                              </td>
                              <td className="py-2 pr-3 text-right">
                                {ch.new_price_tl ? (
                                  <>
                                    <div className="font-medium text-slate-800">{formatPrice(ch.new_price_tl)} TL</div>
                                    {ch.new_price_base && ch.base_currency && ch.base_currency !== "TRY" && (
                                      <div className="text-xs text-slate-400">{formatPrice(ch.new_price_base)} {ch.base_currency}</div>
                                    )}
                                  </>
                                ) : <span className="text-slate-300">-</span>}
                              </td>
                              <td className="py-2 pr-3 text-right text-blue-600">{formatPrice(ch.cheapest_price)} TL</td>
                              <td className="py-2 pr-3 text-xs text-slate-500">{ch.cheapest_competitor || "-"}</td>
                              <td className="py-2 pr-3 text-right">
                                <div className="text-orange-600">{formatPrice(ch.floor_price)} {ch.base_currency || "TL"}</div>
                                {ch.base_currency && ch.base_currency !== "TRY" && ch.floor_price_tl && (
                                  <div className="text-xs text-slate-400">{formatPrice(ch.floor_price_tl)} TL</div>
                                )}
                              </td>
                              <td className="py-2 text-xs text-slate-500 max-w-[150px] truncate">
                                {ch.action === "floor_hit" ? "Dip fiyat korumasi" :
                                 ch.apply_error ? ch.apply_error :
                                 ch.applied ? "Basarili" :
                                 ch.reason || "Bekliyor"}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <p className="text-center text-slate-400 py-4 text-sm">Bu islem icin detay bulunamadi</p>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      ) : (
        /* All Changes View */
        <div className="bg-white border rounded-xl overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-50">
                <tr className="border-b text-left text-xs text-slate-500">
                  <th className="p-3">Durum</th>
                  <th className="p-3">Tarih</th>
                  <th className="p-3">Urun</th>
                  <th className="p-3 text-right">Eski</th>
                  <th className="p-3 text-center"><ArrowDown className="h-3 w-3 inline" /></th>
                  <th className="p-3 text-right">Yeni</th>
                  <th className="p-3 text-right">Rakip</th>
                  <th className="p-3 text-right">Dip Fiyat</th>
                  <th className="p-3">Kaynak</th>
                  <th className="p-3">Sebep</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {recentChanges.map((ch, i) => (
                  <tr key={i} className="hover:bg-slate-50">
                    <td className="p-3">
                      {ch.applied ? <CheckCircle2 className="h-4 w-4 text-emerald-500" /> :
                       ch.action === "floor_hit" ? <AlertTriangle className="h-4 w-4 text-amber-500" /> :
                       <XCircle className="h-4 w-4 text-red-400" />}
                    </td>
                    <td className="p-3 text-xs text-slate-500 whitespace-nowrap">{formatDate(ch.changed_at)}</td>
                    <td className="p-3 max-w-[200px]">
                      <div className="font-medium text-slate-700 truncate">{ch.product_name}</div>
                      {ch.sku && <div className="text-xs text-slate-400">{ch.sku}</div>}
                    </td>
                    <td className="p-3 text-right">
                      <div className="text-slate-500">{formatPrice(ch.old_price_tl)}</div>
                      {ch.base_currency && ch.base_currency !== "TRY" && ch.old_price_base && (
                        <div className="text-xs text-slate-400">{formatPrice(ch.old_price_base)} {ch.base_currency}</div>
                      )}
                    </td>
                    <td className="p-3 text-center text-slate-300">→</td>
                    <td className="p-3 text-right">
                      {ch.new_price_tl ? (
                        <>
                          <div className="font-medium text-slate-800">{formatPrice(ch.new_price_tl)}</div>
                          {ch.new_price_base && ch.base_currency && ch.base_currency !== "TRY" && (
                            <div className="text-xs text-slate-400">{formatPrice(ch.new_price_base)} {ch.base_currency}</div>
                          )}
                        </>
                      ) : <span className="text-slate-300">-</span>}
                    </td>
                    <td className="p-3 text-right text-blue-600">{formatPrice(ch.cheapest_price)}</td>
                    <td className="p-3 text-right">
                      <div className="text-orange-600">{ch.floor_price ? `${formatPrice(ch.floor_price)} ${ch.base_currency || "TL"}` : "-"}</div>
                      {ch.base_currency && ch.base_currency !== "TRY" && ch.floor_price_tl && (
                        <div className="text-xs text-slate-400">{formatPrice(ch.floor_price_tl)} TL</div>
                      )}
                    </td>
                    <td className="p-3 text-xs text-slate-500">{ch.triggered_by === "manual_category" ? "Manuel" : ch.triggered_by === "scheduled" ? "Otomatik" : ch.triggered_by || "-"}</td>
                    <td className="p-3 text-xs text-slate-500 max-w-[120px] truncate">
                      {ch.action === "floor_hit" ? "Dip fiyat" : ch.applied ? "Uygulandi" : ch.apply_error || "Bekliyor"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2">
          <Button size="sm" variant="outline" onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}>Onceki</Button>
          <span className="text-sm text-slate-500">{page} / {totalPages}</span>
          <Button size="sm" variant="outline" onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page === totalPages}>Sonraki</Button>
        </div>
      )}
    </div>
  );
}
