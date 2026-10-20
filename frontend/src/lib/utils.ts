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

/** Deterministic, quiet placeholder tint (a whisper of hue over the surface color) so missing art never looks loud. */
export function coverTint(seed: string): string {
  let h = 0;
  for (let i = 0; i < seed.length; i++) h = (h * 31 + seed.charCodeAt(i)) >>> 0;
  return `color-mix(in srgb, hsl(${h % 360} 28% 50%) 11%, var(--surface-2))`;
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
