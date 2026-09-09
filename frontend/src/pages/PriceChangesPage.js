import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { Button } from "../components/ui/button";
import { Loader2, ChevronDown, ChevronUp, CheckCircle2, XCircle, AlertTriangle, Clock, ArrowUpRight, ArrowDownRight, ArrowRight, TrendingUp, TrendingDown } from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL + "/api";
const getAuthHeaders = () => ({ Authorization: `Bearer ${localStorage.getItem("token")}` });

const formatPrice = (p) => p ? new Intl.NumberFormat("tr-TR", { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(p) : "-";
const formatDate = (d) => d ? new Date(d).toLocaleString("tr-TR", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" }) : "-";

function ActionBadge({ action, applied, applyError }) {
  if (action === "raise")    return <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-semibold bg-blue-100 text-blue-700"><TrendingUp className="h-3 w-3" /> Yükseltildi</span>;
  if (action === "update" && applied) return <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-semibold bg-emerald-100 text-emerald-700"><TrendingDown className="h-3 w-3" /> Düşürüldü</span>;
  if (action === "update" && !applied) return <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-semibold bg-slate-100 text-slate-500"><TrendingDown className="h-3 w-3" /> Güncellenmedi</span>;
  if (action === "floor_hit") return <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-semibold bg-amber-100 text-amber-700"><AlertTriangle className="h-3 w-3" /> Dip Fiyat</span>;
  if (action === "no_change") return <span className="px-2 py-0.5 rounded-md text-[11px] font-semibold bg-slate-100 text-slate-400">Değişmedi</span>;
  if (applyError) return <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-semibold bg-red-100 text-red-600"><XCircle className="h-3 w-3" /> Hata</span>;
  return <span className="px-2 py-0.5 rounded-md text-[11px] bg-slate-100 text-slate-400">—</span>;
}

function PriceDiff({ oldTl, newTl, action }) {
  if (!newTl || !oldTl) return null;
  const diff = Math.abs(newTl - oldTl);
  const isUp = action === "raise";
  return (
    <span className={`text-[11px] font-semibold ml-1 ${isUp ? "text-blue-600" : "text-emerald-600"}`}>
      {isUp ? "+" : "-"}{formatPrice(diff)} ₺
    </span>
  );
}

export default function PriceChangesPage() {
  const [operations, setOperations] = useState([]);
  const [selectedOp, setSelectedOp] = useState(null);
  const [opDetails, setOpDetails] = useState(null);
  const [recentChanges, setRecentChanges] = useState([]);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [view, setView] = useState("operations");

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
          <h1 className="text-xl font-bold text-slate-900">İşlem Logları</h1>
          <p className="text-sm text-slate-500">Fiyat tarama ve güncelleme işlemlerinin kayıtları</p>
        </div>
        <div className="flex gap-2">
          <Button size="sm" variant={view === "operations" ? "default" : "outline"} onClick={() => { setView("operations"); setPage(1); }} data-testid="view-operations">
            İşlemler
          </Button>
          <Button size="sm" variant={view === "all" ? "default" : "outline"} onClick={() => { setView("all"); setPage(1); }} data-testid="view-all">
            Tüm Değişiklikler
          </Button>
        </div>
      </div>

      {/* Legend */}
      <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
        <span className="font-medium text-slate-400 mr-1">Açıklama:</span>
        <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-blue-100 text-blue-700 rounded-md font-semibold"><TrendingUp className="h-3 w-3" /> Yükseltildi</span>
        <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-emerald-100 text-emerald-700 rounded-md font-semibold"><TrendingDown className="h-3 w-3" /> Düşürüldü</span>
        <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-amber-100 text-amber-700 rounded-md font-semibold"><AlertTriangle className="h-3 w-3" /> Dip Fiyat</span>
        <span className="px-2 py-0.5 bg-slate-100 text-slate-400 rounded-md font-semibold">Değişmedi</span>
      </div>

      {view === "operations" ? (
        <div className="space-y-3">
          {operations.length === 0 ? (
            <div className="bg-white border rounded-xl p-12 text-center">
              <Clock className="h-10 w-10 text-slate-300 mx-auto mb-3" />
              <p className="text-slate-500">Henüz işlem kaydı yok</p>
              <p className="text-slate-400 text-sm mt-1">Otomasyon sayfasından bir kategori çalıştırdığınızda burada görünecek</p>
            </div>
          ) : operations.map(op => (
            <div key={op.operation_id} className="bg-white border rounded-xl overflow-hidden shadow-sm" data-testid={`op-${op.operation_id}`}>
              <button onClick={() => loadOpDetail(op.operation_id)} className="w-full p-4 text-left hover:bg-slate-50 transition-colors">
                <div className="flex items-center justify-between flex-wrap gap-2">
                  <div className="flex items-center gap-3">
                    {op.status === "completed" ? <CheckCircle2 className="h-5 w-5 text-emerald-500 flex-shrink-0" /> :
                     op.status === "running" ? <Loader2 className="h-5 w-5 text-blue-500 animate-spin flex-shrink-0" /> :
                     <XCircle className="h-5 w-5 text-red-500 flex-shrink-0" />}
                    <div>
                      <h3 className="font-semibold text-slate-800">{op.category}</h3>
                      <p className="text-xs text-slate-500">
                        {formatDate(op.started_at)} · {op.triggered_by === "manual" ? "Manuel" : "Otomatik"} · {op.total_products} ürün
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 flex-wrap">
                    {(op.raised > 0) && (
                      <span className="inline-flex items-center gap-1 text-xs font-semibold text-blue-700 bg-blue-50 border border-blue-200 px-2.5 py-1 rounded-lg">
                        <TrendingUp className="h-3.5 w-3.5" /> {op.raised} yükseltildi
                      </span>
                    )}
                    {(op.updated > 0) && (
                      <span className="inline-flex items-center gap-1 text-xs font-semibold text-emerald-700 bg-emerald-50 border border-emerald-200 px-2.5 py-1 rounded-lg">
                        <TrendingDown className="h-3.5 w-3.5" /> {op.updated} düşürüldü
                      </span>
                    )}
                    {op.skipped > 0 && <span className="text-xs text-amber-700 bg-amber-50 border border-amber-200 px-2.5 py-1 rounded-lg">{op.skipped} atlandı</span>}
                    {selectedOp === op.operation_id ? <ChevronUp className="h-4 w-4 text-slate-400" /> : <ChevronDown className="h-4 w-4 text-slate-400" />}
                  </div>
                </div>
              </button>

              {selectedOp === op.operation_id && (
                <div className="border-t bg-slate-50/60 p-4">
                  {detailLoading ? (
                    <div className="flex items-center justify-center py-6"><Loader2 className="h-5 w-5 animate-spin text-slate-400" /></div>
                  ) : opDetails?.changes?.length > 0 ? (
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="border-b text-left text-[10px] uppercase tracking-wider text-slate-400">
                            <th className="pb-2 pr-3">İşlem</th>
                            <th className="pb-2 pr-3">Ürün</th>
                            <th className="pb-2 pr-3 text-right">Eski Fiyat</th>
                            <th className="pb-2 pr-3 text-center"></th>
                            <th className="pb-2 pr-3 text-right">Yeni Fiyat</th>
                            <th className="pb-2 pr-3 text-right">Rakip Fiyatı</th>
                            <th className="pb-2 pr-3">Rakip</th>
                            <th className="pb-2 pr-3 text-right">Dip Fiyat</th>
                            <th className="pb-2">Not</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100">
                          {opDetails.changes.map((ch, i) => (
                            <tr key={i} className={`hover:bg-white transition-colors ${ch.action === "raise" ? "bg-blue-50/40" : ch.action === "update" && ch.applied ? "bg-emerald-50/30" : ""}`}>
                              <td className="py-2.5 pr-3">
                                <ActionBadge action={ch.action} applied={ch.applied} applyError={ch.apply_error} />
                              </td>
                              <td className="py-2.5 pr-3 max-w-[220px]">
                                <div className="font-medium text-slate-700 truncate">{ch.product_name}</div>
                                {ch.sku && <div className="text-[11px] text-slate-400">{ch.sku}</div>}
                              </td>
                              <td className="py-2.5 pr-3 text-right">
                                <div className="text-slate-500">{formatPrice(ch.old_price_tl)} ₺</div>
                                {ch.base_currency && ch.base_currency !== "TRY" && ch.old_price_base && (
                                  <div className="text-[11px] text-slate-400">{formatPrice(ch.old_price_base)} {ch.base_currency}</div>
                                )}
                              </td>
                              <td className="py-2.5 pr-2 text-center text-slate-300">
                                {ch.action === "raise" ? <ArrowUpRight className="h-3.5 w-3.5 text-blue-400 mx-auto" /> :
                                 ch.new_price_tl ? <ArrowRight className="h-3.5 w-3.5 text-slate-300 mx-auto" /> : null}
                              </td>
                              <td className="py-2.5 pr-3 text-right">
                                {ch.new_price_tl ? (
                                  <>
                                    <div className={`font-semibold ${ch.action === "raise" ? "text-blue-700" : "text-slate-800"}`}>
                                      {formatPrice(ch.new_price_tl)} ₺
                                      <PriceDiff oldTl={ch.old_price_tl} newTl={ch.new_price_tl} action={ch.action} />
                                    </div>
                                    {ch.new_price_base && ch.base_currency && ch.base_currency !== "TRY" && (
                                      <div className="text-[11px] text-slate-400">{formatPrice(ch.new_price_base)} {ch.base_currency}</div>
                                    )}
                                  </>
                                ) : <span className="text-slate-300">—</span>}
                              </td>
                              <td className="py-2.5 pr-3 text-right text-indigo-600 font-medium">{formatPrice(ch.cheapest_price)} ₺</td>
                              <td className="py-2.5 pr-3 text-xs text-slate-500">{ch.cheapest_competitor || "—"}</td>
                              <td className="py-2.5 pr-3 text-right">
                                <div className="text-amber-600 text-xs">{ch.floor_price ? `${formatPrice(ch.floor_price)} ${ch.base_currency || "₺"}` : "—"}</div>
                                {ch.base_currency && ch.base_currency !== "TRY" && ch.floor_price_tl && (
                                  <div className="text-[11px] text-slate-400">{formatPrice(ch.floor_price_tl)} ₺</div>
                                )}
                              </td>
                              <td className="py-2.5 text-[11px] text-slate-400 max-w-[160px] truncate">
                                {ch.apply_error ? (
                                  <span className="text-red-500" title={ch.apply_error}>{ch.apply_error.slice(0, 60)}</span>
                                ) : ch.reason || "—"}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <p className="text-center text-slate-400 py-4 text-sm">Bu işlem için detay bulunamadı</p>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      ) : (
        /* All Changes View */
        <div className="bg-white border rounded-xl overflow-hidden shadow-sm">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 border-b">
                <tr className="text-left text-[10px] uppercase tracking-wider text-slate-400">
                  <th className="px-4 py-3">İşlem</th>
                  <th className="px-3 py-3">Tarih</th>
                  <th className="px-3 py-3">Ürün</th>
                  <th className="px-3 py-3 text-right">Eski Fiyat</th>
                  <th className="px-1 py-3 text-center"></th>
                  <th className="px-3 py-3 text-right">Yeni Fiyat</th>
                  <th className="px-3 py-3 text-right">Rakip</th>
                  <th className="px-3 py-3 text-right">Dip Fiyat</th>
                  <th className="px-3 py-3">Kaynak</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-50">
                {recentChanges.length === 0 ? (
                  <tr><td colSpan={9} className="text-center py-10 text-slate-400">Kayıt bulunamadı</td></tr>
                ) : recentChanges.map((ch, i) => (
                  <tr key={i} className={`hover:bg-slate-50/60 transition-colors ${ch.action === "raise" ? "bg-blue-50/20" : ""}`}>
                    <td className="px-4 py-3">
                      <ActionBadge action={ch.action} applied={ch.applied} applyError={ch.apply_error} />
                    </td>
                    <td className="px-3 py-3 text-xs text-slate-500 whitespace-nowrap">{formatDate(ch.changed_at)}</td>
                    <td className="px-3 py-3 max-w-[180px]">
                      <div className="font-medium text-slate-700 truncate">{ch.product_name}</div>
                      {ch.sku && <div className="text-[11px] text-slate-400">{ch.sku}</div>}
                    </td>
                    <td className="px-3 py-3 text-right">
                      <div className="text-slate-500">{formatPrice(ch.old_price_tl)} ₺</div>
                      {ch.base_currency && ch.base_currency !== "TRY" && ch.old_price_base && (
                        <div className="text-[11px] text-slate-400">{formatPrice(ch.old_price_base)} {ch.base_currency}</div>
                      )}
                    </td>
                    <td className="px-1 py-3 text-center">
                      {ch.action === "raise"
                        ? <ArrowUpRight className="h-3.5 w-3.5 text-blue-400 mx-auto" />
                        : <ArrowDownRight className="h-3.5 w-3.5 text-emerald-400 mx-auto" />}
                    </td>
                    <td className="px-3 py-3 text-right">
                      {ch.new_price_tl ? (
                        <>
                          <div className={`font-semibold ${ch.action === "raise" ? "text-blue-700" : "text-slate-800"}`}>
                            {formatPrice(ch.new_price_tl)} ₺
                          </div>
                          <PriceDiff oldTl={ch.old_price_tl} newTl={ch.new_price_tl} action={ch.action} />
                          {ch.new_price_base && ch.base_currency && ch.base_currency !== "TRY" && (
                            <div className="text-[11px] text-slate-400">{formatPrice(ch.new_price_base)} {ch.base_currency}</div>
                          )}
                        </>
                      ) : <span className="text-slate-300">—</span>}
                    </td>
                    <td className="px-3 py-3 text-right text-indigo-600 font-medium">{formatPrice(ch.cheapest_price)} ₺</td>
                    <td className="px-3 py-3 text-right">
                      <div className="text-amber-600 text-xs">{ch.floor_price ? `${formatPrice(ch.floor_price)} ${ch.base_currency || "₺"}` : "—"}</div>
                      {ch.base_currency && ch.base_currency !== "TRY" && ch.floor_price_tl && (
                        <div className="text-[11px] text-slate-400">{formatPrice(ch.floor_price_tl)} ₺</div>
                      )}
                    </td>
                    <td className="px-3 py-3 text-xs text-slate-500">
                      {ch.triggered_by === "manual_category" ? "Manuel" : ch.triggered_by === "scheduled" ? "Otomatik" : ch.triggered_by || "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2">
          <Button size="sm" variant="outline" onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}>Önceki</Button>
          <span className="text-sm text-slate-500">{page} / {totalPages}</span>
          <Button size="sm" variant="outline" onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page === totalPages}>Sonraki</Button>
        </div>
      )}
    </div>
  );
}
