import { Check } from "lucide-react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";

const PLANS = [
  { id: "guest", name: "plan.guest", price: "plan.free", items: ["premium.g1", "premium.g2"] },
  { id: "free", name: "plan.free_account", price: "plan.free", items: ["premium.f1", "premium.f2", "premium.f3", "premium.f4", "premium.f5"] },
  { id: "premium", name: "plan.premium", price: "premium.soon", highlight: true, items: ["premium.p1", "premium.p2", "premium.p3", "premium.p4", "premium.p5", "premium.p6"] },
] as const;

export default function Premium() {
  const { me } = useAuth();
  const { t } = useI18n();
  return (
    <div className="space-y-12">
      <header className="mx-auto max-w-2xl text-center"><h1 className="text-4xl md:text-5xl">{t("premium.title")}<span className="text-fg-2">{t("premium.title2")}</span></h1>
        <p className="mt-4 text-lg text-fg-2">{t("premium.sub")}</p></header>
      <div className="grid gap-5 md:grid-cols-3">
        {PLANS.map((p) => (
          <div key={p.id} className={`relative flex flex-col rounded-xl bg-surface p-7 shadow-card ${"highlight" in p ? "ring-2 ring-accent" : ""}`}>
            <h2 className="text-xl">{t(p.name)}</h2><div className="mt-1 text-3xl font-semibold tracking-tight">{t(p.price)}</div>
            <ul className="mt-6 flex-1 space-y-3">{p.items.map((i) => <li key={i} className="flex gap-2.5 text-[15px] text-fg-2"><Check className="mt-0.5 size-4 shrink-0 text-positive" />{t(i)}</li>)}</ul>
            <div className="mt-8">
              {p.id === "premium" ? (me?.plan === "premium" ? <Button variant="secondary" className="w-full" disabled>{t("premium.yours")}</Button> : <Button className="w-full" disabled>{t("premium.coming")}</Button>)
                : p.id === "free" ? (me ? <Button variant="secondary" className="w-full" disabled>{me.plan === "free" ? t("premium.yours") : t("premium.included")}</Button> : <Button asChild className="w-full"><Link to="/signup">{t("premium.signup_free")}</Link></Button>)
                : <Button variant="secondary" className="w-full" disabled>{t("premium.no_account")}</Button>}
            </div>
          </div>))}
      </div>
      <p className="text-center text-sm text-fg-3">{t("premium.note")}</p>
    </div>
  );
}
