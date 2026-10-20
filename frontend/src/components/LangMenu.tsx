import { Check, Globe } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { LANGS, useI18n } from "@/lib/i18n";
import { Button } from "./ui/button";

export function LangMenu() {
  const { lang, setLang, t } = useI18n();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent | KeyboardEvent) => {
      if (e instanceof KeyboardEvent ? e.key === "Escape" : !ref.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", close); document.addEventListener("keydown", close);
    return () => { document.removeEventListener("mousedown", close); document.removeEventListener("keydown", close); };
  }, [open]);
  return (
    <div ref={ref} className="relative">
      <Button variant="ghost" size="icon" aria-label={t("lang.label")} aria-haspopup="menu" aria-expanded={open} onClick={() => setOpen((o) => !o)}><Globe className="size-5" /></Button>
      {open && (
        <div role="menu" aria-label={t("lang.label")} className="material absolute right-0 mt-2 w-52 rounded-lg border border-separator p-1.5 shadow-pop">
          {LANGS.map(({ code, name }) => (
            <button key={code} role="menuitemradio" aria-checked={lang === code} lang={code} onClick={() => { setLang(code); setOpen(false); }}
              className="flex w-full items-center gap-2.5 rounded-md px-3 py-2 text-left text-[15px] hover:bg-surface-2">{name}{lang === code && <Check className="ml-auto size-4 text-accent" />}</button>
          ))}
        </div>
      )}
    </div>
  );
}
