import { Suspense, lazy } from "react";
import { Link, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { useEffect } from "react";
import { Nav } from "./components/Nav";
import { Button } from "./components/ui/button";
import Home from "./pages/Home";

const Catalog = lazy(() => import("./pages/Catalog"));
const Discover = lazy(() => import("./pages/Discover"));
const GameDetail = lazy(() => import("./pages/GameDetail"));
const Profile = lazy(() => import("./pages/Profile"));
const Premium = lazy(() => import("./pages/Premium"));
const Lists = import("./pages/Lists");
const Wishlist = lazy(() => Lists.then((m) => ({ default: m.Wishlist })));
const LibraryPage = lazy(() => Lists.then((m) => ({ default: m.LibraryPage })));
const AuthPages = import("./pages/Auth");
const Login = lazy(() => AuthPages.then((m) => ({ default: m.Login })));
const Signup = lazy(() => AuthPages.then((m) => ({ default: m.Signup })));
const Recover = lazy(() => AuthPages.then((m) => ({ default: m.Recover })));
const ResetPassword = lazy(() => AuthPages.then((m) => ({ default: m.ResetPassword })));

/** Supabase falls back to the Site URL (root) when a redirect URL isn't allow-listed, appending the result
 *  in the hash. Forward recovery results to the reset page instead of leaving the user on a silent home page. */
function RecoveryRedirect() {
  const { pathname, hash } = useLocation();
  const nav = useNavigate();
  useEffect(() => {
    if (pathname === "/reset-password" || !hash) return;
    const h = new URLSearchParams(hash.slice(1));
    if (h.get("type") === "recovery" || h.get("error_code") === "otp_expired") nav(`/reset-password${hash}`, { replace: true });
  }, [pathname, hash, nav]);
  return null;
}

function ScrollTop() {
  const { pathname } = useLocation();
  useEffect(() => { window.scrollTo({ top: 0 }); }, [pathname]);
  return null;
}

export default function App() {
  return (
    <>
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-full focus:bg-accent focus:px-4 focus:py-2 focus:text-white">Skip to content</a>
      <Nav />
      <ScrollTop />
      <RecoveryRedirect />
      <main id="main" className="mx-auto min-h-screen max-w-[1280px] px-4 pb-24 pt-[calc(var(--nav-h)+2rem)] md:px-8">
        <Suspense fallback={<div className="h-96" />}>
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/games" element={<Catalog />} />
            <Route path="/games/:slug" element={<GameDetail />} />
            <Route path="/discover" element={<Discover />} />
            <Route path="/wishlist" element={<Wishlist />} />
            <Route path="/library" element={<LibraryPage />} />
            <Route path="/profile" element={<Profile />} />
            <Route path="/premium" element={<Premium />} />
            <Route path="/login" element={<Login />} />
            <Route path="/signup" element={<Signup />} />
            <Route path="/recover" element={<Recover />} />
            <Route path="/reset-password" element={<ResetPassword />} />
            <Route path="*" element={<div className="py-32 text-center"><h1 className="text-5xl">404</h1><p className="mt-3 text-fg-2">That page doesn’t exist.</p><Button asChild className="mt-8"><Link to="/">Go home</Link></Button></div>} />
          </Routes>
        </Suspense>
      </main>
      <footer className="border-t border-separator py-8 text-center text-sm text-fg-3">Game data from IGDB, Steam and CheapShark · Gamefy is not affiliated with any game store</footer>
    </>
  );
}
