import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { getAuthHeaders, API } from "../context/AuthContext";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../components/ui/table";
import { Loader2, Play, CheckCircle2, XCircle, FileText, Send, ChevronLeft, ChevronRight, RefreshCw, Zap } from "lucide-react";
import { toast } from "sonner";

export default function SeoLogsPage() {
  const [categories, setCategories] = useState([]);
  const [logs, setLogs] = useState([]);
  const [logStats, setLogStats] = useState({});
  const [logPage, setLogPage] = useState(1);
  const [logPages, setLogPages] = useState(1);
  const [logTotal, setLogTotal] = useState(0);
  const [bulkStatuses, setBulkStatuses] = useState([]);
  const [loading, setLoading] = useState(true);
  const [repushStatus, setRepushStatus] = useState(null);
  const [genAllStatus, setGenAllStatus] = useState(null);

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

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, [fetchData]);

  const startBulkSeo = async (category) => {
    try {
      const { data } = await axios.post(`${API}/seo/bulk-generate-push?category=${encodeURIComponent(category)}`, {}, { headers: getAuthHeaders(), withCredentials: true });
      if (data.started) {
        toast.info(data.message, { duration: 5000 });
      } else {
        toast.warning(data.message);
      }
    } catch (err) {
      toast.error(err.response?.data?.detail || "Toplu SEO basarisiz");
    }
  };

  const startRepushAll = async () => {
    try {
      const { data } = await axios.post(`${API}/ikas/repush-all-seo`, {}, { headers: getAuthHeaders(), withCredentials: true });
      toast.info(data.message, { duration: 5000 });
    } catch (err) {
      toast.error(err.response?.data?.detail || "Yeniden aktarim basarisiz");
    }
  };

  const startGenerateAll = async () => {
    try {
      const { data } = await axios.post(`${API}/seo/generate-all`, {}, { headers: getAuthHeaders(), withCredentials: true });
      toast.info(data.message, { duration: 5000 });
    } catch (err) {
      toast.error(err.response?.data?.detail || "Toplu uretim basarisiz");
    }
  };

  const stopGenerateAll = async () => {
    try {
      const { data } = await axios.post(`${API}/seo/generate-all-stop`, {}, { headers: getAuthHeaders(), withCredentials: true });
      toast.info(data.message, { duration: 5000 });
    } catch (err) {
      toast.error(err.response?.data?.detail || "Durdurma basarisiz");
    }
  };

  const hasAnyRunning = bulkStatuses.some(t => t.running && !t.paused);
  const hasAnyPaused = bulkStatuses.some(t => t.paused);

  const formatDate = (iso) => {
    if (!iso) return "-";
    try { return new Date(iso).toLocaleString("tr-TR"); } catch { return iso; }
  };

  const totalProducts = categories.reduce((sum, c) => sum + c.total, 0);
  const totalSeo = categories.reduce((sum, c) => sum + c.seo_generated, 0);
  const totalPushed = categories.reduce((sum, c) => sum + c.ikas_pushed, 0);
  const totalRemaining = categories.reduce((sum, c) => sum + c.remaining, 0);

  return (
    <div className="space-y-6" data-testid="seo-logs-page">
      <div>
        <h2 className="text-2xl font-bold tracking-tight text-slate-900 font-heading">Toplu SEO Yonetimi</h2>
        <p className="text-sm text-slate-500 mt-1">Kategorilere gore SEO uretimi ve Ikas'a gonderme</p>
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card className="border-slate-200"><CardContent className="p-4">
          <p className="text-[10px] uppercase tracking-wider text-slate-500">Toplam Urun</p>
          <p className="text-2xl font-bold text-slate-900">{totalProducts}</p>
        </CardContent></Card>
        <Card className="border-slate-200"><CardContent className="p-4">
          <p className="text-[10px] uppercase tracking-wider text-slate-500">SEO Uretilmis</p>
          <p className="text-2xl font-bold text-emerald-600">{totalSeo}</p>
        </CardContent></Card>
        <Card className="border-slate-200"><CardContent className="p-4">
          <p className="text-[10px] uppercase tracking-wider text-slate-500">Ikas'a Gonderilmis</p>
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
              <p className="text-sm font-semibold text-indigo-900">Tum Ikas Iceriklerini Duzelt</p>
              <p className="text-xs text-indigo-600">Mevcut SEO iceriklerini duzeltilmis HTML formatiyla Ikas'a yeniden aktar</p>
            </div>
            <Button size="sm" className="bg-indigo-600 hover:bg-indigo-700 text-white" onClick={startRepushAll} disabled={repushStatus?.running} data-testid="repush-all-btn">
              <RefreshCw className={`h-3.5 w-3.5 mr-1.5 ${repushStatus?.running ? 'animate-spin' : ''}`} />
              {repushStatus?.running ? `${repushStatus.progress}/${repushStatus.total}` : 'Hepsini Duzelt'}
            </Button>
          </CardContent>
        </Card>
        <Card className="border border-amber-200 bg-amber-50/30">
          <CardContent className="p-4 flex items-center justify-between">
            <div>
              <p className="text-sm font-semibold text-amber-900">Tum Urunleri Uret ve Guncelle</p>
              <p className="text-xs text-amber-600">SEO icerigi olmayan tum urunler icin uret, hepsini Ikas'a aktar</p>
            </div>
            <div className="flex gap-2">
              <Button size="sm" className="bg-amber-600 hover:bg-amber-700 text-white" onClick={startGenerateAll} disabled={genAllStatus?.running} data-testid="generate-all-btn">
                <Zap className={`h-3.5 w-3.5 mr-1.5 ${genAllStatus?.running ? 'animate-pulse' : ''}`} />
                {genAllStatus?.running ? `${genAllStatus.progress}/${genAllStatus.total}` : 'Hepsini Uret'}
              </Button>
              {genAllStatus?.running && (
                <Button size="sm" variant="destructive" onClick={stopGenerateAll} data-testid="stop-generate-all-btn">
                  Durdur
                </Button>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Repush Status */}
      {repushStatus?.running && (
        <Card className="border-indigo-200 bg-indigo-50">
          <CardContent className="p-4 flex items-center gap-3">
            <Loader2 className="h-5 w-5 animate-spin text-indigo-600" />
            <div className="flex-1">
              <p className="text-sm font-medium text-indigo-900">Ikas yeniden aktarim devam ediyor: {repushStatus.progress}/{repushStatus.total}</p>
              <p className="text-xs text-indigo-600">{repushStatus.success || 0} basarili, {repushStatus.failed || 0} basarisiz</p>
              <div className="mt-1 h-1.5 bg-indigo-100 rounded-full"><div className="h-1.5 bg-indigo-500 rounded-full transition-all" style={{ width: `${repushStatus.total > 0 ? (repushStatus.progress / repushStatus.total * 100) : 0}%` }} /></div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Generate All Status */}
      {genAllStatus?.running && (
        <Card className="border-amber-200 bg-amber-50">
          <CardContent className="p-4 flex items-center gap-3">
            <Loader2 className="h-5 w-5 animate-spin text-amber-600" />
            <div className="flex-1">
              <p className="text-sm font-medium text-amber-900">Toplu uretim devam ediyor: {genAllStatus.progress}/{genAllStatus.total}</p>
              <p className="text-xs text-amber-600">{genAllStatus.generated || 0} uretildi, {genAllStatus.pushed || 0} aktarildi, {genAllStatus.failed || 0} basarisiz</p>
              <div className="mt-1 h-1.5 bg-amber-100 rounded-full"><div className="h-1.5 bg-amber-500 rounded-full transition-all" style={{ width: `${genAllStatus.total > 0 ? (genAllStatus.progress / genAllStatus.total * 100) : 0}%` }} /></div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Running/Paused Statuses */}
      {bulkStatuses.filter(t => t.running || t.paused).map((task, idx) => (
        <Card key={idx} className={`border-${task.paused ? 'amber' : 'indigo'}-200 bg-${task.paused ? 'amber' : 'indigo'}-50`}>
          <CardContent className="p-4 flex items-center gap-3">
            {task.paused ? (
              <XCircle className="h-5 w-5 text-amber-600" />
            ) : (
              <Loader2 className="h-5 w-5 animate-spin text-indigo-600" />
            )}
            <div className="flex-1">
              <p className={`text-sm font-medium ${task.paused ? 'text-amber-900' : 'text-indigo-900'}`}>
                {task.paused ? 'DURAKLATILDI' : 'SEO uretimi devam ediyor'}: {task.current || 0}/{task.total || 0}
              </p>
              <p className={`text-xs ${task.paused ? 'text-amber-600' : 'text-indigo-600'}`}>
                {task.success || 0} basarili, {task.failed || 0} basarisiz | Kategori: {task.category || "-"}
                {task.error && <span className="ml-2 text-red-600 font-medium">{task.error}</span>}
              </p>
              {task.paused && (
                <p className="text-xs text-amber-700 mt-1 font-medium">Bakiye yukledikten sonra tekrar "Uret ve Gonder" butonuna basin.</p>
              )}
            </div>
          </CardContent>
        </Card>
      ))}

      {/* Categories Table */}
      <Card className="border-slate-200" data-testid="seo-categories-card">
        <CardHeader className="pb-3">
          <CardTitle className="text-base font-heading flex items-center gap-2">
            <FileText className="h-4 w-4" />Kategoriler
          </CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow className="bg-slate-50">
                <TableHead className="text-[10px] uppercase tracking-wider font-semibold text-slate-500">Kategori</TableHead>
                <TableHead className="text-[10px] uppercase tracking-wider font-semibold text-slate-500 text-center">Toplam</TableHead>
                <TableHead className="text-[10px] uppercase tracking-wider font-semibold text-slate-500 text-center">SEO Uretildi</TableHead>
                <TableHead className="text-[10px] uppercase tracking-wider font-semibold text-slate-500 text-center">Ikas Gonderildi</TableHead>
                <TableHead className="text-[10px] uppercase tracking-wider font-semibold text-slate-500 text-center">Kalan</TableHead>
                <TableHead className="text-[10px] uppercase tracking-wider font-semibold text-slate-500 text-right">Islem</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading ? (
                <TableRow><TableCell colSpan={6} className="text-center py-8"><Loader2 className="h-5 w-5 animate-spin mx-auto" /></TableCell></TableRow>
              ) : categories.length === 0 ? (
                <TableRow><TableCell colSpan={6} className="text-center py-8 text-sm text-slate-500">Kategori bulunamadi</TableCell></TableRow>
              ) : categories.map((cat) => (
                <TableRow key={cat.category} data-testid={`seo-cat-row-${cat.category?.slice(0, 20)}`}>
                  <TableCell className="text-sm font-medium text-slate-900 max-w-[250px] truncate">{cat.category}</TableCell>
                  <TableCell className="text-center text-sm text-slate-600">{cat.total}</TableCell>
                  <TableCell className="text-center">
                    <Badge className={`border-0 text-[10px] ${cat.seo_generated === cat.total ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700"}`}>
                      {cat.seo_generated}/{cat.total}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-center">
                    <Badge className={`border-0 text-[10px] ${cat.ikas_pushed === cat.total ? "bg-indigo-100 text-indigo-700" : "bg-slate-100 text-slate-600"}`}>
                      {cat.ikas_pushed}/{cat.total}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-center text-sm font-medium">
                    {cat.remaining > 0 ? <span className="text-amber-600">{cat.remaining}</span> : <CheckCircle2 className="h-4 w-4 text-emerald-500 mx-auto" />}
                  </TableCell>
                  <TableCell className="text-right">
                    <Button
                      size="sm"
                      onClick={() => startBulkSeo(cat.category)}
                      disabled={cat.running && !cat.paused}
                      data-testid={`seo-start-${cat.category?.slice(0, 20)}`}
                      className={`h-7 text-[10px] ${cat.paused ? 'bg-amber-600 hover:bg-amber-700' : cat.remaining === 0 ? 'bg-emerald-600' : 'bg-indigo-600 hover:bg-indigo-700'} text-white`}
                    >
                      {cat.running && !cat.paused ? <Loader2 className="h-3 w-3 animate-spin mr-1" /> : <Play className="h-3 w-3 mr-1" />}
                      {cat.running && !cat.paused ? "Calisiyor" : cat.paused ? "Devam Et" : cat.remaining === 0 ? "Tamamlandi" : "Uret ve Gonder"}
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
            <CardTitle className="text-base font-heading flex items-center gap-2">
              <Send className="h-4 w-4" />Islem Kayitlari
            </CardTitle>
            <div className="flex items-center gap-3 text-xs text-slate-500">
              <span>Uretildi: <strong className="text-emerald-600">{logStats.generated || 0}</strong></span>
              <span>Ikas: <strong className="text-indigo-600">{logStats.pushed || 0}</strong></span>
              <span>Basarisiz: <strong className="text-red-600">{logStats.failed || 0}</strong></span>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow className="bg-slate-50">
                <TableHead className="text-[10px] uppercase tracking-wider font-semibold text-slate-500">Urun</TableHead>
                <TableHead className="text-[10px] uppercase tracking-wider font-semibold text-slate-500">Kategori</TableHead>
                <TableHead className="text-[10px] uppercase tracking-wider font-semibold text-slate-500 text-center">SEO</TableHead>
                <TableHead className="text-[10px] uppercase tracking-wider font-semibold text-slate-500 text-center">Ikas</TableHead>
                <TableHead className="text-[10px] uppercase tracking-wider font-semibold text-slate-500 text-center">Kelime</TableHead>
                <TableHead className="text-[10px] uppercase tracking-wider font-semibold text-slate-500">Tarih</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {logs.length === 0 ? (
                <TableRow><TableCell colSpan={6} className="text-center py-8 text-sm text-slate-500">Henuz islem kaydi yok</TableCell></TableRow>
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
    </div>
  );
}
