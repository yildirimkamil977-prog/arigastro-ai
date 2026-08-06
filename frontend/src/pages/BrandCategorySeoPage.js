import { useState, useEffect, useCallback } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { toast } from "sonner";
import { Tag, Building2, RefreshCw, Brain, CheckCircle2, Loader2, Search, BarChart3, X, Zap, Send, FileText } from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL;

export default function BrandCategorySeoPage() {
  const [tab, setTab] = useState("category");
  const [items, setItems] = useState([]);
  const [catCount, setCatCount] = useState(0);
  const [brandCount, setBrandCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(null);
  const [pushing, setPushing] = useState(null);
  const [analysisModal, setAnalysisModal] = useState(null);
  const [bulkStatus, setBulkStatus] = useState(null);

  const fetchItems = useCallback(async () => {
    setLoading(true);
    try {
      const [catRes, brandRes] = await Promise.all([
        fetch(`${API}/api/ikas/categories`, { credentials: "include" }),
        fetch(`${API}/api/ikas/brands`, { credentials: "include" }),
      ]);
      const cats = catRes.ok ? await catRes.json() : [];
      const brands = brandRes.ok ? await brandRes.json() : [];
      setCatCount(cats.length);
      setBrandCount(brands.length);
      setItems(tab === "brand" ? brands : cats);
    } catch (e) { toast.error(e.message); }
    finally { setLoading(false); }
  }, [tab]);

  const fetchBulkStatus = useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/ikas/bc-seo/bulk-status/${tab}`, { credentials: "include" });
      const data = await res.json();
      setBulkStatus(data);
    } catch { setBulkStatus(null); }
  }, [tab]);

  useEffect(() => { fetchItems(); fetchBulkStatus(); }, [fetchItems, fetchBulkStatus]);

  // Poll bulk status
  useEffect(() => {
    if (!bulkStatus?.running) return;
    const interval = setInterval(fetchBulkStatus, 5000);
    return () => clearInterval(interval);
  }, [bulkStatus?.running, fetchBulkStatus]);

  const generateSingle = async (id, name) => {
    setGenerating(id);
    try {
      const res = await fetch(`${API}/api/ikas/bc-seo/generate`, {
        method: "POST", headers: { "Content-Type": "application/json" }, credentials: "include",
        body: JSON.stringify({ type: tab, id, name }),
      });
      if (!res.ok) { const e = await res.json(); throw new Error(e.detail); }
      toast.success(`"${name}" icin SEO icerigi uretildi`);
      fetchItems();
    } catch (e) { toast.error("Hata: " + e.message); }
    finally { setGenerating(null); }
  };

  const pushSingle = async (id, name) => {
    setPushing(id);
    try {
      const res = await fetch(`${API}/api/ikas/bc-seo/push`, {
        method: "POST", headers: { "Content-Type": "application/json" }, credentials: "include",
        body: JSON.stringify({ type: tab, id }),
      });
      if (!res.ok) { const e = await res.json(); throw new Error(e.detail); }
      toast.success(`"${name}" Ikas'a gonderildi`);
      fetchItems();
    } catch (e) { toast.error("Hata: " + e.message); }
    finally { setPushing(null); }
  };

  const startBulk = async () => {
    try {
      const res = await fetch(`${API}/api/ikas/bc-seo/bulk-generate`, {
        method: "POST", headers: { "Content-Type": "application/json" }, credentials: "include",
        body: JSON.stringify({ type: tab }),
      });
      const data = await res.json();
      toast.info(data.message);
      fetchBulkStatus();
    } catch (e) { toast.error("Hata: " + e.message); }
  };

  const showAnalysis = async (id) => {
    try {
      const res = await fetch(`${API}/api/ikas/bc-seo/analysis/${id}`, { credentials: "include" });
      const data = await res.json();
      if (data.found === false) { toast.warning("Henuz analiz yapilmamis"); return; }
      setAnalysisModal(data);
    } catch { toast.error("Analiz yuklenemedi"); }
  };

  const generated = items.filter(i => i.seo_generated).length;
  const pushed = items.filter(i => i.seo_status === "pushed").length;

  return (
    <div className="space-y-5" data-testid="bc-seo-page">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h2 className="text-xl font-bold text-slate-900">Marka & Kategori SEO</h2>
          <p className="text-sm text-slate-500 mt-0.5">Rakip analizi ile profesyonel icerik uretimi ve Ikas'a aktarim</p>
        </div>
        <div className="flex gap-2 items-center">
          <Button variant="outline" size="sm" className="h-8 text-xs" onClick={fetchItems} disabled={loading}>
            <RefreshCw className={`h-3 w-3 mr-1 ${loading ? "animate-spin" : ""}`} /> Yenile
          </Button>
          <Button size="sm" className="h-8 text-xs bg-slate-900 hover:bg-slate-800 text-white" onClick={startBulk} disabled={bulkStatus?.running} data-testid="bulk-generate-btn">
            <Zap className={`h-3.5 w-3.5 mr-1.5 ${bulkStatus?.running ? "animate-pulse" : ""}`} />
            {bulkStatus?.running ? "Devam Ediyor..." : `Tumunu Uret ve Gonder`}
          </Button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-2">
        <button onClick={() => setTab("category")} data-testid="tab-categories"
          className={`flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium border ${tab === "category" ? "bg-slate-900 text-white border-slate-900" : "bg-white text-slate-600 border-slate-200 hover:bg-slate-50"}`}>
          <Tag className="h-4 w-4" /> Kategoriler ({catCount})
        </button>
        <button onClick={() => setTab("brand")} data-testid="tab-brands"
          className={`flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium border ${tab === "brand" ? "bg-slate-900 text-white border-slate-900" : "bg-white text-slate-600 border-slate-200 hover:bg-slate-50"}`}>
          <Building2 className="h-4 w-4" /> Markalar ({brandCount})
        </button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Card className="border"><CardContent className="p-3">
          <p className="text-[10px] text-slate-400 uppercase">Toplam</p>
          <p className="text-2xl font-bold text-slate-900">{items.length}</p>
        </CardContent></Card>
        <Card className="border border-blue-200 bg-blue-50/30"><CardContent className="p-3">
          <p className="text-[10px] text-blue-500 uppercase">Icerik Uretildi</p>
          <p className="text-2xl font-bold text-blue-600">{generated}</p>
        </CardContent></Card>
        <Card className="border border-emerald-200 bg-emerald-50/30"><CardContent className="p-3">
          <p className="text-[10px] text-emerald-500 uppercase">Ikas'a Gonderildi</p>
          <p className="text-2xl font-bold text-emerald-600">{pushed}</p>
        </CardContent></Card>
        <Card className="border border-amber-200 bg-amber-50/30"><CardContent className="p-3">
          <p className="text-[10px] text-amber-500 uppercase">Bekliyor</p>
          <p className="text-2xl font-bold text-amber-600">{items.length - generated}</p>
        </CardContent></Card>
      </div>

      {/* Bulk Status */}
      {bulkStatus?.running && (
        <Card className="border border-amber-200 bg-amber-50">
          <CardContent className="p-4 flex items-center gap-3">
            <Loader2 className="h-5 w-5 animate-spin text-amber-600" />
            <div className="flex-1">
              <p className="text-sm font-medium text-amber-900">Toplu uretim: {bulkStatus.progress}/{bulkStatus.total}</p>
              <p className="text-xs text-amber-600">{bulkStatus.generated || 0} uretildi, {bulkStatus.pushed || 0} gonderildi, {bulkStatus.failed || 0} basarisiz</p>
              <div className="mt-1 h-1.5 bg-amber-100 rounded-full">
                <div className="h-1.5 bg-amber-500 rounded-full transition-all" style={{ width: `${bulkStatus.total > 0 ? (bulkStatus.progress / bulkStatus.total * 100) : 0}%` }} />
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Table */}
      {loading ? (
        <div className="flex items-center justify-center py-16"><RefreshCw className="h-6 w-6 text-slate-400 animate-spin" /></div>
      ) : (
        <Card className="border">
          <CardContent className="px-0 pb-0">
            <div className="overflow-x-auto">
              <table className="w-full text-left" data-testid="bc-table">
                <thead><tr className="border-b bg-slate-50/50">
                  <th className="py-2.5 px-4 text-[10px] font-semibold text-slate-500 uppercase">Ad</th>
                  <th className="py-2.5 px-3 text-[10px] font-semibold text-slate-500 uppercase text-center">Durum</th>
                  <th className="py-2.5 px-3 text-[10px] font-semibold text-slate-500 uppercase text-center">Mevcut Icerik</th>
                  <th className="py-2.5 px-3 text-[10px] font-semibold text-slate-500 uppercase text-right">Islemler</th>
                </tr></thead>
                <tbody>
                  {items.map((item) => (
                    <tr key={item.id} className="border-b border-slate-50 hover:bg-slate-50/50">
                      <td className="py-2 px-4">
                        <div className="flex items-center gap-2">
                          {item.seo_status === "pushed" && <CheckCircle2 className="h-4 w-4 text-emerald-500 flex-shrink-0" />}
                          {item.seo_status === "generated" && <FileText className="h-4 w-4 text-blue-500 flex-shrink-0" />}
                          {!item.seo_status && <div className="h-4 w-4 rounded-full border-2 border-slate-200 flex-shrink-0" />}
                          <div>
                            <span className="text-sm font-medium text-slate-900">{item.name}</span>
                            {item.parent_name && <span className="text-[10px] text-slate-400 ml-1.5">({item.parent_name})</span>}
                            {item.children && item.children.length > 0 && <span className="text-[10px] text-blue-400 ml-1.5">{item.children.length} alt kat.</span>}
                          </div>
                        </div>
                      </td>
                      <td className="py-2 px-3 text-center">
                        {item.seo_status === "pushed" ? (
                          <span className="text-[10px] font-medium bg-emerald-100 text-emerald-700 px-2 py-0.5 rounded">Gonderildi</span>
                        ) : item.seo_status === "generated" ? (
                          <span className="text-[10px] font-medium bg-blue-100 text-blue-700 px-2 py-0.5 rounded">Uretildi</span>
                        ) : (
                          <span className="text-[10px] font-medium bg-slate-100 text-slate-500 px-2 py-0.5 rounded">Bekliyor</span>
                        )}
                      </td>
                      <td className="py-2 px-3 text-center">
                        <span className="text-xs text-slate-500">{(item.description?.length || 0) > 0 ? `${item.description.length} kar.` : "Yok"}</span>
                      </td>
                      <td className="py-2 px-3">
                        <div className="flex items-center justify-end gap-1">
                          {item.seo_generated && (
                            <Button variant="ghost" size="sm" className="h-7 text-[10px] text-violet-600" onClick={() => showAnalysis(item.id)} data-testid={`analysis-${item.id}`}>
                              <BarChart3 className="h-3 w-3 mr-0.5" /> Analiz
                            </Button>
                          )}
                          <Button variant="ghost" size="sm" className="h-7 text-[10px] text-blue-600"
                            onClick={() => generateSingle(item.id, item.name)}
                            disabled={generating === item.id} data-testid={`generate-${item.id}`}>
                            {generating === item.id ? <Loader2 className="h-3 w-3 mr-0.5 animate-spin" /> : <Brain className="h-3 w-3 mr-0.5" />}
                            Uret
                          </Button>
                          {item.seo_generated && (
                            <Button variant="ghost" size="sm" className="h-7 text-[10px] text-emerald-600"
                              onClick={() => pushSingle(item.id, item.name)}
                              disabled={pushing === item.id} data-testid={`push-${item.id}`}>
                              {pushing === item.id ? <Loader2 className="h-3 w-3 mr-0.5 animate-spin" /> : <Send className="h-3 w-3 mr-0.5" />}
                              Gonder
                            </Button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Analysis Modal */}
      {analysisModal && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" onClick={() => setAnalysisModal(null)}>
          <div className="bg-white rounded-xl shadow-xl max-w-3xl w-full max-h-[80vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
            <div className="p-4 border-b flex items-center justify-between sticky top-0 bg-white rounded-t-xl">
              <h3 className="text-base font-bold text-slate-900">Rakip Analizi — {analysisModal.entity_name}</h3>
              <Button variant="ghost" size="sm" onClick={() => setAnalysisModal(null)}><X className="h-4 w-4" /></Button>
            </div>
            <div className="p-4 space-y-4">
              {/* Summary */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <div className="bg-blue-50 rounded-lg p-3 text-center">
                  <p className="text-[10px] text-blue-500 uppercase">Analiz Edilen Site</p>
                  <p className="text-xl font-bold text-blue-700">{analysisModal.analysis?.competitors_scraped || 0}</p>
                </div>
                <div className="bg-slate-50 rounded-lg p-3 text-center">
                  <p className="text-[10px] text-slate-500 uppercase">Ort. Kelime Sayisi</p>
                  <p className="text-xl font-bold text-slate-700">{analysisModal.analysis?.avg_word_count || 0}</p>
                </div>
                <div className="bg-amber-50 rounded-lg p-3 text-center">
                  <p className="text-[10px] text-amber-500 uppercase">Ort. AK Yogunlugu</p>
                  <p className="text-xl font-bold text-amber-700">%{analysisModal.analysis?.avg_keyword_density || 0}</p>
                </div>
                <div className="bg-emerald-50 rounded-lg p-3 text-center">
                  <p className="text-[10px] text-emerald-500 uppercase">SERP Pozisyonumuz</p>
                  <p className="text-xl font-bold text-emerald-700">{analysisModal.analysis?.serp_position || "Yok"}</p>
                </div>
              </div>

              {/* Competitor details */}
              <div>
                <h4 className="text-sm font-semibold text-slate-900 mb-2">Rakip Sitelerin Title'lari</h4>
                <div className="space-y-1">
                  {(analysisModal.analysis?.competitor_titles || []).map((t, i) => (
                    <p key={i} className="text-xs text-slate-600 bg-slate-50 rounded px-2 py-1">{i + 1}. {t}</p>
                  ))}
                </div>
              </div>

              <div>
                <h4 className="text-sm font-semibold text-slate-900 mb-2">Rakip Sitelerin Description'lari</h4>
                <div className="space-y-1">
                  {(analysisModal.analysis?.competitor_descriptions || []).map((d, i) => (
                    <p key={i} className="text-xs text-slate-600 bg-slate-50 rounded px-2 py-1">{i + 1}. {d}</p>
                  ))}
                </div>
              </div>

              {(analysisModal.analysis?.competitor_pages || []).length > 0 && (
                <div>
                  <h4 className="text-sm font-semibold text-slate-900 mb-2">Rakip Sayfa Detaylari</h4>
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs">
                      <thead><tr className="border-b bg-slate-50">
                        <th className="py-1.5 px-2">URL</th>
                        <th className="py-1.5 px-2 text-right">Kelime</th>
                        <th className="py-1.5 px-2 text-right">AK %</th>
                        <th className="py-1.5 px-2 text-center">Liste</th>
                        <th className="py-1.5 px-2 text-center">Tablo</th>
                      </tr></thead>
                      <tbody>
                        {analysisModal.analysis.competitor_pages.map((p, i) => (
                          <tr key={i} className="border-b border-slate-50">
                            <td className="py-1.5 px-2 text-blue-600 max-w-[200px] truncate">{p.url}</td>
                            <td className="py-1.5 px-2 text-right font-mono">{p.word_count}</td>
                            <td className="py-1.5 px-2 text-right font-mono">%{p.keyword_density}</td>
                            <td className="py-1.5 px-2 text-center">{p.has_lists ? "Var" : "Yok"}</td>
                            <td className="py-1.5 px-2 text-center">{p.has_tables ? "Var" : "Yok"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {(analysisModal.analysis?.competitor_h2s || []).length > 0 && (
                <div>
                  <h4 className="text-sm font-semibold text-slate-900 mb-2">Rakiplerde Kullanilan H2 Basliklari</h4>
                  <div className="flex flex-wrap gap-1">
                    {analysisModal.analysis.competitor_h2s.map((h, i) => (
                      <span key={i} className="text-[10px] bg-violet-50 text-violet-700 px-2 py-0.5 rounded">{h}</span>
                    ))}
                  </div>
                </div>
              )}

              {/* Generation Notes */}
              {analysisModal.generation_notes && (
                <div>
                  <h4 className="text-sm font-semibold text-slate-900 mb-2">AI Analiz Notu</h4>
                  <div className="text-sm text-slate-700 bg-amber-50 border border-amber-200 rounded-lg p-3 leading-relaxed">
                    {analysisModal.generation_notes}
                  </div>
                </div>
              )}

              {/* Generated content preview */}
              {analysisModal.content && (
                <div>
                  <h4 className="text-sm font-semibold text-slate-900 mb-2">Uretilen Icerik</h4>
                  <div className="border rounded-lg p-3 bg-slate-50 space-y-2">
                    <div className="flex gap-2 items-start">
                      <span className="text-[10px] font-bold text-slate-500 uppercase min-w-[70px]">Title:</span>
                      <span className="text-sm text-slate-800 font-medium">{analysisModal.title}</span>
                    </div>
                    <div className="flex gap-2 items-start">
                      <span className="text-[10px] font-bold text-slate-500 uppercase min-w-[70px]">Description:</span>
                      <span className="text-sm text-slate-700">{analysisModal.description_meta}</span>
                    </div>
                    <div className="flex gap-2 items-start">
                      <span className="text-[10px] font-bold text-slate-500 uppercase min-w-[70px]">Uzunluk:</span>
                      <span className="text-sm text-slate-600">{analysisModal.content.length} karakter</span>
                    </div>
                    <hr className="border-slate-200" />
                    <style>{`
                      .bc-preview h2 { font-size: 1.25rem; font-weight: 700; color: #1e293b; margin: 1.5rem 0 0.75rem; padding-bottom: 0.5rem; border-bottom: 2px solid #f1f5f9; }
                      .bc-preview h3 { font-size: 1.1rem; font-weight: 600; color: #334155; margin: 1.25rem 0 0.5rem; }
                      .bc-preview p { color: #475569; line-height: 1.75; margin: 0.5rem 0; }
                      .bc-preview ul { padding-left: 1.5rem; margin: 0.5rem 0; }
                      .bc-preview li { color: #475569; margin: 0.25rem 0; }
                      .bc-preview strong { color: #1e293b; }
                      .bc-preview a { color: #2563eb; text-decoration: underline; }
                      .bc-preview table { width: 100%; border-collapse: collapse; margin: 1rem 0; }
                      .bc-preview th, .bc-preview td { border: 1px solid #e2e8f0; padding: 0.5rem; font-size: 0.875rem; }
                      .bc-preview th { background: #f8fafc; font-weight: 600; }
                      .bc-preview img { max-width: 100%; border-radius: 8px; margin: 1rem 0; }
                    `}</style>
                    <div className="bc-preview max-h-[500px] overflow-y-auto" dangerouslySetInnerHTML={{ __html: analysisModal.content }} />
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
