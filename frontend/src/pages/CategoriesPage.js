import { useState, useEffect } from "react";
import axios from "axios";
import { getAuthHeaders, API } from "../context/AuthContext";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Badge } from "../components/ui/badge";
import { Switch } from "../components/ui/switch";
import { Download, Search, Tags, Loader2 } from "lucide-react";
import { toast } from "sonner";

export default function CategoriesPage() {
  const [categories, setCategories] = useState([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [importing, setImporting] = useState(false);

  const fetchCategories = async () => {
    try {
      const { data } = await axios.get(`${API}/categories`, { headers: getAuthHeaders(), withCredentials: true });
      setCategories(data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchCategories(); }, []);

  const handleImport = async () => {
    setImporting(true);
    try {
      const { data } = await axios.post(`${API}/sitemap/import-categories`, {}, { headers: getAuthHeaders(), withCredentials: true });
      toast.success(`${data.imported} yeni kategori iceri aktarildi. Toplam: ${data.total}`);
      fetchCategories();
    } catch (err) {
      toast.error("Kategori aktarimi basarisiz");
    } finally {
      setImporting(false);
    }
  };

  const toggleTracking = async (slug) => {
    try {
      const { data } = await axios.put(`${API}/categories/${slug}/toggle-tracking`, {}, { headers: getAuthHeaders(), withCredentials: true });
      setCategories((prev) => prev.map((c) => c.slug === slug ? { ...c, is_tracked: data.is_tracked } : c));
      toast.success(data.is_tracked ? "Kategori takibe alindi" : "Kategori takipten cikarildi");
    } catch (err) {
      toast.error("Guncelleme basarisiz");
    }
  };

  const filtered = categories.filter((c) => c.name.toLowerCase().includes(search.toLowerCase()));
  const trackedCount = categories.filter((c) => c.is_tracked).length;

  return (
    <div className="space-y-6" data-testid="categories-page">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-slate-900 font-heading">Kategoriler</h2>
          <p className="text-sm text-slate-500 mt-1">
            Sitemap'ten kategorileri iceri aktarin ve takip edilecekleri secin
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Badge variant="outline" className="text-xs">
            <Tags className="h-3 w-3 mr-1" />
            {trackedCount} / {categories.length} Takipte
          </Badge>
          <Button
            onClick={handleImport}
            disabled={importing}
            data-testid="import-categories-button"
            className="bg-slate-900 hover:bg-slate-800 text-white text-sm h-9"
          >
            {importing ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Download className="h-4 w-4 mr-2" />}
            Kategorileri Aktar
          </Button>
        </div>
      </div>

      {/* Search */}
      <div className="relative max-w-md">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
        <Input
          data-testid="category-search-input"
          placeholder="Kategori ara..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="pl-10 h-9 border-slate-300"
        />
      </div>

      {/* Grid */}
      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[1,2,3,4,5,6].map((i) => (
            <div key={i} className="h-24 bg-slate-100 rounded-lg animate-pulse" />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <Card className="border-slate-200">
          <CardContent className="py-12 text-center">
            <Tags className="h-10 w-10 mx-auto text-slate-300 mb-3" />
            <p className="text-sm text-slate-500">
              {categories.length === 0 ? "Henuz kategori yok. Yukaridaki butona tiklayarak sitemap'ten aktarin." : "Aramanizla eslesen kategori bulunamadi."}
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {filtered.map((cat) => (
            <Card key={cat.slug} className={`border shadow-sm transition-all duration-150 hover:shadow-md ${cat.is_tracked ? "border-emerald-200 bg-emerald-50/30" : "border-slate-200"}`}>
              <CardContent className="p-4">
                <div className="flex items-center justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-slate-900 truncate" data-testid={`category-name-${cat.slug}`}>{cat.name}</p>
                    <p className="text-xs text-slate-500 truncate mt-0.5">{cat.slug}</p>
                  </div>
                  <Switch
                    data-testid={`category-toggle-${cat.slug}`}
                    checked={cat.is_tracked}
                    onCheckedChange={() => toggleTracking(cat.slug)}
                  />
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
