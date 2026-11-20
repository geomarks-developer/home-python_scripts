"""StockChoice - optimized Sample Portfolio page.

Builds a $10,000 sample portfolio using the existing Growth, Value,
Dividend, and ETF scoring engines without rendering those pages.
"""
from __future__ import annotations

import ast
import html
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
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

initialize_settings()

PORTFOLIO_VALUE = 10_000.0
POSITION_VALUE = 1_000.0
MAX_STOCKS_PER_SECTOR = 2
MAX_ENERGY_STOCKS = 1
CATEGORY_TARGETS = {
    "Growth": 1,
    "Value": 3,
    "Dividend": 3,
    "ETF": 3,
}
CATEGORY_ICONS = {
    "Growth": "🚀",
    "Value": "💎",
    "Dividend": "💵",
    "ETF": "🌐",
}
CATEGORY_COLORS = {
    "Growth": "#1877f2",
    "Value": "#7c3aed",
    "Dividend": "#16a34a",
    "ETF": "#0891b2",
}

st.set_page_config(
    page_title="Sample Portfolio | StockChoice",
    page_icon="💼",
    layout="centered",
)


def _load_page_engine(filename: str) -> dict[str, object]:
    """Load constants and functions from a page without running its UI."""
    path = PROJECT_ROOT / "pages" / filename
    if not path.exists():
        raise FileNotFoundError(f"Could not find {path}")

    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    selected: list[ast.stmt] = []

    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module == "__future__":
            selected.append(node)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            selected.append(node)
        elif isinstance(node, ast.Assign):
            names = [
                target.id
                for target in node.targets
                if isinstance(target, ast.Name)
            ]
            if (
                names
                and all(name.isupper() for name in names)
                and "PROJECT_ROOT" not in names
            ):
                selected.append(node)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id.isupper():
                selected.append(node)

    engine_module = ast.Module(body=selected, type_ignores=[])
    ast.fix_missing_locations(engine_module)

    namespace: dict[str, object] = {
        "__name__": f"stockchoice_engine_{path.stem}",
        "np": np,
        "pd": pd,
        "st": st,
        "yf": yf,
        "Path": Path,
        "sys": sys,
        "cache_ttl": cache_ttl,
    }
    exec(compile(engine_module, str(path), "exec"), namespace)
    return namespace


@st.cache_resource(show_spinner=False)
def get_engines() -> dict[str, dict[str, object]]:
    """Parse and compile each page engine only once per app process."""
    return {
        "Growth": _load_page_engine("growth.py"),
        "Value": _load_page_engine("value.py"),
        "Dividend": _load_page_engine("dividend.py"),
        "ETF": _load_page_engine("etf.py"),
    }


def _engine_jobs() -> dict[str, tuple[object, tuple[str, ...]]]:
    """Return loader functions and ticker universes for each category."""
    engines = get_engines()
    growth = engines["Growth"]
    value = engines["Value"]
    dividend = engines["Dividend"]
    etf = engines["ETF"]

    return {
        "Growth": (
            growth["load_growth_data"],
            tuple(growth["GROWTH_TICKERS"]),
        ),
        "Value": (
            value["load_value_data"],
            tuple(value["VALUE_TICKERS"]),
        ),
        "Dividend": (
            dividend["load_dividend_data"],
            tuple(dividend["DIVIDEND_TICKERS"]),
        ),
        "ETF": (
            etf["load_etf_data"],
            tuple(etf["all_tickers"]()),
        ),
    }


@st.cache_data(ttl=cache_ttl(), show_spinner=False)
def load_all_candidates() -> dict[str, pd.DataFrame]:
    """Load all four candidate universes concurrently and cache the result."""
    jobs = _engine_jobs()
    results: dict[str, pd.DataFrame] = {
        category: pd.DataFrame()
        for category in CATEGORY_TARGETS
    }

    with ThreadPoolExecutor(max_workers=4) as executor:
        future_categories = {
            executor.submit(loader, tickers): category
            for category, (loader, tickers) in jobs.items()
        }

        for future in as_completed(future_categories):
            category = future_categories[future]
            try:
                result = future.result()
                results[category] = (
                    result
                    if isinstance(result, pd.DataFrame)
                    else pd.DataFrame()
                )
            except Exception as exc:
                print(
                    f"Portfolio {category} load error: "
                    f"{type(exc).__name__}: {exc}"
                )
                results[category] = pd.DataFrame()

    return results

def normalize_candidates(
    data: pd.DataFrame,
    category: str,
) -> pd.DataFrame:

    columns = [
        "Category",
        "Ticker",
        "Company",
        "Sector",
        "Price",
        "Score",
        "MA Trend Score",
        "Above 50D",
        "Above 200D",
    ]

    if data is None or data.empty:
        return pd.DataFrame(columns=columns)

    work = data.copy()

    company_col = "Fund" if category == "ETF" else "Company"
    sector_col = "Category" if category == "ETF" else "Sector"

    normalized = pd.DataFrame(index=work.index)

    normalized["Category"] = category

    normalized["Ticker"] = (
        work["Ticker"]
        .astype(str)
        .str.upper()
        .str.strip()
    )

    if company_col in work.columns:
        normalized["Company"] = (
            work[company_col]
            .fillna("")
            .astype(str)
        )
    else:
        normalized["Company"] = (
            work["Ticker"]
            .fillna("")
            .astype(str)
        )

    if sector_col in work.columns:
        normalized["Sector"] = (
            work[sector_col]
            .fillna("Unknown")
            .astype(str)
        )
    else:
        normalized["Sector"] = "Unknown"

    normalized["Price"] = pd.to_numeric(
        work["Price"]
        if "Price" in work.columns
        else np.nan,
        errors="coerce",
    )

    normalized["Score"] = pd.to_numeric(
        work["Overall Score"]
        if "Overall Score" in work.columns
        else np.nan,
        errors="coerce",
    )

    normalized["MA Trend Score"] = pd.to_numeric(
        work["MA Trend Score"]
        if "MA Trend Score" in work.columns
        else np.nan,
        errors="coerce",
    )

    # ---------------------------------------------------------
    # Moving-average trend filters
    # ---------------------------------------------------------

    normalized["Above 50D"] = pd.to_numeric(
        work["Above 50D"]
        if "Above 50D" in work.columns
        else np.nan,
        errors="coerce",
    )

    normalized["Above 200D"] = pd.to_numeric(
        work["Above 200D"]
        if "Above 200D" in work.columns
        else np.nan,
        errors="coerce",
    )

    normalized = normalized.replace(
        [np.inf, -np.inf],
        np.nan,
    )

    # ---------------------------------------------------------
    # Remove invalid tickers
    # ---------------------------------------------------------

    normalized = normalized[
        normalized["Ticker"].notna()
        & normalized["Ticker"].ne("")
        & normalized["Ticker"].ne("NAN")
    ]

    # ---------------------------------------------------------
    # TREND REQUIREMENT
    #
    # Only allow securities trading above BOTH:
    #   50-day moving average
    #   200-day moving average
    #
    # Above 0 means current price is above the moving average.
    # ---------------------------------------------------------

    normalized = normalized[
        (normalized["Above 50D"] > 0)
        & (normalized["Above 200D"] > 0)
    ].copy()

    normalized = normalized.drop_duplicates(
        "Ticker",
        keep="first",
    )

    return normalized.sort_values(
        ["Score", "MA Trend Score"],
        ascending=[False, False],
        na_position="last",
    )


def pick_diversified(
    data: pd.DataFrame,
    category: str,
    count: int,
    used_tickers: set[str],
    used_stock_sectors: dict[str, int],
) -> tuple[pd.DataFrame, bool]:
    """
    Pick the highest-scoring eligible holdings.

    Stock rules:
      - Always prefer the highest Overall Score.
      - Maximum 2 stocks from the same sector portfolio-wide.
      - Maximum 1 Energy stock portfolio-wide.
      - Do not select the same ticker twice.

    ETF rules:
      - Pick highest-scoring ETFs.
      - Prefer different ETF categories when possible.
    """

    work = normalize_candidates(data, category)

    # Remove tickers already used elsewhere in the portfolio.
    work = work[
        ~work["Ticker"].isin(used_tickers)
    ].copy()

    if work.empty:
        return work, False

    # Make absolutely sure candidates are ordered by score.
    work = work.sort_values(
        ["Score", "MA Trend Score"],
        ascending=[False, False],
        na_position="last",
    )

    selected_indices: list[int] = []

    # =========================================================
    # ETFs
    # =========================================================
    if category == "ETF":

        used_categories: set[str] = set()

        # First pass: highest-scoring ETF from each category.
        for index, row in work.iterrows():

            etf_category = (
                str(row["Sector"])
                .strip()
                .casefold()
            )

            if etf_category in used_categories:
                continue

            selected_indices.append(index)
            used_categories.add(etf_category)

            if len(selected_indices) >= count:
                break

        diversification_relaxed = (
            len(selected_indices) < count
        )

        # Fill remaining ETF positions strictly by score.
        if diversification_relaxed:

            selected_set = set(selected_indices)

            for index, row in work.iterrows():

                if index in selected_set:
                    continue

                selected_indices.append(index)
                selected_set.add(index)

                if len(selected_indices) >= count:
                    break

    # =========================================================
    # STOCKS
    # =========================================================
    else:

        # Start with sectors already selected by earlier
        # categories in the portfolio.
        sector_counts = dict(used_stock_sectors)

        # Walk candidates strictly from highest score to lowest.
        for index, row in work.iterrows():

            sector = str(
                row["Sector"]
            ).strip()

            sector_key = sector.casefold()

            current_count = sector_counts.get(
                sector_key,
                0,
            )

            # Energy remains capped at 1.
            if sector_key == "energy":
                sector_limit = MAX_ENERGY_STOCKS
            else:
                sector_limit = MAX_STOCKS_PER_SECTOR

            # Skip only when the sector is already at its limit.
            if current_count >= sector_limit:
                continue

            # Otherwise take the highest-scoring available stock.
            selected_indices.append(index)

            sector_counts[sector_key] = (
                current_count + 1
            )

            if len(selected_indices) >= count:
                break

        # This flag now means the category couldn't fill
        # all requested positions under the sector limits.
        diversification_relaxed = (
            len(selected_indices) < count
        )

    selected = (
        work.loc[selected_indices]
        .head(count)
        .copy()
    )

    return (
        selected.reset_index(drop=True),
        diversification_relaxed,
    )

def build_portfolio(
    candidate_sets: dict[str, pd.DataFrame],
) -> tuple[pd.DataFrame, list[str]]:

    rows: list[dict[str, object]] = []
    warnings: list[str] = []
    used_tickers: set[str] = set()

    # Track stock-sector exposure across Growth, Value, and Dividend.
    used_stock_sectors: dict[str, int] = {}

    for category, target in CATEGORY_TARGETS.items():

        picks, relaxed = pick_diversified(
            candidate_sets.get(category, pd.DataFrame()),
            category,
            target,
            used_tickers,
            used_stock_sectors,
        )

        if len(picks) < target:
            warnings.append(
                f"{category}: only {len(picks)} of {target} "
                "eligible holdings were available."
            )

        elif relaxed:
            label = "categories" if category == "ETF" else "sectors"

            warnings.append(
                f"{category}: unique {label} were not available "
                "for every position, so the next highest-scoring "
                "candidate was used."
            )

        for _, row in picks.iterrows():

            ticker = str(row["Ticker"])
            sector = str(row["Sector"]).strip()

            used_tickers.add(ticker)

            # Track portfolio-wide stock-sector exposure.
            if category != "ETF":
                sector_key = sector.casefold()

                used_stock_sectors[sector_key] = (
                    used_stock_sectors.get(sector_key, 0) + 1
                )

            rows.append(
                {
                    "Category": category,
                    "Ticker": ticker,
                    "Company": row["Company"],
                    "Sector": sector,
                    "Price": row["Price"],
                    "Score": row["Score"],
                    "Allocation": POSITION_VALUE,
                    "Weight": POSITION_VALUE / PORTFOLIO_VALUE,
                }
            )

    return pd.DataFrame(rows), warnings


@st.cache_data(ttl=cache_ttl(), show_spinner=False)
def load_sample_portfolio() -> tuple[pd.DataFrame, list[str]]:
    """Return the cached, fully built sample portfolio."""
    return build_portfolio(load_all_candidates())


def clear_portfolio_caches() -> None:
    """Clear only portfolio-related and underlying market-data caches."""
    load_sample_portfolio.clear()
    load_all_candidates.clear()

    for loader, _ in _engine_jobs().values():
        clear_method = getattr(loader, "clear", None)
        if callable(clear_method):
            clear_method()


def money(value: object) -> str:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return "N/A"
    return f"${numeric:,.2f}" if np.isfinite(numeric) else "N/A"


def score_text(value: object) -> str:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return "N/A"
    return f"{numeric:.0f}" if np.isfinite(numeric) else "N/A"


def whole_shares(allocation: float, price: object) -> tuple[int, float]:
    try:
        numeric_price = float(price)
    except (TypeError, ValueError):
        return 0, allocation

    if not np.isfinite(numeric_price) or numeric_price <= 0:
        return 0, allocation

    shares = int(allocation // numeric_price)
    remainder = allocation - shares * numeric_price
    return shares, remainder


def render_card(row: pd.Series) -> None:
    category = str(row["Category"])
    ticker = html.escape(str(row["Ticker"]))
    company = html.escape(str(row["Company"] or row["Ticker"]))
    group = html.escape(str(row["Sector"] or "Unknown"))
    color = CATEGORY_COLORS[category]
    shares, remainder = whole_shares(float(row["Allocation"]), row["Price"])
    share_text = (
        f"{shares:,} whole shares"
        if shares > 0
        else "Fractional shares needed"
    )

    st.markdown(
        f"""
        <div class="portfolio-card">
            <div class="card-top">
                <div>
                    <div class="ticker">{ticker}</div>
                    <div class="company">{company}</div>
                </div>
                <div class="score" style="background:{color};">
                    {score_text(row['Score'])}
                </div>
            </div>
            <div class="group">{group}</div>
            <div class="card-grid">
                <span>Price <b>{money(row['Price'])}</b></span>
                <span>Allocation <b>${row['Allocation']:,.0f}</b></span>
                <span>Position <b>{row['Weight']:.0%}</b></span>
                <span>Estimate <b>{share_text}</b></span>
            </div>
            <div class="remainder">
                Estimated uninvested cash: ${remainder:,.2f}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


st.markdown(
    """
    <style>
    [data-testid="stSidebar"] {display:none;}
    [data-testid="collapsedControl"],
    [data-testid="stSidebarCollapsedControl"] {
        display:none !important;
        visibility:hidden !important;
    }
    .block-container {
        max-width:520px;
        padding:2.2rem 1rem 5rem 1rem;
    }
    .module-title {font-size:2rem;font-weight:800;margin-bottom:.15rem;}
    .module-subtitle {color:#9aa3b2;font-size:.9rem;margin-bottom:1rem;}
    .section-label {
        font-size:.82rem;
        color:#9aa3b2;
        font-weight:700;
        letter-spacing:.06rem;
        margin-top:1.25rem;
        margin-bottom:.2rem;
    }
    .portfolio-card {
        border:1px solid rgba(128,128,128,.25);
        border-radius:16px;
        padding:.95rem 1rem .85rem;
        background:rgba(128,128,128,.05);
        margin-top:.75rem;
    }
    .card-top {
        display:flex;
        justify-content:space-between;
        gap:.8rem;
        align-items:flex-start;
    }
    .ticker {font-size:1.25rem;font-weight:800;}
    .company {font-size:.82rem;color:#9aa3b2;margin-top:.12rem;}
    .group {font-size:.78rem;color:#9aa3b2;margin-top:.35rem;}
    .score {
        min-width:48px;
        text-align:center;
        border-radius:12px;
        padding:.35rem .45rem;
        color:white;
        font-weight:800;
        font-size:1.02rem;
    }
    .card-grid {
        display:grid;
        grid-template-columns:1fr 1fr;
        gap:.35rem .8rem;
        margin-top:.8rem;
        font-size:.81rem;
        color:#9aa3b2;
    }
    .remainder {font-size:.72rem;color:#7f8897;margin-top:.55rem;}
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="module-title">💼 Sample Portfolio</div>',
    unsafe_allow_html=True,
)
st.markdown(
    '<div class="module-subtitle">A diversified $10,000 model using the '
    'highest-ranked StockChoice candidates.</div>',
    unsafe_allow_html=True,
)

home_col, refresh_col = st.columns(2)
with home_col:
    st.page_link("app.py", label="Home", icon="🏠", width="stretch")
with refresh_col:
    refresh = st.button("🔄 Refresh", use_container_width=True)

if refresh:
    clear_portfolio_caches()
    st.rerun()

try:
    with st.spinner("Building the sample portfolio..."):
        portfolio, portfolio_warnings = load_sample_portfolio()
except Exception as exc:
    st.error(
        f"Portfolio data could not be loaded: "
        f"{type(exc).__name__}: {exc}"
    )
    st.info(
        "Make sure portfolio.py is saved in the pages folder beside growth.py, "
        "value.py, dividend.py, and etf.py."
    )
    st.stop()

actual_value = (
    float(portfolio["Allocation"].sum())
    if not portfolio.empty
    else 0.0
)
stock_count = (
    int((portfolio["Category"] != "ETF").sum())
    if not portfolio.empty
    else 0
)
etf_count = (
    int((portfolio["Category"] == "ETF").sum())
    if not portfolio.empty
    else 0
)

m1, m2 = st.columns(2)
m1.metric("Portfolio", f"${actual_value:,.0f}")
m2.metric("Positions", len(portfolio))
m3, m4 = st.columns(2)
m3.metric("Stocks", stock_count)
m4.metric("ETFs", etf_count)

st.markdown(
    '<div class="section-label">ALLOCATION</div>',
    unsafe_allow_html=True,
)
a, b = st.columns(2)
a.metric("🚀 Growth", "$2,000", "20%")
b.metric("💎 Value", "$2,000", "20%")
c, d = st.columns(2)
c.metric("💵 Dividend", "$2,000", "20%")
d.metric("🌐 ETFs", "$4,000", "40%")


# ============================================================
# STOCK PORTFOLIO HEATMAP
# ============================================================

stock_heatmap = portfolio[
    portfolio["Category"] != "ETF"
].copy()

if not stock_heatmap.empty:

    st.markdown(
        '<div class="section-label">STOCK PORTFOLIO HEATMAP</div>',
        unsafe_allow_html=True,
    )

    stock_heatmap["Score"] = pd.to_numeric(
        stock_heatmap["Score"],
        errors="coerce",
    )

    stock_heatmap["Allocation"] = pd.to_numeric(
        stock_heatmap["Allocation"],
        errors="coerce",
    ).fillna(POSITION_VALUE)

    stock_heatmap["Price"] = pd.to_numeric(
        stock_heatmap["Price"],
        errors="coerce",
    )

    stock_heatmap["Sector"] = (
        stock_heatmap["Sector"]
        .fillna("Unknown")
        .astype(str)
        .str.strip()
        .replace("", "Unknown")
    )

    stock_heatmap["Company"] = (
        stock_heatmap["Company"]
        .fillna("")
        .astype(str)
    )

    # Remove holdings without a valid Overall Score.
    stock_heatmap = stock_heatmap.dropna(
        subset=["Score"]
    )

    if not stock_heatmap.empty:

        fig_heatmap = px.treemap(
            stock_heatmap,
            path=[
                "Sector",
                "Ticker",
            ],
            values="Allocation",
            color="Score",
            color_continuous_scale=[
                [0.00, "#dc2626"],
                [0.40, "#ef4444"],
                [0.50, "#f59e0b"],
                [0.60, "#84cc16"],
                [1.00, "#16a34a"],
            ],
            range_color=[0, 100],

            custom_data=[
                "Score",
                "Company",
                "Category",
                "Price",
                "Allocation",
            ],
        )

        fig_heatmap.update_traces(
            texttemplate=(
                "<b>%{label}</b>"
                "<br>Score %{customdata[0]:.0f}"
            ),
            textfont=dict(
                size=14,
            ),
            marker=dict(
                line=dict(
                    color="rgba(255,255,255,.65)",
                    width=2,
                )
            ),
            hovertemplate=(
                "<b>%{label}</b><br>"
                "%{customdata[1]}<br>"
                "Category: %{customdata[2]}<br>"
                "Score: %{customdata[0]:.0f}<br>"
                "Price: $%{customdata[3]:,.2f}<br>"
                "Allocation: $%{customdata[4]:,.0f}"
                "<extra></extra>"
            ),
        )

        fig_heatmap.update_layout(
            height=430,
            margin=dict(
                l=5,
                r=5,
                t=5,
                b=5,
            ),
            coloraxis_colorbar=dict(
                title="Score",
                thickness=12,
            ),
        )

        st.plotly_chart(
            fig_heatmap,
            use_container_width=True,
            config={
                "displayModeBar": False,
                "responsive": True,
            },
        )

        st.caption(
            "Tile size represents portfolio allocation. "
            "Color represents StockChoice Overall Score."
        )

    else:
        st.info(
            "Stock score data is unavailable for the heatmap."
        )

# ============================================================
# ETF CATEGORY ALLOCATION DONUT
# ============================================================
etf_portfolio = portfolio[portfolio["Category"] == "ETF"].copy()

if not etf_portfolio.empty:
    st.markdown(
        '<div class="section-label">ETF CATEGORY ALLOCATION</div>',
        unsafe_allow_html=True,
    )

    etf_portfolio["Sector"] = (
        etf_portfolio["Sector"]
        .fillna("Unknown")
        .astype(str)
        .str.strip()
        .replace("", "Unknown")
    )
    etf_portfolio["Allocation"] = pd.to_numeric(
        etf_portfolio["Allocation"],
        errors="coerce",
    ).fillna(0)

    etf_category_data = (
        etf_portfolio.groupby("Sector", as_index=False)["Allocation"]
        .sum()
        .sort_values("Allocation", ascending=False)
    )
    etf_category_data = etf_category_data[
        etf_category_data["Allocation"] > 0
    ].copy()

    if not etf_category_data.empty:
        fig_etf_category = px.pie(
            etf_category_data,
            names="Sector",
            values="Allocation",
            hole=0.52,
            color_discrete_sequence=px.colors.qualitative.Pastel,
        )
        fig_etf_category.update_traces(
            textposition="inside",
            texttemplate="%{label}<br>%{percent}",
            insidetextorientation="horizontal",
            hovertemplate=(
                "<b>%{label}</b><br>"
                "Allocation: $%{value:,.0f}<br>"
                "ETF allocation: %{percent}"
                "<extra></extra>"
            ),
            marker=dict(
                line=dict(
                    color="rgba(255,255,255,0.7)",
                    width=2,
                )
            ),
        )
        fig_etf_category.update_layout(
            showlegend=False,
            height=400,
            autosize=True,
            margin=dict(l=10, r=10, t=20, b=20),
            annotations=[
                dict(
                    text="ETF<br>Categories",
                    x=0.5,
                    y=0.5,
                    showarrow=False,
                    font=dict(size=15),
                )
            ],
        )
        st.plotly_chart(
            fig_etf_category,
            use_container_width=True,
            config={"displayModeBar": False, "responsive": True},
        )
    else:
        st.info("ETF category allocation data is not available.")

for warning in portfolio_warnings:
    st.warning(warning)

if portfolio.empty:
    st.warning(
        "No eligible portfolio candidates were returned by the "
        "StockChoice engines."
    )
    st.stop()

for category in CATEGORY_TARGETS:
    holdings = portfolio[portfolio["Category"] == category]
    if holdings.empty:
        continue

    st.markdown(
        f'<div class="section-label">{CATEGORY_ICONS[category]} '
        f'{category.upper()}</div>',
        unsafe_allow_html=True,
    )

    for _, holding in holdings.iterrows():
        render_card(holding)

with st.expander("📋 View Portfolio Table", expanded=False):
    table = portfolio.copy()
    table["Estimated Shares"] = [
        whole_shares(allocation, price)[0]
        for allocation, price in zip(
            table["Allocation"],
            table["Price"],
        )
    ]

    st.dataframe(
        table[
            [
                "Category",
                "Ticker",
                "Company",
                "Sector",
                "Price",
                "Score",
                "Allocation",
                "Weight",
                "Estimated Shares",
            ]
        ],
        hide_index=True,
        use_container_width=True,
        column_config={
            "Price": st.column_config.NumberColumn("Price", format="$%.2f"),
            "Score": st.column_config.NumberColumn("Score", format="%.1f"),
            "Allocation": st.column_config.NumberColumn(
                "Allocation",
                format="$%.0f",
            ),
            "Weight": st.column_config.NumberColumn(
                "Weight",
                format="percent",
            ),
        },
    )

with st.expander("ℹ️ How this portfolio is built", expanded=False):
    st.markdown(
        """
        - The portfolio starts with **$10,000** split into ten **$1,000** positions.
        - It selects **2 Growth, 2 Value, 2 Dividend, and 4 ETF** candidates.
        - Candidates are ranked by the existing StockChoice **Overall Score**.
        - Growth, Value, and Dividend selections use different sectors when possible.
        - ETF selections use different ETF categories when possible.
        - A ticker already selected for one stock category is skipped in later categories.
        - If unique sectors or categories are unavailable, the next highest-ranked candidate is used.
        - Share estimates use whole shares. Remaining cash is shown for each position.
        """
    )

st.divider()
st.caption(
    "Sample portfolio for informational and educational purposes only. "
    "Prices and scores may change, and this is not personalized investment advice."
)
