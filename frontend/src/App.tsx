import { Navigate, Route, Routes } from 'react-router-dom';
import { useAuth } from './context/AuthContext';
import AppLayout from './components/AppLayout';
import { Loading } from './components/ui';
import LoginPage from './pages/Login';
import RegisterPage from './pages/Register';
import DashboardPage from './pages/Dashboard';
import StocksPage from './pages/Stocks';
import StockDetailPage from './pages/StockDetail';
import ScannerPage from './pages/Scanner';
import WatchlistPage from './pages/Watchlist';
import PortfolioPage from './pages/Portfolio';
import BacktestPage from './pages/Backtest';
import AlertsPage from './pages/Alerts';
import ReportsPage from './pages/Reports';
import AdminPage from './pages/Admin';
import SuggestionsPage from './pages/Suggestions';

function Private({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return <Loading />;
  if (!user) return <Navigate to="/login" replace />;
  return children;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route
        path="/"
        element={
          <Private>
            <AppLayout />
          </Private>
        }
      >
        <Route index element={<DashboardPage />} />
        <Route path="suggestions" element={<SuggestionsPage />} />
        <Route path="stocks" element={<StocksPage />} />
        <Route path="stocks/:id" element={<StockDetailPage />} />
        <Route path="scanner" element={<ScannerPage />} />
        <Route path="watchlist" element={<WatchlistPage />} />
        <Route path="portfolio" element={<PortfolioPage />} />
        <Route path="backtest" element={<BacktestPage />} />
        <Route path="alerts" element={<AlertsPage />} />
        <Route path="reports" element={<ReportsPage />} />
        <Route path="admin" element={<AdminPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
