"""Stockchoice - Growth module."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st
import yfinance as yf

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app_utils import cache_ttl, initialize_settings
from securities import format_security_option


# Mobile Growth universe. Keep this deliberately broad but manageable.
initialize_settings()

GROWTH_TICKERS = (
    "AAPL", "ADBE", "AMD", "AMZN", "AVGO", "CRM", "CRWD", "DDOG", "GOOG", "META",
    "MSFT", "NFLX", "NOW", "NVDA", "PANW", "PLTR", "SHOP", "SNOW", "TSLA", "UBER",
)


@st.cache_data(ttl=cache_ttl(), show_spinner=False)
def load_growth_data(tickers: tuple[str, ...]) -> pd.DataFrame:
    rows: list[dict[str, object]] = []

    for ticker in tickers:
        try:
            security = yf.Ticker(ticker)
            info = security.info or {}

            # Use two years of price history so the 12-month calculation
            # and 200-day moving average have enough observations.
            history = security.history(period="2y", auto_adjust=True)

            price = np.nan
            ret_6m = np.nan
            ret_12m = np.nan
            above_50 = np.nan
            above_200 = np.nan

            if history is not None and not history.empty and "Close" in history.columns:
                closes = pd.to_numeric(
                    history["Close"],
                    errors="coerce",
                ).dropna()

                if not closes.empty:
                    price = float(closes.iloc[-1])

                    if len(closes) > 126:
                        ret_6m = float(
                            closes.iloc[-1] / closes.iloc[-127] - 1
                        )

                    if len(closes) > 251:
                        ret_12m = float(
                            closes.iloc[-1] / closes.iloc[-252] - 1
                        )

                    if len(closes) >= 50:
                        above_50 = float(
                            closes.iloc[-1] / closes.tail(50).mean() - 1
                        )

                    if len(closes) >= 200:
                        above_200 = float(
                            closes.iloc[-1] / closes.tail(200).mean() - 1
                        )

            revenue_growth = _number(info.get("revenueGrowth"))
            earnings_growth = _number(info.get("earningsGrowth"))

            # Yahoo's info endpoint can omit growth fields. Fall back to
            # financial statements so Growth scores remain available.
            if not np.isfinite(revenue_growth) or not np.isfinite(earnings_growth):
                fallback_revenue, fallback_earnings = _statement_growth(security)

                if not np.isfinite(revenue_growth):
                    revenue_growth = fallback_revenue

                if not np.isfinite(earnings_growth):
                    earnings_growth = fallback_earnings

            roe = _number(info.get("returnOnEquity"))
            operating_margin = _number(info.get("operatingMargins"))
            forward_pe = _number(info.get("forwardPE"))

            growth_score = _growth_score(
                revenue_growth,
                earnings_growth,
            )

            quality_score = _quality_score(
                roe,
                operating_margin,
            )

            momentum_score = _momentum_score(
                ret_6m,
                ret_12m,
            )
            ma_trend_score = _moving_average_score(above_50, above_200)

            valuation_score = _valuation_score(forward_pe)

            overall_score = _weighted_score(
                growth_score,
                quality_score,
                momentum_score,
                valuation_score,
                ma_trend_score,
            )

            rows.append(
                {
                    "Ticker": ticker,
                    "Company": info.get("shortName") or ticker,
                    "Sector": info.get("sector") or "Unknown",
                    "Price": (
                        price
                        if np.isfinite(price)
                        else _number(info.get("currentPrice"))
                    ),
                    "Market Cap": _number(info.get("marketCap")),
                    "Revenue Growth": revenue_growth,
                    "Earnings Growth": earnings_growth,
                    "ROE": roe,
                    "Operating Margin": operating_margin,
                    "Forward PE": forward_pe,
                    "6M Return": ret_6m,
                    "12M Return": ret_12m,
                    "Above 50D": above_50,
                    "Above 200D": above_200,
                    "Growth Score": growth_score,
                    "Quality Score": quality_score,
                    "Momentum Score": momentum_score,
                    "MA Trend Score": ma_trend_score,
                    "Valuation Score": valuation_score,
                    "Overall Score": overall_score,
                }
            )

        except Exception as exc:
            print(
                f"Growth data error for {ticker}: "
                f"{type(exc).__name__}: {exc}"
            )
            continue

    frame = pd.DataFrame(rows)

    if not frame.empty:
        frame = frame.sort_values(
            "Overall Score",
            ascending=False,
            na_position="last",
        )

    return frame.reset_index(drop=True)


def _number(value: object) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return np.nan

    return result if np.isfinite(result) else np.nan


def _statement_growth(security: yf.Ticker) -> tuple[float, float]:
    """Calculate missing revenue/earnings growth from Yahoo statements."""
    revenue_growth = np.nan
    earnings_growth = np.nan

    for statement_name in ("quarterly_income_stmt", "income_stmt"):
        try:
            statement = getattr(security, statement_name)
        except Exception as exc:
            print(
                f"Growth fallback error for {security.ticker} "
                f"({statement_name}): {type(exc).__name__}: {exc}"
            )
            continue

        if statement is None or statement.empty or statement.shape[1] < 2:
            continue

        if not np.isfinite(revenue_growth):
            revenue_growth = _row_period_growth(
                statement,
                ("Total Revenue", "Operating Revenue"),
            )

        if not np.isfinite(earnings_growth):
            earnings_growth = _row_period_growth(
                statement,
                (
                    "Net Income",
                    "Net Income Common Stockholders",
                    "Diluted EPS",
                    "Basic EPS",
                ),
            )

        if np.isfinite(revenue_growth) and np.isfinite(earnings_growth):
            break

    return revenue_growth, earnings_growth


def _row_period_growth(
    statement: pd.DataFrame,
    row_names: tuple[str, ...],
) -> float:
    """Calculate growth from the two most recent usable statement periods."""
    for row_name in row_names:
        if row_name not in statement.index:
            continue

        values = pd.to_numeric(
            statement.loc[row_name],
            errors="coerce",
        ).dropna()

        if len(values) < 2:
            continue

        newest = _number(values.iloc[0])
        previous = _number(values.iloc[1])

        if (
            not np.isfinite(newest)
            or not np.isfinite(previous)
            or previous <= 0
        ):
            continue

        return float(newest / previous - 1)

    return np.nan


def _linear(value: float, low: float, high: float) -> float:
    if not np.isfinite(value):
        return np.nan

    if high == low:
        return 50.0

    return float(
        np.clip(
            (value - low) / (high - low) * 100,
            0,
            100,
        )
    )


def _mean_available(values: list[float]) -> float:
    available = [
        value
        for value in values
        if np.isfinite(value)
    ]

    return float(np.mean(available)) if available else np.nan



def _moving_average_score(above50: float, above200: float) -> float:
    """Score price position and 50D/200D trend alignment on a 0-100 scale."""
    if np.isfinite(above50):
        if above50 >= 0.05:
            score50 = 7.0
        elif above50 >= 0.02:
            score50 = 6.0
        elif above50 >= 0.00:
            score50 = 5.0
        elif above50 >= -0.02:
            score50 = 2.0
        else:
            score50 = 0.0
    else:
        score50 = np.nan

    if np.isfinite(above200):
        if above200 >= 0.10:
            score200 = 10.0
        elif above200 >= 0.05:
            score200 = 9.0
        elif above200 >= 0.00:
            score200 = 7.0
        elif above200 >= -0.05:
            score200 = 3.0
        else:
            score200 = 0.0
    else:
        score200 = np.nan

    alignment_score = np.nan
    if np.isfinite(above50) and np.isfinite(above200):
        # price / MA is 1 + distance_above_ma, so this derives MA50 / MA200.
        ma_alignment = (1.0 + above200) / (1.0 + above50) - 1.0
        if ma_alignment >= 0.05:
            alignment_score = 8.0
        elif ma_alignment >= 0.02:
            alignment_score = 7.0
        elif ma_alignment >= 0.00:
            alignment_score = 5.0
        elif ma_alignment >= -0.02:
            alignment_score = 2.0
        else:
            alignment_score = 0.0

    weighted_parts = [
        (score50, 7.0),
        (score200, 10.0),
        (alignment_score, 8.0),
    ]
    usable = [(score, maximum) for score, maximum in weighted_parts if np.isfinite(score)]
    if not usable:
        return np.nan
    return float(sum(score for score, _ in usable) / sum(maximum for _, maximum in usable) * 100.0)

def _growth_score(
    revenue_growth: float,
    earnings_growth: float,
) -> float:
    return _mean_available(
        [
            _linear(revenue_growth, -0.05, 0.35),
            _linear(earnings_growth, -0.10, 0.40),
        ]
    )


def _quality_score(
    roe: float,
    operating_margin: float,
) -> float:
    return _mean_available(
        [
            _linear(roe, 0.00, 0.35),
            _linear(operating_margin, 0.00, 0.30),
        ]
    )


def _momentum_score(
    ret_6m: float,
    ret_12m: float,
) -> float:
    return _mean_available(
        [
            _linear(ret_6m, -0.20, 0.35),
            _linear(ret_12m, -0.30, 0.60),
        ]
    )


def _valuation_score(forward_pe: float) -> float:
    if not np.isfinite(forward_pe) or forward_pe <= 0:
        return np.nan

    # Growth stocks are allowed a wider valuation range;
    # lower remains better.
    return float(
        np.clip(
            (55 - forward_pe) / (55 - 15) * 100,
            0,
            100,
        )
    )


def _weighted_score(
    growth: float,
    quality: float,
    momentum: float,
    valuation: float,
    ma_trend: float,
) -> float:
    parts = [
        (growth, 0.22),
        (quality, 0.18),
        (momentum, 0.15),
        (valuation, 0.10),
        (ma_trend, 0.35),
    ]

    usable = [
        (value, weight)
        for value, weight in parts
        if np.isfinite(value)
    ]

    if not usable:
        return np.nan

    denominator = sum(weight for _, weight in usable)

    return (
        sum(value * weight for value, weight in usable)
        / denominator
    )


def add_watchlist(ticker: str) -> bool:
    added = add_to_watchlist(ticker)
    st.session_state["mobile_watchlist"] = load_watchlist()
    return added


def ma_indicator(value: float, label: str) -> str:
    """Return a colored moving-average status pill."""
    if not np.isfinite(value):
        return (
            f'<span class="ma-indicator ma-na">'
            f'● {label} N/A'
            f'</span>'
        )

    distance_display = f"{abs(value):.1%}"

    if value >= 0:
        return (
            f'<span class="ma-indicator ma-above">'
            f'● Above {label} +{distance_display}'
            f'</span>'
        )

    return (
        f'<span class="ma-indicator ma-below">'
        f'● Below {label} -{distance_display}'
        f'</span>'
    )


def stock_card(record: pd.Series) -> None:
    ticker = str(record["Ticker"])
    company = str(record.get("Company") or ticker)

    price = _number(record.get("Price"))
    score = _number(record.get("Overall Score"))
    growth = _number(record.get("Growth Score"))
    momentum = _number(record.get("Momentum Score"))
    ret12 = _number(record.get("12M Return"))
    above_50 = _number(record.get("Above 50D"))
    above_200 = _number(record.get("Above 200D"))

    score_display = f"{score:.0f}" if np.isfinite(score) else "N/A"
    growth_display = f"{growth:.0f}" if np.isfinite(growth) else "N/A"
    momentum_display = f"{momentum:.0f}" if np.isfinite(momentum) else "N/A"
    price_display = f"${price:,.2f}" if np.isfinite(price) else "N/A"
    ret12_display = f"{ret12:.1%}" if np.isfinite(ret12) else "N/A"

    # Generate indicators inside stock_card because the values differ
    # for every stock record.
    ma_50_html = ma_indicator(above_50, "50D")
    ma_200_html = ma_indicator(above_200, "200D")

    card_html = (
        f'<div class="stock-card">'
        f'<div class="stock-row">'
        f'<div class="stock-heading">'
        f'<div class="ticker">{ticker}</div>'
        f'<div class="company">{company}</div>'
        f'<div class="ma-row">'
        f'{ma_50_html}'
        f'{ma_200_html}'
        f'</div>'
        f'</div>'
        f'<div class="score">{score_display}</div>'
        f'</div>'
        f'<div class="mini-row">'
        f'<span>Price <b>{price_display}</b></span>'
        f'<span>Growth <b>{growth_display}</b></span>'
        f'<span>Momentum <b>{momentum_display}</b></span>'
        f'<span>12M <b>{ret12_display}</b></span>'
        f'</div>'
        f'</div>'
    )

    st.markdown(
        card_html,
        unsafe_allow_html=True,
    )


    if st.button(
        "🔎 Details",
        key=f"detail_{ticker}",
        use_container_width=True,
    ):
        st.session_state["mobile_selected_ticker"] = ticker
        st.session_state["mobile_search"] = ticker
        st.switch_page("pages/details.py")
        

# ---------------------------------------------------------
# Mobile styling
# ---------------------------------------------------------

st.markdown(
    """
<style>
[data-testid="stSidebar"] {
    display: none;
}

[data-testid="collapsedControl"] {
    display: none;
}

.block-container {
    max-width: 520px;
    padding: 2.5rem 1rem 5rem 1rem;
}

.module-title {
    font-size: 2rem;
    font-weight: 800;
    margin-bottom: .15rem;
}

.module-subtitle {
    color: #9aa3b2;
    font-size: .9rem;
    margin-bottom: 1rem;
}

.stock-card {
    border: 1px solid rgba(128, 128, 128, .25);
    border-radius: 16px;
    padding: .9rem 1rem .8rem 1rem;
    background: rgba(128, 128, 128, .05);
    margin-top: .75rem;
}

.stock-row {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: .8rem;
}

.stock-heading {
    min-width: 0;
    flex: 1;
}

.ticker {
    font-size: 1.25rem;
    font-weight: 800;
}

.company {
    font-size: .82rem;
    color: #9aa3b2;
    margin-top: .12rem;
}

.ma-row {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: .35rem;
    margin-top: .45rem;
}

.ma-indicator {
    display: inline-block;
    padding: .16rem .48rem;
    border-radius: 999px;
    font-size: .68rem;
    font-weight: 700;
    line-height: 1.25;
    white-space: nowrap;
}

.ma-above {
    color: #21c55d;
    background: rgba(33, 197, 93, .12);
    border: 1px solid rgba(33, 197, 93, .25);
}

.ma-below {
    color: #ef4444;
    background: rgba(239, 68, 68, .12);
    border: 1px solid rgba(239, 68, 68, .25);
}

.ma-na {
    color: #9aa3b2;
    background: rgba(154, 163, 178, .10);
    border: 1px solid rgba(154, 163, 178, .20);
}

.score {
    min-width: 46px;
    text-align: center;
    border-radius: 12px;
    padding: .35rem .45rem;
    background: #1877f2;
    color: white;
    font-weight: 800;
    font-size: 1.05rem;
}

.mini-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: .35rem .8rem;
    margin-top: .8rem;
    font-size: .82rem;
    color: #9aa3b2;
}

.section-label {
    font-size: .82rem;
    color: #9aa3b2;
    font-weight: 650;
    margin-top: .7rem;
}
</style>
""",
    unsafe_allow_html=True,
)


# ---------------------------------------------------------
# Header
# ---------------------------------------------------------

st.markdown(
    '<div class="module-title">📈 Growth</div>',
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="module-subtitle">
    Growth, quality, momentum, and valuation context optimized
    for quick mobile research.
    </div>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------
# Navigation
# ---------------------------------------------------------

home_col, refresh_col = st.columns(2)

with home_col:
    st.page_link(
        "app.py",
        label="Home",
        icon="🏠",
        width="stretch",
    )

with refresh_col:
    refresh = st.button(
        "🔄 Refresh",
        use_container_width=True,
    )

if refresh:
    load_growth_data.clear()
    st.rerun()


# ---------------------------------------------------------
# Load data
# ---------------------------------------------------------

with st.spinner("Loading Growth research..."):
    data = load_growth_data(GROWTH_TICKERS)

if data.empty:
    st.warning("Growth data is currently unavailable.")
    st.stop()


# ---------------------------------------------------------
# Search / filter
# ---------------------------------------------------------

search = st.selectbox(
    "Search Growth",
    options=list(GROWTH_TICKERS),
    index=None,
    placeholder="Search a ticker or company...",
    format_func=format_security_option,
    key="growth_search",
    label_visibility="collapsed",
)

sector_options = (
    ["All"]
    + sorted(
        data["Sector"]
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    )
)

sector = st.selectbox(
    "Sector",
    sector_options,
    label_visibility="collapsed",
)

filtered = data.copy()

if search:
    filtered = filtered[
        filtered["Ticker"].astype(str).str.upper() == search.upper()
    ]

if sector != "All":
    filtered = filtered[
        filtered["Sector"] == sector
    ]

if filtered.empty:
    st.info(
        "No Growth stocks match the current search and sector filter."
    )
    st.stop()


# ---------------------------------------------------------
# Growth Snapshot
# ---------------------------------------------------------

st.markdown(
    '<div class="section-label">GROWTH SNAPSHOT</div>',
    unsafe_allow_html=True,
)

with st.expander("📊 GROWTH SNAPSHOT", expanded=False):
    median_score = filtered["Overall Score"].median()
    median_rev_growth = filtered["Revenue Growth"].median()
    median_12m = filtered["12M Return"].median()

    m1, m2 = st.columns(2)

    m1.metric(
        "Stocks",
        len(filtered),
    )

    m2.metric(
        "Median Score",
        f"{median_score:.0f}"
        if pd.notna(median_score)
        else "N/A",
    )

    m3, m4 = st.columns(2)

    m3.metric(
        "Median Rev Growth",
        f"{median_rev_growth:.1%}"
        if pd.notna(median_rev_growth)
        else "N/A",
    )

    m4.metric(
        "Median 12M",
        f"{median_12m:.1%}"
        if pd.notna(median_12m)
        else "N/A",
    )

# ---------------------------------------------------------
# Top Growth Candidates
# ---------------------------------------------------------

    st.markdown(
        '<div class="section-label">TOP GROWTH CANDIDATES</div>',
        unsafe_allow_html=True,
    )

    allowed_counts = [5, 10, 15, 20]
    default_count = st.session_state.get(
        "mobile_default_result_count",
        20,
    )

    if default_count not in allowed_counts:
        default_count = 20

    show_count = st.select_slider(
        "Show",
        options=allowed_counts,
        value=default_count,
        label_visibility="collapsed",
    )

    leaders = (
        filtered
        .sort_values(
            "Overall Score",
            ascending=False,
            na_position="last",
        )
        .head(show_count)
    )

for _, record in leaders.iterrows():
    stock_card(record)


# ---------------------------------------------------------
# Growth vs Momentum
# ---------------------------------------------------------

st.divider()

st.markdown(
    '<div class="section-label">GROWTH VS MOMENTUM</div>',
    unsafe_allow_html=True,
)

chart = filtered.dropna(
    subset=[
        "Growth Score",
        "Momentum Score",
    ]
).copy()

if not chart.empty:
    chart["Bubble Size"] = (
        pd.to_numeric(
            chart["Market Cap"],
            errors="coerce",
        )
        .clip(lower=1)
    )

    fig = px.scatter(
        chart,
        x="Growth Score",
        y="Momentum Score",
        size="Bubble Size",
        size_max=24,
        color="Sector",
        hover_name="Ticker",
        hover_data={
            "Company": True,
            "Overall Score": ":.1f",
            "Revenue Growth": ":.1%",
            "Earnings Growth": ":.1%",
            "Forward PE": ":.1f",
            "Above 50D": ":.1%",
            "Above 200D": ":.1%",
            "Bubble Size": False,
        },
    )

    fig.update_xaxes(range=[-5, 105])
    fig.update_yaxes(range=[-5, 105])

    fig.update_layout(
        height=390,
        margin=dict(
            l=35,
            r=35,
            t=35,
            b=35,
        ),
        showlegend=False,
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
    )
else:
    st.info("Not enough Growth and Momentum data to build the chart.")


if st.session_state.get("mobile_show_disclaimer", True):
    st.caption(
        "Mobile Growth scores are compact screening signals "
        "for research, not investment recommendations."
    )
