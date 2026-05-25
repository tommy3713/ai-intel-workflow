from pydantic import BaseModel, Field
from typing import Literal, Optional
from datetime import datetime


class NewsItem(BaseModel):
    headline: str
    significance: Literal["high", "medium"]
    dimension: Literal["supply_chain", "capex_orders", "tech_breakthrough", "guidance_revision"]
    affected_tickers: list[str]
    core_insight: str = Field(description="1-2句：邏輯變化，非事件轉述")
    my_positions_impact: Optional[str] = Field(
        None,
        description="若影響我的持倉：說明『原本持有理由是否改變』而非只說漲跌方向，無關則 null"
    )
    citation_url: Optional[str] = None


class DecisionQuestion(BaseModel):
    ticker: str = Field(description="對應的持倉 ticker，如 NVDA 或 AAPL Call")
    question: str = Field(description="一句具體問題，幫助判斷是否需要行動")
    urgency: Literal["today", "this_week", "monitor"]


class MarketSnapshot(BaseModel):
    us_futures_bias: Literal["bullish", "bearish", "neutral"]
    taiwan_sector_bias: Literal["bullish", "bearish", "neutral"]
    key_levels: Optional[str] = None


class OptionsContext(BaseModel):
    iv_environment: Literal["high", "normal", "low"]
    iv_note: str = Field(
        description="說明 IV 環境的含義與風險，不給具體點位，讓使用者自行查 Greeks 後決策"
    )
    positions_at_risk: list[str] = Field(
        description="在當前 IV 環境下，哪些選擇權持倉需要特別注意"
    )
    upcoming_vol_events: list[str] = Field(description="未來兩週的波動事件，如法說會、產品發表")


class WatchItem(BaseModel):
    ticker: str
    watch_for: str = Field(description="今晚關注的具體指標或消息")
    action_trigger: str = Field(description="出現什麼情況考慮什麼行動方向")


class IntelReport(BaseModel):
    report_type: Literal["morning", "evening"]
    generated_at: datetime
    opening_conclusion: Optional[str] = Field(
        None,
        description="早報必填：3句以內說明昨晚美股事件、今日台股關注標的、風險提示。晚報填 null。"
    )
    high_signal_items: list[NewsItem]
    decision_questions: list[DecisionQuestion] = Field(
        description="今日新聞觸發的持倉問題，最多8個，有到期日部位優先，無新聞觸發不硬生成"
    )
    market_snapshot: MarketSnapshot
    options_context: Optional[OptionsContext] = None
    watchlist_tonight: list[WatchItem] = Field(
        default_factory=list,
        description="晚報：今晚最需要關注的持倉，最多3項，早報填 []"
    )
    markdown_report: str
    editor_note: Optional[str] = None
