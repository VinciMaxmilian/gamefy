import { Heart } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/lib/auth";
import { useToggleWishlist, useWishlist } from "@/lib/queries";
import { cn } from "@/lib/utils";

export function WishlistButton({ slug, variant = "icon" }: { slug: string; variant?: "icon" | "full" }) {
  const { me } = useAuth();
  const nav = useNavigate();
  const { data } = useWishlist();
  const toggle = useToggleWishlist();
  const on = !!data?.some((g) => g.slug === slug);
  const click = (e: React.MouseEvent) => {
    e.preventDefault(); e.stopPropagation();
    if (!me) return nav("/login");
    toggle.mutate({ slug, on: !on });
  };
  const aria = on ? "Remove from wishlist" : "Add to wishlist";
  if (variant === "full")
    return (
      <button onClick={click} aria-pressed={on} className={cn("inline-flex h-12 items-center gap-2 rounded-full px-6 font-medium transition active:scale-[0.97]", on ? "bg-surface-2 text-fg" : "bg-surface-2 text-fg hover:bg-surface-3")}>
        <Heart className={cn("size-5", on && "fill-negative text-negative")} /> {on ? "In wishlist" : "Add to wishlist"}
      </button>
    );
  return (
    <button onClick={click} aria-label={aria} aria-pressed={on} className="material grid size-9 place-items-center rounded-full text-fg transition hover:scale-105 active:scale-95">
      <Heart className={cn("size-[18px]", on && "fill-negative text-negative")} />
    </button>
  );
}
