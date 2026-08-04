import { useState, useEffect, useCallback } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { toast } from "sonner";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend, RadarChart, PolarGrid, PolarAngleAxis,
  PolarRadiusAxis, Radar, AreaChart, Area
} from "recharts";
import {
  Search, BarChart3, Brain, RefreshCw, Target, Shield, Globe,
  Clock, Monitor, Smartphone, Tablet, AlertTriangle, TrendingUp,
  Lightbulb, FileText, History, ChevronDown, ChevronUp,
  Award, XCircle, CheckCircle2
} from "lucide-react";
import ReactMarkdown from "react-markdown";

const API = process.env.REACT_APP_BACKEND_URL;

const CATEGORIES = [
  { id: "search_terms", label: "Arama Terimleri", icon: Search, color: "text-blue-600" },
  { id: "ad_performance", label: "Reklam Performansi", icon: BarChart3, color: "text-amber-600" },
  { id: "ad_assets", label: "Reklam Ogeleri", icon: FileText, color: "text-violet-600" },
  { id: "competition", label: "Rekabet Analizi", icon: Shield, color: "text-red-600" },
  { id: "seo", label: "SEO & Organik", icon: Globe, color: "text-emerald-600" },
  { id: "time_device", label: "Zaman & Cihaz", icon: Clock, color: "text-cyan-600" },
  { id: "strategy", label: "Strateji", icon: Target, color: "text-slate-800" },
];

const COLORS = ["#f59e0b", "#3b82f6", "#10b981", "#ef4444", "#8b5cf6", "#06b6d4", "#ec4899"];
const ROAS_COLORS = { good: "#10b981", mid: "#f59e0b", bad: "#ef4444", zero: "#cbd5e1" };

function QSBadge({ score }) {
  if (!score && score !== 0) return <span className="text-[10px] text-slate-400">—</span>;
  const c = score >= 7 ? "text-emerald-700 bg-emerald-50 border-emerald-200" : score >= 4 ? "text-amber-700 bg-amber-50 border-amber-200" : "text-red-700 bg-red-50 border-red-200";
  return <span className={`text-xs font-bold px-1.5 py-0.5 rounded border ${c}`}>{score}</span>;
}

function CompBadge({ val }) {
  if (val === "ABOVE_AVERAGE") return <span className="text-[10px] font-medium text-emerald-600 bg-emerald-50 px-1.5 py-0.5 rounded">Ust</span>;
  if (val === "AVERAGE") return <span className="text-[10px] font-medium text-amber-600 bg-amber-50 px-1.5 py-0.5 rounded">Ort</span>;
  if (val === "BELOW_AVERAGE") return <span className="text-[10px] font-medium text-red-600 bg-red-50 px-1.5 py-0.5 rounded">Alt</span>;
  return <span className="text-[10px] text-slate-400">—</span>;
}

function RoasColor({ v }) {
  const c = v >= 5 ? "text-emerald-600" : v >= 2 ? "text-amber-600" : v > 0 ? "text-red-500" : "text-slate-400";
  return <span className={`font-bold ${c}`}>{v}x</span>;
}

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-white border border-slate-200 rounded-lg shadow-lg px-3 py-2 text-xs">
      <p className="font-semibold text-slate-800 mb-1">{label}</p>
      {payload.map((p, i) => (
        <p key={i} style={{ color: p.color }} className="flex justify-between gap-4">
          <span>{p.name}:</span>
          <span className="font-mono font-medium">{typeof p.value === 'number' ? p.value.toLocaleString("tr-TR") : p.value}</span>
        </p>
      ))}
    </div>
  );
}

export default function ReportsPage() {
  const [cat, setCat] = useState("search_terms");
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [report, setReport] = useState(null);
  const [data, setData] = useState({});
  const [showAI, setShowAI] = useState(false);
  const [pastReports, setPastReports] = useState([]);
  const [showHistory, setShowHistory] = useState(false);
  const [ga4Data, setGa4Data] = useState(null);

  const fetchData = useCallback(async (c) => {
    setLoading(true);
    setData({});
    try {
      const endpoints = {
        search_terms: ["/api/reports/search-terms", "/api/reports/quality-scores"],
        ad_performance: ["/api/reports/competition", "/api/reports/device-performance", "/api/reports/hourly-performance"],
        ad_assets: ["/api/reports/ad-assets"],
        competition: ["/api/reports/competition"],
        seo: ["/api/reports/gsc-pages", "/api/reports/landing-pages"],
        time_device: ["/api/reports/device-performance", "/api/reports/hourly-performance"],
        strategy: ["/api/reports/competition", "/api/reports/device-performance"],
      };
      // Always fetch GA4
      const ga4Res = await fetch(`${API}/api/marketing/dashboard`, { credentials: "include" });
      if (ga4Res.ok) { const g = await ga4Res.json(); setGa4Data(g); }

      const urls = endpoints[c] || [];
      const results = await Promise.all(
        urls.map(url => fetch(`${API}${url}`, { credentials: "include" }).then(r => r.json()).catch(() => []))
      );
      const dm = {};
      urls.forEach((url, i) => { dm[url.split("/").pop()] = Array.isArray(results[i]) ? results[i].filter(x => !x.error) : results[i]; });
      setData(dm);
    } catch (e) { toast.error("Veri alinamadi"); }
    finally { setLoading(false); }
  }, []);

  const generateReport = async () => {
    setGenerating(true); setReport(null); setShowAI(true);
    try {
      const res = await fetch(`${API}/api/reports/ai-report`, {
        method: "POST", headers: { "Content-Type": "application/json" }, credentials: "include",
        body: JSON.stringify({ category: cat }),
      });
      if (!res.ok) { const e = await res.json(); throw new Error(e.detail); }
      const d = await res.json();
      setReport(d.report);
      toast.success("AI icgoruler hazirlandi!");
    } catch (e) { toast.error("Hata: " + e.message); }
    finally { setGenerating(false); }
  };

  const loadHistory = async () => {
    try { const r = await fetch(`${API}/api/reports/history?category=${cat}&limit=5`, { credentials: "include" }); setPastReports(await r.json()); } catch {}
  };

  useEffect(() => { fetchData(cat); setReport(null); setShowAI(false); setShowHistory(false); }, [cat, fetchData]);

  const terms = data["search-terms"] || [];
  const qs = data["quality-scores"] || [];
  const comp = data["competition"] || [];
  const devices = data["device-performance"] || [];
  const hourly = data["hourly-performance"] || [];
  const assets = data["ad-assets"] || [];
  const gscPages = data["gsc-pages"] || [];
  const landingPages = data["landing-pages"] || [];
  const ga4 = ga4Data?.ga4_overview || {};
  const traffic = (ga4Data?.ga4_traffic || []).filter(t => !t.error);
  const campaigns = (ga4Data?.ads_campaigns || []).filter(c => !c.error);

  // Derived
  const wastedTerms = terms.filter(t => t.clicks >= 3 && t.conversions === 0);
  const profitTerms = terms.filter(t => t.roas >= 3 && t.conversions > 0);
  const totalWaste = wastedTerms.reduce((s, t) => s + t.cost, 0);

  // QS Distribution
  const qsDist = [
    { name: "1-3 (Dusuk)", value: qs.filter(k => k.quality_score && k.quality_score <= 3).length, fill: "#ef4444" },
    { name: "4-6 (Orta)", value: qs.filter(k => k.quality_score && k.quality_score >= 4 && k.quality_score <= 6).length, fill: "#f59e0b" },
    { name: "7-10 (Iyi)", value: qs.filter(k => k.quality_score && k.quality_score >= 7).length, fill: "#10b981" },
    { name: "Bilinmiyor", value: qs.filter(k => !k.quality_score).length, fill: "#cbd5e1" },
  ].filter(d => d.value > 0);

  // Hourly chart data
  const hourlyChart = hourly.map(h => ({
    saat: `${String(h.hour).padStart(2, "0")}:00`,
    Harcama: Math.round(h.cost),
    ROAS: h.roas,
    Donusum: Math.round(h.conversions),
    fill: h.roas >= 5 ? ROAS_COLORS.good : h.roas >= 2 ? ROAS_COLORS.mid : h.roas > 0 ? ROAS_COLORS.bad : ROAS_COLORS.zero,
  }));

  // Device chart
  const deviceChart = devices.map(d => ({
    name: d.device === "MOBILE" ? "Mobil" : d.device === "DESKTOP" ? "Masaustu" : "Tablet",
    Harcama: Math.round(d.cost),
    ROAS: d.roas,
    Tiklama: d.clicks,
    Donusum: Math.round(d.conversions),
  }));

  // Competition chart
  const compChart = comp.map(c => ({
    name: c.campaign.split("|")[0].trim().substring(0, 20),
    "Gosterim Payi": c.impression_share,
    "Rank Kaybi": c.lost_is_rank,
    "Butce Kaybi": c.lost_is_budget,
  }));

  // Traffic source chart
  const trafficChart = traffic.slice(0, 8).map(t => ({
    name: `${t.source}/${t.medium}`.substring(0, 18),
    Oturum: t.sessions,
    Gelir: Math.round(t.revenue),
  }));

  const catInfo = CATEGORIES.find(c => c.id === cat);

  return (
    <div className="space-y-5" data-testid="reports-page">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h2 className="text-xl font-bold text-slate-900">Analiz & Rapor</h2>
          <p className="text-sm text-slate-500 mt-0.5">Gercek veriler, gorseller ve AI icgoruler</p>
        </div>
        <div className="flex gap-2 items-center">
          <Button variant="outline" size="sm" className="h-8 text-xs" onClick={() => fetchData(cat)} disabled={loading}>
            <RefreshCw className={`h-3 w-3 mr-1 ${loading ? "animate-spin" : ""}`} /> Yenile
          </Button>
          <Button variant="outline" size="sm" className="h-8 text-xs" onClick={() => { setShowHistory(!showHistory); if (!showHistory) loadHistory(); }}>
            <History className="h-3 w-3 mr-1" /> Gecmis
          </Button>
          <Button size="sm" className="h-8 text-xs bg-slate-900 hover:bg-slate-800 text-white" onClick={generateReport} disabled={generating} data-testid="ai-insights-btn">
            <Brain className={`h-3.5 w-3.5 mr-1.5 ${generating ? "animate-pulse" : ""}`} />
            {generating ? "Hazirlaniyor..." : "AI Icgoruler"}
          </Button>
        </div>
      </div>

      {/* Category Tabs */}
      <div className="flex gap-1.5 overflow-x-auto pb-1" data-testid="report-categories">
        {CATEGORIES.map(c => (
          <button key={c.id} onClick={() => setCat(c.id)} data-testid={`tab-${c.id}`}
            className={`flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium whitespace-nowrap border transition-all
              ${cat === c.id ? "bg-slate-900 text-white border-slate-900" : "bg-white text-slate-600 border-slate-200 hover:border-slate-300 hover:bg-slate-50"}`}>
            <c.icon className="h-3.5 w-3.5" />{c.label}
          </button>
        ))}
      </div>

      {/* GA4 Summary Strip */}
      {ga4 && ga4.sessions && (
        <div className="grid grid-cols-3 md:grid-cols-6 gap-2">
          {[
            { l: "Oturumlar", v: ga4.sessions?.toLocaleString("tr-TR"), c: "text-blue-600" },
            { l: "Kullanicilar", v: ga4.total_users?.toLocaleString("tr-TR"), c: "text-violet-600" },
            { l: "Hemen Cikma", v: `%${ga4.bounce_rate}`, c: ga4.bounce_rate > 50 ? "text-red-600" : "text-emerald-600" },
            { l: "Ort. Sure", v: `${Math.round(ga4.avg_session_duration || 0)}sn`, c: "text-cyan-600" },
            { l: "Satis", v: ga4.purchases, c: "text-emerald-600" },
            { l: "Gelir", v: `${((ga4.revenue || 0) / 1000000).toFixed(1)}M TL`, c: "text-amber-600" },
          ].map((s, i) => (
            <div key={i} className="bg-white border border-slate-100 rounded-lg px-3 py-2">
              <p className="text-[10px] text-slate-400 uppercase">{s.l}</p>
              <p className={`text-sm font-bold ${s.c}`}>{s.v}</p>
            </div>
          ))}
        </div>
      )}

      {/* Past reports */}
      {showHistory && pastReports.length > 0 && (
        <Card className="border border-slate-200">
          <CardContent className="p-3 space-y-1">
            {pastReports.map((r, i) => (
              <div key={i} className="flex items-center justify-between p-2 rounded border border-slate-100 hover:bg-slate-50 cursor-pointer text-sm" onClick={() => { setReport(r.report); setShowHistory(false); setShowAI(true); }}>
                <span className="text-slate-700">{CATEGORIES.find(c => c.id === r.category)?.label}</span>
                <span className="text-xs text-slate-400">{new Date(r.created_at).toLocaleDateString("tr-TR")}</span>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {loading ? (
        <div className="flex items-center justify-center py-16"><RefreshCw className="h-6 w-6 text-slate-400 animate-spin" /></div>
      ) : (
        <>
          {/* ===== SEARCH TERMS ===== */}
          {cat === "search_terms" && (
            <div className="space-y-4">
              {/* Summary row */}
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
                <Card className="border"><CardContent className="p-3">
                  <p className="text-[10px] text-slate-400 uppercase">Toplam Terim</p>
                  <p className="text-2xl font-bold text-slate-900">{terms.length}</p>
                </CardContent></Card>
                <Card className="border border-red-200 bg-red-50/30"><CardContent className="p-3">
                  <p className="text-[10px] text-red-500 uppercase flex items-center gap-1"><XCircle className="h-3 w-3" />Butce Israfi</p>
                  <p className="text-2xl font-bold text-red-600">{wastedTerms.length}</p>
                  <p className="text-xs text-red-500">{totalWaste.toLocaleString("tr-TR", { minimumFractionDigits: 0 })} TL bosa harcama</p>
                </CardContent></Card>
                <Card className="border border-emerald-200 bg-emerald-50/30"><CardContent className="p-3">
                  <p className="text-[10px] text-emerald-500 uppercase flex items-center gap-1"><CheckCircle2 className="h-3 w-3" />Karli Terimler</p>
                  <p className="text-2xl font-bold text-emerald-600">{profitTerms.length}</p>
                </CardContent></Card>
                <Card className="border border-amber-200 bg-amber-50/30"><CardContent className="p-3">
                  <p className="text-[10px] text-amber-500 uppercase flex items-center gap-1"><AlertTriangle className="h-3 w-3" />Dusuk Kalite Puani</p>
                  <p className="text-2xl font-bold text-amber-600">{qs.filter(k => k.quality_score && k.quality_score < 5).length}</p>
                </CardContent></Card>
              </div>

              {/* Charts row */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                {/* QS Distribution Pie */}
                <Card className="border"><CardHeader className="pb-1 pt-3 px-4"><CardTitle className="text-sm font-semibold">Kalite Puani Dagilimi</CardTitle></CardHeader>
                  <CardContent className="px-4 pb-4">
                    <ResponsiveContainer width="100%" height={200}>
                      <PieChart>
                        <Pie data={qsDist} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={75} label={({ name, value }) => `${name}: ${value}`} labelLine={false}>
                          {qsDist.map((e, i) => <Cell key={i} fill={e.fill} />)}
                        </Pie>
                        <Tooltip />
                      </PieChart>
                    </ResponsiveContainer>
                  </CardContent>
                </Card>

                {/* Top wasters bar chart */}
                <Card className="border"><CardHeader className="pb-1 pt-3 px-4"><CardTitle className="text-sm font-semibold text-red-700">En Cok Israfi Yapan Terimler (TL)</CardTitle></CardHeader>
                  <CardContent className="px-4 pb-4">
                    <ResponsiveContainer width="100%" height={200}>
                      <BarChart data={wastedTerms.slice(0, 8).map(t => ({ name: t.term.substring(0, 18), Harcama: Math.round(t.cost), Tiklama: t.clicks }))} layout="vertical">
                        <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                        <XAxis type="number" tick={{ fontSize: 10 }} />
                        <YAxis dataKey="name" type="category" width={120} tick={{ fontSize: 10 }} />
                        <Tooltip content={<CustomTooltip />} />
                        <Bar dataKey="Harcama" fill="#ef4444" radius={[0, 4, 4, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  </CardContent>
                </Card>
              </div>

              {/* Quality Scores Table */}
              {qs.length > 0 && (
                <Card className="border">
                  <CardHeader className="pb-1 pt-3 px-4"><CardTitle className="text-sm font-semibold flex items-center gap-2"><Award className="h-4 w-4 text-amber-500" />Anahtar Kelime Kalite Puanlari</CardTitle></CardHeader>
                  <CardContent className="px-0 pb-0">
                    <div className="overflow-x-auto">
                      <table className="w-full text-left" data-testid="qs-table">
                        <thead><tr className="border-b bg-slate-50/50">
                          <th className="py-2 px-4 text-[10px] font-semibold text-slate-500 uppercase">Kelime</th>
                          <th className="py-2 px-3 text-[10px] text-center">KP</th>
                          <th className="py-2 px-3 text-[10px] text-center">Bek. TO</th>
                          <th className="py-2 px-3 text-[10px] text-center">Reklam</th>
                          <th className="py-2 px-3 text-[10px] text-center">Sayfa</th>
                          <th className="py-2 px-3 text-[10px] text-right">Harcama</th>
                          <th className="py-2 px-3 text-[10px] text-right">ROAS</th>
                        </tr></thead>
                        <tbody>
                          {qs.slice(0, 25).map((k, i) => (
                            <tr key={i} className={`border-b border-slate-50 hover:bg-slate-50/50 ${k.quality_score && k.quality_score < 5 ? "bg-red-50/20" : ""}`}>
                              <td className="py-1.5 px-4 text-sm font-medium text-slate-900">{k.keyword} <span className="text-[10px] text-slate-400">{k.match_type}</span></td>
                              <td className="py-1.5 px-3 text-center"><QSBadge score={k.quality_score} /></td>
                              <td className="py-1.5 px-3 text-center"><CompBadge val={k.expected_ctr} /></td>
                              <td className="py-1.5 px-3 text-center"><CompBadge val={k.creative_quality} /></td>
                              <td className="py-1.5 px-3 text-center"><CompBadge val={k.landing_page_quality} /></td>
                              <td className="py-1.5 px-3 text-sm text-right font-mono">{k.cost.toLocaleString("tr-TR", { minimumFractionDigits: 0 })} TL</td>
                              <td className="py-1.5 px-3 text-sm text-right"><RoasColor v={k.roas} /></td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </CardContent>
                </Card>
              )}
            </div>
          )}

          {/* ===== AD PERFORMANCE ===== */}
          {cat === "ad_performance" && (
            <div className="space-y-4">
              {/* Hourly ROAS Chart */}
              {hourlyChart.length > 0 && (
                <Card className="border"><CardHeader className="pb-1 pt-3 px-4"><CardTitle className="text-sm font-semibold">Saatlik Performans</CardTitle></CardHeader>
                  <CardContent className="px-4 pb-4">
                    <ResponsiveContainer width="100%" height={220}>
                      <BarChart data={hourlyChart}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                        <XAxis dataKey="saat" tick={{ fontSize: 9 }} interval={1} />
                        <YAxis yAxisId="cost" tick={{ fontSize: 10 }} />
                        <YAxis yAxisId="roas" orientation="right" tick={{ fontSize: 10 }} />
                        <Tooltip content={<CustomTooltip />} />
                        <Bar yAxisId="cost" dataKey="Harcama" radius={[2, 2, 0, 0]}>
                          {hourlyChart.map((e, i) => <Cell key={i} fill={e.fill} />)}
                        </Bar>
                        <Area yAxisId="roas" type="monotone" dataKey="ROAS" stroke="#3b82f6" fill="#3b82f620" strokeWidth={2} />
                      </BarChart>
                    </ResponsiveContainer>
                    <div className="flex gap-4 mt-1 text-[10px] text-slate-500">
                      <span className="flex items-center gap-1"><span className="w-2 h-2 rounded" style={{ background: ROAS_COLORS.good }} /> ROAS 5+</span>
                      <span className="flex items-center gap-1"><span className="w-2 h-2 rounded" style={{ background: ROAS_COLORS.mid }} /> 2-5</span>
                      <span className="flex items-center gap-1"><span className="w-2 h-2 rounded" style={{ background: ROAS_COLORS.bad }} /> 0-2</span>
                      <span className="flex items-center gap-1 ml-auto"><span className="w-3 h-0.5 bg-blue-500" /> ROAS (sag eksen)</span>
                    </div>
                  </CardContent>
                </Card>
              )}

              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                {/* Device Chart */}
                {deviceChart.length > 0 && (
                  <Card className="border"><CardHeader className="pb-1 pt-3 px-4"><CardTitle className="text-sm font-semibold">Cihaz Karsilastirmasi</CardTitle></CardHeader>
                    <CardContent className="px-4 pb-4">
                      <ResponsiveContainer width="100%" height={200}>
                        <BarChart data={deviceChart}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                          <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                          <YAxis tick={{ fontSize: 10 }} />
                          <Tooltip content={<CustomTooltip />} />
                          <Bar dataKey="Harcama" fill="#f59e0b" radius={[4, 4, 0, 0]} />
                          <Bar dataKey="Donusum" fill="#10b981" radius={[4, 4, 0, 0]} />
                        </BarChart>
                      </ResponsiveContainer>
                      <div className="grid grid-cols-3 gap-2 mt-3">
                        {devices.map((d, i) => (
                          <div key={i} className="text-center p-2 rounded-lg bg-slate-50 border border-slate-100">
                            <div className="flex items-center justify-center gap-1 mb-1">
                              {d.device === "MOBILE" ? <Smartphone className="h-3.5 w-3.5 text-slate-500" /> : d.device === "DESKTOP" ? <Monitor className="h-3.5 w-3.5 text-slate-500" /> : <Tablet className="h-3.5 w-3.5 text-slate-500" />}
                              <span className="text-xs font-medium text-slate-700">{d.device === "MOBILE" ? "Mobil" : d.device === "DESKTOP" ? "Masaustu" : "Tablet"}</span>
                            </div>
                            <p className="text-lg font-bold"><RoasColor v={d.roas} /></p>
                            <p className="text-[10px] text-slate-500">{d.cost.toLocaleString("tr-TR", { minimumFractionDigits: 0 })} TL</p>
                          </div>
                        ))}
                      </div>
                    </CardContent>
                  </Card>
                )}

                {/* Competition Chart */}
                {compChart.length > 0 && (
                  <Card className="border"><CardHeader className="pb-1 pt-3 px-4"><CardTitle className="text-sm font-semibold">Gosterim Payi Analizi</CardTitle></CardHeader>
                    <CardContent className="px-4 pb-4">
                      <ResponsiveContainer width="100%" height={200}>
                        <BarChart data={compChart} layout="vertical">
                          <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                          <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 10 }} unit="%" />
                          <YAxis dataKey="name" type="category" width={100} tick={{ fontSize: 9 }} />
                          <Tooltip content={<CustomTooltip />} />
                          <Bar dataKey="Gosterim Payi" fill="#3b82f6" stackId="a" radius={[0, 0, 0, 0]} />
                          <Bar dataKey="Rank Kaybi" fill="#ef4444" stackId="a" />
                          <Bar dataKey="Butce Kaybi" fill="#f59e0b" stackId="a" />
                        </BarChart>
                      </ResponsiveContainer>
                      <div className="flex gap-4 mt-1 text-[10px] text-slate-500">
                        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded bg-blue-500" /> Gosterim Payi</span>
                        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded bg-red-500" /> Rank Kaybi</span>
                        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded bg-amber-500" /> Butce Kaybi</span>
                      </div>
                    </CardContent>
                  </Card>
                )}
              </div>

              {/* Traffic Sources from GA4 */}
              {trafficChart.length > 0 && (
                <Card className="border"><CardHeader className="pb-1 pt-3 px-4"><CardTitle className="text-sm font-semibold flex items-center gap-2"><Globe className="h-4 w-4 text-violet-500" />Trafik Kaynaklari (GA4)</CardTitle></CardHeader>
                  <CardContent className="px-4 pb-4">
                    <ResponsiveContainer width="100%" height={180}>
                      <BarChart data={trafficChart}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                        <XAxis dataKey="name" tick={{ fontSize: 9 }} angle={-20} textAnchor="end" height={40} />
                        <YAxis yAxisId="s" tick={{ fontSize: 10 }} />
                        <YAxis yAxisId="g" orientation="right" tick={{ fontSize: 10 }} />
                        <Tooltip content={<CustomTooltip />} />
                        <Bar yAxisId="s" dataKey="Oturum" fill="#8b5cf6" radius={[4, 4, 0, 0]} />
                        <Bar yAxisId="g" dataKey="Gelir" fill="#10b981" radius={[4, 4, 0, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  </CardContent>
                </Card>
              )}
            </div>
          )}

          {/* ===== AD ASSETS ===== */}
          {cat === "ad_assets" && (
            <div className="space-y-4">
              {["HEADLINE", "DESCRIPTION"].map(ft => {
                const items = assets.filter(a => a.field_type === ft);
                if (!items.length) return null;
                const chartData = items.slice(0, 10).map(a => ({ name: (a.text || "—").substring(0, 25), Gosterim: a.impressions, Tiklama: a.clicks }));
                return (
                  <Card key={ft} className="border">
                    <CardHeader className="pb-1 pt-3 px-4"><CardTitle className="text-sm font-semibold">{ft === "HEADLINE" ? "Baslik" : "Aciklama"} Performansi ({items.length})</CardTitle></CardHeader>
                    <CardContent className="px-4 pb-4 space-y-3">
                      <ResponsiveContainer width="100%" height={200}>
                        <BarChart data={chartData} layout="vertical">
                          <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                          <XAxis type="number" tick={{ fontSize: 10 }} />
                          <YAxis dataKey="name" type="category" width={160} tick={{ fontSize: 9 }} />
                          <Tooltip content={<CustomTooltip />} />
                          <Bar dataKey="Gosterim" fill="#8b5cf6" radius={[0, 4, 4, 0]} />
                          <Bar dataKey="Tiklama" fill="#3b82f6" radius={[0, 4, 4, 0]} />
                        </BarChart>
                      </ResponsiveContainer>
                      <div className="overflow-x-auto">
                        <table className="w-full text-left">
                          <thead><tr className="border-b bg-slate-50/50">
                            <th className="py-1.5 px-3 text-[10px] text-slate-500">Metin</th>
                            <th className="py-1.5 px-3 text-[10px] text-center">Performans</th>
                            <th className="py-1.5 px-3 text-[10px] text-right">Gosterim</th>
                            <th className="py-1.5 px-3 text-[10px] text-right">TO</th>
                          </tr></thead>
                          <tbody>
                            {items.slice(0, 15).map((a, i) => {
                              const pc = { BEST: "bg-emerald-100 text-emerald-700", GOOD: "bg-blue-100 text-blue-700", LOW: "bg-red-100 text-red-700" };
                              return (
                                <tr key={i} className="border-b border-slate-50 hover:bg-slate-50/50">
                                  <td className="py-1.5 px-3 text-sm text-slate-800 max-w-xs truncate">{a.text || "—"}</td>
                                  <td className="py-1.5 px-3 text-center"><span className={`text-[10px] px-1.5 py-0.5 rounded ${pc[a.performance_label] || "bg-slate-100 text-slate-500"}`}>{a.performance_label || "N/A"}</span></td>
                                  <td className="py-1.5 px-3 text-sm text-right font-mono">{a.impressions?.toLocaleString("tr-TR")}</td>
                                  <td className="py-1.5 px-3 text-sm text-right font-mono">%{a.ctr}</td>
                                </tr>
                              );
                            })}
                          </tbody>
                        </table>
                      </div>
                    </CardContent>
                  </Card>
                );
              })}
            </div>
          )}

          {/* ===== COMPETITION ===== */}
          {cat === "competition" && comp.length > 0 && (
            <div className="space-y-4">
              <Card className="border"><CardHeader className="pb-1 pt-3 px-4"><CardTitle className="text-sm font-semibold">Kampanya Gosterim Payi</CardTitle></CardHeader>
                <CardContent className="px-4 pb-4">
                  <ResponsiveContainer width="100%" height={250}>
                    <BarChart data={compChart}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                      <XAxis dataKey="name" tick={{ fontSize: 10 }} />
                      <YAxis domain={[0, 100]} tick={{ fontSize: 10 }} unit="%" />
                      <Tooltip content={<CustomTooltip />} />
                      <Legend wrapperStyle={{ fontSize: 11 }} />
                      <Bar dataKey="Gosterim Payi" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                      <Bar dataKey="Rank Kaybi" fill="#ef4444" radius={[4, 4, 0, 0]} />
                      <Bar dataKey="Butce Kaybi" fill="#f59e0b" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </CardContent>
              </Card>

              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                {comp.map((c, i) => (
                  <Card key={i} className="border">
                    <CardContent className="p-4">
                      <p className="text-sm font-semibold text-slate-900 truncate mb-3">{c.campaign}</p>
                      <div className="space-y-2">
                        <div><div className="flex justify-between text-xs mb-0.5"><span className="text-blue-600">Gosterim Payi</span><span className="font-bold">{c.impression_share}%</span></div>
                          <div className="w-full bg-slate-100 rounded-full h-2"><div className="h-2 rounded-full bg-blue-500 transition-all" style={{ width: `${Math.min(c.impression_share, 100)}%` }} /></div></div>
                        <div className="flex justify-between text-xs"><span className="text-red-500">Rank Kaybi</span><span className="font-bold text-red-600">{c.lost_is_rank}%</span></div>
                        <div className="flex justify-between text-xs"><span className="text-amber-500">Butce Kaybi</span><span className="font-bold text-amber-600">{c.lost_is_budget}%</span></div>
                        <div className="flex justify-between text-xs pt-2 border-t"><span>ROAS</span><RoasColor v={c.roas} /></div>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </div>
          )}

          {/* ===== SEO ===== */}
          {cat === "seo" && (
            <div className="space-y-4">
              {gscPages.length > 0 && (
                <Card className="border"><CardHeader className="pb-1 pt-3 px-4"><CardTitle className="text-sm font-semibold">Sayfa Bazli Organik Performans</CardTitle></CardHeader>
                  <CardContent className="px-4 pb-4">
                    <ResponsiveContainer width="100%" height={220}>
                      <BarChart data={gscPages.slice(0, 10).map(p => ({ name: p.page.replace("https://arigastro.com", "").substring(0, 25) || "/", Tiklama: p.clicks, Pozisyon: p.position }))}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                        <XAxis dataKey="name" tick={{ fontSize: 9 }} angle={-15} textAnchor="end" height={50} />
                        <YAxis yAxisId="c" tick={{ fontSize: 10 }} />
                        <YAxis yAxisId="p" orientation="right" reversed tick={{ fontSize: 10 }} />
                        <Tooltip content={<CustomTooltip />} />
                        <Bar yAxisId="c" dataKey="Tiklama" fill="#10b981" radius={[4, 4, 0, 0]} />
                        <Area yAxisId="p" type="monotone" dataKey="Pozisyon" stroke="#ef4444" fill="#ef444420" />
                      </BarChart>
                    </ResponsiveContainer>
                  </CardContent>
                </Card>
              )}

              {landingPages.length > 0 && (
                <Card className="border"><CardHeader className="pb-1 pt-3 px-4"><CardTitle className="text-sm font-semibold flex items-center gap-2"><TrendingUp className="h-4 w-4 text-amber-500" />Acilis Sayfasi Performansi (GA4)</CardTitle></CardHeader>
                  <CardContent className="px-0 pb-0">
                    <div className="overflow-x-auto">
                      <table className="w-full text-left">
                        <thead><tr className="border-b bg-slate-50/50">
                          <th className="py-2 px-4 text-[10px] text-slate-500">Sayfa</th>
                          <th className="py-2 px-3 text-[10px] text-right">Oturum</th>
                          <th className="py-2 px-3 text-[10px] text-right">Hemen Cikma</th>
                          <th className="py-2 px-3 text-[10px] text-right">Satis</th>
                          <th className="py-2 px-3 text-[10px] text-right">Gelir</th>
                        </tr></thead>
                        <tbody>
                          {landingPages.slice(0, 15).map((p, i) => (
                            <tr key={i} className={`border-b border-slate-50 ${p.bounce_rate > 60 ? "bg-red-50/20" : ""}`}>
                              <td className="py-1.5 px-4 text-sm text-slate-800 max-w-xs truncate">{p.page}</td>
                              <td className="py-1.5 px-3 text-sm text-right font-mono">{p.sessions?.toLocaleString("tr-TR")}</td>
                              <td className="py-1.5 px-3 text-sm text-right font-mono"><span className={p.bounce_rate > 60 ? "text-red-500 font-bold" : ""}>{p.bounce_rate}%</span></td>
                              <td className="py-1.5 px-3 text-sm text-right font-mono">{p.purchases}</td>
                              <td className="py-1.5 px-3 text-sm text-right font-mono">{p.revenue?.toLocaleString("tr-TR", { minimumFractionDigits: 0 })} TL</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </CardContent>
                </Card>
              )}
            </div>
          )}

          {/* ===== TIME & DEVICE ===== */}
          {cat === "time_device" && (
            <div className="space-y-4">
              {/* Device Pie + ROAS */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                {devices.length > 0 && (
                  <Card className="border"><CardHeader className="pb-1 pt-3 px-4"><CardTitle className="text-sm font-semibold">Cihaz Harcama Dagilimi</CardTitle></CardHeader>
                    <CardContent className="px-4 pb-4">
                      <ResponsiveContainer width="100%" height={200}>
                        <PieChart>
                          <Pie data={deviceChart} dataKey="Harcama" nameKey="name" cx="50%" cy="50%" outerRadius={70} label={({ name, percent }) => `${name} %${(percent * 100).toFixed(0)}`}>
                            {deviceChart.map((_, i) => <Cell key={i} fill={COLORS[i]} />)}
                          </Pie>
                          <Tooltip />
                        </PieChart>
                      </ResponsiveContainer>
                      <div className="grid grid-cols-3 gap-2 mt-2">
                        {devices.map((d, i) => (
                          <div key={i} className="text-center p-2 rounded-lg bg-slate-50 border">
                            <p className="text-xs text-slate-500">{d.device === "MOBILE" ? "Mobil" : d.device === "DESKTOP" ? "Masaustu" : "Tablet"}</p>
                            <p className="text-lg font-bold"><RoasColor v={d.roas} /></p>
                            <p className="text-[10px] text-slate-400">{d.cost.toLocaleString("tr-TR")} TL</p>
                          </div>
                        ))}
                      </div>
                    </CardContent>
                  </Card>
                )}

                {/* Hourly Area Chart */}
                {hourly.length > 0 && (
                  <Card className="border"><CardHeader className="pb-1 pt-3 px-4"><CardTitle className="text-sm font-semibold">Saatlik ROAS Egisi</CardTitle></CardHeader>
                    <CardContent className="px-4 pb-4">
                      <ResponsiveContainer width="100%" height={220}>
                        <AreaChart data={hourlyChart}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                          <XAxis dataKey="saat" tick={{ fontSize: 9 }} interval={2} />
                          <YAxis tick={{ fontSize: 10 }} />
                          <Tooltip content={<CustomTooltip />} />
                          <Area type="monotone" dataKey="ROAS" stroke="#3b82f6" fill="#3b82f620" strokeWidth={2} />
                          <Area type="monotone" dataKey="Harcama" stroke="#f59e0b" fill="#f59e0b15" strokeWidth={1.5} />
                        </AreaChart>
                      </ResponsiveContainer>
                    </CardContent>
                  </Card>
                )}
              </div>

              {/* Hourly detail table */}
              {hourly.length > 0 && (
                <Card className="border"><CardHeader className="pb-1 pt-3 px-4"><CardTitle className="text-sm font-semibold">Saatlik Detay</CardTitle></CardHeader>
                  <CardContent className="px-0 pb-0">
                    <div className="overflow-x-auto">
                      <table className="w-full text-left">
                        <thead><tr className="border-b bg-slate-50/50">
                          <th className="py-1.5 px-4 text-[10px]">Saat</th>
                          <th className="py-1.5 px-3 text-[10px] text-right">Harcama</th>
                          <th className="py-1.5 px-3 text-[10px] text-right">Tiklama</th>
                          <th className="py-1.5 px-3 text-[10px] text-right">Donusum</th>
                          <th className="py-1.5 px-3 text-[10px] text-right">ROAS</th>
                        </tr></thead>
                        <tbody>
                          {hourly.map((h, i) => (
                            <tr key={i} className={`border-b border-slate-50 ${h.roas >= 5 ? "bg-emerald-50/20" : h.roas < 1 && h.cost > 200 ? "bg-red-50/20" : ""}`}>
                              <td className="py-1 px-4 text-sm font-mono">{String(h.hour).padStart(2, "0")}:00</td>
                              <td className="py-1 px-3 text-sm text-right font-mono">{h.cost.toFixed(0)} TL</td>
                              <td className="py-1 px-3 text-sm text-right font-mono">{h.clicks || 0}</td>
                              <td className="py-1 px-3 text-sm text-right font-mono">{h.conversions}</td>
                              <td className="py-1 px-3 text-sm text-right"><RoasColor v={h.roas} /></td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </CardContent>
                </Card>
              )}
            </div>
          )}

          {/* ===== STRATEGY ===== */}
          {cat === "strategy" && !showAI && (
            <Card className="border bg-gradient-to-r from-slate-50 to-amber-50/20">
              <CardContent className="py-12 text-center">
                <Target className="h-10 w-10 mx-auto mb-3 text-amber-500" />
                <p className="text-base font-semibold text-slate-900">Kapsamli Strateji Raporu</p>
                <p className="text-sm text-slate-500 mt-1 mb-4">Google Ads, GA4 ve Search Console verilerini analiz eden AI stratejik rapor</p>
                <Button onClick={generateReport} disabled={generating} className="bg-slate-900 hover:bg-slate-800 text-white" data-testid="strategy-btn">
                  <Brain className="h-4 w-4 mr-2" /> Strateji Raporu Olustur
                </Button>
              </CardContent>
            </Card>
          )}

          {/* ===== AI INSIGHTS PANEL ===== */}
          {showAI && (
            <Card className="border border-amber-200" data-testid="ai-insights-card">
              <CardHeader className="pb-1 pt-3 px-4">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-sm font-semibold text-amber-800 flex items-center gap-2">
                    <Lightbulb className="h-4 w-4" /> AI Icgoruler — {catInfo?.label}
                  </CardTitle>
                  <Button variant="ghost" size="sm" className="h-7 text-xs" onClick={() => setShowAI(false)}>
                    <ChevronUp className="h-3 w-3 mr-1" /> Gizle
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="px-4 pb-4">
                {generating ? (
                  <div className="py-8 text-center">
                    <Brain className="h-8 w-8 mx-auto mb-2 text-amber-500 animate-pulse" />
                    <p className="text-sm text-slate-500">Veriler analiz ediliyor...</p>
                  </div>
                ) : report ? (
                  <div className="prose prose-sm prose-slate max-w-none" data-testid="ai-report-content">
                    <ReactMarkdown components={{
                      h3: ({ children }) => <h3 className="text-sm font-bold text-slate-900 mt-4 mb-2 pb-1 border-b border-slate-100">{children}</h3>,
                      h2: ({ children }) => <h2 className="text-base font-bold text-slate-900 mt-5 mb-2">{children}</h2>,
                      strong: ({ children }) => <strong className="font-semibold text-slate-800">{children}</strong>,
                      li: ({ children }) => <li className="text-sm text-slate-700 leading-relaxed my-0.5">{children}</li>,
                      p: ({ children }) => <p className="text-sm text-slate-700 leading-relaxed my-1.5">{children}</p>,
                    }}>{report}</ReactMarkdown>
                  </div>
                ) : null}
              </CardContent>
            </Card>
          )}
        </>
      )}
    </div>
  );
}
