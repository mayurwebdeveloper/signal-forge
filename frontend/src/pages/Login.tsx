import { FormEvent, useState } from 'react';
import { Link, Navigate } from 'react-router-dom';
import { Activity } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { Button, Input } from '../components/ui';

export default function LoginPage() {
  const { user, login, loading } = useAuth();
  const [email, setEmail] = useState('admin@signalforge.app');
  const [password, setPassword] = useState('Admin@12345');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  if (!loading && user) return <Navigate to="/" replace />;

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError('');
    try {
      await login(email, password);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen grid lg:grid-cols-2">
      <section className="relative hidden lg:flex flex-col justify-between p-12 text-white overflow-hidden bg-[var(--color-ink)]">
        <div
          className="absolute inset-0 opacity-40"
          style={{
            background:
              'radial-gradient(ellipse at 30% 20%, rgba(20,184,166,0.45), transparent 50%), radial-gradient(ellipse at 80% 80%, rgba(196,92,38,0.35), transparent 45%)',
          }}
        />
        <div className="relative">
          <div className="flex items-center gap-2">
            <Activity />
            <span className="font-display text-3xl">SignalForge</span>
          </div>
        </div>
        <div className="relative max-w-md animate-rise">
          <h2 className="font-display text-5xl leading-tight">See the pattern before the crowd does.</h2>
          <p className="mt-4 text-[#c5d4cd]">
            Historical data, technical indicators, chart patterns, and probability scoring — in one workspace.
          </p>
        </div>
        <p className="relative text-xs text-[#9bb0a8]">Estimates only. Not financial advice.</p>
      </section>
      <section className="flex items-center justify-center p-8">
        <form onSubmit={onSubmit} className="w-full max-w-md card-surface rounded-2xl p-8 animate-rise">
          <h1 className="font-display text-3xl">Sign in</h1>
          <p className="text-sm text-[var(--color-ink-muted)] mt-1">Access your analytics workspace</p>
          <div className="mt-6 space-y-4">
            <div>
              <label className="text-xs font-medium">Email</label>
              <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required className="mt-1" />
            </div>
            <div>
              <label className="text-xs font-medium">Password</label>
              <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required className="mt-1" />
            </div>
            {error && <p className="text-sm text-[var(--color-loss)]">{error}</p>}
            <Button type="submit" disabled={busy} className="w-full">
              {busy ? 'Signing in…' : 'Sign in'}
            </Button>
          </div>
          <p className="mt-4 text-sm text-[var(--color-ink-muted)]">
            No account? <Link className="text-teal-700 font-medium" to="/register">Create one</Link>
          </p>
        </form>
      </section>
    </div>
  );
}
