import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
import { currentLocale, termLabel, translate } from "./i18n";

export const cn = (...inputs: ClassValue[]) => twMerge(clsx(inputs));

export function formatPrice(cents: number | null, currency = "USD"): string {
  if (cents === null) return "—";
  if (cents === 0) return translate("price.free");
  return new Intl.NumberFormat(currentLocale(), { style: "currency", currency }).format(cents / 100);
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

/** Display name for a catalog slug (genre, tag, mode) in the current language. */
export const label = termLabel;
