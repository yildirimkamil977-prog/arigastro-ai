import { useState, useEffect } from "react";
import axios from "axios";
import { getAuthHeaders, API } from "../context/AuthContext";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Settings as SettingsIcon, RefreshCw, Database, Key, Loader2, Clock, CheckCircle2 } from "lucide-react";
import { toast } from "sonner";

export default function SettingsPage() {
  const [feedStatus, setFeedStatus] = useState(null);
  const [matchStatus, setMatchStatus] = useState(null);
  const [priceStatus, setPriceStatus] = useState(null);
  const [schedulerStatus, setSchedulerStatus] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchAll = async () => {
      try {
        const [feed, match, price, sched] = await Promise.all([
          axios.get(`${API}/feed/status`, { headers: getAuthHeaders(), withCredentials: true }).catch(() => ({ data: {} })),
          axios.get(`${API}/products/ai-match-status`, { headers: getAuthHeaders(), withCredentials: true }).catch(() => ({ data: {} })),
          axios.get(`${API}/products/price-check-status`, { headers: getAuthHeaders(), withCredentials: true }).catch(() => ({ data: {} })),
          axios.get(`${API}/scheduler/status`, { headers: getAuthHeaders(), withCredentials: true }).catch(() => ({ data: {} })),
        ]);
        setFeedStatus(feed.data);
        setMatchStatus(match.data);
        setPriceStatus(price.data);
        setSchedulerStatus(sched.data);
      } catch {}
      finally { setLoading(false); }
    };
    fetchAll();
    const interval = setInterval(fetchAll, 10000);
    return () => clearInterval(interval);
  }, []);

  const formatDate = (iso) => {
    if (!iso) return "-";
    try { return new Date(iso).toLocaleString("tr-TR"); } catch { return iso; }
  };

  return (
    <div className="space-y-6 max-w-3xl" data-testid="settings-page">
      <div>
        <h2 className="text-2xl font-bold tracking-tight text-slate-900 font-heading">Ayarlar</h2>
        <p className="text-sm text-slate-500 mt-1">Sistem durumu ve yapilandirma</p>
      </div>

      {/* System Status */}
      <Card className="border-slate-200">
        <CardHeader className="pb-3">
          <CardTitle className="text-base font-heading flex items-center gap-2"><Database className="h-4 w-4" />Sistem Durumu</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div className="bg-slate-50 rounded-lg p-3">
              <p className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold">Feed Durumu</p>
              <p className="text-sm text-slate-900 mt-1">Toplam: {feedStatus?.total_products || 0} urun</p>
              <p className="text-xs text-slate-500">Fiyatli: {feedStatus?.products_with_price || 0}</p>
            </div>
            <div className="bg-slate-50 rounded-lg p-3">
              <p className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold">AI Eslestirme</p>
              {matchStatus?.running ? (
                <div className="flex items-center gap-2 mt-1">
                  <Loader2 className="h-3 w-3 animate-spin text-violet-600" />
                  <span className="text-sm text-violet-700">{matchStatus.current}/{matchStatus.total} isleniyor</span>
                </div>
              ) : (
                <p className="text-sm text-slate-900 mt-1">{matchStatus?.matched || 0} eslesti, {matchStatus?.skipped || 0} belirsiz</p>
              )}
            </div>
            <div className="bg-slate-50 rounded-lg p-3">
              <p className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold">Fiyat Kontrolu</p>
              {priceStatus?.running ? (
                <div className="flex items-center gap-2 mt-1">
                  <Loader2 className="h-3 w-3 animate-spin text-amber-600" />
                  <span className="text-sm text-amber-700">{priceStatus.current}/{priceStatus.total} kontrol ediliyor</span>
                </div>
              ) : (
                <p className="text-sm text-slate-900 mt-1">{priceStatus?.success || 0} basarili, {priceStatus?.failed || 0} basarisiz</p>
              )}
            </div>
            <div className="bg-slate-50 rounded-lg p-3">
              <p className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold">ScraperAPI</p>
              <p className="text-sm text-slate-900 mt-1">
                {feedStatus?.feed_url ? <Badge className="bg-emerald-100 text-emerald-700 border-0 text-[10px]">Aktif</Badge> : <Badge variant="outline" className="text-[10px]">Yapilandirilmamis</Badge>}
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Scheduler Status */}
      <Card className="border-slate-200">
        <CardHeader className="pb-3">
          <CardTitle className="text-base font-heading flex items-center gap-2"><Clock className="h-4 w-4" />Otomatik Zamanlayici</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex items-center gap-2 mb-3">
            <span className="text-sm text-slate-700">Durum:</span>
            {schedulerStatus?.scheduler_running ? (
              <Badge className="bg-emerald-100 text-emerald-700 border-0 text-[10px]" data-testid="scheduler-active-badge"><CheckCircle2 className="h-3 w-3 mr-1" />Aktif</Badge>
            ) : (
              <Badge variant="outline" className="text-[10px]">Pasif</Badge>
            )}
          </div>
          <div className="space-y-2">
            {schedulerStatus?.jobs?.map((job) => (
              <div key={job.id} className="bg-slate-50 rounded-lg p-3 flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-slate-900">{job.name}</p>
                  <p className="text-xs text-slate-500">Sonraki calisma: {formatDate(job.next_run)}</p>
                </div>
                <Badge className="bg-blue-100 text-blue-700 border-0 text-[10px]">Zamanlanmis</Badge>
              </div>
            ))}
            {(!schedulerStatus?.jobs || schedulerStatus.jobs.length === 0) && (
              <p className="text-sm text-slate-500">Zamanlanmis gorev bulunamadi</p>
            )}
          </div>
          {schedulerStatus?.feed_sync_last && (
            <div className="border-t border-slate-100 pt-2 mt-2">
              <p className="text-xs text-slate-500">Son Feed Sync: {formatDate(schedulerStatus.feed_sync_last.last_run)} ({schedulerStatus.feed_sync_last.updated || 0} urun guncellendi)</p>
            </div>
          )}
          {schedulerStatus?.price_check_last && (
            <div className="border-t border-slate-100 pt-2">
              <p className="text-xs text-slate-500">Son Fiyat Kontrolu: {formatDate(schedulerStatus.price_check_last.last_run)} ({schedulerStatus.price_check_last.products_checked || 0} urun kontrol edildi)</p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* API Keys Info */}
      <Card className="border-slate-200">
        <CardHeader className="pb-3">
          <CardTitle className="text-base font-heading flex items-center gap-2"><Key className="h-4 w-4" />API Anahtarlari</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm text-slate-600">
          <div className="flex items-center justify-between py-2 border-b border-slate-100">
            <span>OpenAI API Key</span>
            <Badge className="bg-emerald-100 text-emerald-700 border-0 text-[10px]">Yapilandirildi</Badge>
          </div>
          <div className="flex items-center justify-between py-2 border-b border-slate-100">
            <span>ScraperAPI Key</span>
            <Badge className="bg-emerald-100 text-emerald-700 border-0 text-[10px]">Yapilandirildi</Badge>
          </div>
          <div className="flex items-center justify-between py-2 border-b border-slate-100">
            <span>Feed URL</span>
            <Badge className="bg-emerald-100 text-emerald-700 border-0 text-[10px]">Yapilandirildi</Badge>
          </div>
          <p className="text-xs text-slate-400 mt-2">API anahtarlari backend .env dosyasindan yonetilir.</p>
        </CardContent>
      </Card>
    </div>
  );
}
