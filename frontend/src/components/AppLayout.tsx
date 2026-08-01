import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import {
  Activity,
  Bell,
  Briefcase,
  LayoutDashboard,
  LineChart,
  LogOut,
  Radar,
  Settings,
  Star,
  FlaskConical,
  FileText,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';

const links = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/stocks', label: 'Stocks', icon: LineChart },
  { to: '/scanner', label: 'Scanner', icon: Radar },
  { to: '/watchlist', label: 'Watchlist', icon: Star },
  { to: '/portfolio', label: 'Portfolio', icon: Briefcase },
  { to: '/backtest', label: 'Backtest', icon: FlaskConical },
  { to: '/alerts', label: 'Alerts', icon: Bell },
  { to: '/reports', label: 'Reports', icon: FileText },
];

export default function AppLayout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  return (
    <div className="min-h-screen flex">
      <aside className="w-60 shrink-0 border-r border-[var(--color-line)] bg-[rgba(12,26,23,0.94)] text-[#e7eee9] flex flex-col">
        <div className="px-5 pt-6 pb-4">
          <div className="flex items-center gap-2">
            <Activity className="text-[var(--color-teal-light)]" size={22} />
            <span className="font-display text-2xl tracking-tight">SignalForge</span>
          </div>
          <p className="mt-1 text-xs text-[#9bb0a8]">Pattern intelligence for markets</p>
        </div>
        <nav className="flex-1 px-3 space-y-1">
          {links.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className={({ isActive }) =>
                `flex items-center gap-2.5 rounded-md px-3 py-2 text-sm transition ${
                  isActive ? 'bg-teal-700/40 text-white' : 'text-[#c5d4cd] hover:bg-white/5 hover:text-white'
                }`
              }
            >
              <Icon size={16} />
              {label}
            </NavLink>
          ))}
          {user?.is_admin && (
            <NavLink
              to="/admin"
              className={({ isActive }) =>
                `flex items-center gap-2.5 rounded-md px-3 py-2 text-sm transition ${
                  isActive ? 'bg-teal-700/40 text-white' : 'text-[#c5d4cd] hover:bg-white/5 hover:text-white'
                }`
              }
            >
              <Settings size={16} />
              Admin
            </NavLink>
          )}
        </nav>
        <div className="p-4 border-t border-white/10">
          <div className="text-sm font-medium truncate">{user?.full_name || user?.username}</div>
          <div className="text-xs text-[#9bb0a8] truncate">{user?.email}</div>
          <button
            onClick={() => {
              logout();
              navigate('/login');
            }}
            className="mt-3 flex items-center gap-2 text-xs text-[#c5d4cd] hover:text-white"
          >
            <LogOut size={14} /> Sign out
          </button>
        </div>
      </aside>
      <main className="flex-1 min-w-0">
        <div className="px-6 py-5 border-b border-[var(--color-line)] bg-white/40 backdrop-blur-sm">
          <p className="text-xs text-[var(--color-ink-muted)]">
            Statistical analysis & historical pattern matching — not financial advice. No guarantee of future prices or profits.
          </p>
        </div>
        <div className="p-6">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
