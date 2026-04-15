import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { LayoutDashboard, Tags, Package, TrendingDown, FileText, Settings, Sparkles, RefreshCw, Link2, Pencil } from "lucide-react";

export default function GuidePage() {
  return (
    <div className="space-y-8 max-w-4xl" data-testid="guide-page">
      <div>
        <h2 className="text-2xl font-bold tracking-tight text-slate-900 font-heading">Sistem Kilavuzu</h2>
        <p className="text-sm text-slate-500 mt-1">ARI AI sisteminin nasil calistigini adim adim ogrenin</p>
      </div>

      {/* Step 1 */}
      <Card className="border-slate-200">
        <CardHeader className="pb-3">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-slate-900 text-white flex items-center justify-center text-sm font-bold">1</div>
            <CardTitle className="text-base font-heading">Urunleri ve Kategorileri Iceri Aktarin</CardTitle>
          </div>
        </CardHeader>
        <CardContent className="space-y-2 text-sm text-slate-600">
          <p><strong>Kategoriler sayfasi:</strong> "Kategorileri Aktar" butonuna tiklayarak sitemap'teki tum kategorileri sisteme aktarin.</p>
          <p><strong>Urunler sayfasi:</strong> "Urunleri Aktar" butonu ile sitemap'ten urunleri aktarin. "Feed'den Fiyat Guncelle" ile urun fiyatlarini, marka ve kategori bilgilerini otomatik cekin.</p>
        </CardContent>
      </Card>

      {/* Step 2 */}
      <Card className="border-slate-200">
        <CardHeader className="pb-3">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-slate-900 text-white flex items-center justify-center text-sm font-bold">2</div>
            <CardTitle className="text-base font-heading">Takip Edilecek Kategorileri Secin</CardTitle>
          </div>
        </CardHeader>
        <CardContent className="space-y-2 text-sm text-slate-600">
          <p><strong>Kategoriler sayfasi:</strong> Fiyat takibi yapmak istediginiz kategorilerin tik isaretini acin.</p>
          <p>Sadece aktif kategorilerdeki urunler Fiyat Takip sayfasinda gorunur ve fiyat kontrolune dahil edilir.</p>
          <p className="text-amber-700 bg-amber-50 p-2 rounded">Bir kategorinin tik isaretini kapattiginizda urunler fiyat takipten cikar ama Akakce eslestirmeleri korunur.</p>
        </CardContent>
      </Card>

      {/* Step 3 */}
      <Card className="border-slate-200">
        <CardHeader className="pb-3">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-violet-600 text-white flex items-center justify-center text-sm font-bold">3</div>
            <CardTitle className="text-base font-heading">Akakce Eslestirme (AI veya Manuel)</CardTitle>
          </div>
        </CardHeader>
        <CardContent className="space-y-2 text-sm text-slate-600">
          <p><strong>Otomatik (AI):</strong> Fiyat Takip sayfasinda "AI Eslestirme" butonuna tiklayin. Sistem Google'da arama yaparak her urun icin dogru Akakce urun sayfasini bulur ve GPT ile dogrular.</p>
          <p><strong>Manuel:</strong> Urunler sayfasinda <Badge variant="outline" className="text-[10px]"><Link2 className="h-3 w-3 mr-0.5" />Eslesir</Badge> veya <Badge variant="outline" className="text-[10px]"><Pencil className="h-3 w-3 mr-0.5" /></Badge> butonuna tiklayin, Akakce urun sayfasi URL'sini yapisirin.</p>
          <p className="text-emerald-700 bg-emerald-50 p-2 rounded">Bir kez eslestirilen urun tekrar eslestirmeye calisılmaz. Eslestirme kalici olarak kaydedilir.</p>
        </CardContent>
      </Card>

      {/* Step 4 */}
      <Card className="border-slate-200">
        <CardHeader className="pb-3">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-amber-500 text-black flex items-center justify-center text-sm font-bold">4</div>
            <CardTitle className="text-base font-heading">Fiyat Kontrolu</CardTitle>
          </div>
        </CardHeader>
        <CardContent className="space-y-2 text-sm text-slate-600">
          <p><strong>Toplu:</strong> Fiyat Takip sayfasinda "Toplu Fiyat Kontrolu" butonuna tiklayin. Tum eslesmis urunlerin Akakce sayfalarindan satici fiyatlari cekilir.</p>
          <p><strong>Tekil:</strong> Urunler sayfasinda her urunun yanindaki <Badge variant="outline" className="text-[10px]"><RefreshCw className="h-3 w-3 mr-0.5" />Fiyat</Badge> butonuyla o urunun fiyatini anlik kontrol edebilirsiniz.</p>
          <p>Fiyat kontrolu sonuclari hem Urunler hem Fiyat Takip sayfasinda gorunur.</p>
        </CardContent>
      </Card>

      {/* Step 5 */}
      <Card className="border-slate-200">
        <CardHeader className="pb-3">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-slate-900 text-white flex items-center justify-center text-sm font-bold">5</div>
            <CardTitle className="text-base font-heading">SEO Icerik Uretimi</CardTitle>
          </div>
        </CardHeader>
        <CardContent className="space-y-2 text-sm text-slate-600">
          <p>SEO Uretici sayfasinda bir urun secin ve "AI ile Uret" butonuna tiklayin.</p>
          <p>Sistem urun sayfanizi tarayarak teknik ozellikleri cekar, ardindan GPT ile SEO uyumlu baslik, aciklama ve 500+ kelimelik urun aciklamasi uretir.</p>
          <p>Uretilen icerikler: Kelime sayisi, keyword density, alt basliklar (Ozellikler, Teknik Detaylar, Fiyat, SSS) icermektedir.</p>
        </CardContent>
      </Card>

      {/* ScraperAPI Info */}
      <Card className="border-amber-200 bg-amber-50/50">
        <CardHeader className="pb-3">
          <CardTitle className="text-base font-heading">ScraperAPI Hakkinda</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm text-slate-600">
          <p>Akakce erisimi icin <strong>ScraperAPI</strong> kullanilmaktadir. Her arama ve sayfa kontrolu 1 kredi harcar.</p>
          <p>Ucretsiz plan: Kayitta 5.000 kredi + ayda 1.000 ucretsiz kredi.</p>
          <p>Kredi durumunuzu <a href="https://dashboard.scraperapi.com" target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">ScraperAPI Dashboard</a>'dan takip edebilirsiniz.</p>
        </CardContent>
      </Card>
    </div>
  );
}
