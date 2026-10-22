"""
app.py
------
Streamlit Web Application for Angel One Indian F&O Trading Charges Calculator.
Exclusively built for Angel One brokerage with statutory date-aware tax schedules.
"""

from datetime import date, datetime
from decimal import Decimal
import json

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from calculator import AngelOneCalculator, CalculationResult
from charge_rules import Exchange, PositionType, Segment


# ---------------------------------------------------------
# Page Configuration & Styling
# ---------------------------------------------------------
st.set_page_config(
    page_title="Angel One F&O Charges Calculator",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

CUSTOM_CSS = """
<style>
    /* Metric Card Enhancements */
    .metric-container {
        border-radius: 12px;
        padding: 16px 20px;
        background: linear-gradient(135deg, rgba(22, 31, 48, 0.8), rgba(15, 23, 42, 0.95));
        border: 1px solid rgba(255, 255, 255, 0.08);
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.25);
        margin-bottom: 12px;
    }
    .metric-title {
        font-size: 0.82rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: #94A3B8;
        margin-bottom: 4px;
    }
    .metric-value {
        font-size: 1.7rem;
        font-weight: 700;
        color: #F8FAFC;
    }
    .metric-sub {
        font-size: 0.82rem;
        color: #64748B;
        margin-top: 4px;
    }
    .profit-text {
        color: #10B981 !important;
    }
    .loss-text {
        color: #EF4444 !important;
    }
    .badge-regime {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 600;
        background-color: rgba(242, 101, 34, 0.15);
        color: #F26522;
        border: 1px solid rgba(242, 101, 34, 0.3);
    }
    .badge-verified {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 600;
        background-color: rgba(16, 185, 129, 0.15);
        color: #10B981;
        border: 1px solid rgba(16, 185, 129, 0.3);
    }
    .badge-warning {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 600;
        background-color: rgba(239, 68, 68, 0.15);
        color: #EF4444;
        border: 1px solid rgba(239, 68, 68, 0.3);
    }
    /* Brand Header */
    .brand-title {
        font-size: 1.8rem;
        font-weight: 800;
        letter-spacing: -0.02em;
        margin-bottom: 2px;
    }
    .brand-subtitle {
        color: #94A3B8;
        font-size: 0.95rem;
        margin-bottom: 16px;
    }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


@st.cache_resource

def get_calculator():
    return AngelOneCalculator()


calc = get_calculator()


# ---------------------------------------------------------
# Sidebar Inputs
# ---------------------------------------------------------
with st.sidebar:
    st.markdown(
        """
        <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 10px;">
            <div style="background-color: #F26522; width: 36px; height: 36px; border-radius: 8px; display: flex; align-items: center; justify-content: center; font-weight: bold; color: white; font-size: 18px;">
                A1
            </div>
            <div>
                <div style="font-weight: 800; font-size: 1.1rem; line-height: 1.1;">Angel One</div>
                <div style="font-size: 0.75rem; color: #94A3B8;">F&O Charges Engine</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.subheader("Trade Parameters")

    # Position Type
    position_type = st.radio(
        "Position Type",
        options=[PositionType.LONG, PositionType.SHORT],
        horizontal=True,
        help="Long: Buy first, then Sell to close. Short: Sell first, then Buy to cover.",
    )

    # Exchange
    exchange = st.radio(
        "Exchange",
        options=[Exchange.NSE, Exchange.BSE],
        horizontal=True,
        help="National Stock Exchange (NSE) or Bombay Stock Exchange (BSE)",
    )

    # Segment
    segment = st.selectbox(
        "Derivatives Segment",
        options=Segment.ALL,
        index=2,  # Default to Index Options
        help="Select whether this is an Index or Stock contract, Futures or Options.",
    )

    # Lot size presets helper
    is_options = Segment.is_options(segment)
    is_futures = Segment.is_futures(segment)

    with st.expander("Lot Multiplier Helper", expanded=False):
        preset_cols = st.columns(2)
        with preset_cols[0]:
            if exchange == Exchange.NSE:
                lot_size = st.selectbox("Underlying Lot", options=[65, 25, 15, 30, 100, 1], index=0, help="NIFTY (65/25), BANKNIFTY (15/30), etc.")
            else:
                lot_size = st.selectbox("Underlying Lot", options=[20, 10, 50, 1], index=0, help="SENSEX (20/10), BANKEX (15), etc.")
        with preset_cols[1]:
            lot_count = st.number_input("Lots", min_value=1, max_value=500, value=1, step=1)
        suggested_qty = lot_size * lot_count
        use_suggested = st.checkbox(f"Use {suggested_qty} Qty", value=False)

    # Quantity
    default_qty = suggested_qty if use_suggested else (65 if is_options else 65)
    quantity = st.number_input(
        "Total Quantity",
        min_value=1,
        max_value=10_000_000,
        value=int(default_qty),
        step=1,
        help="Total contract quantity traded (e.g., 65 for 1 lot of NIFTY).",
    )

    # Prices
    col_p1, col_p2 = st.columns(2)
    with col_p1:
        default_buy = 120.0 if is_options else 25000.0
        buy_price = st.number_input(
            "Buy Price (₹)",
            min_value=0.05,
            max_value=1_000_000.0,
            value=float(default_buy),
            step=0.05,
            format="%.2f",
            help="Purchase price / premium per unit.",
        )
    with col_p2:
        default_sell = 135.0 if is_options else 25150.0
        sell_price = st.number_input(
            "Sell Price (₹)",
            min_value=0.05,
            max_value=1_000_000.0,
            value=float(default_sell),
            step=0.05,
            format="%.2f",
            help="Selling price / premium per unit.",
        )

    # Executed Orders
    col_o1, col_o2 = st.columns(2)
    with col_o1:
        buy_orders = st.number_input(
            "Buy Orders",
            min_value=1,
            max_value=1000,
            value=1,
            step=1,
            help="Number of executed buy orders (Brokerage is charged per executed order).",
        )
    with col_o2:
        sell_orders = st.number_input(
            "Sell Orders",
            min_value=1,
            max_value=1000,
            value=1,
            step=1,
            help="Number of executed sell orders.",
        )

    # Trade Date
    trade_date = st.date_input(
        "Trade Date",
        value=date.today(),
        help="Used to apply statutory tax rates applicable on this date (e.g., pre/post 1 April 2026 STT schedules).",
    )

# ---------------------------------------------------------
# Computation
# ---------------------------------------------------------
try:
    result: CalculationResult = calc.calculate(
        exchange=exchange,
        segment=segment,
        buy_price=buy_price,
        sell_price=sell_price,
        quantity=quantity,
        num_buy_orders=buy_orders,
        num_sell_orders=sell_orders,
        trade_date=trade_date,
        position_type=position_type,
        introductory_offer=False,
    )
    has_error = False
    error_msg = ""
except Exception as e:
    has_error = True
    error_msg = str(e)


# ---------------------------------------------------------
# Main Page Header & Regulatory Regime Notices
# ---------------------------------------------------------
st.markdown('<div class="brand-title">Angel One F&O Charges & P&L Calculator</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="brand-subtitle">Exclusively calibrated for Angel One standard F&O tariff (₹20/order) and Indian statutory taxation.</div>',
    unsafe_allow_html=True,
)

if has_error:
    st.error(f"⚠️ Calculation Error: {error_msg}")
    st.stop()


# Regime and Verification Status Header
regime = result.rules.regime
cols_header = st.columns([2, 1, 1])

with cols_header[0]:
    st.markdown(
        f"""
        <div style="margin-bottom: 8px;">
            <span class="badge-regime">📅 Regime: {regime.name}</span>
            {"<span class='badge-verified'>✓ Verified Statutory Rates</span>" if result.rules.is_verified else "<span class='badge-warning'>⚠️ Unverified Schedule</span>"}
        </div>
        """,
        unsafe_allow_html=True,
    )

with cols_header[1]:
    st.caption(f"Brokerage Tariff: **{result.rules.plan_name}**")

with cols_header[2]:
    st.caption(f"Charge Basis: **{'Premium Turnover' if Segment.is_options(segment) else 'Futures Turnover'}**")


# Verification Warning if date outside verified schedule
if result.rules.verification_warning:
    st.warning(f"⚠️ {result.rules.verification_warning}")

# Reconciliation Notice for 1 April 2026 onwards
if result.rules.reconciliation_note:
    st.info(
        f"**Statutory STT Schedule (Effective 1 April 2026):**\n\n"
        f"{result.rules.reconciliation_note}\n\n"
        f"- **Futures STT:** 0.05% on sell turnover (₹5,000 per crore)\n"
        f"- **Options STT:** 0.15% on sell premium turnover (₹15,000 per crore)"
    )


# ---------------------------------------------------------
# Summary KPI Cards
# ---------------------------------------------------------
st.markdown("### Trade Performance Overview")

kpi_cols = st.columns(4)

# Gross P&L
gross_color = "profit-text" if result.gross_pnl > 0 else ("loss-text" if result.gross_pnl < 0 else "")
with kpi_cols[0]:
    st.markdown(
        f"""
        <div class="metric-container">
            <div class="metric-title">Gross P&L</div>
            <div class="metric-value {gross_color}">₹{result.gross_pnl:,.2f}</div>
            <div class="metric-sub">Spread: ₹{(result.sell_price - result.buy_price):+,.2f} / unit</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# Total Charges
with kpi_cols[1]:
    charges_pct = (result.total_charges / result.total_turnover * Decimal("100")) if result.total_turnover > 0 else Decimal("0")
    st.markdown(
        f"""
        <div class="metric-container">
            <div class="metric-title">Total Charges & Taxes</div>
            <div class="metric-value">₹{result.total_charges:,.2f}</div>
            <div class="metric-sub">{charges_pct:.3f}% of total turnover</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# Net P&L
net_color = "profit-text" if result.net_pnl > 0 else ("loss-text" if result.net_pnl < 0 else "")
with kpi_cols[2]:
    st.markdown(
        f"""
        <div class="metric-container">
            <div class="metric-title">Net P&L (Post Charges)</div>
            <div class="metric-value {net_color}">₹{result.net_pnl:,.2f}</div>
            <div class="metric-sub">{'Profit' if result.is_profitable else 'Loss'} after all fees</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# Break-even Price
with kpi_cols[3]:
    st.markdown(
        f"""
        <div class="metric-container">
            <div class="metric-title">Break-Even Exit Price</div>
            <div class="metric-value">₹{result.breakeven_exit_price:,.2f}</div>
            <div class="metric-sub">Need {result.breakeven_diff_points:+,.2f} pts ({result.breakeven_diff_pct:+,.2f}%) to cover fees</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------
# Turnover Breakdown Bar
# ---------------------------------------------------------
t_col1, t_col2, t_col3, t_col4 = st.columns(4)
with t_col1:
    st.metric("Buy Turnover", f"₹{result.buy_turnover:,.2f}")
with t_col2:
    st.metric("Sell Turnover", f"₹{result.sell_turnover:,.2f}")
with t_col3:
    st.metric("Total Turnover", f"₹{result.total_turnover:,.2f}")
with t_col4:
    st.metric("Total Executed Orders", f"{result.total_orders} orders", delta=f"₹{result.total_brokerage:,.2f} Brokerage")


st.markdown("---")


# ---------------------------------------------------------
# Detailed Breakdown & Visual Analysis
# ---------------------------------------------------------
tab_table, tab_chart, tab_contract, tab_breakeven = st.tabs([
    "📋 Itemized Charges Breakdown",
    "📊 Charges Composition Chart",
    "🧾 Angel One Contract Note Preview",
    "🎯 Break-Even Analysis",
])

with tab_table:
    st.caption("Full itemized accounting of all brokerage, statutory, and regulatory levies:")

    table_data = []
    for item in result.line_items:
        table_data.append({
            "Charge Component": item.charge_name,
            "Basis of Charge": item.basis,
            "Rate Applied": item.rate_display,
            "Buy Side (₹)": f"₹{item.buy_component:,.2f}",
            "Sell Side (₹)": f"₹{item.sell_component:,.2f}",
            "Total Amount (₹)": f"₹{item.total_amount:,.2f}",
            "Levying Authority": item.statutory_authority,
        })

    df_table = pd.DataFrame(table_data)
    st.dataframe(df_table, use_container_width=True, hide_index=True)

    # Quick download options
    csv_buffer = df_table.to_csv(index=False).encode("utf-8")
    json_str = json.dumps(result.to_dict(), indent=2)

    dl_cols = st.columns([1, 1, 3])
    with dl_cols[0]:
        st.download_button(
            label="📥 Download CSV",
            data=csv_buffer,
            file_name=f"angel_one_charges_{segment.replace(' ', '_')}.csv",
            mime="text/csv",
        )
    with dl_cols[1]:
        st.download_button(
            label="📥 Download JSON",
            data=json_str,
            file_name=f"angel_one_trade_{segment.replace(' ', '_')}.json",
            mime="application/json",
        )

with tab_chart:
    col_chart1, col_chart2 = st.columns([1, 1])

    with col_chart1:
        st.markdown("#### Charges Distribution")
        # Build donut chart of charges
        charge_labels = []
        charge_values = []
        for item in result.line_items:
            val = float(item.total_amount)
            if val > 0:
                charge_labels.append(item.charge_name.split("(")[0].strip())
                charge_values.append(val)

        if sum(charge_values) > 0:
            fig_pie = go.Figure(
                data=[
                    go.Pie(
                        labels=charge_labels,
                        values=charge_values,
                        hole=0.55,
                        textinfo="label+percent",
                        marker=dict(colors=["#F26522", "#3B82F6", "#10B981", "#8B5CF6", "#EC4899", "#F59E0B", "#6366F1"]),
                    )
                ]
            )
            fig_pie.update_layout(
                showlegend=False,
                margin=dict(t=10, b=10, l=10, r=10),
                height=320,
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#F8FAFC"),
            )
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("Total charges are zero.")

    with col_chart2:
        st.markdown("#### P&L vs Charges Waterfall")
        # Waterfall or Bar comparison
        fig_bar = go.Figure(
            go.Bar(
                x=["Gross P&L", "Total Charges", "Net P&L"],
                y=[float(result.gross_pnl), -float(result.total_charges), float(result.net_pnl)],
                marker_color=["#3B82F6", "#EF4444", "#10B981" if result.net_pnl > 0 else "#EF4444"],
                text=[f"₹{result.gross_pnl:,.2f}", f"-₹{result.total_charges:,.2f}", f"₹{result.net_pnl:,.2f}"],
                textposition="auto",
            )
        )
        fig_bar.update_layout(
            margin=dict(t=10, b=10, l=10, r=10),
            height=320,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#F8FAFC"),
            yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.08)"),
        )
        st.plotly_chart(fig_bar, use_container_width=True)

with tab_contract:
    st.markdown("#### Simulated Angel One Contract Note Excerpt")
    st.caption("Standard broker contract note itemization format:")

    cn_lines = [
        ("Trade Date", result.trade_date.strftime("%d-%b-%Y")),
        ("Exchange & Segment", f"{result.exchange} - {result.segment}"),
        ("Position Direction", result.position_type),
        ("Quantity Traded", f"{result.quantity:,}"),
        ("Buy Turnover", f"₹{result.buy_turnover:,.2f}"),
        ("Sell Turnover", f"₹{result.sell_turnover:,.2f}"),
        ("Total Turnover", f"₹{result.total_turnover:,.2f}"),
        ("---", "---"),
        ("Brokerage (Angel One @ ₹20/order)", f"₹{result.total_brokerage:,.2f}"),
        ("Securities Transaction Tax (STT)", f"₹{result.stt:,.2f}"),
        ("Exchange Transaction Charges", f"₹{result.exchange_txn_charge:,.2f}"),
        ("SEBI Turnover Fees", f"₹{result.sebi_turnover_charge:,.2f}"),
        ("Stamp Duty", f"₹{result.stamp_duty:,.2f}"),
        ("Investor Protection Fund Trust (IPFT)", f"₹{result.ipft:,.2f}"),
        ("GST @ 18% (Brokerage + ETC + SEBI + IPFT)", f"₹{result.gst:,.2f}"),
        ("---", "---"),
        ("Total Charges & Statutory Levies", f"₹{result.total_charges:,.2f}"),
        ("Net Obligation / Realized P&L", f"₹{result.net_pnl:,.2f}"),
    ]

    for label, val in cn_lines:
        if label == "---":
            st.markdown("<hr style='margin: 4px 0; border-color: rgba(255,255,255,0.1);'/>", unsafe_allow_html=True)
        else:
            col_l, col_r = st.columns([2, 1])
            with col_l:
                st.markdown(f"<span style='color: #94A3B8;'>{label}</span>", unsafe_allow_html=True)
            with col_r:
                st.markdown(f"**{val}**")

with tab_breakeven:
    st.markdown("#### Break-Even Mathematical Solution")

    if result.position_type == PositionType.LONG:
        st.write(
            f"You bought at **₹{result.buy_price:.2f}**. To cover Angel One brokerage (₹{result.total_brokerage:.2f}), "
            f"STT, Exchange turnover charges, SEBI charges, Stamp Duty, IPFT, and 18% GST, your sell exit price "
            f"must be at least **₹{result.breakeven_exit_price:.2f}**."
        )
        st.metric(
            label="Required Price Rise to Break Even",
            value=f"₹{result.breakeven_diff_points:+.2f} points",
            delta=f"{result.breakeven_diff_pct:+.2f}%",
        )
    else:
        st.write(
            f"You shorted at **₹{result.sell_price:.2f}**. To cover Angel One brokerage (₹{result.total_brokerage:.2f}) "
            f"and all statutory levies, your buy-back exit price must be no higher than **₹{result.breakeven_exit_price:.2f}**."
        )
        st.metric(
            label="Required Price Drop to Break Even",
            value=f"₹{result.breakeven_diff_points:+.2f} points",
            delta=f"{result.breakeven_diff_pct:+.2f}%",
            delta_color="inverse",
        )

    st.markdown(
        """
        > **Formula Derivation:**
        >
        > Turnover fee factor with GST: $k = (r_{ETC} + r_{SEBI} + r_{IPFT}) \\times (1 + r_{GST})$
        >
        > Buy-side rate: $r_{buy} = r_{Stamp} + k$
        >
        > Sell-side rate: $r_{sell} = r_{STT} + k$
        >
        > Fixed Brokerage with GST: $B_{total} = B \\times (1 + r_{GST})$
        >
        > - **Long Position:** $P_{exit} = \\frac{P_{buy} \\cdot Q \\cdot (1 + r_{buy}) + B_{total}}{Q \\cdot (1 - r_{sell})}$
        > - **Short Position:** $P_{exit} = \\frac{P_{sell} \\cdot Q \\cdot (1 - r_{sell}) - B_{total}}{Q \\cdot (1 + r_{buy})}$
        """
    )


# ---------------------------------------------------------
# Footer & Documentation Links
# ---------------------------------------------------------
st.markdown("---")
f_col1, f_col2 = st.columns([3, 1])
with f_col1:
    st.caption(
        "© 2026 Angel One F&O Charges Calculator. Built for Indian Derivatives Traders. "
        "Verified with CBDT, SEBI True-to-Label, and Exchange circulars."
    )
with f_col2:
    st.caption("Calculations powered by Python `Decimal`")
