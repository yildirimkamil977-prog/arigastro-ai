import { createContext, useContext, useState, useEffect, useCallback } from "react";
import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  const checkAuth = useCallback(async () => {
    try {
      const token = localStorage.getItem("token");
      if (!token) { setLoading(false); return; }
      const { data } = await axios.get(`${API}/auth/me`, {
        headers: { Authorization: `Bearer ${token}` },
        withCredentials: true,
      });
      setUser(data);
    } catch {
      localStorage.removeItem("token");
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { checkAuth(); }, [checkAuth]);

  const login = async (username, password) => {
    const { data } = await axios.post(`${API}/auth/login`, { username, password }, { withCredentials: true });
    localStorage.setItem("token", data.token);
    setUser(data);
    return data;
  };

  const logout = async () => {
    try {
      const token = localStorage.getItem("token");
      await axios.post(`${API}/auth/logout`, {}, {
        headers: { Authorization: `Bearer ${token}` },
        withCredentials: true,
      });
    } catch { /* ignore */ }
    localStorage.removeItem("token");
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);

export function getAuthHeaders() {
  const token = localStorage.getItem("token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export { API };
