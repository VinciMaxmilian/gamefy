import { Link } from "react-router-dom";
import { CardSkeletons, GameCardView } from "@/components/GameCardView";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/auth";
import { useLibrary, useWishlist } from "@/lib/queries";
import { RequireAuth } from "./Auth";

const Empty = ({ text }: { text: string }) => (
  <div className="py-24 text-center"><p className="text-xl text-fg-2">{text}</p><Button asChild className="mt-6"><Link to="/games">Browse the store</Link></Button></div>
);

export function Wishlist() {
  const { data, isLoading } = useWishlist();
  return (
    <RequireAuth>
      <h1 className="mb-8 text-4xl">Wishlist</h1>
      <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">{isLoading ? <CardSkeletons n={4} /> : data?.map((g) => <GameCardView key={g.slug} game={g} />)}</div>
      {data?.length === 0 && <Empty text="Games you save will show up here." />}
    </RequireAuth>
  );
}

export function LibraryPage() {
  const { data, isLoading } = useLibrary();
  const { me } = useAuth();
  return (
    <RequireAuth>
      <h1 className="mb-8 text-4xl">Library</h1>
      <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {isLoading ? <CardSkeletons n={4} /> : data?.map((e) => (
          <div key={e.game.slug} className="space-y-2"><GameCardView game={e.game} /><p className="px-2 text-sm capitalize text-fg-3">{e.status}{e.playtime_minutes ? ` · ${Math.round(e.playtime_minutes / 60)}h played` : ""}</p></div>
        ))}
      </div>
      {me && data?.length === 0 && <Empty text="Add games you own to teach us your taste." />}
    </RequireAuth>
  );
}
