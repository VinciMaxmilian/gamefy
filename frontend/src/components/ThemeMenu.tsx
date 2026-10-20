import { Check, Moon, Monitor, Sun } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useTheme, type ThemeMode } from "@/lib/theme";
import { Button } from "./ui/button";

const OPTIONS: { mode: ThemeMode; label: string; Icon: typeof Sun }[] = [
  { mode: "light", label: "Light", Icon: Sun },
  { mode: "dark", label: "Dark", Icon: Moon },
  { mode: "system", label: "System", Icon: Monitor },
];

export function ThemeMenu() {
  const { mode, setMode } = useTheme();
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
  const Current = OPTIONS.find((o) => o.mode === mode)!.Icon;
  return (
    <div ref={ref} className="relative">
      <Button variant="ghost" size="icon" aria-label="Appearance" aria-haspopup="menu" aria-expanded={open} onClick={() => setOpen((o) => !o)}><Current className="size-5" /></Button>
      {open && (
        <div role="menu" aria-label="Appearance" className="material absolute right-0 mt-2 w-44 rounded-lg border border-separator p-1.5 shadow-pop">
          {OPTIONS.map(({ mode: m, label, Icon }) => (
            <button key={m} role="menuitemradio" aria-checked={mode === m} onClick={() => { setMode(m); setOpen(false); }}
              className="flex w-full items-center gap-2.5 rounded-md px-3 py-2 text-left text-[15px] hover:bg-surface-2"><Icon className="size-4" />{label}{mode === m && <Check className="ml-auto size-4 text-accent" />}</button>
          ))}
        </div>
      )}
    </div>
  );
}
