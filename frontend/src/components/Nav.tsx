import { Heart, Library, LogOut, Search, Sparkles, User } from "lucide-react";
import { useState } from "react";
import { Link, NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";
import { LangMenu } from "./LangMenu";
import { ThemeMenu } from "./ThemeMenu";
import { Button } from "./ui/button";

const link = ({ isActive }: { isActive: boolean }) =>
  cn("rounded-full px-3.5 py-1.5 text-[15px] transition", isActive ? "bg-surface-2 text-fg" : "text-fg-2 hover:text-fg");

export function Nav() {
  const { me, logout } = useAuth();
  const { t } = useI18n();
  const nav = useNavigate();
  const [open, setOpen] = useState(false);
  return (
    <header className="material fixed inset-x-0 top-0 z-40 border-b border-separator">
      <div className="mx-auto flex h-[var(--nav-h)] max-w-[1280px] items-center gap-3 px-4 md:px-8">
        <Link to="/" className="flex items-center gap-2 text-[17px] font-bold tracking-tight">Gamefy</Link>
        <nav className="ml-4 hidden items-center gap-1 md:flex" aria-label={t("nav.main")}>
          <NavLink to="/" end className={link}>{t("nav.discover")}</NavLink>
          <NavLink to="/games" className={link}>{t("nav.store")}</NavLink>
          {me && <NavLink to="/wishlist" className={link}>{t("nav.wishlist")}</NavLink>}
          {me && <NavLink to="/library" className={link}>{t("nav.library")}</NavLink>}
          <NavLink to="/premium" className={link}>{t("nav.premium")}</NavLink>
          {me?.role === "admin" && <NavLink to="/admin" className={link}>{t("nav.admin")}</NavLink>}
        </nav>
        <div className="ml-auto flex items-center gap-1 sm:gap-2">
          <Button variant="ghost" size="icon" aria-label={t("nav.smart_search")} onClick={() => nav("/#search")}><Search className="size-5" /></Button>
          <LangMenu />
          <ThemeMenu />
          {me ? (
            <div className="relative">
              <Button variant="secondary" size="icon" aria-label={t("nav.account")} aria-expanded={open} onClick={() => setOpen((o) => !o)}><User className="size-5" /></Button>
              {open && (
                <div className="material absolute right-0 mt-2 w-60 overflow-hidden rounded-lg border border-separator p-1.5 shadow-pop" onClick={() => setOpen(false)}>
                  <div className="px-3 py-2 text-sm"><div className="truncate font-medium">{me.email}</div><div className="text-fg-3">{t("nav.plan", { plan: t(me.plan === "premium" ? "plan.premium" : "plan.free") })}</div></div>
                  <MenuLink to="/profile" icon={<User className="size-4" />}>{t("nav.profile")}</MenuLink>
                  <MenuLink to="/wishlist" icon={<Heart className="size-4" />}>{t("nav.wishlist")}</MenuLink>
                  <MenuLink to="/library" icon={<Library className="size-4" />}>{t("nav.library")}</MenuLink>
                  <MenuLink to="/premium" icon={<Sparkles className="size-4" />}>{t("nav.plans")}</MenuLink>
                  {me.role === "admin" && <MenuLink to="/admin" icon={<Sparkles className="size-4" />}>{t("nav.admin")}</MenuLink>}
                  <button onClick={() => logout().then(() => nav("/"))} className="flex w-full items-center gap-2.5 rounded-md px-3 py-2 text-left text-[15px] text-negative hover:bg-surface-2"><LogOut className="size-4" />{t("nav.logout")}</button>
                </div>
              )}
            </div>
          ) : (
            <>
              <Button asChild variant="ghost" size="sm"><Link to="/login">{t("nav.login")}</Link></Button>
              <Button asChild size="sm"><Link to="/signup">{t("nav.signup")}</Link></Button>
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
