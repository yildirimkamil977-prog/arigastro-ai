import { useState, useEffect } from "react";
import axios from "axios";
import { getAuthHeaders, API } from "../context/AuthContext";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Package, Tags, TrendingDown, TrendingUp, FileText, AlertTriangle, ArrowRight } from "lucide-react";
import { Link } from "react-router-dom";

export default function DashboardPage() {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const { data } = await axios.get(`${API}/dashboard/stats`, { headers: getAuthHeaders(), withCredentials: true });
        setStats(data);
      } catch (err) {
        console.error("Dashboard stats error:", err);
      } finally {
        setLoading(false);
      }
    };
    fetchStats();
  }, []);

  if (loading) {
    return (
      <div className="animate-pulse space-y-6" data-testid="dashboard-loading">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {[1,2,3,4].map(i => <div key={i} className="h-28 bg-slate-100 rounded-lg" />)}
        </div>
      </div>
    );
  }

  const statCards = [
    { label: "Toplam Urun", value: stats?.total_products || 0, icon: Package, color: "text-slate-700", bg: "bg-slate-50" },
    { label: "Takip Edilen", value: stats?.tracked_products || 0, icon: Tags, color: "text-blue-700", bg: "bg-blue-50" },
    { label: "Rakip Daha Ucuz", value: stats?.competitors_cheaper || 0, icon: TrendingDown, color: "text-red-700", bg: "bg-red-50" },
    { label: "Biz Daha Ucuz", value: stats?.we_are_cheaper || 0, icon: TrendingUp, color: "text-emerald-700", bg: "bg-emerald-50" },
  ];

  const secondaryCards = [
    { label: "Eslesmis Urunler", value: stats?.matched_products || 0, icon: Package, color: "text-amber-700", bg: "bg-amber-50" },
    { label: "Eslesmemis", value: stats?.unmatched_products || 0, icon: AlertTriangle, color: "text-orange-700", bg: "bg-orange-50" },
    { label: "SEO Uretilmis", value: stats?.seo_generated || 0, icon: FileText, color: "text-violet-700", bg: "bg-violet-50" },
    { label: "Kategoriler", value: `${stats?.tracked_categories || 0}/${stats?.total_categories || 0}`, icon: Tags, color: "text-teal-700", bg: "bg-teal-50" },
  ];

  return (
    <div className="space-y-6" data-testid="dashboard-page">
      {/* Stat Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {statCards.map((s) => (
          <Card key={s.label} className="border-slate-200 shadow-sm hover:shadow-md transition-shadow duration-150">
            <CardContent className="p-5">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-[10px] uppercase tracking-wider font-semibold text-slate-500">{s.label}</p>
                  <p className="text-3xl font-bold tracking-tight text-slate-900 mt-1 font-heading" data-testid={`stat-${s.label.toLowerCase().replace(/\s/g, '-')}`}>{s.value}</p>
                </div>
                <div className={`w-10 h-10 rounded-lg ${s.bg} flex items-center justify-center`}>
                  <s.icon className={`h-5 w-5 ${s.color}`} />
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Secondary Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {secondaryCards.map((s) => (
          <Card key={s.label} className="border-slate-200 shadow-sm">
            <CardContent className="p-4">
              <div className="flex items-center gap-3">
                <div className={`w-8 h-8 rounded-md ${s.bg} flex items-center justify-center`}>
                  <s.icon className={`h-4 w-4 ${s.color}`} />
                </div>
                <div>
                  <p className="text-[10px] uppercase tracking-wider text-slate-500">{s.label}</p>
                  <p className="text-lg font-bold text-slate-900">{s.value}</p>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Recent Alerts */}
      <Card className="border-slate-200 shadow-sm">
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-base font-semibold tracking-tight font-heading">Fiyat Uyarilari</CardTitle>
            <Link to="/price-tracking" className="text-xs text-blue-600 hover:underline flex items-center gap-1" data-testid="view-all-alerts">
              Tumunu Gor <ArrowRight className="h-3 w-3" />
            </Link>
          </div>
        </CardHeader>
        <CardContent>
          {stats?.recent_alerts?.length > 0 ? (
            <div className="space-y-2">
              {stats.recent_alerts.map((alert, i) => (
                <div key={i} className="flex items-center justify-between py-2.5 px-3 rounded-md bg-red-50 border border-red-100" data-testid={`alert-row-${i}`}>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-slate-900 truncate">{alert.name}</p>
                    <p className="text-xs text-slate-500 truncate">{alert.cheapest_competitor}</p>
                  </div>
                  <div className="flex items-center gap-4 flex-shrink-0">
                    <div className="text-right">
                      <p className="text-xs text-slate-500">Bizim Fiyat</p>
                      <p className="text-sm font-semibold text-slate-900">{alert.our_price?.toLocaleString('tr-TR')} TL</p>
                    </div>
                    <div className="text-right">
                      <p className="text-xs text-slate-500">En Ucuz</p>
                      <p className="text-sm font-semibold text-red-600">{alert.cheapest_price?.toLocaleString('tr-TR')} TL</p>
                    </div>
                    <Badge variant="destructive" className="bg-red-100 text-red-700 border-0 text-xs">
                      -{alert.price_difference?.toLocaleString('tr-TR')} TL
                    </Badge>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-8 text-slate-500 text-sm">
              <AlertTriangle className="h-8 w-8 mx-auto mb-2 text-slate-300" />
              <p>Henuz fiyat uyarisi yok</p>
              <p className="text-xs mt-1">Urunleri iceri aktarin ve Akakce kontrolu baslatin</p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
