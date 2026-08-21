import React, { useState, useEffect, useCallback } from "react";

const API = process.env.REACT_APP_BACKEND_URL;

export default function FilterManagementPage() {
  const [categories, setCategories] = useState([]);
  const [selectedCategory, setSelectedCategory] = useState("");
  const [job, setJob] = useState(null);
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(false);
  const [editFilters, setEditFilters] = useState([]);
  const [newFilterName, setNewFilterName] = useState("");
  const [polling, setPolling] = useState(false);

  const token = localStorage.getItem("token");
  const headers = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };

  useEffect(() => {
    fetch(`${API}/api/filters/categories`, { headers }).then(r => r.json()).then(d => setCategories(d.categories || []));
    fetch(`${API}/api/filters/jobs`, { headers }).then(r => r.json()).then(d => setJobs(d.jobs || []));
  }, []);

  // Poll job status
  const pollJob = useCallback((jobId) => {
    setPolling(true);
    const interval = setInterval(async () => {
      try {
        const r = await fetch(`${API}/api/filters/job/${jobId}`, { headers });
        const data = await r.json();
        setJob(data);
        if (data.status === "awaiting_review") {
          setEditFilters(data.suggested_filters || []);
          clearInterval(interval);
          setPolling(false);
        } else if (data.status === "completed" || data.status === "error") {
          clearInterval(interval);
          setPolling(false);
        }
      } catch { clearInterval(interval); setPolling(false); }
    }, 3000);
    return () => clearInterval(interval);
  }, []);

  const startAnalysis = async () => {
    if (!selectedCategory) return;
    setLoading(true);
    setJob(null);
    setEditFilters([]);
    try {
      const r = await fetch(`${API}/api/filters/analyze-category`, {
        method: "POST", headers, body: JSON.stringify({ category: selectedCategory }),
      });
      const data = await r.json();
      setJob(data);
      pollJob(data.job_id);
    } catch (e) { alert("Hata: " + e.message); }
    setLoading(false);
  };

  const startExecution = async () => {
    if (!job?.job_id || editFilters.length === 0) return;
    setLoading(true);
    try {
      const r = await fetch(`${API}/api/filters/execute/${job.job_id}`, {
        method: "POST", headers,
        body: JSON.stringify({ filters: editFilters }),
      });
      const data = await r.json();
      setJob(prev => ({ ...prev, ...data }));
      pollJob(job.job_id);
    } catch (e) { alert("Hata: " + e.message); }
    setLoading(false);
  };

  const removeFilter = (idx) => setEditFilters(f => f.filter((_, i) => i !== idx));

  const addFilter = () => {
    if (!newFilterName.trim()) return;
    setEditFilters(f => [...f, { name: newFilterName.trim(), type: "MULTIPLE_CHOICE", sample_values: [] }]);
    setNewFilterName("");
  };

  const resumeJob = (j) => {
    setJob(j);
    setSelectedCategory(j.category);
    if (j.status === "awaiting_review") setEditFilters(j.suggested_filters || []);
    if (j.status === "executing") pollJob(j.job_id);
    if (j.status === "completed" || j.status === "error") {
      fetch(`${API}/api/filters/job/${j.job_id}`, { headers }).then(r => r.json()).then(setJob);
    }
  };

  const statusColors = {
    analyzing: "bg-blue-100 text-blue-700",
    awaiting_review: "bg-yellow-100 text-yellow-700",
    executing: "bg-indigo-100 text-indigo-700",
    completed: "bg-emerald-100 text-emerald-700",
    error: "bg-red-100 text-red-700",
  };
  const statusLabels = {
    analyzing: "Analiz Ediliyor...",
    awaiting_review: "İncelemeniz Bekleniyor",
    executing: "Uygulanıyor...",
    completed: "Tamamlandı",
    error: "Hata",
  };

  return (
    <div className="p-6 max-w-6xl mx-auto" data-testid="filter-management-page">
      <h1 className="text-2xl font-bold text-slate-800 mb-1">Filtre Yönetimi</h1>
      <p className="text-slate-500 mb-6">AI ile ürün özelliklerini otomatik doldur</p>

      {/* Category selector */}
      <div className="bg-white rounded-xl border p-5 mb-6">
        <h2 className="font-semibold text-slate-700 mb-3">1. Kategori Seçin</h2>
        <div className="flex gap-3 items-end">
          <div className="flex-1">
            <select
              data-testid="category-select"
              value={selectedCategory}
              onChange={e => setSelectedCategory(e.target.value)}
              className="w-full h-10 px-3 border rounded-lg text-sm"
            >
              <option value="">Kategori seçin...</option>
              {categories.map(c => (
                <option key={c.name} value={c.name}>{c.name} ({c.product_count} ürün)</option>
              ))}
            </select>
          </div>
          <button
            data-testid="analyze-btn"
            onClick={startAnalysis}
            disabled={!selectedCategory || loading || polling}
            className="h-10 px-5 bg-slate-800 text-white rounded-lg text-sm font-medium disabled:opacity-40 hover:bg-slate-700"
          >
            {loading ? "Başlatılıyor..." : "Analiz Et"}
          </button>
        </div>
      </div>

      {/* Job status */}
      {job && (
        <div className="bg-white rounded-xl border p-5 mb-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold text-slate-700">
              {job.category} — <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${statusColors[job.status] || ""}`}>
                {statusLabels[job.status] || job.status}
              </span>
            </h2>
            {job.total_products > 0 && job.status === "executing" && (
              <span className="text-sm text-slate-500">{job.processed || 0}/{job.total_products} ürün</span>
            )}
          </div>

          {/* Progress bar */}
          {(job.status === "analyzing" || job.status === "executing") && (
            <div className="w-full bg-slate-100 rounded-full h-2 mb-4">
              <div
                className="bg-indigo-500 h-2 rounded-full transition-all duration-500"
                style={{ width: `${job.total_products ? Math.round(((job.processed || 0) / job.total_products) * 100) : 0}%` }}
              />
            </div>
          )}

          {job.status === "error" && (
            <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg p-3 text-sm">{job.error}</div>
          )}

          {/* Filter review */}
          {job.status === "awaiting_review" && (
            <div>
              <h3 className="font-medium text-slate-600 mb-3">2. Önerilen Filtreleri İnceleyin</h3>
              <p className="text-xs text-slate-400 mb-4">İstemediğiniz filtreleri çıkarın, eksik olanları ekleyin. Sonra "Uygula" butonuna tıklayın.</p>

              <div className="space-y-2 mb-4">
                {editFilters.map((f, i) => (
                  <div key={i} className="flex items-center gap-2 bg-slate-50 rounded-lg px-3 py-2">
                    <div className="flex-1">
                      <span className="font-medium text-sm text-slate-700">{f.name}</span>
                      {f.sample_values?.length > 0 && (
                        <span className="text-xs text-slate-400 ml-2">
                          Örnek: {f.sample_values.slice(0, 5).join(", ")}
                        </span>
                      )}
                    </div>
                    <button
                      onClick={() => removeFilter(i)}
                      className="text-red-400 hover:text-red-600 text-sm px-2"
                      data-testid={`remove-filter-${i}`}
                    >
                      Çıkar
                    </button>
                  </div>
                ))}
              </div>

              <div className="flex gap-2 mb-4">
                <input
                  type="text"
                  value={newFilterName}
                  onChange={e => setNewFilterName(e.target.value)}
                  onKeyDown={e => e.key === "Enter" && addFilter()}
                  placeholder="Yeni filtre adı..."
                  className="flex-1 h-9 px-3 border rounded-lg text-sm"
                  data-testid="new-filter-input"
                />
                <button
                  onClick={addFilter}
                  className="h-9 px-4 bg-slate-100 text-slate-700 rounded-lg text-sm hover:bg-slate-200"
                  data-testid="add-filter-btn"
                >
                  Ekle
                </button>
              </div>

              <button
                onClick={startExecution}
                disabled={editFilters.length === 0 || loading}
                className="h-10 px-6 bg-emerald-600 text-white rounded-lg text-sm font-medium disabled:opacity-40 hover:bg-emerald-500"
                data-testid="execute-btn"
              >
                {editFilters.length} Filtre ile Uygula
              </button>
            </div>
          )}

          {/* Results */}
          {(job.status === "completed" || (job.status === "executing" && job.results?.length > 0)) && (
            <div>
              <h3 className="font-medium text-slate-600 mb-3">Sonuçlar</h3>
              <div className="max-h-96 overflow-y-auto border rounded-lg">
                <table className="w-full text-sm">
                  <thead className="bg-slate-50 sticky top-0">
                    <tr>
                      <th className="text-left p-2 font-medium text-slate-600">Ürün</th>
                      <th className="text-left p-2 font-medium text-slate-600">Eklenen Filtreler</th>
                      <th className="text-left p-2 font-medium text-slate-600">Durum</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(job.results || []).map((r, i) => (
                      <tr key={i} className="border-t">
                        <td className="p-2 text-slate-700">{r.product?.substring(0, 45)}</td>
                        <td className="p-2">
                          {r.filters?.length > 0
                            ? r.filters.map((f, j) => (
                                <span key={j} className="inline-block bg-indigo-50 text-indigo-700 px-2 py-0.5 rounded text-xs mr-1 mb-1">
                                  {f.name}: {f.value}
                                </span>
                              ))
                            : <span className="text-slate-400 text-xs">—</span>
                          }
                        </td>
                        <td className="p-2">
                          <span className={`text-xs ${r.status === "OK" ? "text-emerald-600" : "text-red-500"}`}>
                            {r.status}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Previous jobs */}
      {jobs.length > 0 && (
        <div className="bg-white rounded-xl border p-5">
          <h2 className="font-semibold text-slate-700 mb-3">Geçmiş İşlemler</h2>
          <div className="space-y-2">
            {jobs.map(j => (
              <div
                key={j.job_id}
                onClick={() => resumeJob(j)}
                className="flex items-center justify-between p-3 bg-slate-50 rounded-lg cursor-pointer hover:bg-slate-100"
              >
                <div>
                  <span className="font-medium text-sm text-slate-700">{j.category}</span>
                  <span className="text-xs text-slate-400 ml-2">{j.total_products} ürün</span>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-xs text-slate-400">
                    {j.processed || 0}/{j.total_products}
                  </span>
                  <span className={`px-2 py-0.5 rounded text-xs font-medium ${statusColors[j.status] || ""}`}>
                    {statusLabels[j.status] || j.status}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
