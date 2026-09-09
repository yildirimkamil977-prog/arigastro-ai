import { useState, useEffect } from "react";
import axios from "axios";
import { getAuthHeaders, API } from "../context/AuthContext";
import { Link } from "react-router-dom";
import {
  Package, TrendingDown, TrendingUp, FileText, AlertTriangle,
  ArrowRight, Zap, RefreshCw, DollarSign, Euro, BarChart2,
  Clock, CheckCircle2, ArrowUpRight, ArrowDownRight, ShoppingBag,
  Tag, Activity
} from "lucide-react";

const COMPETITOR_COLORS = {
  mutfak10: "#6366f1", cafemarkt: "#10b981", mutbex: "#f59e0b",
  hakbilenler: "#ef4444", oguzmutfak: "#8b5cf6", kariyermutfak: "#ec4899",
};
const COMPETITOR_LABELS = {
  mutfak10: "Mutfak10", cafemarkt: "Cafemarkt", mutbex: "Mutbex",
  hakbilenler: "Hakbilenler", oguzmutfak: "Oğuz Mutfak", kariyermutfak: "Kariyer Mutfak",
};

function StatCard({ label, value, icon: Icon, color, bg, sub, link }) {
  const inner = (
    <div className={`rounded-xl border border-slate-200 ${bg} p-5 hover:shadow-md transition-shadow cursor-default`}>
      <div className="flex items-start justify-between">
        <div>
          <p className="text-[10px] uppercase tracking-widest font-semibold text-slate-400">{label}</p>
          <p className={`text-3xl font-bold mt-1.5 ${color} font-heading tracking-tight`}>{value}</p>
          {sub && <p className="text-xs text-slate-400 mt-1">{sub}</p>}
        </div>
        <div className={`w-11 h-11 rounded-xl flex items-center justify-center ${bg === "bg-white" ? "bg-slate-100" : "bg-white/60"}`}>
          <Icon className={`h-5 w-5 ${color}`} />
        </div>
      </div>
      {link && (
        <div className="mt-3 pt-3 border-t border-slate-100">
          <span className="text-xs text-indigo-600 flex items-center gap-1 font-medium">{link} <ArrowRight className="h-3 w-3" /></span>
        </div>
      )}
    </div>
  );
  return link ? <Link to={link === "Ürünleri Gör" ? "/competitor-products" : link === "Fiyat Değişimleri" ? "/price-changes" : "/seo-logs"}>{inner}</Link> : inner;
}

export default function DashboardPage() {
  const [stats, setStats] = useState(null);
  const [rates, setRates] = useState(null);
  const [scraperApi, setScraperApi] = useState(null);
  const [currencyApi, setCurrencyApi] = useState(null);
  const [loading, setLoading] = useState(true);
  const [ratesUpdated, setRatesUpdated] = useState(null);

  const fetchAll = async () => {
    try {
      const [statsRes, ratesRes, scraperRes, currencyRes] = await Promise.all([
        axios.get(`${API}/dashboard/stats`, { headers: getAuthHeaders(), withCredentials: true }),
        axios.get(`${API}/dashboard/exchange-rates`, { headers: getAuthHeaders(), withCredentials: true }).catch(() => ({ data: {} })),
        axios.get(`${API}/scraperapi/account`, { headers: getAuthHeaders(), withCredentials: true }).catch(() => ({ data: {} })),
        axios.get(`${API}/currencyapi/account`, { headers: getAuthHeaders(), withCredentials: true }).catch(() => ({ data: {} })),
      ]);
      setStats(statsRes.data);
      setRates(ratesRes.data);
      setScraperApi(scraperRes.data);
      setCurrencyApi(currencyRes.data);
      setRatesUpdated(new Date().toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" }));
    } catch (err) {
      console.error("Dashboard error:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAll();
    const interval = setInterval(fetchAll, 30000);
    return () => clearInterval(interval);
  }, []);

  const formatPrice = (v) => v != null ? Number(v).toLocaleString("tr-TR", { minimumFractionDigits: 0, maximumFractionDigits: 0 }) : "—";
  const formatDate = (iso) => {
    if (!iso) return "—";
    try { return new Date(iso).toLocaleString("tr-TR", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" }); }
    catch { return iso; }
  };

  if (loading) {
    return (
      <div className="animate-pulse space-y-6" data-testid="dashboard-loading">
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {[1,2,3,4].map(i => <div key={i} className="h-28 bg-slate-100 rounded-xl" />)}
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {[1,2,3].map(i => <div key={i} className="h-36 bg-slate-100 rounded-xl" />)}
        </div>
      </div>
    );
  }

  const creditUsed = scraperApi?.request_count || 0;
  const creditLimit = scraperApi?.request_limit || 0;
  const creditRemaining = creditLimit - creditUsed;
  const creditPct = creditLimit > 0 ? Math.round((creditUsed / creditLimit) * 100) : 0;

  const autoSeo = stats?.auto_seo_status;
  const scanSt = stats?.scan_status;

  return (
    <div className="space-y-6" data-testid="dashboard-page">

      {/* ── Header ── */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h2 className="text-2xl font-bold text-slate-900 font-heading tracking-tight">Dashboard</h2>
          <p className="text-sm text-slate-400 mt-0.5">Arıgastro rakip takip & fiyat yönetimi</p>
        </div>
        <div className="flex items-center gap-3 flex-wrap">
          {/* Exchange Rates */}
          {rates?.EUR && (
            <div className="flex items-center gap-2 bg-white border border-slate-200 rounded-lg px-3 py-2 text-sm" data-testid="exchange-rates">
              <Euro className="h-3.5 w-3.5 text-blue-500" />
              <span className="font-semibold text-slate-800">1 € = {formatPrice(rates.EUR)} ₺</span>
              <span className="text-slate-300">|</span>
              <DollarSign className="h-3.5 w-3.5 text-emerald-500" />
              <span className="font-semibold text-slate-800">1 $ = {formatPrice(rates.USD)} ₺</span>
              {ratesUpdated && <span className="text-[10px] text-slate-400">{ratesUpdated}</span>}
            </div>
          )}
          <button onClick={fetchAll} className="flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-700 bg-white border border-slate-200 rounded-lg px-3 py-2 transition-colors" data-testid="refresh-dashboard">
            <RefreshCw className="h-3.5 w-3.5" /> Yenile
          </button>
        </div>
      </div>

      {/* ── Main KPIs ── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="Toplam Ürün" value={stats?.total_products || 0} icon={Package} color="text-slate-700" bg="bg-white" link="Ürünleri Gör" />
        <StatCard label="Rakip Eşleşmesi" value={stats?.total_matches || 0} icon={Tag} color="text-indigo-600" bg="bg-indigo-50/60"
          sub={`${Object.keys(stats?.match_summary || {}).length} rakip sitede`} />
        <StatCard
          label="Rakip Daha Ucuz"
          value={stats?.competitors_cheaper || 0}
          icon={TrendingDown} color="text-red-600" bg="bg-red-50/60"
          sub="Fiyat güncellenmeli"
          link="Ürünleri Gör"
        />
        <StatCard
          label="Biz Daha Ucuz"
          value={stats?.we_are_cheaper || 0}
          icon={TrendingUp} color="text-emerald-600" bg="bg-emerald-50/60"
          sub="Rekabetçi konumdayız"
        />
      </div>

      {/* ── Secondary KPIs ── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <p className="text-[10px] uppercase tracking-widest font-semibold text-slate-400">Bugün Güncellenen</p>
          <p className="text-2xl font-bold text-slate-900 mt-1">{stats?.today_applied || 0}</p>
          <p className="text-xs text-slate-400 mt-1">{stats?.today_lower || 0} düşürüldü · {stats?.today_raise || 0} yükseltildi</p>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <p className="text-[10px] uppercase tracking-widest font-semibold text-slate-400">SEO Üretilmiş</p>
          <p className="text-2xl font-bold text-violet-600 mt-1">{stats?.seo_generated || 0}</p>
          <p className="text-xs text-slate-400 mt-1">{stats?.total_products ? `${Math.round((stats.seo_generated / stats.total_products) * 100)}% tamamlandı` : "—"}</p>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <p className="text-[10px] uppercase tracking-widest font-semibold text-slate-400">Kategoriler</p>
          <p className="text-2xl font-bold text-teal-600 mt-1">{stats?.tracked_categories || 0}<span className="text-base font-normal text-slate-400">/{stats?.total_categories || 0}</span></p>
          <p className="text-xs text-slate-400 mt-1">Takip edilen</p>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <p className="text-[10px] uppercase tracking-widest font-semibold text-slate-400">ScraperAPI Kalan</p>
          <p className={`text-2xl font-bold mt-1 ${creditRemaining < 500 ? "text-red-600" : creditPct > 70 ? "text-amber-600" : "text-emerald-600"}`}>
            {creditRemaining.toLocaleString("tr-TR")}
          </p>
          <p className="text-xs text-slate-400 mt-1">%{creditPct} kullanıldı</p>
        </div>
      </div>

      {/* ── Competitor Match Summary + Automation Status ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* Competitor Matches */}
        <div className="rounded-xl border border-slate-200 bg-white p-5" data-testid="competitor-match-summary">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-slate-800 flex items-center gap-2">
              <BarChart2 className="h-4 w-4 text-indigo-500" /> Rakip Eşleşme Dağılımı
            </h3>
            <Link to="/competitor-products" className="text-xs text-indigo-600 hover:underline flex items-center gap-1">
              Tümü <ArrowRight className="h-3 w-3" />
            </Link>
          </div>
          {Object.keys(stats?.match_summary || {}).length === 0 ? (
            <p className="text-sm text-slate-400 text-center py-6">Henüz eşleşme yok</p>
          ) : (
            <div className="space-y-2.5">
              {Object.entries(stats?.match_summary || {}).sort((a, b) => b[1] - a[1]).map(([key, count]) => {
                const total = stats?.total_products || 1;
                const pct = Math.round((count / total) * 100);
                return (
                  <div key={key}>
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs font-medium text-slate-600">{COMPETITOR_LABELS[key] || key}</span>
                      <span className="text-xs text-slate-500">{count} ürün</span>
                    </div>
                    <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden">
                      <div className="h-full rounded-full transition-all duration-700"
                        style={{ width: `${pct}%`, backgroundColor: COMPETITOR_COLORS[key] || "#6366f1" }} />
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Automation Status */}
        <div className="rounded-xl border border-slate-200 bg-white p-5" data-testid="automation-status">
          <h3 className="text-sm font-semibold text-slate-800 flex items-center gap-2 mb-4">
            <Activity className="h-4 w-4 text-emerald-500" /> Gece Otomasyonu Durumu
          </h3>
          <div className="space-y-3">
            {/* Competitor Scan */}
            <div className="flex items-start gap-3 p-3 rounded-lg bg-slate-50">
              <div className={`w-2.5 h-2.5 rounded-full mt-1 flex-shrink-0 ${scanSt?.last_run ? "bg-emerald-500" : "bg-slate-300"}`} />
              <div className="flex-1 min-w-0">
                <p className="text-xs font-semibold text-slate-700">Rakip Fiyat Tarama (00:45)</p>
                {scanSt?.last_run ? (
                  <p className="text-[11px] text-slate-400 mt-0.5">
                    Son: {formatDate(scanSt.last_run)} · {scanSt.scanned || 0} tarandı · {scanSt.auto_updated || 0} güncellendi
                  </p>
                ) : <p className="text-[11px] text-slate-400 mt-0.5">Henüz çalışmadı</p>}
              </div>
              {scanSt?.last_run && <CheckCircle2 className="h-4 w-4 text-emerald-500 flex-shrink-0" />}
            </div>
            {/* Auto SEO */}
            <div className="flex items-start gap-3 p-3 rounded-lg bg-slate-50">
              <div className={`w-2.5 h-2.5 rounded-full mt-1 flex-shrink-0 ${autoSeo?.completed_at ? "bg-emerald-500" : autoSeo?.running ? "bg-blue-500 animate-pulse" : "bg-slate-300"}`} />
              <div className="flex-1 min-w-0">
                <p className="text-xs font-semibold text-slate-700">Otomatik SEO Üretimi (03:00)</p>
                {autoSeo?.completed_at ? (
                  <p className="text-[11px] text-slate-400 mt-0.5">
                    Son: {formatDate(autoSeo.completed_at)} · {autoSeo.generated || 0} üretildi · {autoSeo.failed || 0} başarısız
                  </p>
                ) : autoSeo?.running ? (
                  <p className="text-[11px] text-blue-500 mt-0.5">Çalışıyor: {autoSeo.progress || 0}/{autoSeo.total || 0}</p>
                ) : <p className="text-[11px] text-slate-400 mt-0.5">Henüz çalışmadı</p>}
              </div>
              {autoSeo?.completed_at && !autoSeo?.running && (
                autoSeo.failed > 0
                  ? <AlertTriangle className="h-4 w-4 text-amber-500 flex-shrink-0" />
                  : <CheckCircle2 className="h-4 w-4 text-emerald-500 flex-shrink-0" />
              )}
            </div>
            <Link to="/seo-logs" className="text-xs text-indigo-600 hover:underline flex items-center gap-1 px-3">
              SEO loglarını gör <ArrowRight className="h-3 w-3" />
            </Link>
          </div>
        </div>
      </div>

      {/* ── ScraperAPI Credits ── */}
      {scraperApi?.configured && !scraperApi?.error && (
        <div className="rounded-xl border border-slate-200 bg-white p-5" data-testid="scraperapi-credits-card">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-slate-800 flex items-center gap-2">
              <Zap className="h-4 w-4 text-amber-500" /> ScraperAPI Kredi Durumu
            </h3>
            <a href="https://dashboard.scraperapi.com" target="_blank" rel="noopener noreferrer"
              className="text-xs text-blue-600 hover:underline flex items-center gap-1" data-testid="scraperapi-dashboard-link">
              Dashboard <ArrowRight className="h-3 w-3" />
            </a>
          </div>
          <div className="flex items-center gap-4">
            <div className="flex-1">
              <div className="flex items-center justify-between text-xs mb-1.5">
                <span className="text-slate-500">Kullanılan / Toplam</span>
                <span className="font-semibold text-slate-800" data-testid="scraperapi-credits-text">
                  {creditUsed.toLocaleString("tr-TR")} / {creditLimit.toLocaleString("tr-TR")}
                </span>
              </div>
              <div className="w-full bg-slate-100 rounded-full h-2.5 overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all duration-500 ${creditPct > 80 ? "bg-red-500" : creditPct > 50 ? "bg-amber-500" : "bg-emerald-500"}`}
                  style={{ width: `${Math.min(creditPct, 100)}%` }}
                  data-testid="scraperapi-credits-bar"
                />
              </div>
            </div>
            <div className="text-right flex-shrink-0">
              <p className={`text-lg font-bold ${creditRemaining < 500 ? "text-red-600" : "text-emerald-600"}`}>
                {creditRemaining.toLocaleString("tr-TR")}
              </p>
              <p className="text-[10px] text-slate-400">kredi kaldı</p>
            </div>
          </div>
        </div>
      )}

      {/* ── Recent Price Changes ── */}
      <div className="rounded-xl border border-slate-200 bg-white" data-testid="recent-price-changes">
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100">
          <h3 className="text-sm font-semibold text-slate-800 flex items-center gap-2">
            <Clock className="h-4 w-4 text-slate-400" /> Son Fiyat Değişimleri
          </h3>
          <Link to="/price-changes" className="text-xs text-indigo-600 hover:underline flex items-center gap-1">
            Tümünü Gör <ArrowRight className="h-3 w-3" />
          </Link>
        </div>
        {!stats?.recent_changes?.length ? (
          <div className="text-center py-10 text-slate-400">
            <ShoppingBag className="h-8 w-8 mx-auto mb-2 opacity-30" />
            <p className="text-sm">Henüz fiyat değişimi yok</p>
          </div>
        ) : (
          <div className="divide-y divide-slate-50">
            {stats.recent_changes.map((c, i) => {
              const isRaise = c.action === "raise";
              const isLower = c.action === "update";
              const diff = c.new_price_tl && c.old_price_tl ? Math.abs(c.new_price_tl - c.old_price_tl) : null;
              return (
                <div key={i} className="flex items-center gap-3 px-5 py-3 hover:bg-slate-50/70 transition-colors" data-testid={`recent-change-${i}`}>
                  <div className={`w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 ${isRaise ? "bg-emerald-100" : isLower ? "bg-red-100" : "bg-slate-100"}`}>
                    {isRaise ? <ArrowUpRight className="h-3.5 w-3.5 text-emerald-600" /> : isLower ? <ArrowDownRight className="h-3.5 w-3.5 text-red-500" /> : <AlertTriangle className="h-3.5 w-3.5 text-amber-500" />}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-slate-800 truncate">{c.product_name || "—"}</p>
                    <p className="text-[11px] text-slate-400">{c.cheapest_competitor || "—"} · {formatDate(c.changed_at)}</p>
                  </div>
                  <div className="text-right flex-shrink-0">
                    <p className="text-sm font-semibold text-slate-700">
                      {formatPrice(c.new_price_tl)} <span className="text-slate-400 font-normal text-xs">₺</span>
                    </p>
                    {diff && (
                      <p className={`text-[11px] font-medium ${isRaise ? "text-emerald-600" : "text-red-500"}`}>
                        {isRaise ? "+" : "-"}{formatPrice(diff)} ₺
                      </p>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* ── Price Alerts (competitor cheaper) ── */}
      {stats?.recent_alerts?.length > 0 && (
        <div className="rounded-xl border border-red-200 bg-red-50/40" data-testid="price-alerts">
          <div className="flex items-center justify-between px-5 py-4 border-b border-red-100">
            <h3 className="text-sm font-semibold text-red-800 flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-red-500" /> Rakip Daha Ucuz — Dikkat
            </h3>
            <Link to="/competitor-products" className="text-xs text-red-600 hover:underline flex items-center gap-1">
              Tümünü Gör <ArrowRight className="h-3 w-3" />
            </Link>
          </div>
          <div className="divide-y divide-red-100">
            {stats.recent_alerts.slice(0, 5).map((alert, i) => (
              <div key={i} className="flex items-center justify-between px-5 py-3" data-testid={`alert-row-${i}`}>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-slate-900 truncate">{alert.name}</p>
                  <p className="text-xs text-slate-500">{alert.cheapest_competitor}</p>
                </div>
                <div className="flex items-center gap-5 flex-shrink-0">
                  <div className="text-right">
                    <p className="text-[10px] text-slate-400">Bizim</p>
                    <p className="text-sm font-semibold text-slate-700">{formatPrice(alert.our_price)} ₺</p>
                  </div>
                  <div className="text-right">
                    <p className="text-[10px] text-slate-400">Rakip</p>
                    <p className="text-sm font-semibold text-red-600">{formatPrice(alert.cheapest_price)} ₺</p>
                  </div>
                  <div className="bg-red-100 text-red-700 text-xs font-semibold px-2 py-1 rounded-lg">
                    -{formatPrice(alert.price_difference)} ₺
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
