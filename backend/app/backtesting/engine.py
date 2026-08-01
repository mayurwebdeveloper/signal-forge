"""Backtesting engine."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from app.indicators.engine import compute_all_indicators


STRATEGIES = {
    "sma_crossover": "SMA 20/50 Crossover",
    "ema_crossover": "EMA 9/21 Crossover",
    "rsi_mean_reversion": "RSI Mean Reversion",
    "macd_crossover": "MACD Crossover",
    "bollinger_bounce": "Bollinger Band Bounce",
    "golden_cross": "Golden Cross (SMA 50/200)",
    "supertrend": "SuperTrend Follow",
}


@dataclass
class Trade:
    entry_date: str
    exit_date: str | None
    entry_price: float
    exit_price: float | None
    side: str
    pnl: float | None
    pnl_pct: float | None
    reason: str


def _signals(df: pd.DataFrame, strategy: str, params: dict) -> pd.Series:
    enriched = compute_all_indicators(df)
    sig = pd.Series(0, index=enriched.index)

    if strategy == "sma_crossover":
        fast = params.get("fast", 20)
        slow = params.get("slow", 50)
        f = enriched["close"].rolling(fast).mean()
        s = enriched["close"].rolling(slow).mean()
        sig = np.where(f > s, 1, -1)
    elif strategy == "ema_crossover":
        f = enriched["ema_9"]
        s = enriched["ema_21"]
        sig = np.where(f > s, 1, -1)
    elif strategy == "rsi_mean_reversion":
        rsi = enriched["rsi_14"]
        low = params.get("oversold", 30)
        high = params.get("overbought", 70)
        sig = np.where(rsi < low, 1, np.where(rsi > high, -1, 0))
    elif strategy == "macd_crossover":
        sig = np.where(enriched["macd"] > enriched["macd_signal"], 1, -1)
    elif strategy == "bollinger_bounce":
        sig = np.where(
            enriched["close"] < enriched["bb_lower"],
            1,
            np.where(enriched["close"] > enriched["bb_upper"], -1, 0),
        )
    elif strategy == "golden_cross":
        sig = np.where(enriched["sma_50"] > enriched["sma_200"], 1, -1)
    elif strategy == "supertrend":
        sig = enriched["supertrend_dir"].fillna(0).astype(int).values
    else:
        f = enriched["ema_9"]
        s = enriched["ema_21"]
        sig = np.where(f > s, 1, -1)

    return pd.Series(sig, index=enriched.index), enriched


def run_backtest(
    df: pd.DataFrame,
    strategy: str = "sma_crossover",
    capital: float = 100000.0,
    params: dict | None = None,
) -> dict:
    params = params or {}
    if len(df) < 30:
        return {"error": "Insufficient data for backtest", "win_rate": 0}

    signals, enriched = _signals(df, strategy, params)
    # Trade on next bar open after signal change
    position = 0
    cash = capital
    shares = 0.0
    entry_price = 0.0
    entry_date = None
    trades: list[dict] = []
    equity = []

    dates = enriched.index
    opens = enriched["open"].values
    closes = enriched["close"].values
    sigs = signals.values

    for i in range(1, len(enriched)):
        # Use previous signal to trade at today's open
        prev_sig = int(sigs[i - 1])
        date_str = str(dates[i].date() if hasattr(dates[i], "date") else dates[i])

        if position == 0 and prev_sig == 1:
            shares = cash / opens[i]
            entry_price = float(opens[i])
            entry_date = date_str
            cash = 0
            position = 1
        elif position == 1 and prev_sig == -1:
            exit_price = float(opens[i])
            cash = shares * exit_price
            pnl = cash - (shares * entry_price) + (shares * entry_price) - capital  # noqa simplified below
            trade_pnl = (exit_price - entry_price) * shares
            trade_pnl_pct = (exit_price / entry_price - 1) * 100
            # Recalculate properly
            invested = entry_price * shares
            proceeds = exit_price * shares
            trade_pnl = proceeds - invested
            trades.append(
                {
                    "entry_date": entry_date,
                    "exit_date": date_str,
                    "entry_price": round(entry_price, 4),
                    "exit_price": round(exit_price, 4),
                    "side": "long",
                    "pnl": round(trade_pnl, 2),
                    "pnl_pct": round(trade_pnl_pct, 3),
                    "reason": strategy,
                }
            )
            shares = 0
            position = 0
            entry_price = 0
            entry_date = None

        equity_val = cash + shares * closes[i]
        equity.append(equity_val)

    # Close open position at end
    if position == 1 and shares > 0:
        exit_price = float(closes[-1])
        date_str = str(dates[-1].date() if hasattr(dates[-1], "date") else dates[-1])
        invested = entry_price * shares
        proceeds = exit_price * shares
        trade_pnl = proceeds - invested
        trade_pnl_pct = (exit_price / entry_price - 1) * 100
        cash = proceeds
        trades.append(
            {
                "entry_date": entry_date,
                "exit_date": date_str,
                "entry_price": round(entry_price, 4),
                "exit_price": round(exit_price, 4),
                "side": "long",
                "pnl": round(trade_pnl, 2),
                "pnl_pct": round(trade_pnl_pct, 3),
                "reason": "end_of_period",
            }
        )
        shares = 0

    final_equity = cash
    if not equity:
        equity = [capital]

    eq = np.array(equity)
    returns = np.diff(eq) / eq[:-1] if len(eq) > 1 else np.array([0.0])
    peak = np.maximum.accumulate(eq)
    drawdown = (eq - peak) / peak
    max_dd = float(drawdown.min()) if len(drawdown) else 0.0

    wins = [t for t in trades if t["pnl"] > 0]
    losses = [t for t in trades if t["pnl"] <= 0]
    total_pnl = final_equity - capital
    win_rate = len(wins) / len(trades) * 100 if trades else 0
    sharpe = 0.0
    if len(returns) > 1 and returns.std() > 0:
        sharpe = float(np.sqrt(252) * returns.mean() / returns.std())

    return {
        "strategy": strategy,
        "strategy_name": STRATEGIES.get(strategy, strategy),
        "capital": capital,
        "final_equity": round(final_equity, 2),
        "profit": round(max(total_pnl, 0), 2),
        "loss": round(abs(min(total_pnl, 0)), 2),
        "net_pnl": round(total_pnl, 2),
        "net_pnl_pct": round(total_pnl / capital * 100, 3),
        "win_rate": round(win_rate, 2),
        "success_rate": round(win_rate, 2),
        "trades_count": len(trades),
        "winning_trades": len(wins),
        "losing_trades": len(losses),
        "maximum_drawdown": round(max_dd * 100, 3),
        "sharpe_ratio": round(sharpe, 3),
        "avg_win": round(float(np.mean([t["pnl"] for t in wins])), 2) if wins else 0,
        "avg_loss": round(float(np.mean([t["pnl"] for t in losses])), 2) if losses else 0,
        "equity_curve": [round(float(x), 2) for x in eq[:: max(1, len(eq) // 100)]],
    }, trades
