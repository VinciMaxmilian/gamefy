import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export const cn = (...inputs: ClassValue[]) => twMerge(clsx(inputs));

export function formatPrice(cents: number | null, currency = "USD"): string {
  if (cents === null) return "—";
  if (cents === 0) return "Free";
  return new Intl.NumberFormat("en-US", { style: "currency", currency }).format(cents / 100);
}

export function hoursLabel(h: number | null): string | null {
  if (!h) return null;
  return h < 1 ? "<1h" : `~${Math.round(h)}h`;
}

/** Deterministic cover gradient so the UI never needs third-party art. */
export function coverGradient(seed: string): string {
  let h = 0;
  for (let i = 0; i < seed.length; i++) h = (h * 31 + seed.charCodeAt(i)) >>> 0;
  const a = h % 360;
  const b = (a + 40 + (h >> 8) % 80) % 360;
  return `linear-gradient(135deg, hsl(${a} 62% 34%), hsl(${b} 70% 18%))`;
}

export const safeImageUrl = (u: string | null): string | null => {
  try {
    return u && new URL(u).protocol === "https:" ? u : null;
  } catch {
    return null;
  }
};

const ACRONYMS = new Set(["rpg", "fps", "rts", "pc", "ps4", "ps5", "mmo", "moba", "4x", "2d", "3d"]);
export const label = (s: string) => s.replace(/-/g, " ").split(" ").map((w) => (ACRONYMS.has(w.toLowerCase()) ? w.toUpperCase() : w)).join(" ");
