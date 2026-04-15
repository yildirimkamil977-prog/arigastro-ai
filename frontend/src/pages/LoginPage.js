import { useState } from "react";
import { useAuth } from "../context/AuthContext";
import { useNavigate } from "react-router-dom";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Lock, User } from "lucide-react";

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(username, password);
      navigate("/dashboard");
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === "string" ? detail : "Giriş başarısız. Bilgilerinizi kontrol edin.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex" data-testid="login-page">
      {/* Left: Login Form */}
      <div className="w-full lg:w-1/2 flex items-center justify-center p-8 bg-background">
        <div className="w-full max-w-md space-y-8">
          <div className="space-y-2">
            <div className="flex items-center gap-3 mb-6">
              <div className="w-10 h-10 rounded-md bg-amber-500 flex items-center justify-center">
                <span className="text-black font-bold text-lg font-heading">A</span>
              </div>
              <div>
                <h1 className="text-2xl font-bold tracking-tight text-slate-900 font-heading" data-testid="login-title">
                  ARI AI
                </h1>
                <p className="text-xs uppercase tracking-wider text-slate-500 font-medium">
                  Urun Gelistirme Sistemleri
                </p>
              </div>
            </div>
            <h2 className="text-xl font-semibold tracking-tight text-slate-900 font-heading">
              Yonetim Paneline Giris
            </h2>
            <p className="text-sm text-slate-500">
              Arigastro Endustriyel Mutfak Ekipmanlari
            </p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-5" data-testid="login-form">
            {error && (
              <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-md text-sm" data-testid="login-error">
                {error}
              </div>
            )}
            <div className="space-y-2">
              <Label htmlFor="username" className="text-sm font-medium text-slate-700">Kullanici Adi</Label>
              <div className="relative">
                <User className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                <Input
                  id="username"
                  data-testid="login-username-input"
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="Kullanici adinizi girin"
                  className="pl-10 h-11 rounded-md border-slate-300 focus:ring-slate-900"
                  required
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="password" className="text-sm font-medium text-slate-700">Sifre</Label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                <Input
                  id="password"
                  data-testid="login-password-input"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Sifrenizi girin"
                  className="pl-10 h-11 rounded-md border-slate-300 focus:ring-slate-900"
                  required
                />
              </div>
            </div>
            <Button
              type="submit"
              data-testid="login-submit-button"
              disabled={loading}
              className="w-full h-11 bg-slate-900 hover:bg-slate-800 text-white rounded-md font-medium transition-all duration-150 hover:-translate-y-px hover:shadow-md"
            >
              {loading ? "Giris yapiliyor..." : "Giris Yap"}
            </Button>
          </form>
        </div>
      </div>

      {/* Right: Image */}
      <div className="hidden lg:block lg:w-1/2 relative">
        <div className="absolute inset-0 bg-black/20 z-10" />
        <img
          src="https://static.prod-images.emergentagent.com/jobs/cb4e3230-7652-4b11-9c5b-7808dab23992/images/69c897685665909e97d0ba6d3c187f76d9a0ea3463351f1b12359a5ac26e50f5.png"
          alt="Industrial Kitchen"
          className="w-full h-full object-cover"
        />
        <div className="absolute bottom-8 left-8 right-8 z-20 text-white">
          <h3 className="text-2xl font-bold font-heading tracking-tight">Rakip Fiyat Takip & SEO Sistemi</h3>
          <p className="text-sm text-white/80 mt-2">Urunlerinizi Akakce uzerinden takip edin, AI ile SEO icerikleri olusturun.</p>
        </div>
      </div>
    </div>
  );
}
