import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Button } from "../components/ui/button";
import { Switch } from "../components/ui/switch";
import { Loader2, Play, Pause, RefreshCw, Clock, CheckCircle2, XCircle, AlertTriangle, ChevronDown, ChevronUp } from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL + "/api";
const getAuthHeaders = () => ({ Authorization: `Bearer ${localStorage.getItem("token")}` });

export default function CompetitorScanPage() {
  const [rules, setRules] = useState([]);
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [newCategory, setNewCategory] = useState("");
  const [runningTasks, setRunningTasks] = useState({});
  const [showAddForm, setShowAddForm] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      const [rulesRes, catsRes] = await Promise.all([
        axios.get(`${API}/competitor/category-rules`, { headers: getAuthHeaders() }),
        axios.get(`${API}/filters/categories`, { headers: getAuthHeaders() }),
      ]);
      setRules(rulesRes.data.rules || []);
      setCategories(catsRes.data.categories || []);
    } catch { toast.error("Veri yüklenemedi"); }
    setLoading(false);
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  // Poll running tasks
  useEffect(() => {
    const running = rules.filter(r => r.task_running);
    if (running.length === 0) return;
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, [rules, fetchData]);

  const addRule = async () => {
    if (!newCategory) return;
    try {
      await axios.post(`${API}/competitor/category-rules`, {
        category_name: newCategory,
        undercut_amount: 200,
        auto_update_ikas: false,
        enabled: true,
      }, { headers: getAuthHeaders() });
      toast.success(`"${newCategory}" kategorisi eklendi`);
      setNewCategory("");
      setShowAddForm(false);
      fetchData();
    } catch (e) { toast.error(e.response?.data?.detail || "Eklenemedi"); }
  };

  const deleteRule = async (categoryName) => {
    if (!window.confirm("Bu kategori kuralını silmek istediğinize emin misiniz?")) return;
    try {
      await axios.delete(`${API}/competitor/category-rules/${encodeURIComponent(categoryName)}`, { headers: getAuthHeaders() });
      toast.success("Kural silindi");
      fetchData();
    } catch { toast.error("Silinemedi"); }
  };

  const toggleAutoUpdate = async (rule) => {
    try {
      await axios.post(`${API}/competitor/category-rules`, {
        category_name: rule.category_name,
        enabled: rule.enabled !== false,
        undercut_amount: rule.undercut_amount || 200,
        auto_update_ikas: !rule.auto_update_ikas,
      }, { headers: getAuthHeaders() });
      fetchData();
    } catch { toast.error("Güncellenemedi"); }
  };

  const runNow = async (categoryName) => {
    try {
      setRunningTasks(prev => ({ ...prev, [categoryName]: true }));
      const { data } = await axios.post(`${API}/competitor/run-category-pricing/${categoryName}`, {}, { headers: getAuthHeaders() });
      toast.success(data.message || `"${categoryName}" tarama ve fiyat güncellemesi başlatıldı`);
      fetchData();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Başlatılamadı");
      setRunningTasks(prev => ({ ...prev, [categoryName]: false }));
    }
  };

  const totalProducts = rules.reduce((s, r) => s + (r.product_count || 0), 0);
  const autoEnabled = rules.filter(r => r.auto_update_ikas).length;

  if (loading) return <div className="flex items-center justify-center h-64"><Loader2 className="h-8 w-8 animate-spin text-slate-400" /></div>;

  return (
    <div className="space-y-6" data-testid="automation-page">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-slate-900">Otomasyon Yonetimi</h1>
          <p className="text-sm text-slate-500">Kategorilerin otomatik fiyat takibi ve guncelleme ayarlari</p>
        </div>
        <Button size="sm" onClick={() => setShowAddForm(!showAddForm)} data-testid="add-rule-btn" className="bg-slate-800 text-white hover:bg-slate-700">
          + Kategori Ekle
        </Button>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-white border rounded-xl p-4">
          <p className="text-xs text-slate-500 mb-1">Toplam Kategori</p>
          <p className="text-2xl font-bold text-slate-900">{rules.length}</p>
        </div>
        <div className="bg-white border rounded-xl p-4">
          <p className="text-xs text-slate-500 mb-1">Otomatik Aktif</p>
          <p className="text-2xl font-bold text-emerald-600">{autoEnabled}</p>
        </div>
        <div className="bg-white border rounded-xl p-4">
          <p className="text-xs text-slate-500 mb-1">Takip Edilen Urun</p>
          <p className="text-2xl font-bold text-blue-600">{totalProducts}</p>
        </div>
      </div>

      {/* Info Box */}
      <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 text-sm text-blue-800">
        <div className="flex items-start gap-2">
          <Clock className="h-4 w-4 mt-0.5 flex-shrink-0" />
          <div>
            <p className="font-medium">Gece Otomatik Akis</p>
            <p className="text-blue-600 mt-1">00:00 Ikas fiyat guncelle → 00:30 Rakiplerden fiyat tara → Dip fiyata gore en ucuz rakibin 200 TL altina guncelle ve Ikas'a kaydet</p>
            <p className="text-blue-500 text-xs mt-1">Sadece "Otomatik" acik olan kategoriler icin calisir.</p>
          </div>
        </div>
      </div>

      {/* Add Form */}
      {showAddForm && (
        <div className="bg-white border rounded-xl p-4">
          <h3 className="font-medium text-slate-800 mb-3">Yeni Kategori Ekle</h3>
          <div className="flex gap-3">
            <select value={newCategory} onChange={e => setNewCategory(e.target.value)} className="flex-1 h-10 px-3 border rounded-lg text-sm" data-testid="new-category-select">
              <option value="">Kategori secin...</option>
              {categories.filter(c => !rules.some(r => r.category_name === c.name)).map(c => (
                <option key={c.name} value={c.name}>
                  {c.depth > 0 ? "\u00A0\u00A0".repeat(c.depth) + "└ " : ""}{c.name} ({c.product_count || 0} urun)
                </option>
              ))}
            </select>
            <Button onClick={addRule} disabled={!newCategory} data-testid="confirm-add-btn" className="bg-slate-800 text-white hover:bg-slate-700">Ekle</Button>
            <Button variant="outline" onClick={() => setShowAddForm(false)}>Iptal</Button>
          </div>
        </div>
      )}

      {/* Rules List */}
      {rules.length === 0 ? (
        <div className="bg-white border rounded-xl p-12 text-center">
          <AlertTriangle className="h-10 w-10 text-slate-300 mx-auto mb-3" />
          <p className="text-slate-500">Henuz kategori eklenmemis</p>
          <p className="text-slate-400 text-sm mt-1">Yukaridaki "Kategori Ekle" butonuyla baslayın</p>
        </div>
      ) : (
        <div className="space-y-3">
          {rules.map(rule => (
            <RuleCard key={rule.category_name} rule={rule} onToggle={toggleAutoUpdate} onRun={runNow} onDelete={deleteRule} running={runningTasks[rule.category_name] || rule.task_running} />
          ))}
        </div>
      )}
    </div>
  );
}

function RuleCard({ rule, onToggle, onRun, onDelete, running }) {
  const [expanded, setExpanded] = useState(false);

  const taskStatus = rule.task_status;
  const isRunning = running || taskStatus?.running;
  const lastRun = taskStatus?.completed_at;

  return (
    <div className={`bg-white border rounded-xl overflow-hidden transition-all ${rule.auto_update_ikas ? "border-emerald-200" : "border-slate-200"}`} data-testid={`rule-${rule.category_name}`}>
      <div className="p-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className={`w-2 h-2 rounded-full ${rule.auto_update_ikas ? "bg-emerald-500" : "bg-slate-300"}`} />
            <div>
              <h3 className="font-semibold text-slate-800">{rule.category_name}</h3>
              <p className="text-xs text-slate-500">{rule.product_count || 0} urun | Kirma: {rule.undercut_amount || 200} TL</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            {/* Auto toggle */}
            <div className="flex items-center gap-2">
              <span className="text-xs text-slate-500">Otomatik</span>
              <Switch checked={rule.auto_update_ikas} onCheckedChange={() => onToggle(rule)} data-testid={`toggle-${rule.category_name}`} />
            </div>
            {/* Run Now */}
            <Button size="sm" variant="outline" onClick={() => onRun(rule.category_name)} disabled={isRunning} data-testid={`run-${rule.category_name}`}
              className="border-blue-300 text-blue-700 hover:bg-blue-50">
              {isRunning ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
              <span className="ml-1.5">{isRunning ? "Calisiyor..." : "Simdi Calistir"}</span>
            </Button>
            {/* Expand */}
            <button onClick={() => setExpanded(!expanded)} className="p-1.5 rounded hover:bg-slate-100">
              {expanded ? <ChevronUp className="h-4 w-4 text-slate-400" /> : <ChevronDown className="h-4 w-4 text-slate-400" />}
            </button>
          </div>
        </div>

        {/* Progress bar when running */}
        {isRunning && taskStatus && (
          <div className="mt-3">
            <div className="flex items-center justify-between text-xs text-blue-700 mb-1">
              <span>{taskStatus.phase === "ikas_refresh" ? "Ikas fiyat guncelleniyor..." : taskStatus.phase === "scanning" ? "Rakipler taraniyor..." : "Isleniyor..."}</span>
              <span>{taskStatus.progress || 0} / {taskStatus.total || rule.product_count || 0}</span>
            </div>
            <div className="w-full h-1.5 bg-blue-100 rounded-full">
              <div className="h-full bg-blue-500 rounded-full transition-all" style={{ width: `${Math.min(100, ((taskStatus.progress || 0) / Math.max(1, taskStatus.total || rule.product_count || 1)) * 100)}%` }} />
            </div>
          </div>
        )}

        {/* Last run info */}
        {lastRun && !isRunning && (
          <div className="mt-2 flex items-center gap-4 text-xs text-slate-500">
            <span className="flex items-center gap-1">
              <CheckCircle2 className="h-3 w-3 text-emerald-500" />
              Son: {new Date(lastRun).toLocaleString("tr-TR")}
            </span>
            {taskStatus?.updated > 0 && <span className="text-emerald-600 font-medium">{taskStatus.updated} guncellendi</span>}
            {taskStatus?.skipped > 0 && <span className="text-amber-600">{taskStatus.skipped} atlandi</span>}
          </div>
        )}
      </div>

      {/* Expanded details */}
      {expanded && (
        <div className="border-t bg-slate-50 p-4">
          <div className="flex items-center justify-between">
            <div className="text-xs text-slate-500 space-y-1">
              <p>Fiyat kirma tutari: <span className="font-medium text-slate-700">{rule.undercut_amount || 200} TL</span></p>
              <p>Otomatik guncelleme: <span className={`font-medium ${rule.auto_update_ikas ? "text-emerald-600" : "text-slate-400"}`}>{rule.auto_update_ikas ? "Aktif" : "Kapali"}</span></p>
              {taskStatus?.matched_total > 0 && <p>Eslesmis urun: <span className="font-medium text-slate-700">{taskStatus.matched_total}</span></p>}
            </div>
            <Button size="sm" variant="outline" onClick={() => onDelete(rule.category_name)} className="text-red-500 border-red-200 hover:bg-red-50 text-xs">
              Kurali Sil
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
