"use client";

import { createContext, useContext, useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { fetchMe } from "@/services/stats.service";
import { getToken, setToken, removeToken } from "@/lib/utils";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  const loadUser = useCallback(async () => {
    const token = getToken();
    if (!token) {
      setUser(null);
      setLoading(false);
      return;
    }
    try {
      const me = await fetchMe();
      setUser(me);
    } catch {
      removeToken();
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadUser();
  }, [loadUser]);

  const login = useCallback((token) => {
    setToken(token);
    loadUser();
  }, [loadUser]);

  const logout = useCallback(() => {
    removeToken();
    setUser(null);
    router.push("/login");
  }, [router]);

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, reload: loadUser }}>
      {children}
    </AuthContext.Provider>
  );
}

/**
 * Hook to access auth state.
 * Returns { user, loading, login, logout, reload }.
 */
export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
