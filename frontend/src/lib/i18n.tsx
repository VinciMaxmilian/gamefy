import { createContext, Fragment, useContext, useEffect, useState, type ReactNode } from "react";
import en, { type Key } from "./locales/en";
import ptBR from "./locales/pt-BR";

export type Lang = "en" | "pt-BR";
export const LANGS: { code: Lang; name: string }[] = [{ code: "en", name: "English" }, { code: "pt-BR", name: "Português (Brasil)" }];
const DICTS: Record<Lang, Record<Key, string>> = { en, "pt-BR": ptBR };
const STORAGE = "gf_lang";
type Params = Record<string, string | number>;

function detect(): Lang {
  try {
    const saved = localStorage.getItem(STORAGE);
    if (saved === "en" || saved === "pt-BR") return saved;
  } catch { /* storage unavailable: fall back to the browser language */ }
  return (navigator.languages ?? [navigator.language]).some((l) => l?.toLowerCase().startsWith("pt")) ? "pt-BR" : "en";
}

let current: Lang = detect();
export const currentLang = () => current;
export const currentLocale = () => (current === "pt-BR" ? "pt-BR" : "en-US");

/** Translate outside React (formatters). Components should use useI18n(), which re-renders on language change. */
export function translate(key: Key, params?: Params, lang: Lang = current): string {
  let s = DICTS[lang][key] ?? en[key] ?? key;
  if (s.includes("|") && params && "n" in params) {
    const [one, many] = s.split("|");
    s = Number(params.n) === 1 ? one : many;
  }
  return params ? s.replace(/\{(\w+)\}/g, (_, k) => String(params[k] ?? `{${k}}`)) : s;
}

/** Look up a server-provided English message (error detail) in the dictionary; unknown messages are shown as-is. */
export function translateServer(message: string): string {
  const key = `err.${message.replace(/^Value error, /, "")}` as Key;
  return key in en ? translate(key) : message;
}

interface Ctx { lang: Lang; setLang: (l: Lang) => void; t: (key: Key, params?: Params) => string }
const I18nContext = createContext<Ctx>({ lang: current, setLang: () => {}, t: (k, p) => translate(k, p) });

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(current);
  current = lang;
  useEffect(() => { document.documentElement.lang = lang === "pt-BR" ? "pt-BR" : "en"; }, [lang]);
  const setLang = (l: Lang) => {
    try { localStorage.setItem(STORAGE, l); } catch { /* the choice still applies for this visit */ }
    current = l;
    setLangState(l);
  };
  // Re-mounting on change guarantees that every string, including those produced by plain formatter functions, updates.
  return <I18nContext.Provider value={{ lang, setLang, t: (k, p) => translate(k, p, lang) }}><Fragment key={lang}>{children}</Fragment></I18nContext.Provider>;
}
export const useI18n = () => useContext(I18nContext);

// Display names for catalog vocabulary (genres, tags, modes). Unlisted slugs are shown prettified.
const TERMS_PT: Record<string, string> = {
  rpg: "RPG", action: "Ação", adventure: "Aventura", shooter: "Tiro", strategy: "Estratégia", "turn-based": "Por turnos", rts: "RTS", simulation: "Simulação",
  sports: "Esportes", racing: "Corrida", puzzle: "Quebra-cabeça", platformer: "Plataforma", fighting: "Luta", indie: "Indie", arcade: "Arcade", tactical: "Tático",
  "point-and-click": "Point-and-click", music: "Música", "card-game": "Jogo de cartas", "visual-novel": "Visual novel", trivia: "Perguntas e respostas", moba: "MOBA",
  "sci-fi": "Ficção científica", fantasy: "Fantasia", horror: "Terror", survival: "Sobrevivência", "open-world": "Mundo aberto", stealth: "Furtividade", humor: "Humor",
  historical: "Histórico", sandbox: "Sandbox", party: "Festa", mystery: "Mistério", thriller: "Suspense", "story-rich": "Rico em história", war: "Guerra", family: "Família",
  "first-person": "Primeira pessoa", "third-person": "Terceira pessoa", "side-view": "Visão lateral", "bird-view-isometric": "Visão isométrica", text: "Texto",
  "single-player": "Um jogador", multiplayer: "Multijogador", "co-op": "Cooperativo", "split-screen": "Tela dividida", mmo: "MMO", "battle-royale": "Battle royale",
  "controller-support": "Suporte a controle", exploration: "Exploração", relaxing: "Relaxante", cozy: "Aconchegante", difficult: "Difícil", atmospheric: "Atmosférico",
  crafting: "Criação", building: "Construção", "pixel-art": "Pixel art", "choices-matter": "Escolhas importam", metroidvania: "Metroidvania", soulslike: "Soulslike",
  roguelike: "Roguelike", procedural: "Procedural", replayable: "Rejogável", bosses: "Chefes", short: "Curto", "no-combat": "Sem combate", emotional: "Emocional",
  "party-based": "Em grupo", deckbuilding: "Montagem de deck", "dark-fantasy": "Fantasia sombria", "fast-paced": "Ritmo acelerado", competitive: "Competitivo",
};
const ACRONYMS = new Set(["rpg", "fps", "rts", "pc", "ps4", "ps5", "mmo", "moba", "4x", "2d", "3d"]);
const SPECIAL: Record<string, string> = { "co-op": "Co-op", xbox: "Xbox", switch: "Switch", mac: "Mac", linux: "Linux", ps4: "PS4", ps5: "PS5" };
const cap = (w: string) => (ACRONYMS.has(w.toLowerCase()) ? w.toUpperCase() : w.charAt(0).toUpperCase() + w.slice(1));
export function termLabel(slug: string): string {
  if (current === "pt-BR" && TERMS_PT[slug]) return TERMS_PT[slug];
  return SPECIAL[slug] ?? slug.replace(/-/g, " ").split(" ").map(cap).join(" ");
}

/** Render a language-neutral reason ({code, args}) produced by the server. */
export function reasonText(r: { code: string; args: string[] }): string {
  const key = `reason.${r.code}` as Key;
  if (!(key in en)) return r.code;
  const hwName = (a: string) => ("hw." + a in en ? translate(`hw.${a}` as Key) : a);
  switch (r.code) {
    case "taste": case "genre_asked": return translate(key, { args: r.args.map(termLabel).join(", ") });
    case "duration": return translate(key, { h: r.args[0] ?? "" });
    case "below_min_field": case "below_rec_field": return translate(key, { field: hwName(r.args[0] ?? "") });
    case "add_fields": return translate(key, { fields: r.args.map(hwName).join(", ") });
    default: return translate(key);
  }
}
