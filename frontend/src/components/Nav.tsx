import { Heart, Library, LogOut, Search, Sparkles, User } from "lucide-react";
import { useState } from "react";
import { Link, NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";
import { ThemeMenu } from "./ThemeMenu";
import { Button } from "./ui/button";

const link = ({ isActive }: { isActive: boolean }) =>
  cn("rounded-full px-3.5 py-1.5 text-[15px] transition", isActive ? "bg-surface-2 text-fg" : "text-fg-2 hover:text-fg");

export function Nav() {
  const { me, logout } = useAuth();
  const nav = useNavigate();
  const [open, setOpen] = useState(false);
  return (
    <header className="material fixed inset-x-0 top-0 z-40 border-b border-separator">
      <div className="mx-auto flex h-[var(--nav-h)] max-w-[1280px] items-center gap-3 px-4 md:px-8">
        <Link to="/" className="flex items-center gap-2 text-[17px] font-bold tracking-tight">Gamefy</Link>
        <nav className="ml-4 hidden items-center gap-1 md:flex" aria-label="Main">
          <NavLink to="/" end className={link}>Discover</NavLink>
          <NavLink to="/games" className={link}>Store</NavLink>
          {me && <NavLink to="/wishlist" className={link}>Wishlist</NavLink>}
          {me && <NavLink to="/library" className={link}>Library</NavLink>}
          <NavLink to="/premium" className={link}>Premium</NavLink>
          {me?.role === "admin" && <NavLink to="/admin" className={link}>Admin</NavLink>}
        </nav>
        <div className="ml-auto flex items-center gap-2">
          <Button variant="ghost" size="icon" aria-label="Smart search" onClick={() => nav("/#search")}><Search className="size-5" /></Button>
          <ThemeMenu />
          {me ? (
            <div className="relative">
              <Button variant="secondary" size="icon" aria-label="Account menu" aria-expanded={open} onClick={() => setOpen((o) => !o)}><User className="size-5" /></Button>
              {open && (
                <div className="material absolute right-0 mt-2 w-60 overflow-hidden rounded-lg border border-separator p-1.5 shadow-pop" onClick={() => setOpen(false)}>
                  <div className="px-3 py-2 text-sm"><div className="truncate font-medium">{me.email}</div><div className="capitalize text-fg-3">{me.plan} plan</div></div>
                  <MenuLink to="/profile" icon={<User className="size-4" />}>Profile & taste</MenuLink>
                  <MenuLink to="/wishlist" icon={<Heart className="size-4" />}>Wishlist</MenuLink>
                  <MenuLink to="/library" icon={<Library className="size-4" />}>Library</MenuLink>
                  <MenuLink to="/premium" icon={<Sparkles className="size-4" />}>Plans</MenuLink>
                  {me.role === "admin" && <MenuLink to="/admin" icon={<Sparkles className="size-4" />}>Admin</MenuLink>}
                  <button onClick={() => logout().then(() => nav("/"))} className="flex w-full items-center gap-2.5 rounded-md px-3 py-2 text-left text-[15px] text-negative hover:bg-surface-2"><LogOut className="size-4" />Log out</button>
                </div>
              )}
            </div>
          ) : (
            <>
              <Button asChild variant="ghost" size="sm"><Link to="/login">Log in</Link></Button>
              <Button asChild size="sm"><Link to="/signup">Sign up</Link></Button>
            </>
          )}
        </div>
      </div>
    </header>
  );
}

const MenuLink = ({ to, icon, children }: { to: string; icon: React.ReactNode; children: React.ReactNode }) => (
  <Link to={to} className="flex items-center gap-2.5 rounded-md px-3 py-2 text-[15px] hover:bg-surface-2">{icon}{children}</Link>
);
