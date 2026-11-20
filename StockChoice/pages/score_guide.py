"""Stockchoice score guide."""
from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app_utils import apply_card_density, initialize_settings

initialize_settings()

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
    padding:2.5rem 1rem 5rem 1rem;
}
.module-title {
    font-size:2rem;
    font-weight:800;
    margin-bottom:.15rem;
}
.module-subtitle {
    color:#9aa3b2;
    font-size:.9rem;
    margin-bottom:1rem;
}
.guide-card {
    border:1px solid rgba(128,128,128,.25);
    border-radius:16px;
    padding:.9rem 1rem;
    background:rgba(128,128,128,.05);
    margin:.6rem 0;
}
.guide-title {
    font-size:1rem;
    font-weight:800;
    margin-bottom:.25rem;
}
.guide-text {
    font-size:.86rem;
    color:#9aa3b2;
    line-height:1.5;
}
.section-label {
    font-size:.82rem;
    color:#9aa3b2;
    font-weight:700;
    margin-top:1rem;
    margin-bottom:.35rem;
}
</style>
""",
    unsafe_allow_html=True,
)

apply_card_density()

st.markdown(
    '<div class="module-title">📖 Score Guide</div>',
    unsafe_allow_html=True,
)
st.markdown(
    '<div class="module-subtitle">How Stockchoice calculates and interprets '
    'the scores shown on Growth, Value, Dividend, and ETF research cards.</div>',
    unsafe_allow_html=True,
)

st.page_link("app.py", label="Home", icon="🏠", width="stretch")

st.markdown(
    '<div class="section-label">HOW TO READ THE SCORES</div>',
    unsafe_allow_html=True,
)
st.markdown(
    """
<div class="guide-card">
  <div class="guide-title">0–100 scoring</div>
  <div class="guide-text">
    Factor scores, the Moving Average Trend Score, and Overall Score are
    normalized to a 0–100 scale. Higher is generally stronger. When an input
    is unavailable, Stockchoice uses the available components and reweights
    them proportionally rather than treating the missing value as zero.
  </div>
</div>
""",
    unsafe_allow_html=True,
)

st.write("**Suggested interpretation**")
st.write("• **80–100:** Very Strong")
st.write("• **65–79:** Strong")
st.write("• **50–64:** Moderate")
st.write("• **35–49:** Weak")
st.write("• **0–34:** Very Weak")
st.caption(
    "These bands are an interpretation aid, not part of the underlying score formulas."
)

st.markdown(
    '<div class="section-label">MOVING AVERAGE TREND SCORE</div>',
    unsafe_allow_html=True,
)
st.markdown(
    """
<div class="guide-card">
  <div class="guide-title">Why moving averages now matter more</div>
  <div class="guide-text">
    The Moving Average Trend Score contributes 35% of every Overall Score.
    It combines the price's percentage distance from the 50-day average,
    its percentage distance from the 200-day average, and the alignment of
    the 50-day average relative to the 200-day average.
  </div>
</div>
""",
    unsafe_allow_html=True,
)

with st.expander("📊 Moving-average percentage thresholds", expanded=True):
    st.write("**Price versus the 50-day moving average: 7 points maximum**")
    st.write("• **At least 5% above:** 7 points")
    st.write("• **2% to under 5% above:** 6 points")
    st.write("• **At or up to 2% above:** 5 points")
    st.write("• **Less than 2% below:** 2 points")
    st.write("• **2% or more below:** 0 points")

    st.write("**Price versus the 200-day moving average: 10 points maximum**")
    st.write("• **At least 10% above:** 10 points")
    st.write("• **5% to under 10% above:** 9 points")
    st.write("• **At or up to 5% above:** 7 points")
    st.write("• **Less than 5% below:** 3 points")
    st.write("• **5% or more below:** 0 points")

    st.write("**50-day versus 200-day alignment: 8 points maximum**")
    st.write("• **50-day at least 5% above 200-day:** 8 points")
    st.write("• **50-day 2% to under 5% above 200-day:** 7 points")
    st.write("• **50-day at or up to 2% above 200-day:** 5 points")
    st.write("• **50-day less than 2% below 200-day:** 2 points")
    st.write("• **50-day 2% or more below 200-day:** 0 points")

    st.caption(
        "The earned points are divided by the available maximum points and "
        "converted to a 0–100 MA Trend Score. Missing moving-average inputs "
        "are excluded and the available portions are reweighted."
    )

with st.expander("📈 Growth scores", expanded=True):
    st.write(
        "**Overall Score:** Growth 22% + Quality 18% + Momentum 15% + "
        "Valuation 10% + MA Trend 35%."
    )
    st.write(
        "**Growth Score:** Revenue growth and earnings growth. Revenue growth "
        "is scored from -5% to 35%, while earnings growth is scored from -10% "
        "to 40%. Values are capped to the 0–100 scoring range."
    )
    st.write(
        "**Quality Score:** Return on equity from 0% to 35% and operating "
        "margin from 0% to 30%."
    )
    st.write(
        "**Momentum Score:** The average of 6-month return scored from -20% "
        "to 35% and 12-month return scored from -30% to 60%."
    )
    st.write(
        "**Valuation Score:** Based on positive forward P/E. A forward P/E of "
        "15 or lower receives the strongest score, and 55 or higher receives "
        "the weakest score."
    )
    st.write(
        "**MA Trend Score:** Price versus the 50-day average, price versus the "
        "200-day average, and 50-day/200-day alignment."
    )
    st.write(
        "**Card fields:** Price, Growth Score, Momentum Score, 12-month return, "
        "and percentage above or below the 50-day and 200-day averages. The "
        "colored badge is Overall Score."
    )

with st.expander("💎 Value scores"):
    st.write(
        "**Overall Score:** Valuation 25% + Quality 20% + Financial Strength "
        "10% + Momentum 10% + MA Trend 35%."
    )
    st.write(
        "**Valuation Score:** Forward P/E scored from 8 to 30, price-to-book "
        "from 1 to 6, EV/EBITDA from 5 to 20, and free-cash-flow yield from 0% "
        "to 10%. Lower valuation multiples and higher FCF yield score better."
    )
    st.write(
        "**Quality Score:** Return on equity from 0% to 30%, operating margin "
        "from 0% to 25%, and whether free cash flow is positive."
    )
    st.write(
        "**Financial Strength Score:** Debt-to-equity scored from 25 to 250, "
        "with lower leverage scoring better."
    )
    st.write(
        "**Momentum Score:** 12-month return scored from -30% to 35%."
    )
    st.write(
        "**MA Trend Score:** Price versus the 50-day average, price versus the "
        "200-day average, and 50-day/200-day alignment."
    )
    st.write(
        "**Value Trap Risk:** A separate risk score based on revenue and "
        "earnings deterioration, negative free cash flow, weak quality, and "
        "weak momentum. **Lower is better.**"
    )
    st.write(
        "**Card fields:** Price, Valuation Score, FCF Yield, Value Trap Risk, "
        "and percentage above or below the 50-day and 200-day averages. The "
        "colored badge is Overall Score."
    )

with st.expander("💰 Dividend scores"):
    st.write(
        "**Overall Score:** Income 25% + Sustainability 20% + Quality 10% + "
        "Balance Sheet 5% + Momentum 5% + MA Trend 35%."
    )
    st.write(
        "**Income Score:** Dividend yield scored from 1% to 6%, with higher "
        "yields scoring better within that range."
    )
    st.write(
        "**Sustainability / Safety Score:** Payout ratio scored from 35% to "
        "90% with lower values scoring better, positive free cash flow, and "
        "earnings growth scored from -10% to 15%."
    )
    st.write(
        "**Quality Score:** Return on equity from 5% to 30% and operating "
        "margin from 5% to 25%."
    )
    st.write(
        "**Balance Sheet Score:** Debt-to-equity scored from 25 to 250, with "
        "lower leverage scoring better."
    )
    st.write(
        "**Momentum Score:** 12-month price return scored from -25% to 35%."
    )
    st.write(
        "**MA Trend Score:** Price versus the 50-day average, price versus the "
        "200-day average, and 50-day/200-day alignment."
    )
    st.write(
        "**Card fields:** Price, Dividend Yield, Payout Ratio, Sustainability "
        "Score, and percentage above or below the 50-day and 200-day averages. "
        "The colored badge is Overall Score."
    )

with st.expander("🌐 ETF scores"):
    st.write(
        "**Overall Score:** Performance 23% + Momentum 15% + Risk 10% + "
        "Cost 10% + Income 7% + MA Trend 35%."
    )
    st.write(
        "**Performance Score:** The average of 3-month return scored from -12% "
        "to 18%, 6-month return scored from -18% to 30%, and 12-month return "
        "scored from -25% to 45%."
    )
    st.write(
        "**Momentum Score:** Uses the same 3-month, 6-month, and 12-month "
        "return ranges as the Performance Score."
    )
    st.write(
        "**Risk Score:** Annualized price volatility scored from 10% to 40%, "
        "with lower volatility scoring better."
    )
    st.write(
        "**Cost Score:** Expense ratio scored from 0.02% to 0.75%, with lower "
        "expenses scoring better."
    )
    st.write(
        "**Income Score:** Trailing dividend yield scored from 0% to 4.5%, "
        "using approximately the previous 365 days of distributions relative "
        "to the current price."
    )
    st.write(
        "**MA Trend Score:** Price versus the 50-day average, price versus the "
        "200-day average, and 50-day/200-day alignment."
    )
    st.write(
        "**Card fields:** Price, 12-month return, Expense Ratio, Dividend Yield, "
        "and percentage above or below the 50-day and 200-day averages. The "
        "colored badge is Overall Score."
    )

st.divider()
st.info(
    "Stockchoice scores are screening and ranking signals. They are designed "
    "to organize research, not predict returns or provide personalized "
    "investment advice."
)
