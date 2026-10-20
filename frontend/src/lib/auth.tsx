import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createContext, useContext, type ReactNode } from "react";
import { api, ApiError, setSessionHint } from "./api";
import type { Me } from "./types";

interface AuthState { me: Me | null; loading: boolean; refresh: () => Promise<unknown>; logout: () => Promise<void> }
const Ctx = createContext<AuthState>({ me: null, loading: true, refresh: async () => {}, logout: async () => {} });

export function AuthProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient();
  const q = useQuery({
    queryKey: ["me"],
    retry: false,
    staleTime: 60_000,
    queryFn: async () => {
      try { return await api<Me>("/me"); }
      catch (e) { if (e instanceof ApiError && e.status === 401) return null; throw e; }
    },
  });
  const logout = async () => {
    try { await api("/auth/logout", { method: "POST" }); } finally {
      setSessionHint(false);
      qc.clear();
      await qc.invalidateQueries({ queryKey: ["me"] });
    }
  };
  return <Ctx.Provider value={{ me: q.data ?? null, loading: q.isLoading, refresh: () => qc.invalidateQueries({ queryKey: ["me"] }), logout }}>{children}</Ctx.Provider>;
}
export const useAuth = () => useContext(Ctx);
