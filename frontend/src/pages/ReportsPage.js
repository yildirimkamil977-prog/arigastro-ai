import { useState, useEffect, useCallback } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { toast } from "sonner";
import {
  Search, BarChart3, Brain, RefreshCw, Target, Shield, Globe,
  Clock, Monitor, Smartphone, Tablet, AlertTriangle, TrendingUp,
  TrendingDown, Lightbulb, FileText, History, ChevronDown, ChevronUp,
  Zap, Award, XCircle, CheckCircle2, MinusCircle
} from "lucide-react";
import ReactMarkdown from "react-markdown";

const API = process.env.REACT_APP_BACKEND_URL;

const CATEGORIES = [
  { id: "search_terms", label: "Arama Terimleri & Anahtar Kelimeler", icon: Search, color: "text-blue-600", description: "Kalite puani, butce israfi, karli terimler" },
  { id: "ad_performance", label: "Reklam Performansi", icon: BarChart3, color: "text-amber-600", description: "Kampanya analizi, ROAS, butce optimizasyonu" },
  { id: "ad_assets", label: "Reklam Ogeleri", icon: FileText, color: "text-violet-600", description: "Baslik, aciklama, uzanti performansi" },
  { id: "competition", label: "Rekabet Analizi", icon: Shield, color: "text-red-600", description: "Gosterim payi, rakip pozisyonu" },
  { id: "seo", label: "SEO & Organik", icon: Globe, color: "text-emerald-600", description: "Search Console, organik firsatlar" },
  { id: "time_device", label: "Zaman & Cihaz", icon: Clock, color: "text-cyan-600", description: "Saat/cihaz bazli performans" },
  { id: "strategy", label: "Strateji Raporu", icon: Target, color: "text-slate-800", description: "Kapsamli strateji ve aksiyon plani" },
];

function QualityBadge({ value, type }) {
  if (!value) return <span className="text-xs text-slate-400">—</span>;
  const map = {
    "ABOVE_AVERAGE": { color: "bg-emerald-100 text-emerald-700", label: "Ort. Ustu" },
    "AVERAGE": { color: "bg-amber-100 text-amber-700", label: "Ortalama" },
    "BELOW_AVERAGE": { color: "bg-red-100 text-red-700", label: "Ort. Alti" },
  };
  const style = map[value] || { color: "bg-slate-100 text-slate-600", label: value };
  return <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded ${style.color}`}>{style.label}</span>;
}

function QSScore({ score }) {
  if (!score && score !== 0) return <span className="text-xs text-slate-400">—</span>;
  const color = score >= 7 ? "text-emerald-600 bg-emerald-50" : score >= 4 ? "text-amber-600 bg-amber-50" : "text-red-600 bg-red-50";
  return <span className={`text-sm font-bold px-2 py-0.5 rounded ${color}`}>{score}/10</span>;
}

function RoasBadge({ value }) {
  const color = value >= 5 ? "text-emerald-600" : value >= 2 ? "text-amber-600" : value > 0 ? "text-red-500" : "text-slate-400";
  return <span className={`font-bold ${color}`}>{value}x</span>;
}

function DeviceIcon({ device }) {
  if (device === "MOBILE") return <Smartphone className="h-4 w-4" />;
  if (device === "TABLET") return <Tablet className="h-4 w-4" />;
  return <Monitor className="h-4 w-4" />;
}

export default function ReportsPage() {
  const [activeCategory, setActiveCategory] = useState("search_terms");
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [report, setReport] = useState(null);
  const [data, setData] = useState({});
  const [showData, setShowData] = useState(true);
  const [pastReports, setPastReports] = useState([]);
  const [showHistory, setShowHistory] = useState(false);

  const fetchData = useCallback(async (cat) => {
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
        strategy: [],
      };
      const urls = endpoints[cat] || [];
      const results = await Promise.all(
        urls.map(url => fetch(`${API}${url}`, { credentials: "include" }).then(r => r.json()).catch(() => []))
      );
      const dataMap = {};
      urls.forEach((url, i) => {
        const key = url.split("/").pop();
        dataMap[key] = Array.isArray(results[i]) ? results[i].filter(x => !x.error) : results[i];
      });
      setData(dataMap);
    } catch (e) {
      toast.error("Veri alinamadi");
    } finally {
      setLoading(false);
    }
  }, []);

  const generateReport = async () => {
    setGenerating(true);
    setReport(null);
    try {
      const res = await fetch(`${API}/api/reports/ai-report`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ category: activeCategory }),
      });
      if (!res.ok) { const err = await res.json(); throw new Error(err.detail); }
      const d = await res.json();
      setReport(d.report);
      toast.success("AI raporu olusturuldu!");
    } catch (e) {
      toast.error("Rapor olusturulamadi: " + e.message);
    } finally {
      setGenerating(false);
    }
  };

  const loadHistory = async () => {
    try {
      const res = await fetch(`${API}/api/reports/history?category=${activeCategory}&limit=5`, { credentials: "include" });
      const d = await res.json();
      setPastReports(d);
    } catch { /* ignore */ }
  };

  useEffect(() => {
    fetchData(activeCategory);
    setReport(null);
    setShowHistory(false);
  }, [activeCategory, fetchData]);

  const searchTerms = data["search-terms"] || [];
  const qualityScores = data["quality-scores"] || [];
  const competition = data["competition"] || [];
  const devices = data["device-performance"] || [];
  const hourly = data["hourly-performance"] || [];
  const adAssets = data["ad-assets"] || [];
  const gscPages = data["gsc-pages"] || [];
  const landingPages = data["landing-pages"] || [];

  // Derived insights
  const wastedTerms = searchTerms.filter(t => t.clicks >= 3 && t.conversions === 0);
  const profitableTerms = searchTerms.filter(t => t.roas >= 3 && t.conversions > 0);
  const lowQSKeywords = qualityScores.filter(k => k.quality_score && k.quality_score < 5);
  const highQSKeywords = qualityScores.filter(k => k.quality_score && k.quality_score >= 7);

  const catInfo = CATEGORIES.find(c => c.id === activeCategory);

  return (
    <div className="space-y-5" data-testid="reports-page">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h2 className="text-xl font-bold text-slate-900 tracking-tight">Analiz & Rapor</h2>
          <p className="text-sm text-slate-500 mt-0.5">Profesyonel dijital pazarlama raporlari ve AI analizler</p>
        </div>
      </div>

      {/* Category Tabs */}
      <div className="flex gap-1.5 overflow-x-auto pb-1" data-testid="report-categories">
        {CATEGORIES.map(cat => (
          <button
            key={cat.id}
            onClick={() => setActiveCategory(cat.id)}
            data-testid={`report-tab-${cat.id}`}
            className={`flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium whitespace-nowrap border transition-all
              ${activeCategory === cat.id
                ? "bg-slate-900 text-white border-slate-900 shadow-sm"
                : "bg-white text-slate-600 border-slate-200 hover:border-slate-300 hover:bg-slate-50"}`}
          >
            <cat.icon className="h-3.5 w-3.5" />
            {cat.label}
          </button>
        ))}
      </div>

      {/* Category Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {catInfo && <catInfo.icon className={`h-5 w-5 ${catInfo.color}`} />}
          <div>
            <h3 className="text-base font-semibold text-slate-900">{catInfo?.label}</h3>
            <p className="text-xs text-slate-500">{catInfo?.description}</p>
          </div>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" className="h-8 text-xs" onClick={() => { setShowHistory(!showHistory); if (!showHistory) loadHistory(); }} data-testid="report-history-btn">
            <History className="h-3 w-3 mr-1" /> Gecmis
          </Button>
          <Button variant="outline" size="sm" className="h-8 text-xs" onClick={() => fetchData(activeCategory)} disabled={loading} data-testid="refresh-data-btn">
            <RefreshCw className={`h-3 w-3 mr-1 ${loading ? "animate-spin" : ""}`} /> Veri Yenile
          </Button>
          <Button size="sm" className="h-8 text-xs bg-slate-900 hover:bg-slate-800 text-white" onClick={generateReport} disabled={generating} data-testid="generate-report-btn">
            <Brain className={`h-3.5 w-3.5 mr-1.5 ${generating ? "animate-pulse" : ""}`} />
            {generating ? "Rapor Olusturuluyor..." : "AI Rapor Olustur"}
          </Button>
        </div>
      </div>

      {/* Past Reports */}
      {showHistory && pastReports.length > 0 && (
        <Card className="border border-slate-200">
          <CardContent className="p-3 space-y-2">
            {pastReports.map((r, i) => (
              <div key={i} className="flex items-center justify-between p-2 rounded-lg border border-slate-100 hover:bg-slate-50 cursor-pointer" onClick={() => { setReport(r.report); setShowHistory(false); }}>
                <div className="flex items-center gap-2">
                  <Brain className="h-3.5 w-3.5 text-amber-500" />
                  <span className="text-sm text-slate-700">{CATEGORIES.find(c => c.id === r.category)?.label}</span>
                </div>
                <span className="text-xs text-slate-400">{new Date(r.created_at).toLocaleDateString("tr-TR")} {new Date(r.created_at).toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" })}</span>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {loading ? (
        <div className="flex items-center justify-center py-16">
          <RefreshCw className="h-6 w-6 text-slate-400 animate-spin" />
          <span className="ml-2 text-sm text-slate-500">Veriler yukleniyor...</span>
        </div>
      ) : (
        <>
          {/* DATA PANELS — Category Specific */}
          <div className="flex items-center justify-between">
            <button onClick={() => setShowData(!showData)} className="flex items-center gap-1 text-xs font-medium text-slate-500 hover:text-slate-700">
              {showData ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
              {showData ? "Veri Panellerini Gizle" : "Veri Panellerini Goster"}
            </button>
          </div>

          {showData && (
            <>
              {/* SEARCH TERMS & KEYWORDS */}
              {activeCategory === "search_terms" && (
                <div className="space-y-4">
                  {/* Summary Cards */}
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                    <Card className="border border-slate-200"><CardContent className="p-3">
                      <p className="text-xs text-slate-500">Toplam Terim</p>
                      <p className="text-xl font-bold text-slate-900">{searchTerms.length}</p>
                    </CardContent></Card>
                    <Card className="border border-red-200 bg-red-50/30"><CardContent className="p-3">
                      <p className="text-xs text-red-600 flex items-center gap-1"><XCircle className="h-3 w-3" /> Butce Israfi</p>
                      <p className="text-xl font-bold text-red-700">{wastedTerms.length} terim</p>
                      <p className="text-xs text-red-500">{wastedTerms.reduce((s, t) => s + t.cost, 0).toLocaleString("tr-TR", { minimumFractionDigits: 0 })} TL</p>
                    </CardContent></Card>
                    <Card className="border border-emerald-200 bg-emerald-50/30"><CardContent className="p-3">
                      <p className="text-xs text-emerald-600 flex items-center gap-1"><CheckCircle2 className="h-3 w-3" /> Karli Terimler</p>
                      <p className="text-xl font-bold text-emerald-700">{profitableTerms.length}</p>
                    </CardContent></Card>
                    <Card className="border border-amber-200 bg-amber-50/30"><CardContent className="p-3">
                      <p className="text-xs text-amber-600 flex items-center gap-1"><AlertTriangle className="h-3 w-3" /> Dusuk Kalite</p>
                      <p className="text-xl font-bold text-amber-700">{lowQSKeywords.length} / {qualityScores.length}</p>
                    </CardContent></Card>
                  </div>

                  {/* Budget Wasters */}
                  {wastedTerms.length > 0 && (
                    <Card className="border border-red-200">
                      <CardHeader className="pb-2 pt-3 px-4">
                        <CardTitle className="text-sm font-semibold text-red-700 flex items-center gap-2">
                          <XCircle className="h-4 w-4" /> Butce Israfi Yapan Terimler (Tiklama Var, Donusum Yok)
                        </CardTitle>
                      </CardHeader>
                      <CardContent className="px-0 pb-0">
                        <div className="overflow-x-auto">
                          <table className="w-full text-left" data-testid="wasted-terms-table">
                            <thead><tr className="border-b border-red-100 bg-red-50/50">
                              <th className="py-2 px-4 text-[10px] font-semibold text-red-600 uppercase">Arama Terimi</th>
                              <th className="py-2 px-3 text-[10px] font-semibold text-red-600 uppercase">Kampanya</th>
                              <th className="py-2 px-3 text-[10px] font-semibold text-red-600 uppercase text-right">Tiklama</th>
                              <th className="py-2 px-3 text-[10px] font-semibold text-red-600 uppercase text-right">Harcama</th>
                              <th className="py-2 px-3 text-[10px] font-semibold text-red-600 uppercase text-right">Durum</th>
                            </tr></thead>
                            <tbody>
                              {wastedTerms.slice(0, 20).map((t, i) => (
                                <tr key={i} className="border-b border-red-50 hover:bg-red-50/30">
                                  <td className="py-2 px-4 text-sm font-medium text-slate-900">"{t.term}"</td>
                                  <td className="py-2 px-3 text-xs text-slate-500">{t.campaign}</td>
                                  <td className="py-2 px-3 text-sm text-right font-mono">{t.clicks}</td>
                                  <td className="py-2 px-3 text-sm text-right font-mono text-red-600">{t.cost.toLocaleString("tr-TR", { minimumFractionDigits: 2 })} TL</td>
                                  <td className="py-2 px-3 text-right"><span className="text-[10px] bg-red-100 text-red-700 px-1.5 py-0.5 rounded">{t.status === "NONE" ? "Negatif Onerisi" : t.status}</span></td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </CardContent>
                    </Card>
                  )}

                  {/* Quality Scores */}
                  {qualityScores.length > 0 && (
                    <Card className="border border-slate-200">
                      <CardHeader className="pb-2 pt-3 px-4">
                        <CardTitle className="text-sm font-semibold text-slate-900 flex items-center gap-2">
                          <Award className="h-4 w-4 text-amber-500" /> Anahtar Kelime Kalite Puanlari
                        </CardTitle>
                      </CardHeader>
                      <CardContent className="px-0 pb-0">
                        <div className="overflow-x-auto">
                          <table className="w-full text-left" data-testid="quality-scores-table">
                            <thead><tr className="border-b border-slate-200 bg-slate-50/50">
                              <th className="py-2 px-4 text-[10px] font-semibold text-slate-500 uppercase">Anahtar Kelime</th>
                              <th className="py-2 px-3 text-[10px] font-semibold text-slate-500 uppercase text-center">KP</th>
                              <th className="py-2 px-3 text-[10px] font-semibold text-slate-500 uppercase text-center">Beklenen TO</th>
                              <th className="py-2 px-3 text-[10px] font-semibold text-slate-500 uppercase text-center">Reklam Uyumu</th>
                              <th className="py-2 px-3 text-[10px] font-semibold text-slate-500 uppercase text-center">Sayfa Kalitesi</th>
                              <th className="py-2 px-3 text-[10px] font-semibold text-slate-500 uppercase text-right">Harcama</th>
                              <th className="py-2 px-3 text-[10px] font-semibold text-slate-500 uppercase text-right">ROAS</th>
                            </tr></thead>
                            <tbody>
                              {qualityScores.slice(0, 30).map((k, i) => (
                                <tr key={i} className={`border-b border-slate-100 hover:bg-slate-50/50 ${k.quality_score && k.quality_score < 5 ? "bg-red-50/20" : ""}`}>
                                  <td className="py-2 px-4"><span className="text-sm font-medium text-slate-900">{k.keyword}</span><span className="ml-1.5 text-[10px] text-slate-400">{k.match_type}</span></td>
                                  <td className="py-2 px-3 text-center"><QSScore score={k.quality_score} /></td>
                                  <td className="py-2 px-3 text-center"><QualityBadge value={k.expected_ctr} /></td>
                                  <td className="py-2 px-3 text-center"><QualityBadge value={k.creative_quality} /></td>
                                  <td className="py-2 px-3 text-center"><QualityBadge value={k.landing_page_quality} /></td>
                                  <td className="py-2 px-3 text-sm text-right font-mono">{k.cost.toLocaleString("tr-TR", { minimumFractionDigits: 0 })} TL</td>
                                  <td className="py-2 px-3 text-sm text-right"><RoasBadge value={k.roas} /></td>
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

              {/* AD PERFORMANCE */}
              {activeCategory === "ad_performance" && (
                <div className="space-y-4">
                  {/* Competition / Impression Share */}
                  {competition.length > 0 && (
                    <Card className="border border-slate-200">
                      <CardHeader className="pb-2 pt-3 px-4">
                        <CardTitle className="text-sm font-semibold text-slate-900">Kampanya Gosterim Payi & Rekabet</CardTitle>
                      </CardHeader>
                      <CardContent className="px-0 pb-0">
                        <div className="overflow-x-auto">
                          <table className="w-full text-left" data-testid="competition-table">
                            <thead><tr className="border-b border-slate-200 bg-slate-50/50">
                              <th className="py-2 px-4 text-[10px] font-semibold text-slate-500 uppercase">Kampanya</th>
                              <th className="py-2 px-3 text-[10px] font-semibold text-slate-500 uppercase text-right">Gosterim Payi</th>
                              <th className="py-2 px-3 text-[10px] font-semibold text-slate-500 uppercase text-right">Rank Kaybi</th>
                              <th className="py-2 px-3 text-[10px] font-semibold text-slate-500 uppercase text-right">Butce Kaybi</th>
                              <th className="py-2 px-3 text-[10px] font-semibold text-slate-500 uppercase text-right">Harcama</th>
                              <th className="py-2 px-3 text-[10px] font-semibold text-slate-500 uppercase text-right">ROAS</th>
                            </tr></thead>
                            <tbody>
                              {competition.map((c, i) => (
                                <tr key={i} className="border-b border-slate-100 hover:bg-slate-50/50">
                                  <td className="py-2 px-4 text-sm font-medium text-slate-900">{c.campaign}</td>
                                  <td className="py-2 px-3 text-right">
                                    <div className="flex items-center justify-end gap-2">
                                      <div className="w-16 bg-slate-100 rounded-full h-1.5"><div className="h-1.5 rounded-full bg-blue-500" style={{ width: `${Math.min(c.impression_share, 100)}%` }} /></div>
                                      <span className="text-sm font-mono font-medium">{c.impression_share}%</span>
                                    </div>
                                  </td>
                                  <td className="py-2 px-3 text-sm text-right font-mono text-red-500">{c.lost_is_rank}%</td>
                                  <td className="py-2 px-3 text-sm text-right font-mono text-amber-600">{c.lost_is_budget}%</td>
                                  <td className="py-2 px-3 text-sm text-right font-mono">{c.cost.toLocaleString("tr-TR", { minimumFractionDigits: 0 })} TL</td>
                                  <td className="py-2 px-3 text-sm text-right"><RoasBadge value={c.roas} /></td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </CardContent>
                    </Card>
                  )}

                  {/* Device + Hourly side by side */}
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                    {devices.length > 0 && (
                      <Card className="border border-slate-200">
                        <CardHeader className="pb-2 pt-3 px-4"><CardTitle className="text-sm font-semibold text-slate-900">Cihaz Performansi</CardTitle></CardHeader>
                        <CardContent className="px-4 pb-4 space-y-3">
                          {devices.map((d, i) => (
                            <div key={i} className="flex items-center justify-between p-3 rounded-lg border border-slate-100 bg-slate-50/30">
                              <div className="flex items-center gap-3">
                                <DeviceIcon device={d.device} />
                                <div>
                                  <p className="text-sm font-medium text-slate-900">{d.device === "MOBILE" ? "Mobil" : d.device === "DESKTOP" ? "Masaustu" : "Tablet"}</p>
                                  <p className="text-xs text-slate-500">{d.clicks.toLocaleString("tr-TR")} tiklama</p>
                                </div>
                              </div>
                              <div className="text-right">
                                <p className="text-sm font-mono">{d.cost.toLocaleString("tr-TR", { minimumFractionDigits: 0 })} TL</p>
                                <p className="text-xs"><RoasBadge value={d.roas} /></p>
                              </div>
                            </div>
                          ))}
                        </CardContent>
                      </Card>
                    )}

                    {hourly.length > 0 && (
                      <Card className="border border-slate-200">
                        <CardHeader className="pb-2 pt-3 px-4"><CardTitle className="text-sm font-semibold text-slate-900">Saat Bazli Performans (ROAS)</CardTitle></CardHeader>
                        <CardContent className="px-4 pb-4">
                          <div className="flex items-end gap-0.5 h-32">
                            {hourly.map((h, i) => {
                              const maxCost = Math.max(...hourly.map(x => x.cost));
                              const height = maxCost > 0 ? (h.cost / maxCost) * 100 : 0;
                              const color = h.roas >= 5 ? "bg-emerald-400" : h.roas >= 2 ? "bg-amber-400" : h.roas > 0 ? "bg-red-400" : "bg-slate-200";
                              return (
                                <div key={i} className="flex-1 flex flex-col items-center gap-0.5 group relative">
                                  <div className={`w-full rounded-t ${color} transition-all`} style={{ height: `${Math.max(height, 2)}%` }} />
                                  <span className="text-[8px] text-slate-400">{String(h.hour).padStart(2, "0")}</span>
                                  <div className="absolute bottom-full mb-1 hidden group-hover:block bg-slate-900 text-white text-[10px] px-2 py-1 rounded whitespace-nowrap z-10">
                                    {h.hour}:00 | {h.cost.toFixed(0)} TL | ROAS {h.roas}
                                  </div>
                                </div>
                              );
                            })}
                          </div>
                          <div className="flex items-center gap-4 mt-2 text-[10px] text-slate-500">
                            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded bg-emerald-400" /> ROAS 5+</span>
                            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded bg-amber-400" /> ROAS 2-5</span>
                            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded bg-red-400" /> ROAS 0-2</span>
                          </div>
                        </CardContent>
                      </Card>
                    )}
                  </div>
                </div>
              )}

              {/* AD ASSETS */}
              {activeCategory === "ad_assets" && adAssets.length > 0 && (
                <div className="space-y-4">
                  {["HEADLINE", "DESCRIPTION"].map(fieldType => {
                    const filtered = adAssets.filter(a => a.field_type === fieldType);
                    if (filtered.length === 0) return null;
                    return (
                      <Card key={fieldType} className="border border-slate-200">
                        <CardHeader className="pb-2 pt-3 px-4">
                          <CardTitle className="text-sm font-semibold text-slate-900">{fieldType === "HEADLINE" ? "Baslik" : "Aciklama"} Performansi ({filtered.length})</CardTitle>
                        </CardHeader>
                        <CardContent className="px-0 pb-0">
                          <div className="overflow-x-auto">
                            <table className="w-full text-left">
                              <thead><tr className="border-b border-slate-200 bg-slate-50/50">
                                <th className="py-2 px-4 text-[10px] font-semibold text-slate-500 uppercase">Metin</th>
                                <th className="py-2 px-3 text-[10px] font-semibold text-slate-500 uppercase text-center">Performans</th>
                                <th className="py-2 px-3 text-[10px] font-semibold text-slate-500 uppercase text-right">Gosterim</th>
                                <th className="py-2 px-3 text-[10px] font-semibold text-slate-500 uppercase text-right">Tiklama</th>
                                <th className="py-2 px-3 text-[10px] font-semibold text-slate-500 uppercase text-right">TO</th>
                              </tr></thead>
                              <tbody>
                                {filtered.slice(0, 20).map((a, i) => {
                                  const perfColors = { BEST: "bg-emerald-100 text-emerald-700", GOOD: "bg-blue-100 text-blue-700", LOW: "bg-red-100 text-red-700" };
                                  const perfColor = perfColors[a.performance_label] || "bg-slate-100 text-slate-500";
                                  return (
                                    <tr key={i} className="border-b border-slate-100 hover:bg-slate-50/50">
                                      <td className="py-2 px-4 text-sm text-slate-900 max-w-xs truncate">{a.text || "—"}</td>
                                      <td className="py-2 px-3 text-center"><span className={`text-[10px] font-medium px-1.5 py-0.5 rounded ${perfColor}`}>{a.performance_label || "N/A"}</span></td>
                                      <td className="py-2 px-3 text-sm text-right font-mono">{a.impressions?.toLocaleString("tr-TR")}</td>
                                      <td className="py-2 px-3 text-sm text-right font-mono">{a.clicks}</td>
                                      <td className="py-2 px-3 text-sm text-right font-mono">%{a.ctr}</td>
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

              {/* COMPETITION */}
              {activeCategory === "competition" && competition.length > 0 && (
                <div className="space-y-4">
                  {/* IS Overview Cards */}
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                    {competition.map((c, i) => (
                      <Card key={i} className="border border-slate-200">
                        <CardContent className="p-4">
                          <p className="text-xs font-medium text-slate-500 truncate">{c.campaign}</p>
                          <div className="mt-2 space-y-2">
                            <div>
                              <div className="flex justify-between text-xs mb-0.5"><span className="text-slate-500">Gosterim Payi</span><span className="font-medium">{c.impression_share}%</span></div>
                              <div className="w-full bg-slate-100 rounded-full h-2"><div className="h-2 rounded-full bg-blue-500" style={{ width: `${Math.min(c.impression_share, 100)}%` }} /></div>
                            </div>
                            <div className="flex justify-between text-xs"><span className="text-red-500">Rank Kaybi</span><span className="font-medium text-red-600">{c.lost_is_rank}%</span></div>
                            <div className="flex justify-between text-xs"><span className="text-amber-500">Butce Kaybi</span><span className="font-medium text-amber-600">{c.lost_is_budget}%</span></div>
                            <div className="flex justify-between text-xs pt-1 border-t border-slate-100"><span>ROAS</span><RoasBadge value={c.roas} /></div>
                          </div>
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                </div>
              )}

              {/* SEO */}
              {activeCategory === "seo" && (
                <div className="space-y-4">
                  {gscPages.length > 0 && (
                    <Card className="border border-slate-200">
                      <CardHeader className="pb-2 pt-3 px-4"><CardTitle className="text-sm font-semibold text-slate-900">Sayfa Bazli Organik Performans</CardTitle></CardHeader>
                      <CardContent className="px-0 pb-0">
                        <div className="overflow-x-auto">
                          <table className="w-full text-left" data-testid="gsc-pages-table">
                            <thead><tr className="border-b border-slate-200 bg-slate-50/50">
                              <th className="py-2 px-4 text-[10px] font-semibold text-slate-500 uppercase">Sayfa</th>
                              <th className="py-2 px-3 text-[10px] font-semibold text-slate-500 uppercase text-right">Tiklama</th>
                              <th className="py-2 px-3 text-[10px] font-semibold text-slate-500 uppercase text-right">Gosterim</th>
                              <th className="py-2 px-3 text-[10px] font-semibold text-slate-500 uppercase text-right">CTR</th>
                              <th className="py-2 px-3 text-[10px] font-semibold text-slate-500 uppercase text-right">Pozisyon</th>
                            </tr></thead>
                            <tbody>
                              {gscPages.map((p, i) => (
                                <tr key={i} className="border-b border-slate-100 hover:bg-slate-50/50">
                                  <td className="py-2 px-4 text-sm text-blue-600 max-w-xs truncate">{p.page.replace("https://arigastro.com", "")}</td>
                                  <td className="py-2 px-3 text-sm text-right font-mono">{p.clicks}</td>
                                  <td className="py-2 px-3 text-sm text-right font-mono">{p.impressions?.toLocaleString("tr-TR")}</td>
                                  <td className="py-2 px-3 text-sm text-right font-mono">%{p.ctr}</td>
                                  <td className="py-2 px-3 text-sm text-right font-mono">{p.position}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </CardContent>
                    </Card>
                  )}
                  {landingPages.length > 0 && (
                    <Card className="border border-slate-200">
                      <CardHeader className="pb-2 pt-3 px-4"><CardTitle className="text-sm font-semibold text-slate-900">Acilis Sayfasi Performansi (GA4)</CardTitle></CardHeader>
                      <CardContent className="px-0 pb-0">
                        <div className="overflow-x-auto">
                          <table className="w-full text-left">
                            <thead><tr className="border-b border-slate-200 bg-slate-50/50">
                              <th className="py-2 px-4 text-[10px] font-semibold text-slate-500 uppercase">Sayfa</th>
                              <th className="py-2 px-3 text-[10px] font-semibold text-slate-500 uppercase text-right">Oturum</th>
                              <th className="py-2 px-3 text-[10px] font-semibold text-slate-500 uppercase text-right">Hemen Cikma</th>
                              <th className="py-2 px-3 text-[10px] font-semibold text-slate-500 uppercase text-right">Satis</th>
                              <th className="py-2 px-3 text-[10px] font-semibold text-slate-500 uppercase text-right">Gelir</th>
                            </tr></thead>
                            <tbody>
                              {landingPages.slice(0, 20).map((p, i) => (
                                <tr key={i} className="border-b border-slate-100 hover:bg-slate-50/50">
                                  <td className="py-2 px-4 text-sm text-slate-900 max-w-xs truncate">{p.page}</td>
                                  <td className="py-2 px-3 text-sm text-right font-mono">{p.sessions?.toLocaleString("tr-TR")}</td>
                                  <td className="py-2 px-3 text-sm text-right font-mono">%{p.bounce_rate}</td>
                                  <td className="py-2 px-3 text-sm text-right font-mono">{p.purchases}</td>
                                  <td className="py-2 px-3 text-sm text-right font-mono">{p.revenue?.toLocaleString("tr-TR", { minimumFractionDigits: 0 })} TL</td>
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

              {/* TIME & DEVICE */}
              {activeCategory === "time_device" && (
                <div className="space-y-4">
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                    {devices.length > 0 && (
                      <Card className="border border-slate-200">
                        <CardHeader className="pb-2 pt-3 px-4"><CardTitle className="text-sm font-semibold text-slate-900">Cihaz Karsilastirmasi</CardTitle></CardHeader>
                        <CardContent className="px-0 pb-0">
                          <table className="w-full text-left">
                            <thead><tr className="border-b border-slate-200 bg-slate-50/50">
                              <th className="py-2 px-4 text-[10px] font-semibold text-slate-500 uppercase">Cihaz</th>
                              <th className="py-2 px-3 text-[10px] font-semibold text-slate-500 uppercase text-right">Gosterim</th>
                              <th className="py-2 px-3 text-[10px] font-semibold text-slate-500 uppercase text-right">Tiklama</th>
                              <th className="py-2 px-3 text-[10px] font-semibold text-slate-500 uppercase text-right">Harcama</th>
                              <th className="py-2 px-3 text-[10px] font-semibold text-slate-500 uppercase text-right">Donusum</th>
                              <th className="py-2 px-3 text-[10px] font-semibold text-slate-500 uppercase text-right">ROAS</th>
                            </tr></thead>
                            <tbody>
                              {devices.map((d, i) => (
                                <tr key={i} className="border-b border-slate-100">
                                  <td className="py-2 px-4 text-sm font-medium text-slate-900 flex items-center gap-2"><DeviceIcon device={d.device} />{d.device === "MOBILE" ? "Mobil" : d.device === "DESKTOP" ? "Masaustu" : "Tablet"}</td>
                                  <td className="py-2 px-3 text-sm text-right font-mono">{d.impressions?.toLocaleString("tr-TR")}</td>
                                  <td className="py-2 px-3 text-sm text-right font-mono">{d.clicks?.toLocaleString("tr-TR")}</td>
                                  <td className="py-2 px-3 text-sm text-right font-mono">{d.cost?.toLocaleString("tr-TR", { minimumFractionDigits: 0 })} TL</td>
                                  <td className="py-2 px-3 text-sm text-right font-mono">{d.conversions}</td>
                                  <td className="py-2 px-3 text-sm text-right"><RoasBadge value={d.roas} /></td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </CardContent>
                      </Card>
                    )}

                    {hourly.length > 0 && (
                      <Card className="border border-slate-200">
                        <CardHeader className="pb-2 pt-3 px-4"><CardTitle className="text-sm font-semibold text-slate-900">Saatlik Detay</CardTitle></CardHeader>
                        <CardContent className="px-0 pb-0 max-h-80 overflow-y-auto">
                          <table className="w-full text-left">
                            <thead className="sticky top-0 bg-white"><tr className="border-b border-slate-200">
                              <th className="py-2 px-4 text-[10px] font-semibold text-slate-500">Saat</th>
                              <th className="py-2 px-3 text-[10px] font-semibold text-slate-500 text-right">Harcama</th>
                              <th className="py-2 px-3 text-[10px] font-semibold text-slate-500 text-right">Donusum</th>
                              <th className="py-2 px-3 text-[10px] font-semibold text-slate-500 text-right">ROAS</th>
                            </tr></thead>
                            <tbody>
                              {hourly.map((h, i) => (
                                <tr key={i} className={`border-b border-slate-50 ${h.roas >= 5 ? "bg-emerald-50/30" : h.roas < 1 && h.cost > 100 ? "bg-red-50/30" : ""}`}>
                                  <td className="py-1.5 px-4 text-sm font-mono">{String(h.hour).padStart(2, "0")}:00</td>
                                  <td className="py-1.5 px-3 text-sm text-right font-mono">{h.cost.toFixed(0)} TL</td>
                                  <td className="py-1.5 px-3 text-sm text-right font-mono">{h.conversions}</td>
                                  <td className="py-1.5 px-3 text-sm text-right"><RoasBadge value={h.roas} /></td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </CardContent>
                      </Card>
                    )}
                  </div>
                </div>
              )}

              {/* STRATEGY - no data panel, just AI report */}
              {activeCategory === "strategy" && !report && !generating && (
                <Card className="border border-slate-200 bg-gradient-to-r from-slate-50 to-amber-50/20">
                  <CardContent className="py-12 text-center">
                    <Target className="h-10 w-10 mx-auto mb-3 text-amber-500" />
                    <p className="text-base font-semibold text-slate-900">Kapsamli Strateji Raporu</p>
                    <p className="text-sm text-slate-500 mt-1 mb-4">Tum kanallari analiz eden, 1-3 aylik aksiyon plani iceren profesyonel rapor</p>
                    <Button onClick={generateReport} disabled={generating} className="bg-slate-900 hover:bg-slate-800 text-white" data-testid="strategy-report-btn">
                      <Brain className="h-4 w-4 mr-2" /> Strateji Raporu Olustur
                    </Button>
                  </CardContent>
                </Card>
              )}
            </>
          )}

          {/* AI REPORT */}
          {generating && (
            <Card className="border border-slate-200">
              <CardContent className="py-12 text-center">
                <Brain className="h-10 w-10 mx-auto mb-3 text-amber-500 animate-pulse" />
                <p className="text-base font-semibold text-slate-900">AI Raporu Olusturuluyor...</p>
                <p className="text-sm text-slate-500 mt-1">Google Ads, GA4 ve Search Console verileri inceleniyor</p>
              </CardContent>
            </Card>
          )}

          {report && !generating && (
            <Card className="border border-slate-200" data-testid="ai-report-card">
              <CardHeader className="pb-2 pt-4 px-4">
                <CardTitle className="text-sm font-semibold text-slate-900 flex items-center gap-2">
                  <Brain className="h-4 w-4 text-amber-500" /> AI {catInfo?.label} Raporu
                </CardTitle>
              </CardHeader>
              <CardContent className="px-4 pb-4">
                <div className="prose prose-sm prose-slate max-w-none" data-testid="report-content">
                  <ReactMarkdown
                    components={{
                      h3: ({ children }) => <h3 className="text-base font-bold text-slate-900 mt-6 mb-3 pb-1 border-b border-slate-100">{children}</h3>,
                      h2: ({ children }) => <h2 className="text-lg font-bold text-slate-900 mt-8 mb-3 pb-2 border-b-2 border-amber-200">{children}</h2>,
                      strong: ({ children }) => <strong className="font-semibold text-slate-800">{children}</strong>,
                      li: ({ children }) => <li className="text-sm text-slate-700 leading-relaxed my-1">{children}</li>,
                      p: ({ children }) => <p className="text-sm text-slate-700 leading-relaxed my-2">{children}</p>,
                      ul: ({ children }) => <ul className="space-y-1 my-2">{children}</ul>,
                      table: ({ children }) => <table className="w-full border-collapse border border-slate-200 my-3">{children}</table>,
                      th: ({ children }) => <th className="border border-slate-200 px-3 py-1.5 bg-slate-50 text-xs font-semibold text-left">{children}</th>,
                      td: ({ children }) => <td className="border border-slate-200 px-3 py-1.5 text-sm">{children}</td>,
                    }}
                  >
                    {report}
                  </ReactMarkdown>
                </div>
              </CardContent>
            </Card>
          )}
        </>
      )}
    </div>
  );
}
