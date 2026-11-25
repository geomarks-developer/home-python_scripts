"""
TickerTrends Portfolio Page
===========================

Loads current scan results from SQLite and sends them to the
example portfolio module.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from core.database import get_all_ticker_states
from modules.example_portfolio import (
    PortfolioConfig,
    build_example_portfolio,
    create_score_scatter_chart,
    create_sector_allocation_chart,
    get_holdings_display,
    portfolio_rules_text,
)


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="Portfolio | TickerTrends",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ============================================================
# LOAD SQLITE DATA
# ============================================================

@st.cache_data(ttl=300)
def load_portfolio_data() -> pd.DataFrame:
    """
    Load current TickerTrends results from SQLite.

    No market-data requests are made from this page.
    """

    rows = get_all_ticker_states()

    if not rows:
        return pd.DataFrame()

    return pd.DataFrame(rows)


# ============================================================
# NAVIGATION
# ============================================================

if st.button(
    "🏠 Home",
    key="portfolio_home_button",
):
    st.switch_page("Summary.py")


# ============================================================
# HEADER
# ============================================================

st.title("💼 Example Portfolio")

st.caption(
    "A hypothetical $10,000 portfolio built from the latest "
    "TickerTrends scan. This model is for analysis and is not "
    "investment advice."
)


# ============================================================
# PORTFOLIO SETTINGS
# ============================================================

config = PortfolioConfig(
    capital=10_000.0,
    holdings_target=10,
    max_per_sector=3,
    max_position_pct=0.15,
    eligible_trends=(
        "Strong Bullish",
        "Bullish",
    ),
    use_fractional_shares=True,
)


# ============================================================
# LOAD DATA
# ============================================================

df = load_portfolio_data()

if df.empty:
    st.info(
        "No TickerTrends scan data is currently available."
    )
    st.stop()


# ============================================================
# BUILD PORTFOLIO
# ============================================================

try:
    holdings, summary = build_example_portfolio(
        df,
        config,
    )

except ValueError as exc:
    st.error(str(exc))
    st.stop()


if holdings.empty:
    st.warning(
        "No Strong Bullish or Bullish stocks currently meet "
        "the portfolio requirements."
    )
    st.stop()


# ============================================================
# SUMMARY METRICS
# ============================================================

metric_1, metric_2, metric_3 = st.columns(3)

metric_1.metric(
    "Starting Capital",
    f"${summary['capital']:,.0f}",
)

metric_2.metric(
    "Invested",
    f"${summary['invested']:,.0f}",
)

metric_3.metric(
    "Cash",
    f"${summary['cash']:,.0f}",
)

metric_4, metric_5, metric_6 = st.columns(3)

metric_4.metric(
    "Holdings",
    (
        f"{summary['holdings']} "
        f"of {config.holdings_target}"
    ),
)

metric_5.metric(
    "Average Score",
    f"{summary['average_score']:.1f}",
)

metric_6.metric(
    "Sectors",
    summary["sectors"],
)


# ============================================================
# TREND BREAKDOWN
# ============================================================

st.subheader("Trend Composition")

trend_1, trend_2 = st.columns(2)

trend_1.metric(
    "Strong Bullish",
    summary["strong_bullish"],
)

trend_2.metric(
    "Bullish",
    summary["bullish"],
)


# ============================================================
# QUALIFICATION NOTICE
# ============================================================

if summary["holdings"] < config.holdings_target:
    st.info(
        f"Only {summary['holdings']} stocks met all portfolio "
        "requirements. The unused allocation remains in cash."
    )


# ============================================================
# HOLDINGS TABLE
# ============================================================

st.subheader("Portfolio Holdings")

display = get_holdings_display(
    holdings
)

st.dataframe(
    display,
    use_container_width=True,
    hide_index=True,
    column_config={
        "rank": st.column_config.NumberColumn(
            "#",
            format="%d",
        ),
        "ticker": st.column_config.TextColumn(
            "Ticker",
        ),
        "company_name": st.column_config.TextColumn(
            "Company",
        ),
        "trend_state": st.column_config.TextColumn(
            "Trend",
        ),
        "total_score": st.column_config.NumberColumn(
            "Score",
            format="%.1f",
        ),
        "sector": st.column_config.TextColumn(
            "Sector",
        ),
        "price": st.column_config.NumberColumn(
            "Price",
            format="$%.2f",
        ),
        "portfolio_pct": st.column_config.NumberColumn(
            "Allocation",
            format="percent",
        ),
        "invested": st.column_config.NumberColumn(
            "Investment",
            format="$%.2f",
        ),
        "shares": st.column_config.NumberColumn(
            "Shares",
            format="%.3f",
        ),
    },
)


# ============================================================
# CHARTS
# ============================================================

st.subheader("Portfolio Analysis")

chart_left, chart_right = st.columns(2)

with chart_left:

    sector_figure = create_sector_allocation_chart(
        holdings
    )

    if sector_figure is not None:
        st.plotly_chart(
            sector_figure,
            use_container_width=True,
        )
    else:
        st.info(
            "Sector allocation is unavailable."
        )


with chart_right:

    score_figure = create_score_scatter_chart(
        holdings
    )

    if score_figure is not None:
        st.plotly_chart(
            score_figure,
            use_container_width=True,
        )
    else:
        st.info(
            "Technical and fundamental score data are "
            "not available for the selected holdings."
        )


# ============================================================
# PORTFOLIO RULES
# ============================================================

st.divider()

st.caption(
    portfolio_rules_text(config)
)

st.caption(
    "Portfolio results are loaded from the latest "
    "TickerTrends scan stored in SQLite."
)