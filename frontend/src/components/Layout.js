import { useState } from "react";
import { useAuth } from "../context/AuthContext";
import { useNavigate, useLocation, Link } from "react-router-dom";
import { Button } from "./ui/button";
import {
  LayoutDashboard, Package, Tags, TrendingDown, FileText,
  ChevronLeft, ChevronRight, LogOut, Menu, Sparkles
} from "lucide-react";

const navItems = [
  { path: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { path: "/categories", label: "Kategoriler", icon: Tags },
  { path: "/products", label: "Urunler", icon: Package },
  { path: "/price-tracking", label: "Fiyat Takip", icon: TrendingDown },
  { path: "/seo", label: "SEO Uretici", icon: FileText },
];

export default function Layout({ children }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  const handleLogout = async () => {
    await logout();
    navigate("/login");
  };

  return (
    <div className="min-h-screen flex bg-background" data-testid="app-layout">
      {/* Sidebar */}
      <aside
        data-testid="sidebar"
        className={`fixed inset-y-0 left-0 z-40 bg-white border-r border-slate-200 flex flex-col transition-all duration-200 ease-out
          ${collapsed ? "w-16" : "w-60"}
          ${mobileOpen ? "translate-x-0" : "-translate-x-full"} lg:translate-x-0`}
      >
        {/* Logo */}
        <div className={`flex items-center h-16 border-b border-slate-200 px-4 ${collapsed ? "justify-center" : "gap-3"}`}>
          <div className="w-8 h-8 rounded-md bg-amber-500 flex items-center justify-center flex-shrink-0">
            <Sparkles className="h-4 w-4 text-black" />
          </div>
          {!collapsed && (
            <div className="overflow-hidden">
              <p className="text-sm font-bold tracking-tight text-slate-900 font-heading truncate">ARI AI</p>
              <p className="text-[10px] uppercase tracking-wider text-slate-500 truncate">Urun Gelistirme</p>
            </div>
          )}
        </div>

        {/* Nav */}
        <nav className="flex-1 py-4 px-2 space-y-1">
          {navItems.map((item) => {
            const isActive = location.pathname === item.path;
            return (
              <Link
                key={item.path}
                to={item.path}
                data-testid={`nav-${item.path.slice(1)}`}
                onClick={() => setMobileOpen(false)}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-md text-sm font-medium transition-all duration-150
                  ${isActive
                    ? "bg-slate-900 text-white shadow-sm"
                    : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
                  }
                  ${collapsed ? "justify-center" : ""}`}
              >
                <item.icon className="h-4 w-4 flex-shrink-0" />
                {!collapsed && <span className="truncate">{item.label}</span>}
              </Link>
            );
          })}
        </nav>

        {/* Footer */}
        <div className="border-t border-slate-200 p-3 space-y-2">
          {!collapsed && (
            <div className="px-2 py-1">
              <p className="text-xs font-medium text-slate-700 truncate">{user?.name || user?.username}</p>
              <p className="text-[10px] text-slate-500">{user?.role}</p>
            </div>
          )}
          <div className={`flex ${collapsed ? "flex-col items-center gap-2" : "items-center gap-2"}`}>
            <Button
              variant="ghost"
              size="sm"
              data-testid="logout-button"
              onClick={handleLogout}
              className="text-slate-500 hover:text-red-600 hover:bg-red-50 flex-1"
            >
              <LogOut className="h-4 w-4" />
              {!collapsed && <span className="ml-2 text-xs">Cikis</span>}
            </Button>
            <Button
              variant="ghost"
              size="icon"
              data-testid="sidebar-toggle"
              onClick={() => setCollapsed(!collapsed)}
              className="text-slate-400 hover:text-slate-600 hidden lg:flex h-8 w-8"
            >
              {collapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
            </Button>
          </div>
        </div>
      </aside>

      {/* Mobile overlay */}
      {mobileOpen && (
        <div className="fixed inset-0 bg-black/30 z-30 lg:hidden" onClick={() => setMobileOpen(false)} />
      )}

      {/* Main */}
      <main className={`flex-1 transition-all duration-200 ${collapsed ? "lg:ml-16" : "lg:ml-60"}`}>
        {/* Top bar */}
        <header className="h-14 border-b border-slate-200 bg-white flex items-center px-4 gap-4 sticky top-0 z-20">
          <Button
            variant="ghost"
            size="icon"
            data-testid="mobile-menu-button"
            onClick={() => setMobileOpen(!mobileOpen)}
            className="lg:hidden h-8 w-8 text-slate-600"
          >
            <Menu className="h-5 w-5" />
          </Button>
          <h1 className="text-sm font-semibold text-slate-900 font-heading tracking-tight">
            {navItems.find((n) => n.path === location.pathname)?.label || "ARI AI"}
          </h1>
        </header>
        <div className="p-4 md:p-6">
          {children}
        </div>
      </main>
    </div>
  );
}
