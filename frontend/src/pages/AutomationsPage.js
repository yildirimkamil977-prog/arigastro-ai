import { useState, useEffect, useCallback } from "react";
import Layout from "../components/Layout";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import {
  Play, Pause, Trash2, Plus, RefreshCw, Clock, Zap, CheckCircle2, AlertCircle, XCircle
} from "lucide-react";
import { toast } from "sonner";

const API = process.env.REACT_APP_BACKEND_URL;

const JOB_TYPE_OPTIONS = [
  { value: "competitor_scan", label: "Rakip Fiyat Tarama" },
];

function StatusBadge({ isPaused }) {
  if (isPaused) {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-amber-50 text-amber-700 border border-amber-200">
        <Pause className="w-3 h-3" /> Duraklatıldı
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
      <Play className="w-3 h-3" /> Aktif
    </span>
  );
}

function TypeBadge({ label }) {
  const colors = {
    "Rakip Fiyat Tarama": "bg-blue-50 text-blue-700 border-blue-200",
    "Feed Senkron": "bg-purple-50 text-purple-700 border-purple-200",
    "İkas Senkron": "bg-indigo-50 text-indigo-700 border-indigo-200",
    "Akakçe Fiyat": "bg-orange-50 text-orange-700 border-orange-200",
    "Otomatik SEO": "bg-teal-50 text-teal-700 border-teal-200",
  };
  const cls = colors[label] || "bg-slate-50 text-slate-600 border-slate-200";
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border ${cls}`}>
      {label}
    </span>
  );
}

export default function AutomationsPage() {
  const [jobs, setJobs] = useState([]);
  const [schedulerRunning, setSchedulerRunning] = useState(true);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState({});
  const [showAddForm, setShowAddForm] = useState(false);
  const [newJob, setNewJob] = useState({ job_type: "competitor_scan", hour: "12", minute: "00" });
  const [addLoading, setAddLoading] = useState(false);

  const fetchJobs = useCallback(async () => {
    try {
      const token = localStorage.getItem("token");
      const res = await fetch(`${API}/api/automations`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      const data = await res.json();
      setJobs(data.jobs || []);
      setSchedulerRunning(data.scheduler_running);
    } catch {
      toast.error("Otomasyonlar yüklenemedi");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchJobs();
    const interval = setInterval(fetchJobs, 30000);
    return () => clearInterval(interval);
  }, [fetchJobs]);

  const handlePause = async (jobId) => {
    setActionLoading(p => ({ ...p, [jobId]: "pause" }));
    try {
      const token = localStorage.getItem("token");
      const res = await fetch(`${API}/api/automations/${jobId}/pause`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` }
      });
      const data = await res.json();
      if (data.success) {
        toast.success("Otomasyon duraklatıldı");
        fetchJobs();
      } else {
        toast.error(data.detail || "Hata oluştu");
      }
    } catch {
      toast.error("İşlem başarısız");
    } finally {
      setActionLoading(p => ({ ...p, [jobId]: null }));
    }
  };

  const handleResume = async (jobId) => {
    setActionLoading(p => ({ ...p, [jobId]: "resume" }));
    try {
      const token = localStorage.getItem("token");
      const res = await fetch(`${API}/api/automations/${jobId}/resume`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` }
      });
      const data = await res.json();
      if (data.success) {
        toast.success("Otomasyon devam ettirildi");
        fetchJobs();
      } else {
        toast.error(data.detail || "Hata oluştu");
      }
    } catch {
      toast.error("İşlem başarısız");
    } finally {
      setActionLoading(p => ({ ...p, [jobId]: null }));
    }
  };

  const handleDelete = async (jobId) => {
    if (!window.confirm("Bu otomasyonu silmek istediğinize emin misiniz?")) return;
    setActionLoading(p => ({ ...p, [jobId]: "delete" }));
    try {
      const token = localStorage.getItem("token");
      const res = await fetch(`${API}/api/automations/${jobId}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` }
      });
      const data = await res.json();
      if (data.success) {
        toast.success("Otomasyon silindi");
        fetchJobs();
      } else {
        toast.error(data.detail || "Hata oluştu");
      }
    } catch {
      toast.error("İşlem başarısız");
    } finally {
      setActionLoading(p => ({ ...p, [jobId]: null }));
    }
  };

  const handleAddJob = async (e) => {
    e.preventDefault();
    setAddLoading(true);
    try {
      const token = localStorage.getItem("token");
      const res = await fetch(`${API}/api/automations`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          job_type: newJob.job_type,
          hour: parseInt(newJob.hour),
          minute: parseInt(newJob.minute)
        })
      });
      const data = await res.json();
      if (data.success) {
        toast.success(`Otomasyon eklendi: ${data.name}`);
        setShowAddForm(false);
        setNewJob({ job_type: "competitor_scan", hour: "12", minute: "00" });
        fetchJobs();
      } else {
        toast.error(data.detail || "Eklenemedi");
      }
    } catch {
      toast.error("İşlem başarısız");
    } finally {
      setAddLoading(false);
    }
  };

  const activeCount = jobs.filter(j => !j.is_paused).length;
  const pausedCount = jobs.filter(j => j.is_paused).length;

  return (
    <Layout>
      <div className="space-y-6">
        {/* Stats */}
        <div className="flex items-center justify-between">
          <div className="grid grid-cols-3 gap-4 flex-1">
            <div className="bg-white rounded-xl border border-slate-200 p-4 flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-emerald-50 flex items-center justify-center">
                <Zap className="w-5 h-5 text-emerald-600" />
              </div>
              <div>
                <p className="text-xs text-slate-500">Toplam</p>
                <p className="text-2xl font-bold text-slate-800">{jobs.length}</p>
              </div>
            </div>
            <div className="bg-white rounded-xl border border-slate-200 p-4 flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-blue-50 flex items-center justify-center">
                <CheckCircle2 className="w-5 h-5 text-blue-600" />
              </div>
              <div>
                <p className="text-xs text-slate-500">Aktif</p>
                <p className="text-2xl font-bold text-slate-800">{activeCount}</p>
              </div>
            </div>
            <div className="bg-white rounded-xl border border-slate-200 p-4 flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-amber-50 flex items-center justify-center">
                <AlertCircle className="w-5 h-5 text-amber-600" />
              </div>
              <div>
                <p className="text-xs text-slate-500">Duraklatıldı</p>
                <p className="text-2xl font-bold text-slate-800">{pausedCount}</p>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2 ml-4">
            <Button variant="outline" size="sm" onClick={fetchJobs} data-testid="refresh-automations-btn">
              <RefreshCw className="w-4 h-4 mr-1" /> Yenile
            </Button>
            <Button size="sm" onClick={() => setShowAddForm(true)} className="bg-blue-600 hover:bg-blue-700 text-white" data-testid="add-automation-btn">
              <Plus className="w-4 h-4 mr-1" /> Yeni Otomasyon
            </Button>
          </div>
        </div>

        {/* Add Form */}
        {showAddForm && (
          <div className="bg-white rounded-xl border border-blue-200 p-5 shadow-sm" data-testid="add-automation-form">
            <h3 className="font-semibold text-slate-800 mb-4 flex items-center gap-2">
              <Plus className="w-4 h-4 text-blue-600" /> Yeni Otomasyon Ekle
            </h3>
            <form onSubmit={handleAddJob} className="flex flex-wrap items-end gap-4">
              <div>
                <label className="block text-xs text-slate-500 mb-1">Otomasyon Tipi</label>
                <select
                  value={newJob.job_type}
                  onChange={e => setNewJob(p => ({ ...p, job_type: e.target.value }))}
                  className="border border-slate-200 rounded-lg px-3 py-2 text-sm text-slate-700 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                  data-testid="new-job-type-select"
                >
                  {JOB_TYPE_OPTIONS.map(o => (
                    <option key={o.value} value={o.value}>{o.label}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs text-slate-500 mb-1">Saat (TR)</label>
                <input
                  type="number"
                  min="0" max="23"
                  value={newJob.hour}
                  onChange={e => setNewJob(p => ({ ...p, hour: e.target.value }))}
                  className="border border-slate-200 rounded-lg px-3 py-2 text-sm w-20 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  data-testid="new-job-hour-input"
                />
              </div>
              <div>
                <label className="block text-xs text-slate-500 mb-1">Dakika</label>
                <input
                  type="number"
                  min="0" max="59"
                  value={newJob.minute}
                  onChange={e => setNewJob(p => ({ ...p, minute: e.target.value }))}
                  className="border border-slate-200 rounded-lg px-3 py-2 text-sm w-20 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  data-testid="new-job-minute-input"
                />
              </div>
              <div className="flex gap-2">
                <Button type="submit" size="sm" className="bg-blue-600 hover:bg-blue-700 text-white" disabled={addLoading} data-testid="save-new-job-btn">
                  {addLoading ? "Ekleniyor..." : "Kaydet"}
                </Button>
                <Button type="button" variant="outline" size="sm" onClick={() => setShowAddForm(false)}>
                  İptal
                </Button>
              </div>
            </form>
          </div>
        )}

        {/* Jobs Table */}
        <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
          <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between">
            <h2 className="font-semibold text-slate-700 flex items-center gap-2">
              <Clock className="w-4 h-4 text-slate-400" /> Zamanlanmış Görevler
            </h2>
            <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${schedulerRunning ? "bg-emerald-50 text-emerald-700" : "bg-red-50 text-red-700"}`}>
              {schedulerRunning ? "Scheduler Çalışıyor" : "Scheduler Durdu"}
            </span>
          </div>

          {loading ? (
            <div className="py-16 text-center text-slate-400 text-sm">Yükleniyor...</div>
          ) : jobs.length === 0 ? (
            <div className="py-16 text-center text-slate-400 text-sm">Otomasyon bulunamadı</div>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-slate-50 text-xs text-slate-500 uppercase tracking-wide">
                  <th className="px-5 py-3 text-left font-medium">Görev Adı</th>
                  <th className="px-4 py-3 text-left font-medium">Tip</th>
                  <th className="px-4 py-3 text-left font-medium">Saat (TR)</th>
                  <th className="px-4 py-3 text-left font-medium">Durum</th>
                  <th className="px-4 py-3 text-left font-medium">Sonraki Çalışma</th>
                  <th className="px-4 py-3 text-left font-medium">İşlemler</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {jobs.map(job => (
                  <tr key={job.id} className="hover:bg-slate-50 transition-colors" data-testid={`job-row-${job.id}`}>
                    <td className="px-5 py-3.5">
                      <div className="font-medium text-slate-800 leading-tight">{job.name}</div>
                      {!job.is_system && (
                        <span className="text-xs text-slate-400 mt-0.5 block">Özel otomasyon</span>
                      )}
                    </td>
                    <td className="px-4 py-3.5">
                      <TypeBadge label={job.type_label} />
                    </td>
                    <td className="px-4 py-3.5 font-mono text-slate-700">
                      {job.hour !== "?" ? `${String(job.hour).padStart(2,"0")}:${String(job.minute).padStart(2,"0")}` : "—"}
                    </td>
                    <td className="px-4 py-3.5">
                      <StatusBadge isPaused={job.is_paused} />
                    </td>
                    <td className="px-4 py-3.5 text-slate-500 text-xs">
                      {job.is_paused ? <span className="text-amber-600">Duraklatıldı</span> : (job.next_run || "—")}
                    </td>
                    <td className="px-4 py-3.5">
                      <div className="flex items-center gap-1.5">
                        {job.is_paused ? (
                          <button
                            onClick={() => handleResume(job.id)}
                            disabled={actionLoading[job.id]}
                            className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-medium bg-emerald-50 text-emerald-700 hover:bg-emerald-100 border border-emerald-200 transition-colors disabled:opacity-50"
                            data-testid={`resume-btn-${job.id}`}
                          >
                            <Play className="w-3 h-3" /> Başlat
                          </button>
                        ) : (
                          <button
                            onClick={() => handlePause(job.id)}
                            disabled={actionLoading[job.id]}
                            className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-medium bg-amber-50 text-amber-700 hover:bg-amber-100 border border-amber-200 transition-colors disabled:opacity-50"
                            data-testid={`pause-btn-${job.id}`}
                          >
                            <Pause className="w-3 h-3" /> Durdur
                          </button>
                        )}
                        {!job.is_system && (
                          <button
                            onClick={() => handleDelete(job.id)}
                            disabled={actionLoading[job.id]}
                            className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-medium bg-red-50 text-red-600 hover:bg-red-100 border border-red-200 transition-colors disabled:opacity-50"
                            data-testid={`delete-btn-${job.id}`}
                          >
                            <Trash2 className="w-3 h-3" /> Sil
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Info box */}
        <div className="bg-blue-50 border border-blue-200 rounded-xl px-5 py-4 text-sm text-blue-800">
          <strong>Bilgi:</strong> Sistem otomasyonları (00:00, 00:15, 00:30, 00:45, 03:00, 10:00, 14:00, 18:00) duraklatılabilir ancak silinemez.
          Özel eklenen otomasyonlar tamamen yönetilebilir ve sunucu yeniden başladığında otomatik yüklenir.
        </div>
      </div>
    </Layout>
  );
}
