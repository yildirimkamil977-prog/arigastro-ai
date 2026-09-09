import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { getAuthHeaders, API } from "../context/AuthContext";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../components/ui/table";
import { Loader2, Play, CheckCircle2, XCircle, FileText, Send, ChevronLeft, ChevronRight, RefreshCw, Zap, Moon, AlertCircle, Clock } from "lucide-react";
import { toast } from "sonner";

export default function SeoLogsPage() {
  const [activeTab, setActiveTab] = useState("bulk");
  const [categories, setCategories] = useState([]);
  const [uniqueTotals, setUniqueTotals] = useState({});
  const [logs, setLogs] = useState([]);
  const [logStats, setLogStats] = useState({});
  const [logPage, setLogPage] = useState(1);
  const [logPages, setLogPages] = useState(1);
  const [logTotal, setLogTotal] = useState(0);
  const [bulkStatuses, setBulkStatuses] = useState([]);
  const [loading, setLoading] = useState(true);
  const [repushStatus, setRepushStatus] = useState(null);
  const [genAllStatus, setGenAllStatus] = useState(null);
  const [syncing, setSyncing] = useState(false);

  // Nightly tab state
  const [nightlyRuns, setNightlyRuns] = useState([]);
  const [selectedRun, setSelectedRun] = useState(null);
  const [nightlyLogs, setNightlyLogs] = useState([]);
  const [nightlyPage, setNightlyPage] = useState(1);
  const [nightlyPages, setNightlyPages] = useState(1);
  const [nightlyTotal, setNightlyTotal] = useState(0);
  const [nightlyLoading, setNightlyLoading] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      const [catRes, logRes, statusRes, repushRes, genAllRes] = await Promise.all([
        axios.get(`${API}/seo/categories/stats`, { headers: getAuthHeaders(), withCredentials: true }),
        axios.get(`${API}/seo/logs?page=${logPage}&limit=30`, { headers: getAuthHeaders(), withCredentials: true }),
        axios.get(`${API}/seo/bulk-status`, { headers: getAuthHeaders(), withCredentials: true }),
        axios.get(`${API}/ikas/repush-status`, { headers: getAuthHeaders(), withCredentials: true }).catch(() => ({ data: {} })),
        axios.get(`${API}/seo/generate-all-status`, { headers: getAuthHeaders(), withCredentials: true }).catch(() => ({ data: {} })),
      ]);
      setCategories(catRes.data.categories || []);
      setUniqueTotals({
        total: catRes.data.unique_total || 0,
        seo: catRes.data.unique_seo || 0,
        pushed: catRes.data.unique_pushed || 0,
        remaining: catRes.data.unique_remaining || 0,
      });
      setLogs(logRes.data.logs || []);
      setLogStats(logRes.data.stats || {});
      setLogPages(logRes.data.pages || 1);
      setLogTotal(logRes.data.total || 0);
      setBulkStatuses(statusRes.data.tasks || []);
      setRepushStatus(repushRes.data || null);
      setGenAllStatus(genAllRes.data || null);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [logPage]);

  const fetchNightlyRuns = useCallback(async () => {
    try {
      const { data } = await axios.get(`${API}/seo/nightly-runs`, { headers: getAuthHeaders(), withCredentials: true });
      setNightlyRuns(data.runs || []);
    } catch (err) {
      console.error(err);
    }
  }, []);

  const fetchNightlyLogs = useCallback(async (date) => {
    setNightlyLoading(true);
    try {
      const { data } = await axios.get(
        `${API}/seo/logs?trigger=auto_nightly&page=${nightlyPage}&limit=50`,
        { headers: getAuthHeaders(), withCredentials: true }
      );
      // Filter by date if provided
      let logsToShow = data.logs || [];
      if (date) logsToShow = logsToShow.filter(l => l.timestamp?.startsWith(date));
      setNightlyLogs(logsToShow);
      setNightlyPages(data.pages || 1);
      setNightlyTotal(data.total || 0);
    } catch (err) {
      console.error(err);
    } finally {
      setNightlyLoading(false);
    }
  }, [nightlyPage]);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, [fetchData]);

  useEffect(() => {
    if (activeTab === "nightly") {
      fetchNightlyRuns();
    }
  }, [activeTab, fetchNightlyRuns]);

  useEffect(() => {
    if (selectedRun) {
      fetchNightlyLogs(selectedRun);
    }
  }, [selectedRun, fetchNightlyLogs]);

  const startBulkSeo = async (category) => {
    try {
      const { data } = await axios.post(`${API}/seo/bulk-generate-push?category=${encodeURIComponent(category)}`, {}, { headers: getAuthHeaders(), withCredentials: true });
      if (data.started) toast.info(data.message, { duration: 5000 });
      else toast.warning(data.message);
    } catch (err) {
      toast.error(err.response?.data?.detail || "Toplu SEO basarisiz");
    }
  };

  const startRepushAll = async () => {
    try {
      const { data } = await axios.post(`${API}/ikas/repush-all-seo`, {}, { headers: getAuthHeaders(), withCredentials: true });
      toast.info(data.message, { duration: 5000 });
    } catch (err) { toast.error(err.response?.data?.detail || "Yeniden aktarim basarisiz"); }
  };

  const startGenerateAll = async () => {
    try {
      const { data } = await axios.post(`${API}/seo/generate-all`, {}, { headers: getAuthHeaders(), withCredentials: true });
      toast.info(data.message, { duration: 5000 });
    } catch (err) { toast.error(err.response?.data?.detail || "Toplu uretim basarisiz"); }
  };

  const stopGenerateAll = async () => {
    try {
      const { data } = await axios.post(`${API}/seo/generate-all-stop`, {}, { headers: getAuthHeaders(), withCredentials: true });
      toast.info(data.message, { duration: 5000 });
    } catch (err) { toast.error(err.response?.data?.detail || "Durdurma basarisiz"); }
  };

  const syncProductsCategories = async () => {
    setSyncing(true);
    try {
      const { data } = await axios.post(`${API}/competitor/sync-ikas-currencies`, {}, { headers: getAuthHeaders(), withCredentials: true });
      if (data.started) {
        toast.success("Ürün ve kategori güncelleme başlatıldı");
        const poll = setInterval(async () => {
          try {
            const { data: st } = await axios.get(`${API}/competitor/sync-ikas-currencies-status`, { headers: getAuthHeaders(), withCredentials: true });
            if (!st.running) { clearInterval(poll); setSyncing(false); toast.success(`Güncelleme tamamlandı: ${st.updated || 0} ürün`); fetchData(); }
          } catch { clearInterval(poll); setSyncing(false); }
        }, 3000);
      } else { toast.info(data.message); setSyncing(false); }
    } catch { toast.error("Senkronizasyon başlatılamadı"); setSyncing(false); }
  };

  const formatDate = (iso) => {
    if (!iso) return "-";
    try { return new Date(iso).toLocaleString("tr-TR"); } catch { return iso; }
  };

  const formatDateShort = (dateStr) => {
    if (!dateStr) return "-";
    try {
      const d = new Date(dateStr + "T00:00:00");
      return d.toLocaleDateString("tr-TR", { day: "2-digit", month: "long", year: "numeric" });
    } catch { return dateStr; }
  };

  const totalProducts = uniqueTotals.total || 0;
  const totalSeo = uniqueTotals.seo || 0;
  const totalPushed = uniqueTotals.pushed || 0;
  const totalRemaining = uniqueTotals.remaining || 0;

  return (
    <div className="space-y-6" data-testid="seo-logs-page">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-slate-900 font-heading">SEO Yönetimi</h2>
          <p className="text-sm text-slate-500 mt-1">Toplu SEO üretimi ve otomasyon logları</p>
        </div>
        <Button size="sm" variant="outline" onClick={syncProductsCategories} disabled={syncing} data-testid="sync-seo-products-btn" className="border-blue-300 text-blue-700 bg-blue-50 hover:bg-blue-100">
          {syncing ? <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5 mr-1.5" />}
          {syncing ? "Güncelleniyor..." : "Ürün ve Kategorileri Güncelle"}
        </Button>
      </div>

      {/* Tab Switcher */}
      <div className="flex border-b border-slate-200">
        <button
          onClick={() => setActiveTab("bulk")}
          className={`px-5 py-2.5 text-sm font-medium transition-colors border-b-2 -mb-px ${activeTab === "bulk" ? "border-indigo-600 text-indigo-600" : "border-transparent text-slate-500 hover:text-slate-700"}`}
          data-testid="tab-bulk"
        >
          <Send className="h-3.5 w-3.5 inline mr-1.5" />Toplu SEO Yönetimi
        </button>
        <button
          onClick={() => setActiveTab("nightly")}
          className={`px-5 py-2.5 text-sm font-medium transition-colors border-b-2 -mb-px ${activeTab === "nightly" ? "border-indigo-600 text-indigo-600" : "border-transparent text-slate-500 hover:text-slate-700"}`}
          data-testid="tab-nightly"
        >
          <Moon className="h-3.5 w-3.5 inline mr-1.5" />Gece Otomasyonu Logları
        </button>
      </div>

      {/* ===== BULK TAB ===== */}
      {activeTab === "bulk" && (
        <>
          {/* Summary Stats */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <Card className="border-slate-200"><CardContent className="p-4">
              <p className="text-[10px] uppercase tracking-wider text-slate-500">Toplam Ürün</p>
              <p className="text-2xl font-bold text-slate-900">{totalProducts}</p>
            </CardContent></Card>
            <Card className="border-slate-200"><CardContent className="p-4">
              <p className="text-[10px] uppercase tracking-wider text-slate-500">SEO Üretilmiş</p>
              <p className="text-2xl font-bold text-emerald-600">{totalSeo}</p>
            </CardContent></Card>
            <Card className="border-slate-200"><CardContent className="p-4">
              <p className="text-[10px] uppercase tracking-wider text-slate-500">İkas'a Gönderilmiş</p>
              <p className="text-2xl font-bold text-indigo-600">{totalPushed}</p>
            </CardContent></Card>
            <Card className="border-slate-200"><CardContent className="p-4">
              <p className="text-[10px] uppercase tracking-wider text-slate-500">Kalan</p>
              <p className="text-2xl font-bold text-amber-600">{totalRemaining}</p>
            </CardContent></Card>
          </div>

          {/* Action Buttons */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <Card className="border border-indigo-200 bg-indigo-50/30">
              <CardContent className="p-4 flex items-center justify-between">
                <div>
                  <p className="text-sm font-semibold text-indigo-900">Tüm İkas İçeriklerini Düzelt</p>
                  <p className="text-xs text-indigo-600">Mevcut SEO içeriklerini düzeltilmiş HTML formatıyla yeniden aktar</p>
                </div>
                <Button size="sm" className="bg-indigo-600 hover:bg-indigo-700 text-white" onClick={startRepushAll} disabled={repushStatus?.running} data-testid="repush-all-btn">
                  <RefreshCw className={`h-3.5 w-3.5 mr-1.5 ${repushStatus?.running ? 'animate-spin' : ''}`} />
                  {repushStatus?.running ? `${repushStatus.progress}/${repushStatus.total}` : 'Hepsini Düzelt'}
                </Button>
              </CardContent>
            </Card>
            <Card className="border border-amber-200 bg-amber-50/30">
              <CardContent className="p-4 flex items-center justify-between">
                <div>
                  <p className="text-sm font-semibold text-amber-900">Tüm Ürünleri Üret ve Güncelle</p>
                  <p className="text-xs text-amber-600">SEO içeriği olmayan tüm ürünler için üret ve İkas'a aktar</p>
                </div>
                <div className="flex gap-2">
                  <Button size="sm" className="bg-amber-600 hover:bg-amber-700 text-white" onClick={startGenerateAll} disabled={genAllStatus?.running} data-testid="generate-all-btn">
                    <Zap className={`h-3.5 w-3.5 mr-1.5 ${genAllStatus?.running ? 'animate-pulse' : ''}`} />
                    {genAllStatus?.running ? `${genAllStatus.progress}/${genAllStatus.total}` : 'Hepsini Üret'}
                  </Button>
                  {genAllStatus?.running && (
                    <Button size="sm" variant="destructive" onClick={stopGenerateAll} data-testid="stop-generate-all-btn">Durdur</Button>
                  )}
                </div>
              </CardContent>
            </Card>
          </div>

          {repushStatus?.running && (
            <Card className="border-indigo-200 bg-indigo-50"><CardContent className="p-4 flex items-center gap-3">
              <Loader2 className="h-5 w-5 animate-spin text-indigo-600" />
              <div className="flex-1">
                <p className="text-sm font-medium text-indigo-900">İkas aktarımı: {repushStatus.progress}/{repushStatus.total}</p>
                <p className="text-xs text-indigo-600">{repushStatus.success || 0} başarılı, {repushStatus.failed || 0} başarısız</p>
                <div className="mt-1 h-1.5 bg-indigo-100 rounded-full"><div className="h-1.5 bg-indigo-500 rounded-full" style={{ width: `${repushStatus.total > 0 ? (repushStatus.progress / repushStatus.total * 100) : 0}%` }} /></div>
              </div>
            </CardContent></Card>
          )}

          {genAllStatus?.running && (
            <Card className="border-amber-200 bg-amber-50"><CardContent className="p-4 flex items-center gap-3">
              <Loader2 className="h-5 w-5 animate-spin text-amber-600" />
              <div className="flex-1">
                <p className="text-sm font-medium text-amber-900">Toplu üretim: {genAllStatus.progress}/{genAllStatus.total}</p>
                <p className="text-xs text-amber-600">{genAllStatus.generated || 0} üretildi, {genAllStatus.pushed || 0} aktarıldı, {genAllStatus.failed || 0} başarısız</p>
                <div className="mt-1 h-1.5 bg-amber-100 rounded-full"><div className="h-1.5 bg-amber-500 rounded-full" style={{ width: `${genAllStatus.total > 0 ? (genAllStatus.progress / genAllStatus.total * 100) : 0}%` }} /></div>
              </div>
            </CardContent></Card>
          )}

          {bulkStatuses.filter(t => t.running || t.paused).map((task, idx) => (
            <Card key={idx} className={`border-${task.paused ? 'amber' : 'indigo'}-200 bg-${task.paused ? 'amber' : 'indigo'}-50`}>
              <CardContent className="p-4 flex items-center gap-3">
                {task.paused ? <XCircle className="h-5 w-5 text-amber-600" /> : <Loader2 className="h-5 w-5 animate-spin text-indigo-600" />}
                <div className="flex-1">
                  <p className={`text-sm font-medium ${task.paused ? 'text-amber-900' : 'text-indigo-900'}`}>
                    {task.paused ? 'DURAKLATILDI' : 'SEO üretimi devam ediyor'}: {task.current || 0}/{task.total || 0}
                  </p>
                  <p className={`text-xs ${task.paused ? 'text-amber-600' : 'text-indigo-600'}`}>
                    {task.success || 0} başarılı, {task.failed || 0} başarısız | Kategori: {task.category || "-"}
                    {task.error && <span className="ml-2 text-red-600 font-medium">{task.error}</span>}
                  </p>
                  {task.paused && <p className="text-xs text-amber-700 mt-1 font-medium">Bakiye yükledikten sonra tekrar "Üret ve Gönder" butonuna basın.</p>}
                </div>
              </CardContent>
            </Card>
          ))}

          {/* Categories Table */}
          <Card className="border-slate-200" data-testid="seo-categories-card">
            <CardHeader className="pb-3">
              <CardTitle className="text-base font-heading flex items-center gap-2"><FileText className="h-4 w-4" />Kategoriler</CardTitle>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow className="bg-slate-50">
                    <TableHead className="text-[10px] uppercase tracking-wider font-semibold text-slate-500">Kategori</TableHead>
                    <TableHead className="text-[10px] uppercase tracking-wider font-semibold text-slate-500 text-center">Toplam</TableHead>
                    <TableHead className="text-[10px] uppercase tracking-wider font-semibold text-slate-500 text-center">SEO Üretildi</TableHead>
                    <TableHead className="text-[10px] uppercase tracking-wider font-semibold text-slate-500 text-center">İkas Gönderildi</TableHead>
                    <TableHead className="text-[10px] uppercase tracking-wider font-semibold text-slate-500 text-center">Kalan</TableHead>
                    <TableHead className="text-[10px] uppercase tracking-wider font-semibold text-slate-500 text-right">İşlem</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {loading ? (
                    <TableRow><TableCell colSpan={6} className="text-center py-8"><Loader2 className="h-5 w-5 animate-spin mx-auto" /></TableCell></TableRow>
                  ) : categories.length === 0 ? (
                    <TableRow><TableCell colSpan={6} className="text-center py-8 text-sm text-slate-500">Kategori bulunamadı</TableCell></TableRow>
                  ) : categories.map((cat) => (
                    <TableRow key={cat.category} data-testid={`seo-cat-row-${cat.category?.slice(0, 20)}`}>
                      <TableCell className="text-sm font-medium text-slate-900 max-w-[250px] truncate">{cat.category}</TableCell>
                      <TableCell className="text-center text-sm text-slate-600">{cat.total}</TableCell>
                      <TableCell className="text-center">
                        <Badge className={`border-0 text-[10px] ${cat.seo_generated === cat.total ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700"}`}>{cat.seo_generated}/{cat.total}</Badge>
                      </TableCell>
                      <TableCell className="text-center">
                        <Badge className={`border-0 text-[10px] ${cat.ikas_pushed === cat.total ? "bg-indigo-100 text-indigo-700" : "bg-slate-100 text-slate-600"}`}>{cat.ikas_pushed}/{cat.total}</Badge>
                      </TableCell>
                      <TableCell className="text-center text-sm font-medium">
                        {cat.remaining > 0 ? <span className="text-amber-600">{cat.remaining}</span> : <CheckCircle2 className="h-4 w-4 text-emerald-500 mx-auto" />}
                      </TableCell>
                      <TableCell className="text-right">
                        <Button size="sm" onClick={() => startBulkSeo(cat.category)} disabled={cat.running && !cat.paused}
                          data-testid={`seo-start-${cat.category?.slice(0, 20)}`}
                          className={`h-7 text-[10px] ${cat.paused ? 'bg-amber-600 hover:bg-amber-700' : cat.remaining === 0 ? 'bg-emerald-600' : 'bg-indigo-600 hover:bg-indigo-700'} text-white`}>
                          {cat.running && !cat.paused ? <Loader2 className="h-3 w-3 animate-spin mr-1" /> : <Play className="h-3 w-3 mr-1" />}
                          {cat.running && !cat.paused ? "Çalışıyor" : cat.paused ? "Devam Et" : cat.remaining === 0 ? "Tamamlandı" : "Üret ve Gönder"}
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>

          {/* Logs */}
          <Card className="border-slate-200" data-testid="seo-logs-card">
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-base font-heading flex items-center gap-2"><Send className="h-4 w-4" />İşlem Kayıtları</CardTitle>
                <div className="flex items-center gap-3 text-xs text-slate-500">
                  <span>Üretildi: <strong className="text-emerald-600">{logStats.generated || 0}</strong></span>
                  <span>İkas: <strong className="text-indigo-600">{logStats.pushed || 0}</strong></span>
                  <span>Başarısız: <strong className="text-red-600">{logStats.failed || 0}</strong></span>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow className="bg-slate-50">
                    <TableHead className="text-[10px] uppercase tracking-wider font-semibold text-slate-500">Ürün</TableHead>
                    <TableHead className="text-[10px] uppercase tracking-wider font-semibold text-slate-500">Kategori</TableHead>
                    <TableHead className="text-[10px] uppercase tracking-wider font-semibold text-slate-500 text-center">SEO</TableHead>
                    <TableHead className="text-[10px] uppercase tracking-wider font-semibold text-slate-500 text-center">İkas</TableHead>
                    <TableHead className="text-[10px] uppercase tracking-wider font-semibold text-slate-500 text-center">Kelime</TableHead>
                    <TableHead className="text-[10px] uppercase tracking-wider font-semibold text-slate-500">Tarih</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {logs.length === 0 ? (
                    <TableRow><TableCell colSpan={6} className="text-center py-8 text-sm text-slate-500">Henüz işlem kaydı yok</TableCell></TableRow>
                  ) : logs.map((log, i) => (
                    <TableRow key={`${log.product_slug}-${i}`}>
                      <TableCell className="text-sm text-slate-900 max-w-[200px] truncate">{log.product_name}</TableCell>
                      <TableCell className="text-xs text-slate-500 max-w-[150px] truncate">{log.category?.split(" > ").pop() || "-"}</TableCell>
                      <TableCell className="text-center">
                        {log.seo_generated ? <CheckCircle2 className="h-4 w-4 text-emerald-500 mx-auto" /> : <XCircle className="h-4 w-4 text-red-400 mx-auto" />}
                      </TableCell>
                      <TableCell className="text-center">
                        {log.ikas_pushed ? <CheckCircle2 className="h-4 w-4 text-indigo-500 mx-auto" /> : <XCircle className="h-4 w-4 text-slate-300 mx-auto" />}
                      </TableCell>
                      <TableCell className="text-center text-xs text-slate-600">{log.word_count || "-"}</TableCell>
                      <TableCell className="text-xs text-slate-500">{formatDate(log.timestamp)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
              {logPages > 1 && (
                <div className="flex items-center justify-between mt-3">
                  <p className="text-xs text-slate-500">Sayfa {logPage}/{logPages} (Toplam {logTotal})</p>
                  <div className="flex gap-2">
                    <Button variant="outline" size="sm" disabled={logPage <= 1} onClick={() => setLogPage(logPage - 1)}><ChevronLeft className="h-4 w-4" /></Button>
                    <Button variant="outline" size="sm" disabled={logPage >= logPages} onClick={() => setLogPage(logPage + 1)}><ChevronRight className="h-4 w-4" /></Button>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </>
      )}

      {/* ===== NIGHTLY TAB ===== */}
      {activeTab === "nightly" && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
            {/* Run List */}
            <div className="space-y-2">
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">Gece Çalışmaları</p>
              {nightlyRuns.length === 0 ? (
                <Card className="border-slate-200">
                  <CardContent className="p-6 text-center text-sm text-slate-400">
                    <Moon className="h-8 w-8 mx-auto mb-2 opacity-30" />
                    <p>Henüz gece otomasyonu kaydı yok</p>
                    <p className="text-xs mt-1 text-slate-300">Her gece 03:00'de otomatik çalışır</p>
                  </CardContent>
                </Card>
              ) : nightlyRuns.map((run) => (
                <button
                  key={run.date}
                  onClick={() => setSelectedRun(run.date)}
                  data-testid={`nightly-run-${run.date}`}
                  className={`w-full text-left p-3 rounded-lg border transition-all ${selectedRun === run.date ? "border-indigo-400 bg-indigo-50" : "border-slate-200 bg-white hover:border-slate-300"}`}
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm font-semibold text-slate-800">{formatDateShort(run.date)}</p>
                      <p className="text-xs text-slate-500 mt-0.5">
                        {run.total} ürün işlendi
                      </p>
                    </div>
                    <div className="text-right">
                      {run.failed > 0 ? (
                        <Badge className="bg-red-100 text-red-700 border-0 text-[10px]">{run.failed} hata</Badge>
                      ) : (
                        <Badge className="bg-emerald-100 text-emerald-700 border-0 text-[10px]">Başarılı</Badge>
                      )}
                      <p className="text-[10px] text-slate-400 mt-0.5">
                        <span className="text-emerald-600 font-medium">{run.generated}</span> üretildi · <span className="text-indigo-600 font-medium">{run.pushed}</span> gönderildi
                      </p>
                    </div>
                  </div>
                </button>
              ))}
            </div>

            {/* Run Detail */}
            <div className="lg:col-span-2">
              {!selectedRun ? (
                <Card className="border-slate-200 h-full">
                  <CardContent className="flex items-center justify-center h-48 text-slate-400">
                    <div className="text-center">
                      <Clock className="h-8 w-8 mx-auto mb-2 opacity-30" />
                      <p className="text-sm">Detayları görmek için bir tarih seçin</p>
                    </div>
                  </CardContent>
                </Card>
              ) : (
                <Card className="border-slate-200">
                  <CardHeader className="pb-3 border-b">
                    <div className="flex items-center justify-between">
                      <CardTitle className="text-base font-heading flex items-center gap-2">
                        <Moon className="h-4 w-4 text-indigo-500" />
                        {formatDateShort(selectedRun)} — Gece SEO Çalışması
                      </CardTitle>
                      <Button size="sm" variant="outline" onClick={() => fetchNightlyLogs(selectedRun)} data-testid="refresh-nightly-logs">
                        <RefreshCw className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  </CardHeader>
                  <CardContent className="p-0">
                    {nightlyLoading ? (
                      <div className="flex items-center justify-center py-12">
                        <Loader2 className="h-6 w-6 animate-spin text-indigo-500" />
                      </div>
                    ) : nightlyLogs.length === 0 ? (
                      <div className="text-center py-12 text-slate-400">
                        <p className="text-sm">Bu tarih için kayıt bulunamadı</p>
                      </div>
                    ) : (
                      <Table>
                        <TableHeader>
                          <TableRow className="bg-slate-50">
                            <TableHead className="text-[10px] uppercase tracking-wider font-semibold text-slate-500 pl-4">Ürün</TableHead>
                            <TableHead className="text-[10px] uppercase tracking-wider font-semibold text-slate-500 text-center">SEO</TableHead>
                            <TableHead className="text-[10px] uppercase tracking-wider font-semibold text-slate-500 text-center">İkas</TableHead>
                            <TableHead className="text-[10px] uppercase tracking-wider font-semibold text-slate-500">Saat</TableHead>
                            <TableHead className="text-[10px] uppercase tracking-wider font-semibold text-slate-500">Hata</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {nightlyLogs.map((log, i) => (
                            <TableRow key={i} className={log.error ? "bg-red-50/50" : ""}>
                              <TableCell className="text-sm text-slate-900 max-w-[240px] pl-4">
                                <p className="truncate font-medium" title={log.product_name}>{log.product_name}</p>
                                <p className="text-[10px] text-slate-400 truncate">{log.category?.split(" > ").pop()}</p>
                              </TableCell>
                              <TableCell className="text-center">
                                {log.seo_generated
                                  ? <CheckCircle2 className="h-4 w-4 text-emerald-500 mx-auto" />
                                  : <XCircle className="h-4 w-4 text-red-400 mx-auto" />}
                              </TableCell>
                              <TableCell className="text-center">
                                {log.ikas_pushed
                                  ? <CheckCircle2 className="h-4 w-4 text-indigo-500 mx-auto" />
                                  : <XCircle className="h-4 w-4 text-slate-300 mx-auto" />}
                              </TableCell>
                              <TableCell className="text-xs text-slate-500">
                                {log.timestamp ? new Date(log.timestamp).toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" }) : "-"}
                              </TableCell>
                              <TableCell className="text-xs max-w-[200px]">
                                {log.error ? (
                                  <span className="text-red-600 flex items-start gap-1">
                                    <AlertCircle className="h-3.5 w-3.5 flex-shrink-0 mt-0.5" />
                                    <span className="truncate" title={log.error}>{log.error.slice(0, 80)}</span>
                                  </span>
                                ) : <span className="text-slate-300">—</span>}
                              </TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    )}
                  </CardContent>
                </Card>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
