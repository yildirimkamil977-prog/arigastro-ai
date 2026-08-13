import { useState, useEffect, useCallback } from "react";
import { API, getAuthHeaders } from "../context/AuthContext";
import axios from "axios";
import { toast } from "sonner";
import {
  Play, Square, Loader2, RefreshCw, TrendingDown, AlertTriangle,
  CheckCircle2, BarChart3, Settings2, Percent, Save, Trash2, Plus
} from "lucide-react";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../components/ui/dialog";

export default function CompetitorScanPage() {
  const [dashboard, setDashboard] = useState(null);
  const [scanStatus, setScanStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [showRuleDialog, setShowRuleDialog] = useState(false);
  const [categories, setCategories] = useState([]);
  const [newRule, setNewRule] = useState({ category_name: "", profit_margin_pct: 20, undercut_amount: 100, scan_hour: 3, enabled: true });

  const fetchDashboard = useCallback(async () => {
    try {
      const { data } = await axios.get(`${API}/competitor/dashboard`, { headers: getAuthHeaders(), withCredentials: true });
      setDashboard(data);
    } catch (err) {
      toast.error("Dashboard yüklenemedi");
    }
    setLoading(false);
  }, []);

  const fetchScanStatus = useCallback(async () => {
    try {
      const { data } = await axios.get(`${API}/competitor/scan-status`, { headers: getAuthHeaders(), withCredentials: true });
      setScanStatus(data);
      return data;
    } catch { return null; }
  }, []);

  const fetchCategories = async () => {
    try {
      const { data } = await axios.get(`${API}/competitor/products?page=1&limit=1`, { headers: getAuthHeaders(), withCredentials: true });
      setCategories(data.categories || []);
    } catch {}
  };

  useEffect(() => {
    fetchDashboard();
    fetchScanStatus();
    fetchCategories();
  }, []);

  useEffect(() => {
    if (!scanStatus?.running) return;
    const interval = setInterval(async () => {
      const data = await fetchScanStatus();
      if (data && !data.running) {
        clearInterval(interval);
        fetchDashboard();
        toast.success("Fiyat taraması tamamlandı");
      }
    }, 3000);
    return () => clearInterval(interval);
  }, [scanStatus?.running]);

  const startScan = async () => {
    try {
      const { data } = await axios.post(`${API}/competitor/scan-all`, {}, { headers: getAuthHeaders(), withCredentials: true });
      if (data.started) {
        toast.success(data.message);
        fetchScanStatus();
      } else {
        toast.error(data.message);
      }
    } catch (err) {
      toast.error("Tarama başlatılamadı");
    }
  };

  const stopScan = async () => {
    try {
      await axios.post(`${API}/competitor/scan-stop`, {}, { headers: getAuthHeaders(), withCredentials: true });
      toast.info("Tarama durduruluyor...");
    } catch {}
  };

  const saveRule = async () => {
    if (!newRule.category_name) { toast.error("Kategori seçin"); return; }
    try {
      await axios.post(`${API}/competitor/category-rules`, newRule, { headers: getAuthHeaders(), withCredentials: true });
      toast.success("Kategori kuralı kaydedildi");
      setShowRuleDialog(false);
      setNewRule({ category_name: "", profit_margin_pct: 20, undercut_amount: 100, scan_hour: 3, enabled: true });
      fetchDashboard();
    } catch { toast.error("Kaydetme başarısız"); }
  };

  const deleteRule = async (catName) => {
    try {
      await axios.delete(`${API}/competitor/category-rules/${encodeURIComponent(catName)}`, { headers: getAuthHeaders(), withCredentials: true });
      toast.success("Kural silindi");
      fetchDashboard();
    } catch { toast.error("Silme başarısız"); }
  };

  const formatPrice = (price) => {
    if (!price && price !== 0) return "-";
    return new Intl.NumberFormat("tr-TR", { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(price);
  };

  if (loading) {
    return <div className="flex items-center justify-center py-20"><Loader2 className="h-8 w-8 animate-spin text-slate-400" /></div>;
  }

  return (
    <div className="space-y-6" data-testid="competitor-scan-page">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-xl font-bold text-slate-900" data-testid="page-title">Rakip Fiyat Tarama</h1>
          <p className="text-sm text-slate-500">Rakip fiyat taraması, karşılaştırma ve otomatik fiyatlama kuralları</p>
        </div>
        <div className="flex gap-2">
          <Button size="sm" variant="outline" onClick={() => { fetchDashboard(); fetchScanStatus(); }} data-testid="refresh-btn">
            <RefreshCw className="h-3.5 w-3.5 mr-1.5" /> Yenile
          </Button>
          {scanStatus?.running ? (
            <Button size="sm" onClick={stopScan} className="bg-red-600 hover:bg-red-700 text-white" data-testid="stop-scan-btn">
              <Square className="h-3.5 w-3.5 mr-1.5" /> Taramayı Durdur
            </Button>
          ) : (
            <Button size="sm" onClick={startScan} className="bg-violet-600 hover:bg-violet-700 text-white" data-testid="start-scan-btn">
              <Play className="h-3.5 w-3.5 mr-1.5" /> Tüm Fiyatları Tara
            </Button>
          )}
        </div>
      </div>

      {scanStatus?.running && (
        <div className="bg-violet-50 border border-violet-200 rounded-xl p-4" data-testid="scan-progress">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <Loader2 className="h-4 w-4 animate-spin text-violet-600" />
              <span className="font-medium text-violet-900">Fiyat taraması devam ediyor...</span>
            </div>
            <span className="text-sm text-violet-700 font-mono">{scanStatus.scanned || 0}/{scanStatus.total || 0}</span>
          </div>
          <div className="w-full bg-violet-200 rounded-full h-2">
            <div className="bg-violet-600 h-2 rounded-full transition-all duration-500" style={{ width: `${scanStatus.total ? (scanStatus.scanned / scanStatus.total * 100) : 0}%` }} />
          </div>
          {scanStatus.current_product && <p className="text-xs text-violet-600 mt-1.5 truncate">Taranan: {scanStatus.current_product}</p>}
        </div>
      )}

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <StatCard icon={<BarChart3 className="h-5 w-5" />} label="Toplam Ürün" value={dashboard?.total_products || 0} color="bg-slate-100 text-slate-700" />
        <StatCard icon={<CheckCircle2 className="h-5 w-5" />} label="Eşleşmiş" value={dashboard?.matched_products || 0} color="bg-emerald-100 text-emerald-700" />
        <StatCard icon={<AlertTriangle className="h-5 w-5" />} label="Rakip Daha Ucuz" value={dashboard?.cheaper_count || 0} color="bg-red-100 text-red-700" />
        <StatCard icon={<TrendingDown className="h-5 w-5" />} label="Fiyat Önerisi" value={dashboard?.recommend_count || 0} color="bg-blue-100 text-blue-700" />
      </div>

      {dashboard?.scan_status?.completed_at && !scanStatus?.running && (
        <div className="bg-white rounded-xl border p-4 text-sm" data-testid="last-scan-info">
          <div className="flex items-center justify-between">
            <span className="text-slate-600">Son Tarama:</span>
            <span className="font-medium">{new Date(dashboard.scan_status.completed_at).toLocaleDateString("tr-TR")} {new Date(dashboard.scan_status.completed_at).toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" })}</span>
          </div>
          <div className="flex gap-4 mt-2 text-xs text-slate-500">
            <span>Taranan: <strong>{dashboard.scan_status.scanned || 0}</strong></span>
            <span>Başarılı: <strong className="text-emerald-600">{dashboard.scan_status.success || 0}</strong></span>
            <span>Başarısız: <strong className="text-red-600">{dashboard.scan_status.failed || 0}</strong></span>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-xl border shadow-sm" data-testid="category-rules-section">
          <div className="flex items-center justify-between px-4 py-3 border-b">
            <h2 className="font-semibold text-sm text-slate-800 flex items-center gap-1.5"><Settings2 className="h-4 w-4" /> Kategori Fiyatlama Kuralları</h2>
            <Button size="sm" variant="outline" onClick={() => { setShowRuleDialog(true); fetchCategories(); }} data-testid="add-rule-btn"><Plus className="h-3.5 w-3.5 mr-1" /> Kural Ekle</Button>
          </div>
          <div className="p-3">
            {(dashboard?.category_rules || []).length === 0 ? (
              <div className="text-center py-8">
                <Settings2 className="h-8 w-8 text-slate-300 mx-auto mb-2" />
                <p className="text-sm text-slate-400">Henüz kategori kuralı tanımlanmadı</p>
                <p className="text-xs text-slate-400 mt-1">Kural ekleyerek otomatik fiyatlama başlatın</p>
              </div>
            ) : (
              <div className="space-y-2">
                {(dashboard?.category_rules || []).map(rule => (
                  <div key={rule.category_name} className={`flex items-center justify-between p-3 rounded-lg border ${rule.enabled ? "bg-white border-slate-200" : "bg-slate-50 border-slate-100 opacity-60"}`} data-testid={`rule-${rule.category_name}`}>
                    <div>
                      <div className="font-medium text-sm text-slate-800">{rule.category_name}</div>
                      <div className="flex gap-3 text-xs text-slate-500 mt-1">
                        <span className="flex items-center gap-0.5"><Percent className="h-3 w-3" /> Kâr: <strong className="text-emerald-600">%{rule.profit_margin_pct || 0}</strong></span>
                        <span>Kırma: <strong className="text-blue-600">{rule.undercut_amount || 100} ₺</strong></span>
                        <span className={`font-medium ${rule.enabled ? "text-emerald-600" : "text-red-500"}`}>{rule.enabled ? "Aktif" : "Pasif"}</span>
                      </div>
                    </div>
                    <Button size="sm" variant="ghost" className="h-7 w-7 p-0 text-red-400 hover:text-red-600 hover:bg-red-50" onClick={() => deleteRule(rule.category_name)}><Trash2 className="h-3.5 w-3.5" /></Button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="bg-white rounded-xl border shadow-sm" data-testid="recent-changes-section">
          <div className="px-4 py-3 border-b">
            <h2 className="font-semibold text-sm text-slate-800 flex items-center gap-1.5"><TrendingDown className="h-4 w-4" /> Son Fiyat Önerileri</h2>
          </div>
          <div className="p-3">
            {(dashboard?.recent_changes || []).length === 0 ? (
              <div className="text-center py-8">
                <TrendingDown className="h-8 w-8 text-slate-300 mx-auto mb-2" />
                <p className="text-sm text-slate-400">Henüz fiyat değişikliği önerisi yok</p>
                <p className="text-xs text-slate-400 mt-1">Fiyat taraması çalıştıktan sonra öneriler burada görünecek</p>
              </div>
            ) : (
              <div className="space-y-2 max-h-[360px] overflow-y-auto">
                {(dashboard?.recent_changes || []).map((ch, i) => (
                  <div key={i} className="p-3 bg-slate-50 rounded-lg text-sm border">
                    <div className="font-medium text-slate-800 truncate">{ch.product_name}</div>
                    <div className="flex items-center gap-2 mt-1.5 text-xs">
                      <span className="text-slate-500 line-through">{formatPrice(ch.old_price)} ₺</span>
                      <span className="text-slate-400">&rarr;</span>
                      <span className="font-bold text-blue-700">{formatPrice(ch.new_price)} ₺</span>
                      <span className="text-emerald-600 font-medium">(-{formatPrice((ch.old_price || 0) - (ch.new_price || 0))} ₺)</span>
                      <span className={`ml-auto px-1.5 py-0.5 rounded text-[10px] font-medium ${ch.applied ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700"}`}>{ch.applied ? "Uygulandı" : "Bekliyor"}</span>
                    </div>
                    <div className="text-[11px] text-slate-400 mt-1">{ch.reason}</div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      <Dialog open={showRuleDialog} onOpenChange={setShowRuleDialog}>
        <DialogContent className="max-w-md">
          <DialogHeader><DialogTitle>Kategori Fiyatlama Kuralı</DialogTitle></DialogHeader>
          <div className="space-y-4 pt-2">
            <div>
              <label className="text-sm font-medium text-slate-700 mb-1 block">Kategori</label>
              <select value={newRule.category_name} onChange={e => setNewRule(r => ({ ...r, category_name: e.target.value }))} className="w-full border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-violet-200 focus:border-violet-400 outline-none" data-testid="rule-category-select">
                <option value="">Kategori seçin</option>
                {categories.map(c => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-sm font-medium text-slate-700 mb-1 block">Kâr Marjı (%)</label>
                <p className="text-[11px] text-slate-400 mb-1">Alış fiyatına eklenecek kâr oranı</p>
                <div className="relative">
                  <Input type="number" value={newRule.profit_margin_pct} onChange={e => setNewRule(r => ({ ...r, profit_margin_pct: parseFloat(e.target.value) || 0 }))} className="pr-8" data-testid="rule-margin-input" />
                  <Percent className="absolute right-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-slate-400" />
                </div>
              </div>
              <div>
                <label className="text-sm font-medium text-slate-700 mb-1 block">Fiyat Kırma (₺)</label>
                <p className="text-[11px] text-slate-400 mb-1">En ucuz rakibin altına düşülecek tutar</p>
                <Input type="number" value={newRule.undercut_amount} onChange={e => setNewRule(r => ({ ...r, undercut_amount: parseFloat(e.target.value) || 0 }))} data-testid="rule-undercut-input" />
              </div>
            </div>
            <div className="flex items-center gap-3">
              <label className="text-sm font-medium text-slate-700">Aktif</label>
              <button onClick={() => setNewRule(r => ({ ...r, enabled: !r.enabled }))} className={`w-10 h-5 rounded-full transition-colors ${newRule.enabled ? "bg-violet-600" : "bg-slate-300"}`} data-testid="rule-enabled-toggle">
                <div className={`w-4 h-4 bg-white rounded-full shadow transition-transform ${newRule.enabled ? "translate-x-5" : "translate-x-0.5"}`} />
              </button>
            </div>
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 text-xs text-blue-700">
              <strong>Kural mantığı:</strong> Dip Fiyat = Alış Fiyatı x (1 + Kâr Marjı%). Sistem, en ucuz rakipten Kırma tutarı kadar düşük fiyat önerir ancak Dip Fiyat'ın altına inmez.
            </div>
            <div className="flex gap-2 justify-end pt-2">
              <Button variant="outline" onClick={() => setShowRuleDialog(false)}>İptal</Button>
              <Button onClick={saveRule} className="bg-violet-600 hover:bg-violet-700 text-white" data-testid="save-rule-btn"><Save className="h-3.5 w-3.5 mr-1.5" /> Kaydet</Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function StatCard({ icon, label, value, color }) {
  return (
    <div className={`rounded-xl border p-4 ${color}`} data-testid={`stat-${label}`}>
      <div className="flex items-center gap-2 mb-1 opacity-70">{icon}<span className="text-xs font-medium uppercase tracking-wide">{label}</span></div>
      <div className="text-2xl font-bold">{typeof value === "number" ? value.toLocaleString("tr-TR") : value}</div>
    </div>
  );
}
