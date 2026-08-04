import { useState, useEffect, useCallback } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { toast } from "sonner";
import {
  TrendingUp, TrendingDown, Eye, MousePointerClick, DollarSign, Users,
  Search, BarChart3, RefreshCw, Brain, ChevronDown, ChevronUp,
  Play, Pause, ArrowUpRight, ArrowDownRight, AlertTriangle,
  Lightbulb, Target, Clock, History, Zap, Globe, ShoppingCart
} from "lucide-react";
import ReactMarkdown from "react-markdown";

const API = process.env.REACT_APP_BACKEND_URL;

function StatCard({ title, value, subtitle, icon: Icon, trend, color = "amber" }) {
  const colorMap = {
    amber: "bg-amber-50 text-amber-600 border-amber-200",
    blue: "bg-blue-50 text-blue-600 border-blue-200",
    green: "bg-emerald-50 text-emerald-600 border-emerald-200",
    red: "bg-red-50 text-red-600 border-red-200",
    purple: "bg-violet-50 text-violet-600 border-violet-200",
    slate: "bg-slate-50 text-slate-600 border-slate-200",
  };
  return (
    <Card className="border border-slate-200" data-testid={`stat-${title.toLowerCase().replace(/\s/g, "-")}`}>
      <CardContent className="p-4">
        <div className="flex items-start justify-between">
          <div className="space-y-1">
            <p className="text-xs font-medium text-slate-500 uppercase tracking-wide">{title}</p>
            <p className="text-2xl font-bold text-slate-900">{value}</p>
            {subtitle && <p className="text-xs text-slate-500">{subtitle}</p>}
          </div>
          <div className={`w-9 h-9 rounded-lg flex items-center justify-center border ${colorMap[color]}`}>
            <Icon className="h-4 w-4" />
          </div>
        </div>
        {trend !== undefined && (
          <div className={`flex items-center gap-1 mt-2 text-xs font-medium ${trend >= 0 ? "text-emerald-600" : "text-red-500"}`}>
            {trend >= 0 ? <ArrowUpRight className="h-3 w-3" /> : <ArrowDownRight className="h-3 w-3" />}
            <span>{Math.abs(trend)}%</span>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function CampaignRow({ campaign, onAction, actionLoading }) {
  const statusColors = {
    ENABLED: "bg-emerald-100 text-emerald-700",
    PAUSED: "bg-yellow-100 text-yellow-700",
    REMOVED: "bg-red-100 text-red-700",
  };
  return (
    <tr className="border-b border-slate-100 hover:bg-slate-50/50 transition-colors" data-testid={`campaign-row-${campaign.id}`}>
      <td className="py-3 px-4">
        <div>
          <p className="text-sm font-medium text-slate-900">{campaign.name}</p>
          <p className="text-xs text-slate-500">{campaign.channel}</p>
        </div>
      </td>
      <td className="py-3 px-3">
        <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${statusColors[campaign.status] || "bg-slate-100 text-slate-600"}`}>
          {campaign.status === "ENABLED" ? "Aktif" : campaign.status === "PAUSED" ? "Duraklatildi" : campaign.status}
        </span>
      </td>
      <td className="py-3 px-3 text-sm text-right font-mono">{campaign.impressions?.toLocaleString("tr-TR")}</td>
      <td className="py-3 px-3 text-sm text-right font-mono">{campaign.clicks?.toLocaleString("tr-TR")}</td>
      <td className="py-3 px-3 text-sm text-right font-mono">%{campaign.ctr}</td>
      <td className="py-3 px-3 text-sm text-right font-mono">{campaign.cost?.toLocaleString("tr-TR", { minimumFractionDigits: 2 })} TL</td>
      <td className="py-3 px-3 text-sm text-right font-mono">{campaign.conversions}</td>
      <td className="py-3 px-3 text-sm text-right">
        <span className={`font-bold ${campaign.roas >= 3 ? "text-emerald-600" : campaign.roas >= 1 ? "text-amber-600" : "text-red-600"}`}>
          {campaign.roas}x
        </span>
      </td>
      <td className="py-3 px-3 text-right">
        <div className="flex items-center justify-end gap-1">
          {campaign.status === "ENABLED" ? (
            <Button
              variant="ghost" size="sm"
              className="h-7 text-xs text-yellow-600 hover:bg-yellow-50"
              onClick={() => onAction("pause_campaign", campaign.id)}
              disabled={actionLoading}
              data-testid={`pause-btn-${campaign.id}`}
            >
              <Pause className="h-3 w-3 mr-1" /> Duraklat
            </Button>
          ) : campaign.status === "PAUSED" ? (
            <Button
              variant="ghost" size="sm"
              className="h-7 text-xs text-emerald-600 hover:bg-emerald-50"
              onClick={() => onAction("enable_campaign", campaign.id)}
              disabled={actionLoading}
              data-testid={`enable-btn-${campaign.id}`}
            >
              <Play className="h-3 w-3 mr-1" /> Etkinlestir
            </Button>
          ) : null}
        </div>
      </td>
    </tr>
  );
}

export default function MarketingPage() {
  const [dashboardData, setDashboardData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [analysis, setAnalysis] = useState(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [activeTab, setActiveTab] = useState("overview");
  const [showKeywords, setShowKeywords] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState(null);
  const [pastAnalyses, setPastAnalyses] = useState([]);
  const [showPastAnalyses, setShowPastAnalyses] = useState(false);
  const [dateRange, setDateRange] = useState("30");

  const getDateRange = useCallback(() => {
    const to = new Date().toISOString().split("T")[0];
    const from = new Date(Date.now() - parseInt(dateRange) * 86400000).toISOString().split("T")[0];
    return { date_from: from, date_to: to };
  }, [dateRange]);

  const fetchDashboard = useCallback(async () => {
    setLoading(true);
    try {
      const { date_from, date_to } = getDateRange();
      const res = await fetch(`${API}/api/marketing/dashboard?date_from=${date_from}&date_to=${date_to}`, { credentials: "include" });
      if (!res.ok) throw new Error("Veri alinamadi");
      const data = await res.json();
      setDashboardData(data);
    } catch (e) {
      toast.error("Marketing verileri alinamadi: " + e.message);
    } finally {
      setLoading(false);
    }
  }, [getDateRange]);

  const testConnection = async () => {
    try {
      const res = await fetch(`${API}/api/marketing/test-connection`, { credentials: "include" });
      const data = await res.json();
      setConnectionStatus(data);
      const allOk = data.ga4?.ok && data.search_console?.ok && data.google_ads?.ok;
      if (allOk) toast.success("Tum API baglantilari basarili!");
      else toast.warning("Bazi API baglantilari basarisiz");
    } catch (e) {
      toast.error("Baglanti testi basarisiz: " + e.message);
    }
  };

  const runAnalysis = async (focus = "genel") => {
    setAnalyzing(true);
    setAnalysis(null);
    try {
      const { date_from, date_to } = getDateRange();
      const res = await fetch(`${API}/api/marketing/ai-analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ date_from, date_to, focus }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Analiz basarisiz");
      }
      const data = await res.json();
      setAnalysis(data.analysis);
      setActiveTab("analysis");
      toast.success("AI analizi tamamlandi!");
    } catch (e) {
      toast.error("AI analiz hatasi: " + e.message);
    } finally {
      setAnalyzing(false);
    }
  };

  const executeAction = async (actionType, campaignId, value = null) => {
    setActionLoading(true);
    try {
      const res = await fetch(`${API}/api/marketing/ads-action`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ action_type: actionType, campaign_id: campaignId, value }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Aksiyon basarisiz");
      toast.success(data.message);
      fetchDashboard();
    } catch (e) {
      toast.error("Aksiyon hatasi: " + e.message);
    } finally {
      setActionLoading(false);
    }
  };

  const fetchPastAnalyses = async () => {
    try {
      const res = await fetch(`${API}/api/marketing/analyses?limit=10`, { credentials: "include" });
      const data = await res.json();
      setPastAnalyses(data);
    } catch (e) { /* ignore */ }
  };

  useEffect(() => { fetchDashboard(); }, [fetchDashboard]);

  const ga4 = dashboardData?.ga4_overview || {};
  const campaigns = (dashboardData?.ads_campaigns || []).filter(c => !c.error);
  const keywords = (dashboardData?.ads_keywords || []).filter(k => !k.error);
  const gscQueries = (dashboardData?.gsc_queries || []).filter(q => !q.error);
  const traffic = (dashboardData?.ga4_traffic || []).filter(t => !t.error);
  const apiErrors = dashboardData?.api_errors || [];

  const totalAdSpend = campaigns.reduce((s, c) => s + (c.cost || 0), 0);
  const totalClicks = campaigns.reduce((s, c) => s + (c.clicks || 0), 0);
  const totalImpressions = campaigns.reduce((s, c) => s + (c.impressions || 0), 0);
  const totalConversions = campaigns.reduce((s, c) => s + (c.conversions || 0), 0);
  const avgRoas = campaigns.length > 0 ? (campaigns.reduce((s, c) => s + (c.roas || 0), 0) / campaigns.length).toFixed(1) : "0";

  const tabs = [
    { id: "overview", label: "Genel Bakis", icon: BarChart3 },
    { id: "ads", label: "Google Ads", icon: Target },
    { id: "seo", label: "SEO & Search", icon: Search },
    { id: "traffic", label: "Trafik", icon: Globe },
    { id: "analysis", label: "AI Analiz", icon: Brain },
  ];

  return (
    <div className="space-y-6" data-testid="marketing-page">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-900 tracking-tight">AI Pazarlama Analizci</h2>
          <p className="text-sm text-slate-500 mt-0.5">Google Ads, GA4 ve Search Console verilerini analiz edin</p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <select
            value={dateRange}
            onChange={(e) => setDateRange(e.target.value)}
            className="h-9 px-3 text-sm border border-slate-200 rounded-lg bg-white text-slate-700 focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500"
            data-testid="date-range-select"
          >
            <option value="7">Son 7 Gun</option>
            <option value="14">Son 14 Gun</option>
            <option value="30">Son 30 Gun</option>
            <option value="60">Son 60 Gun</option>
            <option value="90">Son 90 Gun</option>
          </select>
          <Button variant="outline" size="sm" onClick={testConnection} data-testid="test-connection-btn" className="h-9">
            <Zap className="h-3.5 w-3.5 mr-1.5" /> Baglanti Testi
          </Button>
          <Button variant="outline" size="sm" onClick={fetchDashboard} disabled={loading} data-testid="refresh-btn" className="h-9">
            <RefreshCw className={`h-3.5 w-3.5 mr-1.5 ${loading ? "animate-spin" : ""}`} /> Yenile
          </Button>
          <Button
            size="sm"
            onClick={() => runAnalysis("genel")}
            disabled={analyzing || loading}
            className="h-9 bg-slate-900 hover:bg-slate-800 text-white"
            data-testid="ai-analyze-btn"
          >
            <Brain className={`h-3.5 w-3.5 mr-1.5 ${analyzing ? "animate-pulse" : ""}`} />
            {analyzing ? "Analiz Ediliyor..." : "AI Analiz Baslat"}
          </Button>
        </div>
      </div>

      {/* Connection Status */}
      {connectionStatus && (
        <div className="grid grid-cols-1 sm:grid-cols-4 gap-3" data-testid="connection-status">
          {["service_account", "ga4", "search_console", "google_ads"].map(key => {
            const s = connectionStatus[key];
            const labels = { service_account: "Service Account", ga4: "Google Analytics", search_console: "Search Console", google_ads: "Google Ads" };
            return (
              <div key={key} className={`flex items-center gap-2 p-3 rounded-lg border text-sm ${s?.ok ? "bg-emerald-50 border-emerald-200 text-emerald-700" : "bg-red-50 border-red-200 text-red-700"}`}>
                <div className={`w-2 h-2 rounded-full ${s?.ok ? "bg-emerald-500" : "bg-red-500"}`} />
                <span className="font-medium">{labels[key]}</span>
                {s?.ok ? <span className="ml-auto text-xs">Bagli</span> : <span className="ml-auto text-xs truncate max-w-[120px]">{s?.error?.slice(0, 40)}</span>}
              </div>
            );
          })}
        </div>
      )}

      {/* API Errors */}
      {apiErrors.length > 0 && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-3">
          <div className="flex items-center gap-2 text-amber-700 text-sm font-medium mb-1">
            <AlertTriangle className="h-4 w-4" /> API Uyarilari
          </div>
          {apiErrors.map((e, i) => <p key={i} className="text-xs text-amber-600 ml-6">{e}</p>)}
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-1 border-b border-slate-200 overflow-x-auto" data-testid="marketing-tabs">
        {tabs.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            data-testid={`tab-${tab.id}`}
            className={`flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors whitespace-nowrap
              ${activeTab === tab.id ? "border-slate-900 text-slate-900" : "border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300"}`}
          >
            <tab.icon className="h-3.5 w-3.5" /> {tab.label}
            {tab.id === "analysis" && analysis && <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 ml-1" />}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-20">
          <div className="flex flex-col items-center gap-3">
            <RefreshCw className="h-8 w-8 text-slate-400 animate-spin" />
            <p className="text-sm text-slate-500">Google API verileri yukleniyor...</p>
          </div>
        </div>
      ) : (
        <>
          {/* OVERVIEW TAB */}
          {activeTab === "overview" && (
            <div className="space-y-6">
              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
                <StatCard title="Oturumlar" value={ga4.sessions?.toLocaleString("tr-TR") || "0"} icon={Users} color="blue" />
                <StatCard title="Kullanicilar" value={ga4.total_users?.toLocaleString("tr-TR") || "0"} icon={Users} color="purple" />
                <StatCard title="Sayfa Goruntulenme" value={ga4.page_views?.toLocaleString("tr-TR") || "0"} icon={Eye} color="slate" />
                <StatCard title="Reklam Harcamasi" value={`${totalAdSpend.toLocaleString("tr-TR", { minimumFractionDigits: 0 })} TL`} icon={DollarSign} color="red" />
                <StatCard title="Satis" value={ga4.purchases || "0"} icon={ShoppingCart} color="green" />
                <StatCard title="Gelir" value={`${(ga4.revenue || 0).toLocaleString("tr-TR", { minimumFractionDigits: 0 })} TL`} icon={TrendingUp} color="amber" />
              </div>

              {/* Quick overview cards */}
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                {/* Ads Summary */}
                <Card className="border border-slate-200">
                  <CardHeader className="pb-2 pt-4 px-4">
                    <CardTitle className="text-sm font-semibold text-slate-900 flex items-center gap-2">
                      <Target className="h-4 w-4 text-amber-500" /> Google Ads Ozeti
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="px-4 pb-4 space-y-2">
                    {campaigns.length > 0 ? (
                      <>
                        <div className="flex justify-between text-sm"><span className="text-slate-500">Aktif Kampanya</span><span className="font-medium">{campaigns.filter(c => c.status === "ENABLED").length}</span></div>
                        <div className="flex justify-between text-sm"><span className="text-slate-500">Toplam Tiklama</span><span className="font-medium">{totalClicks.toLocaleString("tr-TR")}</span></div>
                        <div className="flex justify-between text-sm"><span className="text-slate-500">Toplam Gosterim</span><span className="font-medium">{totalImpressions.toLocaleString("tr-TR")}</span></div>
                        <div className="flex justify-between text-sm"><span className="text-slate-500">Donusum</span><span className="font-medium">{totalConversions}</span></div>
                        <div className="flex justify-between text-sm"><span className="text-slate-500">Ort. ROAS</span><span className={`font-bold ${parseFloat(avgRoas) >= 3 ? "text-emerald-600" : parseFloat(avgRoas) >= 1 ? "text-amber-600" : "text-red-600"}`}>{avgRoas}x</span></div>
                      </>
                    ) : (
                      <p className="text-sm text-slate-400 italic">Kampanya verisi bulunamadi</p>
                    )}
                  </CardContent>
                </Card>

                {/* SEO Summary */}
                <Card className="border border-slate-200">
                  <CardHeader className="pb-2 pt-4 px-4">
                    <CardTitle className="text-sm font-semibold text-slate-900 flex items-center gap-2">
                      <Search className="h-4 w-4 text-blue-500" /> Search Console Ozeti
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="px-4 pb-4 space-y-2">
                    {gscQueries.length > 0 ? (
                      <>
                        <div className="flex justify-between text-sm"><span className="text-slate-500">Sorgu Sayisi</span><span className="font-medium">{gscQueries.length}</span></div>
                        <div className="flex justify-between text-sm"><span className="text-slate-500">Toplam Tiklama</span><span className="font-medium">{gscQueries.reduce((s, q) => s + q.clicks, 0).toLocaleString("tr-TR")}</span></div>
                        <div className="flex justify-between text-sm"><span className="text-slate-500">Toplam Gosterim</span><span className="font-medium">{gscQueries.reduce((s, q) => s + q.impressions, 0).toLocaleString("tr-TR")}</span></div>
                        <div className="flex justify-between text-sm"><span className="text-slate-500">En Iyi Sorgu</span><span className="font-medium text-xs truncate max-w-[120px]">{gscQueries[0]?.query}</span></div>
                      </>
                    ) : (
                      <p className="text-sm text-slate-400 italic">Search Console verisi bulunamadi</p>
                    )}
                  </CardContent>
                </Card>

                {/* Traffic Summary */}
                <Card className="border border-slate-200">
                  <CardHeader className="pb-2 pt-4 px-4">
                    <CardTitle className="text-sm font-semibold text-slate-900 flex items-center gap-2">
                      <Globe className="h-4 w-4 text-violet-500" /> Trafik Ozeti
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="px-4 pb-4 space-y-2">
                    {traffic.length > 0 ? (
                      <>
                        <div className="flex justify-between text-sm"><span className="text-slate-500">Kaynak Sayisi</span><span className="font-medium">{traffic.length}</span></div>
                        <div className="flex justify-between text-sm"><span className="text-slate-500">Hemen Cikma</span><span className="font-medium">%{ga4.bounce_rate || 0}</span></div>
                        <div className="flex justify-between text-sm"><span className="text-slate-500">Ort. Oturum</span><span className="font-medium">{Math.round(ga4.avg_session_duration || 0)} sn</span></div>
                        <div className="flex justify-between text-sm"><span className="text-slate-500">En Iyi Kaynak</span><span className="font-medium text-xs">{traffic[0]?.source}/{traffic[0]?.medium}</span></div>
                      </>
                    ) : (
                      <p className="text-sm text-slate-400 italic">Trafik verisi bulunamadi</p>
                    )}
                  </CardContent>
                </Card>
              </div>

              {/* Quick AI Analysis Buttons */}
              <Card className="border border-slate-200 bg-gradient-to-r from-slate-50 to-amber-50/30">
                <CardContent className="p-4">
                  <div className="flex flex-col sm:flex-row sm:items-center gap-3">
                    <div className="flex items-center gap-2 flex-1">
                      <Brain className="h-5 w-5 text-amber-500" />
                      <div>
                        <p className="text-sm font-semibold text-slate-900">AI ile Hizli Analiz</p>
                        <p className="text-xs text-slate-500">Odak alani secin, AI detayli rapor hazirlasin</p>
                      </div>
                    </div>
                    <div className="flex gap-2 flex-wrap">
                      {[
                        { f: "genel", label: "Genel Rapor", icon: BarChart3 },
                        { f: "ads", label: "Reklam Analizi", icon: Target },
                        { f: "seo", label: "SEO Analizi", icon: Search },
                        { f: "traffic", label: "Trafik Analizi", icon: Globe },
                      ].map(item => (
                        <Button
                          key={item.f}
                          variant="outline"
                          size="sm"
                          onClick={() => runAnalysis(item.f)}
                          disabled={analyzing}
                          className="h-8 text-xs"
                          data-testid={`analyze-${item.f}-btn`}
                        >
                          <item.icon className="h-3 w-3 mr-1" /> {item.label}
                        </Button>
                      ))}
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>
          )}

          {/* ADS TAB */}
          {activeTab === "ads" && (
            <div className="space-y-4">
              {/* Campaign Table */}
              <Card className="border border-slate-200">
                <CardHeader className="pb-2 pt-4 px-4">
                  <CardTitle className="text-sm font-semibold text-slate-900">Kampanya Performansi</CardTitle>
                </CardHeader>
                <CardContent className="px-0 pb-0">
                  {campaigns.length > 0 ? (
                    <div className="overflow-x-auto">
                      <table className="w-full text-left" data-testid="campaigns-table">
                        <thead>
                          <tr className="border-b border-slate-200 bg-slate-50/50">
                            <th className="py-2.5 px-4 text-xs font-semibold text-slate-500 uppercase tracking-wide">Kampanya</th>
                            <th className="py-2.5 px-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Durum</th>
                            <th className="py-2.5 px-3 text-xs font-semibold text-slate-500 uppercase tracking-wide text-right">Gosterim</th>
                            <th className="py-2.5 px-3 text-xs font-semibold text-slate-500 uppercase tracking-wide text-right">Tiklama</th>
                            <th className="py-2.5 px-3 text-xs font-semibold text-slate-500 uppercase tracking-wide text-right">CTR</th>
                            <th className="py-2.5 px-3 text-xs font-semibold text-slate-500 uppercase tracking-wide text-right">Maliyet</th>
                            <th className="py-2.5 px-3 text-xs font-semibold text-slate-500 uppercase tracking-wide text-right">Donusum</th>
                            <th className="py-2.5 px-3 text-xs font-semibold text-slate-500 uppercase tracking-wide text-right">ROAS</th>
                            <th className="py-2.5 px-3 text-xs font-semibold text-slate-500 uppercase tracking-wide text-right">Aksiyonlar</th>
                          </tr>
                        </thead>
                        <tbody>
                          {campaigns.map(c => (
                            <CampaignRow key={c.id} campaign={c} onAction={executeAction} actionLoading={actionLoading} />
                          ))}
                        </tbody>
                        <tfoot>
                          <tr className="border-t-2 border-slate-200 bg-slate-50/80">
                            <td className="py-2.5 px-4 text-sm font-bold text-slate-900" colSpan={2}>Toplam</td>
                            <td className="py-2.5 px-3 text-sm text-right font-bold font-mono">{totalImpressions.toLocaleString("tr-TR")}</td>
                            <td className="py-2.5 px-3 text-sm text-right font-bold font-mono">{totalClicks.toLocaleString("tr-TR")}</td>
                            <td className="py-2.5 px-3 text-sm text-right font-bold font-mono">%{totalImpressions > 0 ? ((totalClicks / totalImpressions) * 100).toFixed(2) : 0}</td>
                            <td className="py-2.5 px-3 text-sm text-right font-bold font-mono">{totalAdSpend.toLocaleString("tr-TR", { minimumFractionDigits: 2 })} TL</td>
                            <td className="py-2.5 px-3 text-sm text-right font-bold font-mono">{totalConversions}</td>
                            <td className="py-2.5 px-3 text-sm text-right font-bold">{avgRoas}x</td>
                            <td></td>
                          </tr>
                        </tfoot>
                      </table>
                    </div>
                  ) : (
                    <div className="p-8 text-center text-sm text-slate-400">
                      <Target className="h-10 w-10 mx-auto mb-2 text-slate-300" />
                      <p>Google Ads kampanya verisi bulunamadi</p>
                      <p className="text-xs mt-1">Baglanti durumunu kontrol edin</p>
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* Keywords */}
              <Card className="border border-slate-200">
                <CardHeader className="pb-2 pt-4 px-4">
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-sm font-semibold text-slate-900">Anahtar Kelime Performansi</CardTitle>
                    <Button variant="ghost" size="sm" onClick={() => setShowKeywords(!showKeywords)} className="h-7 text-xs" data-testid="toggle-keywords-btn">
                      {showKeywords ? <ChevronUp className="h-3 w-3 mr-1" /> : <ChevronDown className="h-3 w-3 mr-1" />}
                      {showKeywords ? "Gizle" : "Goster"} ({keywords.length})
                    </Button>
                  </div>
                </CardHeader>
                {showKeywords && (
                  <CardContent className="px-0 pb-0">
                    {keywords.length > 0 ? (
                      <div className="overflow-x-auto">
                        <table className="w-full text-left" data-testid="keywords-table">
                          <thead>
                            <tr className="border-b border-slate-200 bg-slate-50/50">
                              <th className="py-2.5 px-4 text-xs font-semibold text-slate-500 uppercase">Anahtar Kelime</th>
                              <th className="py-2.5 px-3 text-xs font-semibold text-slate-500 uppercase">Kampanya</th>
                              <th className="py-2.5 px-3 text-xs font-semibold text-slate-500 uppercase text-right">Gosterim</th>
                              <th className="py-2.5 px-3 text-xs font-semibold text-slate-500 uppercase text-right">Tiklama</th>
                              <th className="py-2.5 px-3 text-xs font-semibold text-slate-500 uppercase text-right">CTR</th>
                              <th className="py-2.5 px-3 text-xs font-semibold text-slate-500 uppercase text-right">Maliyet</th>
                              <th className="py-2.5 px-3 text-xs font-semibold text-slate-500 uppercase text-right">ROAS</th>
                            </tr>
                          </thead>
                          <tbody>
                            {keywords.map((k, i) => (
                              <tr key={i} className="border-b border-slate-100 hover:bg-slate-50/50">
                                <td className="py-2.5 px-4">
                                  <span className="text-sm font-medium text-slate-900">"{k.keyword}"</span>
                                  <span className="ml-2 text-xs text-slate-400">{k.match_type}</span>
                                </td>
                                <td className="py-2.5 px-3 text-xs text-slate-500">{k.campaign}</td>
                                <td className="py-2.5 px-3 text-sm text-right font-mono">{k.impressions?.toLocaleString("tr-TR")}</td>
                                <td className="py-2.5 px-3 text-sm text-right font-mono">{k.clicks}</td>
                                <td className="py-2.5 px-3 text-sm text-right font-mono">%{k.ctr}</td>
                                <td className="py-2.5 px-3 text-sm text-right font-mono">{k.cost?.toLocaleString("tr-TR", { minimumFractionDigits: 2 })} TL</td>
                                <td className="py-2.5 px-3 text-sm text-right">
                                  <span className={`font-bold ${k.roas >= 3 ? "text-emerald-600" : k.roas >= 1 ? "text-amber-600" : "text-red-600"}`}>{k.roas}x</span>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    ) : (
                      <div className="p-6 text-center text-sm text-slate-400">Anahtar kelime verisi bulunamadi</div>
                    )}
                  </CardContent>
                )}
              </Card>
            </div>
          )}

          {/* SEO TAB */}
          {activeTab === "seo" && (
            <div className="space-y-4">
              <Card className="border border-slate-200">
                <CardHeader className="pb-2 pt-4 px-4">
                  <CardTitle className="text-sm font-semibold text-slate-900">Search Console - Arama Sorgulari</CardTitle>
                </CardHeader>
                <CardContent className="px-0 pb-0">
                  {gscQueries.length > 0 ? (
                    <div className="overflow-x-auto">
                      <table className="w-full text-left" data-testid="gsc-table">
                        <thead>
                          <tr className="border-b border-slate-200 bg-slate-50/50">
                            <th className="py-2.5 px-4 text-xs font-semibold text-slate-500 uppercase">#</th>
                            <th className="py-2.5 px-3 text-xs font-semibold text-slate-500 uppercase">Sorgu</th>
                            <th className="py-2.5 px-3 text-xs font-semibold text-slate-500 uppercase text-right">Tiklama</th>
                            <th className="py-2.5 px-3 text-xs font-semibold text-slate-500 uppercase text-right">Gosterim</th>
                            <th className="py-2.5 px-3 text-xs font-semibold text-slate-500 uppercase text-right">CTR</th>
                            <th className="py-2.5 px-3 text-xs font-semibold text-slate-500 uppercase text-right">Pozisyon</th>
                            <th className="py-2.5 px-3 text-xs font-semibold text-slate-500 uppercase text-right">Durum</th>
                          </tr>
                        </thead>
                        <tbody>
                          {gscQueries.map((q, i) => {
                            let status = "text-emerald-600";
                            let statusText = "Iyi";
                            if (q.position > 20) { status = "text-red-500"; statusText = "Dusuk"; }
                            else if (q.position > 10) { status = "text-amber-600"; statusText = "Orta"; }
                            else if (q.position > 3) { status = "text-blue-600"; statusText = "Iyi"; }
                            else { status = "text-emerald-600"; statusText = "Harika"; }

                            const isOpportunity = q.position >= 5 && q.position <= 15 && q.impressions > 50;
                            return (
                              <tr key={i} className={`border-b border-slate-100 hover:bg-slate-50/50 ${isOpportunity ? "bg-amber-50/30" : ""}`}>
                                <td className="py-2.5 px-4 text-xs text-slate-400">{i + 1}</td>
                                <td className="py-2.5 px-3">
                                  <div className="flex items-center gap-2">
                                    <span className="text-sm font-medium text-slate-900">{q.query}</span>
                                    {isOpportunity && (
                                      <span className="text-[10px] bg-amber-100 text-amber-700 px-1.5 py-0.5 rounded font-medium">FIRSAT</span>
                                    )}
                                  </div>
                                </td>
                                <td className="py-2.5 px-3 text-sm text-right font-mono">{q.clicks}</td>
                                <td className="py-2.5 px-3 text-sm text-right font-mono">{q.impressions?.toLocaleString("tr-TR")}</td>
                                <td className="py-2.5 px-3 text-sm text-right font-mono">%{q.ctr}</td>
                                <td className="py-2.5 px-3 text-sm text-right font-mono font-medium">{q.position}</td>
                                <td className={`py-2.5 px-3 text-sm text-right font-medium ${status}`}>{statusText}</td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <div className="p-8 text-center text-sm text-slate-400">
                      <Search className="h-10 w-10 mx-auto mb-2 text-slate-300" />
                      <p>Search Console verisi bulunamadi</p>
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* SEO Opportunities */}
              {gscQueries.filter(q => q.position >= 5 && q.position <= 15 && q.impressions > 50).length > 0 && (
                <Card className="border border-amber-200 bg-amber-50/30">
                  <CardHeader className="pb-2 pt-4 px-4">
                    <CardTitle className="text-sm font-semibold text-amber-800 flex items-center gap-2">
                      <Lightbulb className="h-4 w-4" /> SEO Firsatlari
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="px-4 pb-4">
                    <p className="text-xs text-amber-700 mb-3">Bu sorgular 5-15 pozisyon araliginda ve yuksek gosterime sahip. Icerik optimizasyonu ile ilk sayfaya cikarabilirsiniz.</p>
                    <div className="space-y-2">
                      {gscQueries.filter(q => q.position >= 5 && q.position <= 15 && q.impressions > 50).map((q, i) => (
                        <div key={i} className="flex items-center justify-between bg-white rounded-lg px-3 py-2 border border-amber-100">
                          <span className="text-sm font-medium text-slate-900">"{q.query}"</span>
                          <div className="flex items-center gap-3 text-xs text-slate-500">
                            <span>Poz: {q.position}</span>
                            <span>{q.impressions.toLocaleString("tr-TR")} gosterim</span>
                            <span>%{q.ctr} CTR</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}
            </div>
          )}

          {/* TRAFFIC TAB */}
          {activeTab === "traffic" && (
            <div className="space-y-4">
              {/* GA4 KPIs */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <StatCard title="Oturumlar" value={ga4.sessions?.toLocaleString("tr-TR") || "0"} icon={Users} color="blue" />
                <StatCard title="Hemen Cikma" value={`%${ga4.bounce_rate || 0}`} icon={TrendingDown} color={ga4.bounce_rate > 50 ? "red" : "green"} />
                <StatCard title="Ort. Sure" value={`${Math.round(ga4.avg_session_duration || 0)} sn`} icon={Clock} color="purple" />
                <StatCard title="Gelir" value={`${(ga4.revenue || 0).toLocaleString("tr-TR", { minimumFractionDigits: 0 })} TL`} icon={DollarSign} color="amber" />
              </div>

              {/* Traffic Sources Table */}
              <Card className="border border-slate-200">
                <CardHeader className="pb-2 pt-4 px-4">
                  <CardTitle className="text-sm font-semibold text-slate-900">Trafik Kaynaklari</CardTitle>
                </CardHeader>
                <CardContent className="px-0 pb-0">
                  {traffic.length > 0 ? (
                    <div className="overflow-x-auto">
                      <table className="w-full text-left" data-testid="traffic-table">
                        <thead>
                          <tr className="border-b border-slate-200 bg-slate-50/50">
                            <th className="py-2.5 px-4 text-xs font-semibold text-slate-500 uppercase">Kaynak / Ortam</th>
                            <th className="py-2.5 px-3 text-xs font-semibold text-slate-500 uppercase text-right">Oturumlar</th>
                            <th className="py-2.5 px-3 text-xs font-semibold text-slate-500 uppercase text-right">Kullanicilar</th>
                            <th className="py-2.5 px-3 text-xs font-semibold text-slate-500 uppercase text-right">Satislar</th>
                            <th className="py-2.5 px-3 text-xs font-semibold text-slate-500 uppercase text-right">Gelir</th>
                          </tr>
                        </thead>
                        <tbody>
                          {traffic.map((t, i) => (
                            <tr key={i} className="border-b border-slate-100 hover:bg-slate-50/50">
                              <td className="py-2.5 px-4">
                                <span className="text-sm font-medium text-slate-900">{t.source}</span>
                                <span className="text-xs text-slate-400 ml-1">/ {t.medium}</span>
                              </td>
                              <td className="py-2.5 px-3 text-sm text-right font-mono">{t.sessions?.toLocaleString("tr-TR")}</td>
                              <td className="py-2.5 px-3 text-sm text-right font-mono">{t.users?.toLocaleString("tr-TR")}</td>
                              <td className="py-2.5 px-3 text-sm text-right font-mono">{t.purchases}</td>
                              <td className="py-2.5 px-3 text-sm text-right font-mono">{t.revenue?.toLocaleString("tr-TR", { minimumFractionDigits: 2 })} TL</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <div className="p-8 text-center text-sm text-slate-400">
                      <Globe className="h-10 w-10 mx-auto mb-2 text-slate-300" />
                      <p>Trafik verisi bulunamadi</p>
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>
          )}

          {/* AI ANALYSIS TAB */}
          {activeTab === "analysis" && (
            <div className="space-y-4">
              {analyzing ? (
                <Card className="border border-slate-200">
                  <CardContent className="py-16 text-center">
                    <Brain className="h-12 w-12 mx-auto mb-4 text-amber-500 animate-pulse" />
                    <p className="text-lg font-semibold text-slate-900">AI Analizi Devam Ediyor...</p>
                    <p className="text-sm text-slate-500 mt-1">Google Ads, GA4 ve Search Console verileri inceleniyor</p>
                  </CardContent>
                </Card>
              ) : analysis ? (
                <Card className="border border-slate-200">
                  <CardHeader className="pb-2 pt-4 px-4">
                    <div className="flex items-center justify-between">
                      <CardTitle className="text-sm font-semibold text-slate-900 flex items-center gap-2">
                        <Brain className="h-4 w-4 text-amber-500" /> AI Pazarlama Analizi
                      </CardTitle>
                      <div className="flex gap-2">
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-7 text-xs"
                          onClick={() => { setShowPastAnalyses(!showPastAnalyses); if (!showPastAnalyses) fetchPastAnalyses(); }}
                          data-testid="past-analyses-btn"
                        >
                          <History className="h-3 w-3 mr-1" /> Gecmis
                        </Button>
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent className="px-4 pb-4">
                    <div className="prose prose-sm prose-slate max-w-none" data-testid="ai-analysis-content">
                      <ReactMarkdown
                        components={{
                          h3: ({ children }) => <h3 className="text-base font-bold text-slate-900 mt-6 mb-3 pb-1 border-b border-slate-100">{children}</h3>,
                          strong: ({ children }) => <strong className="font-semibold text-slate-800">{children}</strong>,
                          li: ({ children }) => <li className="text-sm text-slate-700 leading-relaxed my-1">{children}</li>,
                          p: ({ children }) => <p className="text-sm text-slate-700 leading-relaxed my-2">{children}</p>,
                          ul: ({ children }) => <ul className="space-y-1 my-2">{children}</ul>,
                        }}
                      >
                        {analysis}
                      </ReactMarkdown>
                    </div>
                  </CardContent>
                </Card>
              ) : (
                <Card className="border border-slate-200">
                  <CardContent className="py-16 text-center">
                    <Brain className="h-12 w-12 mx-auto mb-4 text-slate-300" />
                    <p className="text-lg font-semibold text-slate-700">Henuz Analiz Yapilmadi</p>
                    <p className="text-sm text-slate-500 mt-1 mb-4">AI ile detayli pazarlama analizi almak icin asagidaki butona tiklayin</p>
                    <Button onClick={() => runAnalysis("genel")} disabled={analyzing} className="bg-slate-900 hover:bg-slate-800 text-white" data-testid="start-analysis-btn">
                      <Brain className="h-4 w-4 mr-2" /> Analiz Baslat
                    </Button>
                  </CardContent>
                </Card>
              )}

              {/* Past Analyses */}
              {showPastAnalyses && pastAnalyses.length > 0 && (
                <Card className="border border-slate-200">
                  <CardHeader className="pb-2 pt-4 px-4">
                    <CardTitle className="text-sm font-semibold text-slate-900">Gecmis Analizler</CardTitle>
                  </CardHeader>
                  <CardContent className="px-4 pb-4 space-y-2">
                    {pastAnalyses.map((a, i) => (
                      <div key={a._id || a.id || i} className="border border-slate-100 rounded-lg p-3 hover:bg-slate-50 cursor-pointer transition-colors" onClick={() => { setAnalysis(a.analysis); setShowPastAnalyses(false); }}>
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <Brain className="h-3.5 w-3.5 text-amber-500" />
                            <span className="text-sm font-medium text-slate-700">
                              {a.focus === "genel" ? "Genel Rapor" : a.focus === "ads" ? "Reklam Analizi" : a.focus === "seo" ? "SEO Analizi" : "Trafik Analizi"}
                            </span>
                          </div>
                          <span className="text-xs text-slate-400">
                            {new Date(a.created_at).toLocaleDateString("tr-TR")} {new Date(a.created_at).toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" })}
                          </span>
                        </div>
                        <div className="flex gap-3 mt-1 text-xs text-slate-500">
                          <span>{a.raw_data_summary?.campaigns_count || 0} kampanya</span>
                          <span>{a.raw_data_summary?.gsc_queries_count || 0} sorgu</span>
                          <span>{a.raw_data_summary?.ga4_sessions || 0} oturum</span>
                        </div>
                      </div>
                    ))}
                  </CardContent>
                </Card>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
