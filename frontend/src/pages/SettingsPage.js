import { useState, useEffect } from "react";
import axios from "axios";
import { getAuthHeaders, API, useAuth } from "../context/AuthContext";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "../components/ui/dialog";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../components/ui/table";
import { Database, Key, Loader2, Clock, CheckCircle2, Users, Plus, Trash2, KeyRound, Eye, EyeOff } from "lucide-react";
import { toast } from "sonner";

export default function SettingsPage() {
  const { user: currentUser } = useAuth();
  const [feedStatus, setFeedStatus] = useState(null);
  const [matchStatus, setMatchStatus] = useState(null);
  const [priceStatus, setPriceStatus] = useState(null);
  const [schedulerStatus, setSchedulerStatus] = useState(null);
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);

  // User management state
  const [showAddUser, setShowAddUser] = useState(false);
  const [newUser, setNewUser] = useState({ username: "", password: "", name: "" });
  const [showPassword, setShowPassword] = useState(false);
  const [changingPassword, setChangingPassword] = useState(null);
  const [newPassword, setNewPassword] = useState("");
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    const fetchAll = async () => {
      try {
        const [feed, match, price, sched, usersRes] = await Promise.all([
          axios.get(`${API}/feed/status`, { headers: getAuthHeaders(), withCredentials: true }).catch(() => ({ data: {} })),
          axios.get(`${API}/products/ai-match-status`, { headers: getAuthHeaders(), withCredentials: true }).catch(() => ({ data: {} })),
          axios.get(`${API}/products/price-check-status`, { headers: getAuthHeaders(), withCredentials: true }).catch(() => ({ data: {} })),
          axios.get(`${API}/scheduler/status`, { headers: getAuthHeaders(), withCredentials: true }).catch(() => ({ data: {} })),
          axios.get(`${API}/users`, { headers: getAuthHeaders(), withCredentials: true }).catch(() => ({ data: [] })),
        ]);
        setFeedStatus(feed.data);
        setMatchStatus(match.data);
        setPriceStatus(price.data);
        setSchedulerStatus(sched.data);
        setUsers(Array.isArray(usersRes.data) ? usersRes.data : []);
      } catch {}
      finally { setLoading(false); }
    };
    fetchAll();
    const interval = setInterval(fetchAll, 15000);
    return () => clearInterval(interval);
  }, []);

  const formatDate = (iso) => {
    if (!iso) return "-";
    try { return new Date(iso).toLocaleString("tr-TR"); } catch { return iso; }
  };

  const handleAddUser = async () => {
    if (!newUser.username || !newUser.password) {
      toast.error("Kullanici adi ve sifre zorunludur");
      return;
    }
    setSaving(true);
    try {
      await axios.post(`${API}/users`, newUser, { headers: getAuthHeaders(), withCredentials: true });
      toast.success("Kullanici olusturuldu");
      setShowAddUser(false);
      setNewUser({ username: "", password: "", name: "" });
      // Refresh users
      const { data } = await axios.get(`${API}/users`, { headers: getAuthHeaders(), withCredentials: true });
      setUsers(Array.isArray(data) ? data : []);
    } catch (err) {
      toast.error(err.response?.data?.detail || "Kullanici olusturulamadi");
    } finally { setSaving(false); }
  };

  const handleChangePassword = async () => {
    if (!newPassword || newPassword.length < 6) {
      toast.error("Sifre en az 6 karakter olmali");
      return;
    }
    setSaving(true);
    try {
      await axios.put(`${API}/users/${changingPassword}/password`, { new_password: newPassword }, { headers: getAuthHeaders(), withCredentials: true });
      toast.success("Sifre guncellendi");
      setChangingPassword(null);
      setNewPassword("");
    } catch (err) {
      toast.error(err.response?.data?.detail || "Sifre guncellenemedi");
    } finally { setSaving(false); }
  };

  const handleDeleteUser = async (username) => {
    if (!window.confirm(`"${username}" kullanicisini silmek istediginize emin misiniz?`)) return;
    try {
      await axios.delete(`${API}/users/${username}`, { headers: getAuthHeaders(), withCredentials: true });
      toast.success("Kullanici silindi");
      setUsers(prev => prev.filter(u => u.username !== username));
    } catch (err) {
      toast.error(err.response?.data?.detail || "Kullanici silinemedi");
    }
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
              <div className="text-sm text-slate-900 mt-1">
                {feedStatus?.feed_url ? <Badge className="bg-emerald-100 text-emerald-700 border-0 text-[10px]">Aktif</Badge> : <Badge variant="outline" className="text-[10px]">Yapilandirilmamis</Badge>}
              </div>
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

      {/* User Management */}
      <Card className="border-slate-200">
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-base font-heading flex items-center gap-2"><Users className="h-4 w-4" />Kullanici Yonetimi</CardTitle>
            <Button size="sm" onClick={() => setShowAddUser(true)} className="h-8 text-xs bg-slate-900 hover:bg-slate-800 text-white" data-testid="add-user-button">
              <Plus className="h-3 w-3 mr-1" />Yeni Kullanici
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow className="bg-slate-50">
                <TableHead className="text-[10px] uppercase tracking-wider font-semibold text-slate-500">Kullanici Adi</TableHead>
                <TableHead className="text-[10px] uppercase tracking-wider font-semibold text-slate-500">Ad</TableHead>
                <TableHead className="text-[10px] uppercase tracking-wider font-semibold text-slate-500">Rol</TableHead>
                <TableHead className="text-[10px] uppercase tracking-wider font-semibold text-slate-500">Olusturulma</TableHead>
                <TableHead className="text-[10px] uppercase tracking-wider font-semibold text-slate-500 text-right">Islemler</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {users.map((u) => (
                <TableRow key={u.username} data-testid={`user-row-${u.username}`}>
                  <TableCell className="text-sm font-medium text-slate-900">{u.username}</TableCell>
                  <TableCell className="text-sm text-slate-600">{u.name || "-"}</TableCell>
                  <TableCell><Badge variant="outline" className="text-[10px]">{u.role}</Badge></TableCell>
                  <TableCell className="text-xs text-slate-500">{formatDate(u.created_at)}</TableCell>
                  <TableCell className="text-right">
                    <div className="flex items-center gap-1 justify-end">
                      <Button
                        variant="outline" size="sm"
                        className="h-7 text-[10px] px-2"
                        onClick={() => { setChangingPassword(u.username); setNewPassword(""); }}
                        data-testid={`change-password-${u.username}`}
                      >
                        <KeyRound className="h-3 w-3 mr-1" />Sifre
                      </Button>
                      {u.username !== currentUser?.username && (
                        <Button
                          variant="outline" size="sm"
                          className="h-7 text-[10px] px-2 text-red-600 border-red-200 hover:bg-red-50"
                          onClick={() => handleDeleteUser(u.username)}
                          data-testid={`delete-user-${u.username}`}
                        >
                          <Trash2 className="h-3 w-3" />
                        </Button>
                      )}
                    </div>
                  </TableCell>
                </TableRow>
              ))}
              {users.length === 0 && (
                <TableRow>
                  <TableCell colSpan={5} className="text-center py-6 text-sm text-slate-500">Kullanici bulunamadi</TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
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

      {/* Add User Dialog */}
      <Dialog open={showAddUser} onOpenChange={setShowAddUser}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="font-heading text-lg">Yeni Kullanici Ekle</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label className="text-sm font-medium">Kullanici Adi</Label>
              <Input
                data-testid="new-user-username"
                value={newUser.username}
                onChange={(e) => setNewUser(prev => ({ ...prev, username: e.target.value }))}
                placeholder="ornek: yonetici2"
                className="text-sm"
              />
            </div>
            <div className="space-y-2">
              <Label className="text-sm font-medium">Ad Soyad</Label>
              <Input
                data-testid="new-user-name"
                value={newUser.name}
                onChange={(e) => setNewUser(prev => ({ ...prev, name: e.target.value }))}
                placeholder="Ahmet Yilmaz"
                className="text-sm"
              />
            </div>
            <div className="space-y-2">
              <Label className="text-sm font-medium">Sifre</Label>
              <div className="relative">
                <Input
                  data-testid="new-user-password"
                  type={showPassword ? "text" : "password"}
                  value={newUser.password}
                  onChange={(e) => setNewUser(prev => ({ ...prev, password: e.target.value }))}
                  placeholder="En az 6 karakter"
                  className="text-sm pr-10"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowAddUser(false)}>Iptal</Button>
            <Button onClick={handleAddUser} disabled={saving} className="bg-slate-900 hover:bg-slate-800 text-white" data-testid="save-new-user-button">
              {saving ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
              Olustur
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Change Password Dialog */}
      <Dialog open={!!changingPassword} onOpenChange={(open) => !open && setChangingPassword(null)}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="font-heading text-lg">Sifre Degistir</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="bg-slate-50 rounded-lg p-3">
              <p className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold">Kullanici</p>
              <p className="text-sm font-medium text-slate-900 mt-1">{changingPassword}</p>
            </div>
            <div className="space-y-2">
              <Label className="text-sm font-medium">Yeni Sifre</Label>
              <div className="relative">
                <Input
                  data-testid="change-password-input"
                  type={showNewPassword ? "text" : "password"}
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  placeholder="En az 6 karakter"
                  className="text-sm pr-10"
                />
                <button
                  type="button"
                  onClick={() => setShowNewPassword(!showNewPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                >
                  {showNewPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setChangingPassword(null)}>Iptal</Button>
            <Button onClick={handleChangePassword} disabled={saving} className="bg-slate-900 hover:bg-slate-800 text-white" data-testid="save-password-button">
              {saving ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
              Guncelle
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
