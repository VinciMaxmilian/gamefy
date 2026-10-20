export interface GameCard {
  slug: string; title: string; summary: string; cover_url: string | null;
  price_cents: number | null; currency: string; genres: string[]; tags: string[]; platforms: string[];
  rating: number | null; avg_duration_hours: number | null; release_date: string | null;
}
export interface Compatibility { verdict: "recommended" | "partial" | "minimum" | "below_minimum" | "unknown"; reasons: string[] }
export interface StoreOffer { store: string; name: string; url: string; price_cents: number | null; normal_price_cents: number | null; discount_percent: number; currency: string; updated_at: string }
export interface GameDetail extends GameCard {
  stores: StoreOffer[];
  description: string; developer: string | null; features: string[]; difficulty: number | null;
  rating_count: number; req: { min?: Record<string, number>; rec?: Record<string, number> }; compatibility: Compatibility | null;
}
export interface Recommendation { game: GameCard; score: number; reasons: string[]; compatibility: Compatibility | null }
export interface Page { items: GameCard[]; total: number; limit: number; offset: number }
export interface Me {
  email: string | null; display_name: string | null; plan: "free" | "premium"; role: "user" | "admin";
  limits: { smart_search_per_day: number; ai_chat_per_day: number }; usage: { smart_search_today: number };
}
export interface SmartResult {
  query: string; remaining_today: number; items: Recommendation[];
  understood: { genres: string[]; tags: string[]; features: string[]; platforms: string[]; max_price_cents: number | null; max_duration_hours: number | null; similar_to: string[] };
}
export interface TasteItem { key: string; label: string; kind: string; weight: number }
export interface Facets { [k: string]: { value: string; count: number }[] }
export interface LibraryEntry { game: GameCard; status: string; playtime_minutes: number }
