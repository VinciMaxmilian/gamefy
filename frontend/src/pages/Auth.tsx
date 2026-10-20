import { useMutation } from "@tanstack/react-query";
import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/input";
import { api, errorMessage, setSessionHint } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export function RequireAuth({ children }: { children: ReactNode }) {
  const { me, loading } = useAuth();
  if (loading) return <div className="h-64" />;
  if (!me) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

function Shell({ title, subtitle, children, footer }: { title: string; subtitle?: string; children: ReactNode; footer?: ReactNode }) {
  return (
    <div className="mx-auto max-w-md pt-6 md:pt-14">
      <div className="mb-8 text-center"><h1 className="text-3xl md:text-4xl">{title}</h1>{subtitle && <p className="mt-2 text-fg-2">{subtitle}</p>}</div>
      <div className="rounded-xl bg-surface p-6 shadow-card md:p-8">{children}</div>
      {footer && <p className="mt-6 text-center text-sm text-fg-2">{footer}</p>}
    </div>
  );
}
const Err = ({ msg }: { msg?: string }) => (msg ? <p role="alert" className="rounded-md bg-negative/10 px-3 py-2 text-sm text-negative">{msg}</p> : null);

export function Login() {
  const nav = useNavigate();
  const { refresh } = useAuth();
  const [email, setEmail] = useState(""); const [password, setPassword] = useState("");
  const m = useMutation({
    mutationFn: () => api("/auth/login", { method: "POST", body: { email, password } }),
    onSuccess: async () => { setSessionHint(true); await refresh(); nav("/"); },
  });
  const submit = (e: FormEvent) => { e.preventDefault(); m.mutate(); };
  return (
    <Shell title="Welcome back" footer={<>New here? <Link to="/signup" className="text-accent">Create an account</Link></>}>
      <form onSubmit={submit} className="space-y-4">
        <div><Label htmlFor="email">Email</Label><Input id="email" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} /></div>
        <div><Label htmlFor="password">Password</Label><Input id="password" type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} /></div>
        <Err msg={m.isError ? errorMessage(m.error) : undefined} />
        <Button type="submit" size="lg" className="w-full" disabled={m.isPending}>{m.isPending ? "Signing in…" : "Log in"}</Button>
        <p className="text-center text-sm"><Link to="/recover" className="text-fg-2 hover:text-fg">Forgot password?</Link></p>
      </form>
    </Shell>
  );
}

export function Signup() {
  const [email, setEmail] = useState(""); const [password, setPassword] = useState("");
  const m = useMutation({ mutationFn: () => api<{ message: string }>("/auth/signup", { method: "POST", body: { email, password } }) });
  if (m.isSuccess) return <Shell title="Almost there" subtitle={m.data.message} footer={<Link to="/login" className="text-accent">Go to log in</Link>}><p className="text-center text-fg-2">You can close this tab once you’ve confirmed your email.</p></Shell>;
  return (
    <Shell title="Create your account" subtitle="Free. Recommendations that learn your taste." footer={<>Have an account? <Link to="/login" className="text-accent">Log in</Link></>}>
      <form onSubmit={(e) => { e.preventDefault(); m.mutate(); }} className="space-y-4">
        <div><Label htmlFor="email">Email</Label><Input id="email" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} /></div>
        <div><Label htmlFor="password">Password</Label><Input id="password" type="password" autoComplete="new-password" minLength={10} required value={password} onChange={(e) => setPassword(e.target.value)} />
          <p className="mt-1.5 text-xs text-fg-3">At least 10 characters. A few random words make a great password.</p></div>
        <Err msg={m.isError ? errorMessage(m.error) : undefined} />
        <Button type="submit" size="lg" className="w-full" disabled={m.isPending}>{m.isPending ? "Creating…" : "Sign up"}</Button>
      </form>
    </Shell>
  );
}

export function Recover() {
  const [email, setEmail] = useState("");
  const m = useMutation({ mutationFn: () => api<{ message: string }>("/auth/recover", { method: "POST", body: { email } }) });
  return (
    <Shell title="Reset your password" subtitle="We’ll email you a link." footer={<Link to="/login" className="text-accent">Back to log in</Link>}>
      {m.isSuccess ? <p className="text-center text-fg-2">{m.data.message}</p> : (
        <form onSubmit={(e) => { e.preventDefault(); m.mutate(); }} className="space-y-4">
          <div><Label htmlFor="email">Email</Label><Input id="email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} /></div>
          <Err msg={m.isError ? errorMessage(m.error) : undefined} />
          <Button type="submit" size="lg" className="w-full" disabled={m.isPending}>Send link</Button>
        </form>)}
    </Shell>
  );
}

/** Two ways in, both read once into memory and removed from the address bar immediately:
 *  - ?token_hash=…&type=recovery   (our e-mail template; the one-time token is only consumed when you submit)
 *  - #access_token=…&type=recovery (Supabase default redirect), or #error=…&error_code=otp_expired */
function readRecoveryParams() {
  const q = new URLSearchParams(window.location.search);
  const h = new URLSearchParams(window.location.hash.slice(1));
  const tokenHash = q.get("type") === "recovery" ? (q.get("token_hash") ?? "") : "";
  const accessToken = h.get("type") === "recovery" || !h.get("type") ? (h.get("access_token") ?? "") : "";
  const code = h.get("error_code") ?? h.get("error") ?? "";
  return { tokenHash, accessToken, usable: !!(tokenHash || accessToken), expired: code === "otp_expired", failed: !!code };
}

export function ResetPassword() {
  const [{ tokenHash, accessToken, usable, expired, failed }] = useState(readRecoveryParams);
  useEffect(() => { if (window.location.hash || window.location.search) history.replaceState(null, "", window.location.pathname); }, []);
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [show, setShow] = useState(false);
  const mismatch = confirm.length > 0 && confirm !== password;
  const m = useMutation({ mutationFn: () => api("/auth/reset-password", { method: "POST", body: { password, ...(tokenHash ? { token_hash: tokenHash } : { access_token: accessToken }) } }) });

  if (m.isSuccess)
    return (
      <Shell title="Password updated" subtitle="You can now log in with your new password.">
        <Button asChild size="lg" className="w-full"><Link to="/login">Log in</Link></Button>
      </Shell>
    );
  if (!usable)
    return (
      <Shell title={expired ? "This link has expired" : "This link doesn’t work"} footer={<Link to="/login" className="text-accent">Back to log in</Link>}>
        <p className="text-center text-fg-2">
          {expired || failed ? "Recovery links work once and expire quickly. " : "Open the link from your email on this device. "}
          Request a new one and use it right away.
        </p>
        <Button asChild size="lg" className="mt-6 w-full"><Link to="/recover">Request a new link</Link></Button>
      </Shell>
    );
  return (
    <Shell title="Choose a new password" subtitle="Use at least 10 characters. A few random words work well.">
      <form onSubmit={(e) => { e.preventDefault(); if (!mismatch) m.mutate(); }} className="space-y-4">
        <div>
          <Label htmlFor="pw">New password</Label>
          <div className="relative">
            <Input id="pw" type={show ? "text" : "password"} autoComplete="new-password" minLength={10} maxLength={128} required autoFocus
              value={password} onChange={(e) => setPassword(e.target.value)} className="pr-16" />
            <button type="button" onClick={() => setShow((v) => !v)} aria-pressed={show}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-sm text-fg-2 hover:text-fg">{show ? "Hide" : "Show"}</button>
          </div>
        </div>
        <div>
          <Label htmlFor="pw2">Confirm password</Label>
          <Input id="pw2" type={show ? "text" : "password"} autoComplete="new-password" required value={confirm}
            onChange={(e) => setConfirm(e.target.value)} aria-invalid={mismatch} />
          {mismatch && <p role="alert" className="mt-1.5 text-sm text-negative">Passwords don’t match.</p>}
        </div>
        <Err msg={m.isError ? errorMessage(m.error) : undefined} />
        <Button type="submit" size="lg" className="w-full" disabled={m.isPending || mismatch || password.length < 10}>
          {m.isPending ? "Updating…" : "Update password"}
        </Button>
      </form>
    </Shell>
  );
}
