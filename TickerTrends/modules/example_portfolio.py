"""
TickerTrends Example Portfolio
==============================

Portfolio construction and visualization helpers.

Rules:
    - $10,000 starting portfolio
    - Maximum 10 stocks
    - Strong Bullish stocks receive first priority
    - Bullish stocks fill remaining positions
    - Higher TickerTrends scores rank first
    - Maximum 3 stocks from the same sector
    - Score-weighted allocations
    - Maximum 15% target allocation per stock
    - Unused allocation remains as cash
    - No market-data calls are made from this module
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

import numpy as np
import pandas as pd
import plotly.express as px


# ============================================================
# CONFIGURATION
# ============================================================

@dataclass(frozen=True)
class PortfolioConfig:
    capital: float = 10_000.0
    holdings_target: int = 10
    max_per_sector: int = 3
    max_position_pct: float = 0.15

    eligible_trends: tuple[str, ...] = (
        "Strong Bullish",
        "Bullish",
    )

    use_fractional_shares: bool = True


# ============================================================
# REQUIRED COLUMNS
# ============================================================

REQUIRED_COLUMNS = (
    "ticker",
    "company_name",
    "sector",
    "price",
    "total_score",
    "trend_state",
)


# ============================================================
# DATA PREPARATION
# ============================================================

def prepare_portfolio_data(
    df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Validate and clean the ticker-state DataFrame.
    """

    if df is None or df.empty:
        return pd.DataFrame()

    missing = [
        column
        for column in REQUIRED_COLUMNS
        if column not in df.columns
    ]

    if missing:
        raise ValueError(
            "Portfolio data is missing required columns: "
            + ", ".join(missing)
        )

    work = df.copy()

    # --------------------------------------------------------
    # TICKER
    # --------------------------------------------------------

    work["ticker"] = (
        work["ticker"]
        .fillna("")
        .astype(str)
        .str.upper()
        .str.strip()
    )

    # --------------------------------------------------------
    # COMPANY NAME
    # --------------------------------------------------------

    work["company_name"] = (
        work["company_name"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    work.loc[
        work["company_name"].eq(""),
        "company_name",
    ] = work["ticker"]

    # --------------------------------------------------------
    # SECTOR
    # --------------------------------------------------------

    work["sector"] = (
        work["sector"]
        .fillna("Unknown")
        .astype(str)
        .str.strip()
    )

    work.loc[
        work["sector"].eq(""),
        "sector",
    ] = "Unknown"

    # --------------------------------------------------------
    # TREND STATE
    # --------------------------------------------------------

    work["trend_state"] = (
        work["trend_state"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    # --------------------------------------------------------
    # NUMERIC FIELDS
    # --------------------------------------------------------

    numeric_columns = [
        "price",
        "total_score",
        "technical_score",
        "fundamental_score",
        "pe_ratio",
        "peg_ratio",
        "free_cash_flow",
        "fcf_metric",
        "relative_performance",
        "rsi_14",
        "sma_50",
        "sma_200",
        "pct_from_sma50",
        "pct_from_sma200",
    ]

    for column in numeric_columns:

        if column not in work.columns:
            continue

        work[column] = pd.to_numeric(
            work[column],
            errors="coerce",
        )

    # --------------------------------------------------------
    # CLEAN RECORDS
    # --------------------------------------------------------

    work = work[
        work["ticker"].ne("")
    ]

    work = work.drop_duplicates(
        subset="ticker",
        keep="first",
    )

    return work.reset_index(
        drop=True
    )


# ============================================================
# ELIGIBLE STOCKS
# ============================================================

def get_eligible_stocks(
    df: pd.DataFrame,
    config: PortfolioConfig,
) -> pd.DataFrame:
    """
    Return stocks eligible for portfolio selection.

    Strong Bullish receives priority over Bullish.

    Stocks within each category are ranked by total_score.
    """

    work = prepare_portfolio_data(df)

    if work.empty:
        return work

    eligible = work[
        work["trend_state"].isin(
            config.eligible_trends
        )
        & work["total_score"].notna()
        & work["price"].notna()
        & work["price"].gt(0)
    ].copy()

    if eligible.empty:
        return eligible

    trend_priority = {
        "Strong Bullish": 0,
        "Bullish": 1,
    }

    eligible["_trend_priority"] = (
        eligible["trend_state"]
        .map(trend_priority)
        .fillna(99)
    )

    eligible = eligible.sort_values(
        by=[
            "_trend_priority",
            "total_score",
            "ticker",
        ],
        ascending=[
            True,
            False,
            True,
        ],
        na_position="last",
    )

    return eligible.reset_index(
        drop=True
    )


# ============================================================
# PORTFOLIO SELECTION
# ============================================================

def select_portfolio_holdings(
    df: pd.DataFrame,
    config: PortfolioConfig,
) -> pd.DataFrame:
    """
    Select the highest ranking eligible stocks while enforcing
    the maximum number of holdings allowed per sector.
    """

    eligible = get_eligible_stocks(
        df,
        config,
    )

    if eligible.empty:
        return eligible

    selected_rows = []

    sector_counts: Counter[str] = Counter()

    for _, row in eligible.iterrows():

        sector = row["sector"]

        # Maximum holdings from one sector.
        if (
            sector_counts[sector]
            >= config.max_per_sector
        ):
            continue

        selected_rows.append(
            row.to_dict()
        )

        sector_counts[sector] += 1

        # Stop when portfolio target is reached.
        if (
            len(selected_rows)
            >= config.holdings_target
        ):
            break

    if not selected_rows:

        return pd.DataFrame(
            columns=eligible.columns
        )

    holdings = pd.DataFrame(
        selected_rows
    )

    holdings = holdings.drop(
        columns=["_trend_priority"],
        errors="ignore",
    )

    return holdings.reset_index(
        drop=True
    )


# ============================================================
# SCORE WEIGHTING
# ============================================================

def calculate_score_weights(
    scores: pd.Series,
    max_position_pct: float,
) -> pd.Series:
    """
    Convert TickerTrends total scores into portfolio weights.

    Higher scores receive slightly larger allocations.

    Positions above the maximum allocation are capped and the
    excess is redistributed among the remaining stocks.
    """

    scores = pd.to_numeric(
        scores,
        errors="coerce",
    ).fillna(0.0)

    scores = scores.clip(
        lower=0.0
    )

    count = len(scores)

    if count == 0:

        return pd.Series(
            dtype=float
        )

    # --------------------------------------------------------
    # INITIAL WEIGHTS
    # --------------------------------------------------------

    if scores.sum() <= 0:

        weights = pd.Series(
            1.0 / count,
            index=scores.index,
        )

    else:

        weights = (
            scores
            / scores.sum()
        )

    # --------------------------------------------------------
    # APPLY POSITION CAP
    # --------------------------------------------------------

    final_weights = pd.Series(
        0.0,
        index=weights.index,
    )

    active = pd.Series(
        True,
        index=weights.index,
    )

    remaining_weight = 1.0

    while active.any():

        active_scores = scores[
            active
        ]

        if active_scores.empty:
            break

        if active_scores.sum() <= 0:

            proposed = pd.Series(
                remaining_weight
                / len(active_scores),
                index=active_scores.index,
            )

        else:

            proposed = (
                active_scores
                / active_scores.sum()
                * remaining_weight
            )

        over_cap = (
            proposed
            > max_position_pct
        )

        if not over_cap.any():

            final_weights.loc[
                proposed.index
            ] = proposed

            break

        capped_indexes = (
            proposed[
                over_cap
            ]
            .index
        )

        final_weights.loc[
            capped_indexes
        ] = max_position_pct

        active.loc[
            capped_indexes
        ] = False

        remaining_weight = (
            1.0
            - final_weights.sum()
        )

        if remaining_weight <= 0:
            break

    # --------------------------------------------------------
    # SAFETY FALLBACK
    # --------------------------------------------------------

    if final_weights.sum() <= 0:

        final_weights[:] = (
            1.0 / count
        )

    return final_weights


# ============================================================
# BUILD PORTFOLIO
# ============================================================

def build_example_portfolio(
    df: pd.DataFrame,
    config: PortfolioConfig | None = None,
) -> tuple[pd.DataFrame, dict]:
    """
    Build the hypothetical TickerTrends portfolio.

    Returns:
        holdings DataFrame
        summary dictionary
    """

    if config is None:
        config = PortfolioConfig()

    holdings = select_portfolio_holdings(
        df,
        config,
    )

    # --------------------------------------------------------
    # EMPTY PORTFOLIO
    # --------------------------------------------------------

    if holdings.empty:

        summary = {
            "capital": config.capital,
            "invested": 0.0,
            "cash": config.capital,
            "holdings": 0,
            "average_score": np.nan,
            "strong_bullish": 0,
            "bullish": 0,
            "sectors": 0,
        }

        return holdings, summary

    # --------------------------------------------------------
    # AVAILABLE INVESTMENT
    # --------------------------------------------------------
    #
    # Each desired portfolio position represents an equal
    # potential slice of the starting capital.
    #
    # If fewer than the desired number of stocks qualify,
    # the missing slots remain in cash.
    # --------------------------------------------------------

    slot_value = (
        config.capital
        / config.holdings_target
    )

    invested_budget = min(
        config.capital,
        slot_value * len(holdings),
    )

    # --------------------------------------------------------
    # SCORE WEIGHTS
    # --------------------------------------------------------

    score_weights = calculate_score_weights(
        holdings["total_score"],
        config.max_position_pct,
    )

    weight_total = score_weights.sum()

    if weight_total <= 0:

        score_weights = pd.Series(
            1.0 / len(holdings),
            index=holdings.index,
        )

    else:

        score_weights = (
            score_weights
            / weight_total
        )

    # --------------------------------------------------------
    # TARGET INVESTMENT
    # --------------------------------------------------------

    holdings["allocation_pct"] = (
        score_weights
        * (
            invested_budget
            / config.capital
        )
    )

    holdings["target_investment"] = (
        holdings["allocation_pct"]
        * config.capital
    )

    # --------------------------------------------------------
    # SHARES
    # --------------------------------------------------------

    if config.use_fractional_shares:

        holdings["shares"] = (
            holdings["target_investment"]
            / holdings["price"]
        )

        holdings["invested"] = (
            holdings["target_investment"]
        )

    else:

        holdings["shares"] = np.floor(
            holdings["target_investment"]
            / holdings["price"]
        )

        holdings["invested"] = (
            holdings["shares"]
            * holdings["price"]
        )

    # --------------------------------------------------------
    # ACTUAL PORTFOLIO PERCENTAGE
    # --------------------------------------------------------

    holdings["portfolio_pct"] = (
        holdings["invested"]
        / config.capital
    )

    # --------------------------------------------------------
    # RANK HOLDINGS
    # --------------------------------------------------------

    holdings = holdings.sort_values(
        by=[
            "total_score",
            "ticker",
        ],
        ascending=[
            False,
            True,
        ],
    )

    holdings = holdings.reset_index(
        drop=True
    )

    holdings.insert(
        0,
        "rank",
        range(
            1,
            len(holdings) + 1,
        ),
    )

    # --------------------------------------------------------
    # SUMMARY
    # --------------------------------------------------------

    invested = float(
        holdings[
            "invested"
        ].sum()
    )

    cash = max(
        0.0,
        config.capital - invested,
    )

    average_score = float(
        holdings[
            "total_score"
        ].mean()
    )

    strong_bullish = int(
        (
            holdings["trend_state"]
            == "Strong Bullish"
        ).sum()
    )

    bullish = int(
        (
            holdings["trend_state"]
            == "Bullish"
        ).sum()
    )

    sectors = int(
        holdings["sector"]
        .nunique()
    )

    summary = {
        "capital": config.capital,
        "invested": invested,
        "cash": cash,
        "holdings": len(holdings),
        "average_score": average_score,
        "strong_bullish": strong_bullish,
        "bullish": bullish,
        "sectors": sectors,
    }

    return holdings, summary


# ============================================================
# HOLDINGS DISPLAY
# ============================================================

def get_holdings_display(
    holdings: pd.DataFrame,
) -> pd.DataFrame:
    """
    Return the columns displayed by the Streamlit portfolio
    page.
    """

    if holdings is None or holdings.empty:
        return pd.DataFrame()

    columns = [
        "rank",
        "ticker",
        "company_name",
        "trend_state",
        "total_score",
        "sector",
        "price",
        "portfolio_pct",
        "invested",
        "shares",
    ]

    available_columns = [
        column
        for column in columns
        if column in holdings.columns
    ]

    return holdings[
        available_columns
    ].copy()


# ============================================================
# SECTOR ALLOCATION
# ============================================================

def get_sector_allocation(
    holdings: pd.DataFrame,
) -> pd.DataFrame:
    """
    Aggregate portfolio investments by sector.
    """

    if holdings is None or holdings.empty:

        return pd.DataFrame(
            columns=[
                "sector",
                "invested",
                "allocation_pct",
                "holdings",
            ]
        )

    sector_data = (
        holdings
        .groupby(
            "sector",
            as_index=False,
        )
        .agg(
            invested=(
                "invested",
                "sum",
            ),
            holdings=(
                "ticker",
                "count",
            ),
        )
    )

    total_invested = (
        sector_data[
            "invested"
        ].sum()
    )

    if total_invested > 0:

        sector_data[
            "allocation_pct"
        ] = (
            sector_data["invested"]
            / total_invested
        )

    else:

        sector_data[
            "allocation_pct"
        ] = 0.0

    sector_data = (
        sector_data
        .sort_values(
            "invested",
            ascending=False,
        )
        .reset_index(
            drop=True
        )
    )

    return sector_data


# ============================================================
# SECTOR ALLOCATION CHART
# ============================================================

def create_sector_allocation_chart(
    holdings: pd.DataFrame,
):
    """
    Create sector allocation donut chart.

    Dollar allocation determines the size of each sector.
    """

    sector_data = get_sector_allocation(
        holdings
    )

    if sector_data.empty:
        return None

    fig = px.pie(
        sector_data,
        names="sector",
        values="invested",
        hole=0.58,
        title="Sector Allocation",
        custom_data=[
            "holdings",
        ],
    )

    fig.update_traces(
        textposition="inside",
        textinfo="percent+label",
        hovertemplate=(
            "<b>%{label}</b><br>"
            "Allocation: %{percent}<br>"
            "Investment: $%{value:,.0f}<br>"
            "Holdings: %{customdata[0]}"
            "<extra></extra>"
        ),
    )

    fig.update_layout(
        margin=dict(
            l=20,
            r=20,
            t=60,
            b=20,
        ),
        legend_title_text="Sector",
    )

    return fig


# ============================================================
# TECHNICAL VS FUNDAMENTAL SCATTER
# ============================================================

def create_score_scatter_chart(
    holdings: pd.DataFrame,
):
    """
    Create a Technical Score vs Fundamental Score scatter.

    X-axis:
        Fundamental Score

    Y-axis:
        Technical Score

    Bubble size:
        Portfolio investment

    Bubble color:
        Sector

    Bubble label:
        Ticker
    """

    if holdings is None or holdings.empty:
        return None

    required = {
        "technical_score",
        "fundamental_score",
    }

    if not required.issubset(
        holdings.columns
    ):
        return None

    plot_data = holdings.dropna(
        subset=[
            "technical_score",
            "fundamental_score",
        ]
    ).copy()

    if plot_data.empty:
        return None

    fig = px.scatter(
        plot_data,
        x="fundamental_score",
        y="technical_score",
        size="invested",
        color="sector",
        text="ticker",
        hover_name="company_name",
        hover_data={
            "ticker": False,
            "sector": True,
            "total_score": ":.1f",
            "trend_state": True,
            "price": ":$,.2f",
            "invested": ":$,.0f",
            "portfolio_pct": ":.1%",
            "technical_score": ":.1f",
            "fundamental_score": ":.1f",
        },
        title=(
            "Technical Strength vs. Fundamentals"
        ),
        labels={
            "fundamental_score":
                "Fundamental Score",

            "technical_score":
                "Technical Score",

            "sector":
                "Sector",
        },
    )

    fig.update_traces(
        textposition="top center",
    )

    fig.update_layout(
        margin=dict(
            l=20,
            r=20,
            t=60,
            b=20,
        ),
        legend_title_text="Sector",
    )

    return fig


# ============================================================
# RULES TEXT
# ============================================================

def portfolio_rules_text(
    config: PortfolioConfig | None = None,
) -> str:
    """
    Return a concise description of the model portfolio rules.
    """

    if config is None:
        config = PortfolioConfig()

    return (
        "Model portfolio rules: "
        "Strong Bullish stocks receive first priority, "
        "followed by Bullish stocks; "
        f"maximum {config.holdings_target} holdings; "
        f"maximum {config.max_per_sector} stocks per sector; "
        f"maximum {config.max_position_pct:.0%} target "
        "allocation per stock; "
        "stocks are ranked by TickerTrends score; "
        "unused allocation remains in cash."
    )