import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "./context/AuthContext";
import { Toaster } from "./components/ui/sonner";
import Layout from "./components/Layout";
import LoginPage from "./pages/LoginPage";
import DashboardPage from "./pages/DashboardPage";
import CategoriesPage from "./pages/CategoriesPage";
import ProductsPage from "./pages/ProductsPage";
import PriceTrackingPage from "./pages/PriceTrackingPage";
import SeoGeneratorPage from "./pages/SeoGeneratorPage";
import "./App.css";

function ProtectedRoute({ children }) {
  const { user, loading } = useAuth();
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="flex flex-col items-center gap-3">
          <div className="w-10 h-10 rounded-md bg-amber-500 flex items-center justify-center animate-pulse">
            <span className="text-black font-bold text-lg">A</span>
          </div>
          <p className="text-sm text-slate-500">Yukleniyor...</p>
        </div>
      </div>
    );
  }
  if (!user) return <Navigate to="/login" replace />;
  return <Layout>{children}</Layout>;
}

function PublicRoute({ children }) {
  const { user, loading } = useAuth();
  if (loading) return null;
  if (user) return <Navigate to="/dashboard" replace />;
  return children;
}

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<PublicRoute><LoginPage /></PublicRoute>} />
          <Route path="/dashboard" element={<ProtectedRoute><DashboardPage /></ProtectedRoute>} />
          <Route path="/categories" element={<ProtectedRoute><CategoriesPage /></ProtectedRoute>} />
          <Route path="/products" element={<ProtectedRoute><ProductsPage /></ProtectedRoute>} />
          <Route path="/price-tracking" element={<ProtectedRoute><PriceTrackingPage /></ProtectedRoute>} />
          <Route path="/seo" element={<ProtectedRoute><SeoGeneratorPage /></ProtectedRoute>} />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </BrowserRouter>
      <Toaster position="top-right" richColors />
    </AuthProvider>
  );
}

export default App;
