import { useMutation } from "@tanstack/react-query";
import { useState, type FormEvent, type ReactNode } from "react";
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
      <div className="mb-8 text-center"><div className="ai-text mb-3 text-3xl">✦</div><h1 className="text-3xl md:text-4xl">{title}</h1>{subtitle && <p className="mt-2 text-fg-2">{subtitle}</p>}</div>
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

/** Supabase redirects here with #access_token=…&type=recovery. The token never leaves this page except to our API. */
export function ResetPassword() {
  const [password, setPassword] = useState("");
  const token = new URLSearchParams(window.location.hash.slice(1)).get("access_token") ?? "";
  const nav = useNavigate();
  const m = useMutation({
    mutationFn: () => api("/auth/reset-password", { method: "POST", body: { password, access_token: token } }),
    onSuccess: () => { history.replaceState(null, "", "/reset-password"); nav("/login"); },
  });
  if (!token) return <Shell title="Link expired" footer={<Link to="/recover" className="text-accent">Request a new link</Link>}><p className="text-center text-fg-2">This recovery link is invalid or has expired.</p></Shell>;
  return (
    <Shell title="Choose a new password">
      <form onSubmit={(e) => { e.preventDefault(); m.mutate(); }} className="space-y-4">
        <div><Label htmlFor="pw">New password</Label><Input id="pw" type="password" autoComplete="new-password" minLength={10} required value={password} onChange={(e) => setPassword(e.target.value)} /></div>
        <Err msg={m.isError ? errorMessage(m.error) : undefined} />
        <Button type="submit" size="lg" className="w-full" disabled={m.isPending}>Update password</Button>
      </form>
    </Shell>
  );
}
