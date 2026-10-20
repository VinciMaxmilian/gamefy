import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

export type ThemeMode = "light" | "dark" | "system";
const KEY = "gf_theme";

const read = (): ThemeMode => {
  try { const v = localStorage.getItem(KEY); return v === "light" || v === "system" ? v : "dark"; } catch { return "dark"; }
};
const prefersDark = () => window.matchMedia("(prefers-color-scheme: dark)").matches;

function apply(mode: ThemeMode) {
  const dark = mode === "dark" || (mode === "system" && prefersDark());
  document.documentElement.setAttribute("data-theme", dark ? "dark" : "light");
  document.querySelector('meta[name="theme-color"]')?.setAttribute("content", dark ? "#000000" : "#f5f5f7");
}

const Ctx = createContext<{ mode: ThemeMode; setMode: (m: ThemeMode) => void }>({ mode: "dark", setMode: () => {} });

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [mode, setModeState] = useState<ThemeMode>(read);
  useEffect(() => {
    apply(mode);
    if (mode !== "system") return;
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const on = () => apply("system");
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, [mode]);
  const setMode = (m: ThemeMode) => {
    try { localStorage.setItem(KEY, m); } catch { /* storage unavailable: theme still applies for this visit */ }
    setModeState(m);
  };
  return <Ctx.Provider value={{ mode, setMode }}>{children}</Ctx.Provider>;
}
export const useTheme = () => useContext(Ctx);
