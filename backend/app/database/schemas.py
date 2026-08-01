"""Pydantic schemas."""
from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


# ---------- Auth ----------
class UserRegister(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=8, max_length=128)
    full_name: Optional[str] = None

    @field_validator("username")
    @classmethod
    def username_alnum(cls, v: str) -> str:
        if not v.replace("_", "").isalnum():
            raise ValueError("Username must be alphanumeric (underscores allowed)")
        return v.lower()


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


class UserOut(BaseModel):
    id: int
    email: str
    username: str
    full_name: Optional[str] = None
    is_active: bool
    is_admin: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class ProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    username: Optional[str] = Field(default=None, min_length=3, max_length=50)


# ---------- Stocks ----------
class StockCreate(BaseModel):
    symbol: str
    company_name: str
    exchange: str = "NSE"
    sector: Optional[str] = None
    industry: Optional[str] = None
    isin: Optional[str] = None
    market_cap: Optional[float] = None


class StockOut(BaseModel):
    id: int
    symbol: str
    company_name: str
    exchange: str
    sector: Optional[str] = None
    industry: Optional[str] = None
    isin: Optional[str] = None
    market_cap: Optional[float] = None
    currency: str
    is_active: bool
    last_updated: Optional[datetime] = None

    model_config = {"from_attributes": True}


class PriceBar(BaseModel):
    date: date
    open: float
    high: float
    low: float
    close: float
    adj_close: float
    volume: float


class StockDetailOut(StockOut):
    latest_price: Optional[float] = None
    change_pct: Optional[float] = None
    volume: Optional[float] = None


# ---------- Watchlist ----------
class WatchlistCreate(BaseModel):
    name: str = "My Watchlist"


class WatchlistItemAdd(BaseModel):
    stock_id: int
    notes: Optional[str] = None


class WatchlistItemOut(BaseModel):
    id: int
    stock_id: int
    notes: Optional[str] = None
    added_at: datetime
    stock: Optional[StockOut] = None

    model_config = {"from_attributes": True}


class WatchlistOut(BaseModel):
    id: int
    name: str
    created_at: datetime
    items: list[WatchlistItemOut] = []

    model_config = {"from_attributes": True}


# ---------- Alerts ----------
class AlertCreate(BaseModel):
    stock_id: Optional[int] = None
    alert_type: str
    condition: dict[str, Any] = {}
    channel: str = "browser"


class AlertOut(BaseModel):
    id: int
    stock_id: Optional[int] = None
    alert_type: str
    condition: dict
    channel: str
    is_active: bool
    last_triggered: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------- Portfolio ----------
class HoldingCreate(BaseModel):
    stock_id: int
    quantity: float = Field(gt=0)
    avg_buy_price: float = Field(gt=0)
    buy_date: Optional[date] = None
    notes: Optional[str] = None


class PortfolioCreate(BaseModel):
    name: str = "My Portfolio"


class HoldingOut(BaseModel):
    id: int
    stock_id: int
    quantity: float
    avg_buy_price: float
    buy_date: Optional[date] = None
    notes: Optional[str] = None
    stock: Optional[StockOut] = None
    current_price: Optional[float] = None
    market_value: Optional[float] = None
    pnl: Optional[float] = None
    pnl_pct: Optional[float] = None

    model_config = {"from_attributes": True}


class PortfolioOut(BaseModel):
    id: int
    name: str
    created_at: datetime
    holdings: list[HoldingOut] = []
    total_investment: float = 0
    total_value: float = 0
    total_pnl: float = 0
    total_return_pct: float = 0

    model_config = {"from_attributes": True}


# ---------- Backtest ----------
class BacktestRequest(BaseModel):
    stock_id: int
    strategy: str = "sma_crossover"
    start_date: date
    end_date: date
    capital: float = Field(default=100000, gt=0)
    params: dict[str, Any] = {}


class BacktestOut(BaseModel):
    id: int
    stock_id: int
    strategy: str
    start_date: date
    end_date: date
    capital: float
    results: dict
    trades: Optional[list] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------- Scanner ----------
class ScannerFilters(BaseModel):
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    min_volume: Optional[float] = None
    sector: Optional[str] = None
    min_market_cap: Optional[float] = None
    max_market_cap: Optional[float] = None
    min_rsi: Optional[float] = None
    max_rsi: Optional[float] = None
    macd_signal: Optional[str] = None  # bullish / bearish
    ema_cross: Optional[str] = None
    golden_cross: Optional[bool] = None
    death_cross: Optional[bool] = None
    breakout: Optional[bool] = None
    near_support: Optional[bool] = None
    near_resistance: Optional[bool] = None
    near_52w_high: Optional[bool] = None
    near_52w_low: Optional[bool] = None
    limit: int = Field(default=50, le=200)


# ---------- Reports ----------
class ReportRequest(BaseModel):
    report_type: str  # stock_analysis / performance / strategy / portfolio
    stock_id: Optional[int] = None
    portfolio_id: Optional[int] = None
    backtest_id: Optional[int] = None
    format: str = "pdf"


class MessageOut(BaseModel):
    message: str
    detail: Optional[Any] = None


class PredictionOut(BaseModel):
    id: int
    stock_id: int
    bullish_probability: float
    bearish_probability: float
    expected_direction: str
    confidence: str
    holding_period: str
    risk: str
    scores: Optional[dict] = None
    model_version: str
    disclaimer: str
    created_at: datetime

    model_config = {"from_attributes": True}
