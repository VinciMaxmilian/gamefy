import { Check } from "lucide-react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/auth";

const PLANS = [
  { id: "guest", name: "Guest", price: "Free", items: ["Full catalog, search & filters", "Game pages & requirements"] },
  { id: "free", name: "Free account", price: "Free", items: ["Everything in Guest", "Wishlist, library, ratings", "Taste profile & recommendations", "A few ✦ smart searches a day", "PC compatibility checks"] },
  { id: "premium", name: "Premium", price: "✦", highlight: true, items: ["Everything in Free", "Conversational ✦ assistant", "Compare games side by side", "Budget & hardware-aware curation", "Explained recommendations", "Much higher daily limits"] },
] as const;

export default function Premium() {
  const { me } = useAuth();
  return (
    <div className="space-y-12">
      <header className="mx-auto max-w-2xl text-center"><h1 className="text-4xl md:text-5xl">Find your next game, <span className="ai-text">together.</span></h1>
        <p className="mt-4 text-lg text-fg-2">Most of Gamefy runs without AI. Premium adds a conversational curator on top.</p></header>
      <div className="grid gap-5 md:grid-cols-3">
        {PLANS.map((p) => (
          <div key={p.id} className={`relative flex flex-col rounded-xl bg-surface p-7 shadow-card ${"highlight" in p ? "ai-ring" : ""}`}>
            <h2 className="text-xl">{p.name}</h2><div className="mt-1 text-3xl font-semibold tracking-tight">{p.price}</div>
            <ul className="mt-6 flex-1 space-y-3">{p.items.map((i) => <li key={i} className="flex gap-2.5 text-[15px] text-fg-2"><Check className="mt-0.5 size-4 shrink-0 text-positive" />{i}</li>)}</ul>
            <div className="mt-8">
              {p.id === "premium" ? (me?.plan === "premium" ? <Button variant="secondary" className="w-full" disabled>Your plan</Button> : <Button variant="ai" className="w-full" disabled>Coming soon</Button>)
                : p.id === "free" ? (me ? <Button variant="secondary" className="w-full" disabled>{me.plan === "free" ? "Your plan" : "Included"}</Button> : <Button asChild className="w-full"><Link to="/signup">Sign up free</Link></Button>)
                : <Button variant="secondary" className="w-full" disabled>No account needed</Button>}
            </div>
          </div>))}
      </div>
      <p className="text-center text-sm text-fg-3">The Premium assistant is in development. Plans are enforced by the server and every AI feature has usage limits.</p>
    </div>
  );
}
