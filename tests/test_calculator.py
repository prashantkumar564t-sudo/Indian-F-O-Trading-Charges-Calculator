"""
tests/test_calculator.py
------------------------
Automated test suite for Angel One Indian F&O Trading Charges Calculator.
"""

from datetime import date
from decimal import Decimal
import pytest

from calculator import AngelOneCalculator, round_curr
from charge_rules import Exchange, PositionType, Segment, get_stt_regime, resolve_charge_rules


@pytest.fixture
def calc():
    return AngelOneCalculator()


# ==========================================
# 1. Statutory STT Date Regime Tests
# ==========================================

def test_stt_regime_pre_oct_2024():
    """Verify STT rates before 1 October 2024."""
    test_date = date(2024, 6, 15)
    regime, is_verified, warning = get_stt_regime(test_date)
    assert regime.regime_id == "historical_pre_oct_2024"
    assert regime.futures_sell_rate == Decimal("0.000125")  # 0.0125%
    assert regime.options_sell_rate == Decimal("0.000625")  # 0.0625%
    assert is_verified is True
    assert warning is None


def test_stt_regime_oct_2024_to_mar_2026():
    """Verify STT rates under Finance (No. 2) Act 2024 (1 Oct 2024 - 31 Mar 2026)."""
    test_date = date(2025, 5, 20)
    regime, is_verified, warning = get_stt_regime(test_date)
    assert regime.regime_id == "budget_2024_to_mar_2026"
    assert regime.futures_sell_rate == Decimal("0.000200")  # 0.02%
    assert regime.options_sell_rate == Decimal("0.001000")  # 0.10%
    assert is_verified is True
    assert warning is None


def test_stt_regime_post_apr_2026_statutory():
    """Verify STT statutory hike effective 1 April 2026."""
    test_date = date(2026, 4, 1)
    regime, is_verified, warning = get_stt_regime(test_date)
    assert regime.regime_id == "budget_2026_statutory"
    assert regime.futures_sell_rate == Decimal("0.000500")  # 0.05%
    assert regime.options_sell_rate == Decimal("0.001500")  # 0.15%
    assert is_verified is True
    assert warning is None

    # Check later date in 2026
    later_date = date(2026, 10, 22)
    regime_later, is_verified_later, warning_later = get_stt_regime(later_date)
    assert regime_later.regime_id == "budget_2026_statutory"
    assert regime_later.futures_sell_rate == Decimal("0.000500")
    assert regime_later.options_sell_rate == Decimal("0.001500")
    assert is_verified_later is True
    assert warning_later is None


def test_stt_unverified_future_date_warning():
    """Dates past the verified schedule trigger a verification warning."""
    future_date = date(2028, 1, 1)
    regime, is_verified, warning = get_stt_regime(future_date)
    assert is_verified is False
    assert warning is not None
    assert "beyond the verified schedule" in warning


# ==========================================
# 2. Angel One Brokerage Plan Tests
# ==========================================

def test_angel_one_standard_brokerage(calc):
    """Angel One standard plan: ₹20 per executed order."""
    res = calc.calculate(
        exchange=Exchange.NSE,
        segment=Segment.INDEX_FUTURES,
        buy_price=25000,
        sell_price=25100,
        quantity=50,
        num_buy_orders=2,
        num_sell_orders=3,
        trade_date=date(2026, 5, 10),
        introductory_offer=False,
    )
    # 2 buy orders * 20 = 40, 3 sell orders * 20 = 60
    assert res.brokerage_buy == Decimal("40.00")
    assert res.brokerage_sell == Decimal("60.00")
    assert res.total_brokerage == Decimal("100.00")
    assert res.total_orders == 5


def test_angel_one_introductory_zero_brokerage(calc):
    """Angel One introductory offer: ₹0 brokerage; statutory charges still apply."""
    res = calc.calculate(
        exchange=Exchange.NSE,
        segment=Segment.INDEX_FUTURES,
        buy_price=25000,
        sell_price=25100,
        quantity=50,
        num_buy_orders=1,
        num_sell_orders=1,
        trade_date=date(2026, 5, 10),
        introductory_offer=True,
    )
    assert res.total_brokerage == Decimal("0.00")
    assert res.stt > Decimal("0.00")
    assert res.stamp_duty > Decimal("0.00")
    assert res.exchange_txn_charge > Decimal("0.00")
    assert res.total_charges > Decimal("0.00")


# ==========================================
# 3. Futures Calculation Tests (April 2026 STT @ 0.05%)
# ==========================================

def test_futures_calculation_post_apr_2026(calc):
    """
    Test Index Futures trade on NSE post 1 April 2026:
    Buy Price: 25,000, Sell Price: 25,100, Qty: 50.
    Buy Turnover = 1,250,000; Sell Turnover = 1,255,000; Total = 2,505,000.
    Brokerage = 20 * 2 = 40.
    STT = 0.05% of 1,255,000 = 627.50.
    Stamp Duty = 0.002% of 1,250,000 = 25.00.
    ETC = 0.00173% of 2,505,000 = 43.3365 -> 43.34.
    SEBI = 0.0001% of 2,505,000 = 2.505 -> 2.51.
    IPFT = 0.0001% of 2,505,000 = 2.505 -> 2.51.
    Taxable Services = 40 + 43.3365 + 2.505 + 2.505 = 88.347
    GST = 18% of 88.347 = 15.90246 -> 15.90.
    """
    res = calc.calculate(
        exchange=Exchange.NSE,
        segment=Segment.INDEX_FUTURES,
        buy_price=Decimal("25000"),
        sell_price=Decimal("25100"),
        quantity=50,
        num_buy_orders=1,
        num_sell_orders=1,
        trade_date=date(2026, 4, 15),
    )

    assert res.buy_turnover == Decimal("1250000.00")
    assert res.sell_turnover == Decimal("1255000.00")
    assert res.total_turnover == Decimal("2505000.00")
    assert res.total_brokerage == Decimal("40.00")
    assert res.stt == Decimal("627.50")
    assert res.stamp_duty == Decimal("25.00")
    assert res.exchange_txn_charge == Decimal("43.34")
    assert res.sebi_turnover_charge == Decimal("2.51")
    assert res.ipft == Decimal("2.51")
    assert res.gst == Decimal("15.90")

    # Gross P&L: (25100 - 25000) * 50 = 5000
    assert res.gross_pnl == Decimal("5000.00")

    # Total charges approx: 40 + 627.50 + 25.00 + 43.3365 + 2.505 + 2.505 + 15.90246 = 756.75
    assert res.total_charges == Decimal("756.75")
    assert res.net_pnl == Decimal("4243.25")
    assert res.is_profitable is True


# ==========================================
# 4. Options Calculation Tests (Premium Turnover basis)
# ==========================================

def test_options_premium_turnover_basis_post_apr_2026(calc):
    """
    Test Index Options trade on NSE post 1 April 2026:
    Options charges MUST use Premium Turnover, NOT strike turnover.
    Buy Premium: 100, Sell Premium: 120, Qty: 200 (e.g. 8 lots NIFTY).
    Buy Turnover = 20,000; Sell Turnover = 24,000; Total = 44,000.
    Brokerage = 40.
    STT = 0.15% on sell premium (24,000 * 0.0015) = 36.00.
    Stamp Duty = 0.003% on buy premium (20,000 * 0.00003) = 0.60.
    ETC = 0.03503% on total premium (44,000 * 0.0003503) = 15.41.
    SEBI = 0.0001% on total premium (44,000 * 0.000001) = 0.04.
    IPFT = 0.0005% on total premium (44,000 * 0.000005) = 0.22.
    """
    res = calc.calculate(
        exchange=Exchange.NSE,
        segment=Segment.INDEX_OPTIONS,
        buy_price=Decimal("100"),
        sell_price=Decimal("120"),
        quantity=200,
        num_buy_orders=1,
        num_sell_orders=1,
        trade_date=date(2026, 6, 1),
    )

    assert res.buy_turnover == Decimal("20000.00")
    assert res.sell_turnover == Decimal("24000.00")
    assert res.total_turnover == Decimal("44000.00")
    assert res.stt == Decimal("36.00")
    assert res.stamp_duty == Decimal("0.60")
    assert res.exchange_txn_charge == Decimal("15.41")
    assert res.sebi_turnover_charge == Decimal("0.04")
    assert res.ipft == Decimal("0.22")
    assert res.gross_pnl == Decimal("4000.00")
    assert res.net_pnl > Decimal("3800.00")
    assert "Premium Turnover" in res.turnover_basis_description


# ==========================================
# 5. BSE Specific Rates Tests
# ==========================================

def test_bse_futures_zero_exchange_charge(calc):
    """BSE Equity Futures have ₹0 exchange transaction charge and ₹0 IPFT."""
    res = calc.calculate(
        exchange=Exchange.BSE,
        segment=Segment.INDEX_FUTURES,
        buy_price=80000,
        sell_price=80200,
        quantity=10,
        trade_date=date(2026, 5, 1),
    )
    assert res.exchange_txn_charge == Decimal("0.00")
    assert res.ipft == Decimal("0.00")


def test_bse_options_rates(calc):
    """BSE Index Options vs Stock Options transaction rates."""
    # Sensex Index Options: 0.0325%
    res_index = calc.calculate(
        exchange=Exchange.BSE,
        segment=Segment.INDEX_OPTIONS,
        buy_price=200,
        sell_price=220,
        quantity=100,
        trade_date=date(2026, 5, 1),
    )
    # Total turnover = (200 + 220) * 100 = 42,000.
    # ETC = 42,000 * 0.000325 = 13.65
    assert res_index.exchange_txn_charge == Decimal("13.65")
    assert res_index.ipft == Decimal("0.00")

    # Stock Options: 0.0050%
    res_stock = calc.calculate(
        exchange=Exchange.BSE,
        segment=Segment.STOCK_OPTIONS,
        buy_price=20,
        sell_price=25,
        quantity=500,
        trade_date=date(2026, 5, 1),
    )
    # Total turnover = (20 + 25) * 500 = 22,500.
    # ETC = 22,500 * 0.00005 = 1.125 -> 1.13
    assert res_stock.exchange_txn_charge == Decimal("1.13")


# ==========================================
# 6. Break-Even Price Accuracy Tests
# ==========================================

def test_breakeven_long_position_net_pnl_is_zero(calc):
    """
    Verify that selling at breakeven_exit_price yields net P&L of approximately 0.00.
    """
    buy_price = Decimal("25000")
    res_initial = calc.calculate(
        exchange=Exchange.NSE,
        segment=Segment.INDEX_FUTURES,
        buy_price=buy_price,
        sell_price=Decimal("25100"),
        quantity=50,
        position_type=PositionType.LONG,
        trade_date=date(2026, 4, 15),
    )

    breakeven_price = res_initial.breakeven_exit_price
    assert breakeven_price > buy_price

    # Recalculate using breakeven_price as the exit (sell) price
    res_be = calc.calculate(
        exchange=Exchange.NSE,
        segment=Segment.INDEX_FUTURES,
        buy_price=buy_price,
        sell_price=breakeven_price,
        quantity=50,
        position_type=PositionType.LONG,
        trade_date=date(2026, 4, 15),
    )

    # Net P&L should be within ₹0.50 of zero due to 2-decimal currency quantization
    assert abs(res_be.net_pnl) <= Decimal("0.50")


def test_breakeven_short_position_net_pnl_is_zero(calc):
    """
    Verify that buying back at breakeven_exit_price yields net P&L of approximately 0.00.
    """
    sell_price = Decimal("25500")
    res_initial = calc.calculate(
        exchange=Exchange.NSE,
        segment=Segment.INDEX_FUTURES,
        buy_price=Decimal("25400"),
        sell_price=sell_price,
        quantity=50,
        position_type=PositionType.SHORT,
        trade_date=date(2026, 4, 15),
    )

    breakeven_buy_price = res_initial.breakeven_exit_price
    # For a short position, profitable exit is lower than entry
    assert breakeven_buy_price < sell_price

    # Recalculate using breakeven_buy_price as the exit (buy) price
    res_be = calc.calculate(
        exchange=Exchange.NSE,
        segment=Segment.INDEX_FUTURES,
        buy_price=breakeven_buy_price,
        sell_price=sell_price,
        quantity=50,
        position_type=PositionType.SHORT,
        trade_date=date(2026, 4, 15),
    )

    # Net P&L should be within ₹0.50 of zero
    assert abs(res_be.net_pnl) <= Decimal("0.50")


# ==========================================
# 7. Input Validation & Error Handling Tests
# ==========================================

def test_invalid_prices(calc):
    """Calculator rejects non-positive prices."""
    with pytest.raises(ValueError, match="Buy price must be strictly greater than 0"):
        calc.calculate(
            exchange=Exchange.NSE,
            segment=Segment.INDEX_FUTURES,
            buy_price=0,
            sell_price=100,
            quantity=50,
        )

    with pytest.raises(ValueError, match="Sell price must be strictly greater than 0"):
        calc.calculate(
            exchange=Exchange.NSE,
            segment=Segment.INDEX_FUTURES,
            buy_price=100,
            sell_price=-10,
            quantity=50,
        )


def test_invalid_quantity_and_orders(calc):
    """Calculator rejects non-positive quantity and orders."""
    with pytest.raises(ValueError, match="Quantity must be strictly greater than 0"):
        calc.calculate(
            exchange=Exchange.NSE,
            segment=Segment.INDEX_FUTURES,
            buy_price=100,
            sell_price=105,
            quantity=0,
        )

    with pytest.raises(ValueError, match="Executed buy orders must be at least 1"):
        calc.calculate(
            exchange=Exchange.NSE,
            segment=Segment.INDEX_FUTURES,
            buy_price=100,
            sell_price=105,
            quantity=50,
            num_buy_orders=0,
        )


def test_invalid_exchange_and_segment(calc):
    """Calculator rejects unrecognized exchange or segment."""
    with pytest.raises(ValueError, match="Invalid exchange"):
        calc.calculate(
            exchange="MCX",
            segment=Segment.INDEX_FUTURES,
            buy_price=100,
            sell_price=105,
            quantity=50,
        )

    with pytest.raises(ValueError, match="Invalid segment"):
        calc.calculate(
            exchange=Exchange.NSE,
            segment="Commodity",
            buy_price=100,
            sell_price=105,
            quantity=50,
        )


def test_reconciliation_note_presence(calc):
    """Verify that April 1, 2026 statutory reconciliation note is provided."""
    res_apr = calc.calculate(
        exchange=Exchange.NSE,
        segment=Segment.INDEX_OPTIONS,
        buy_price=100,
        sell_price=110,
        quantity=50,
        trade_date=date(2026, 4, 1),
    )
    assert res_apr.rules.reconciliation_note is not None
    assert "Statutory 1 April 2026 STT Revision Applied" in res_apr.rules.reconciliation_note
