"""
charge_rules.py
---------------
Charge rules, statutory schedule resolution, and input validation
specifically configured for Angel One brokerage and Indian derivatives markets.
"""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


CONFIG_PATH = Path(__file__).parent / "config" / "angel_one_rates.json"


class Segment:
    INDEX_FUTURES = "Index Futures"
    STOCK_FUTURES = "Stock Futures"
    INDEX_OPTIONS = "Index Options"
    STOCK_OPTIONS = "Stock Options"

    ALL = [INDEX_FUTURES, STOCK_FUTURES, INDEX_OPTIONS, STOCK_OPTIONS]
    FUTURES = [INDEX_FUTURES, STOCK_FUTURES]
    OPTIONS = [INDEX_OPTIONS, STOCK_OPTIONS]

    @classmethod
    def is_options(cls, segment: str) -> bool:
        return segment in cls.OPTIONS

    @classmethod
    def is_futures(cls, segment: str) -> bool:
        return segment in cls.FUTURES


class Exchange:
    NSE = "NSE"
    BSE = "BSE"
    ALL = [NSE, BSE]


class PositionType:
    LONG = "Long"
    SHORT = "Short"
    ALL = [LONG, SHORT]


@dataclass(frozen=True)
class STTRegime:
    regime_id: str
    name: str
    effective_from: date
    effective_to: date
    is_verified: bool
    futures_sell_rate: Decimal
    options_sell_rate: Decimal
    summary: str


@dataclass(frozen=True)
class ResolvedChargeRules:
    broker_name: str
    plan_name: str
    plan_id: str
    brokerage_per_order: Decimal
    stt_rate: Decimal
    stamp_duty_rate: Decimal
    exchange_txn_rate: Decimal
    sebi_rate: Decimal
    ipft_rate: Decimal
    gst_rate: Decimal
    regime: STTRegime
    is_verified: bool
    verification_warning: Optional[str]
    reconciliation_note: Optional[str]


def load_config() -> Dict[str, Any]:
    """Load configuration from angel_one_rates.json."""
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"Configuration file not found at {CONFIG_PATH}")
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def parse_date(trade_date: Any) -> date:
    """Parse date from date object or ISO string."""
    if isinstance(trade_date, date):
        return trade_date
    if isinstance(trade_date, datetime):
        return trade_date.date()
    if isinstance(trade_date, str):
        return datetime.strptime(trade_date, "%Y-%m-%d").date()
    raise ValueError(f"Invalid date format: {trade_date}")


def get_stt_regime(trade_date: date, config: Optional[Dict[str, Any]] = None) -> Tuple[STTRegime, bool, Optional[str]]:
    """
    Determine the applicable STT regime based on the selected trade date.
    Returns (regime, is_verified, warning_message).
    """
    if config is None:
        config = load_config()

    regimes_data = config.get("stt_regimes", [])
    selected_regime: Optional[STTRegime] = None

    for r in regimes_data:
        eff_from = datetime.strptime(r["effective_from"], "%Y-%m-%d").date()
        eff_to = datetime.strptime(r["effective_to"], "%Y-%m-%d").date()
        if eff_from <= trade_date <= eff_to:
            selected_regime = STTRegime(
                regime_id=r["regime_id"],
                name=r["name"],
                effective_from=eff_from,
                effective_to=eff_to,
                is_verified=bool(r.get("is_verified", True)),
                futures_sell_rate=Decimal(str(r["futures_sell_rate"])),
                options_sell_rate=Decimal(str(r["options_sell_rate"])),
                summary=r.get("summary", "")
            )
            break

    if selected_regime is None:
        # Fallback to the latest regime if future date
        last_r = regimes_data[-1]
        eff_from = datetime.strptime(last_r["effective_from"], "%Y-%m-%d").date()
        eff_to = datetime.strptime(last_r["effective_to"], "%Y-%m-%d").date()
        selected_regime = STTRegime(
            regime_id=last_r["regime_id"],
            name=last_r["name"],
            effective_from=eff_from,
            effective_to=eff_to,
            is_verified=False,
            futures_sell_rate=Decimal(str(last_r["futures_sell_rate"])),
            options_sell_rate=Decimal(str(last_r["options_sell_rate"])),
            summary=last_r.get("summary", "")
        )

    verified_date_max_str = config.get("verified_date_max", "2027-03-31")
    verified_date_max = datetime.strptime(verified_date_max_str, "%Y-%m-%d").date()

    is_verified = selected_regime.is_verified and (trade_date <= verified_date_max) and (trade_date >= date(2000, 1, 1))
    warning = None

    if trade_date > verified_date_max:
        warning = (
            f"Caution: Trade date {trade_date.isoformat()} is beyond the verified schedule "
            f"(up to {verified_date_max.isoformat()}). Rate calculations assume continuation "
            "of the 1 April 2026 statutory regime and are subject to future Union Budgets."
        )
    elif trade_date < date(2000, 1, 1):
        warning = f"Caution: Trade date {trade_date.isoformat()} is prior to modern Indian derivatives market regulations."

    return selected_regime, is_verified, warning


def resolve_charge_rules(
    exchange: str,
    segment: str,
    trade_date: Any,
    introductory_offer: bool = False,
    config: Optional[Dict[str, Any]] = None,
) -> ResolvedChargeRules:
    """
    Resolve complete statutory and Angel One brokerage charge parameters
    for the specified exchange, segment, date, and plan configuration.
    """
    if config is None:
        config = load_config()

    if exchange not in Exchange.ALL:
        raise ValueError(f"Invalid exchange: {exchange}. Allowed: {Exchange.ALL}")
    if segment not in Segment.ALL:
        raise ValueError(f"Invalid segment: {segment}. Allowed: {Segment.ALL}")

    parsed_date = parse_date(trade_date)
    regime, is_verified, verification_warning = get_stt_regime(parsed_date, config)

    # Angel One Brokerage resolution
    plans = config.get("brokerage_plans", {})
    if introductory_offer:
        plan_data = plans.get("introductory_zero", {
            "name": "Angel One Promotional (Zero Brokerage)",
            "rate_per_executed_order": "0.00",
            "id": "introductory_zero"
        })
    else:
        plan_data = plans.get("standard", {
            "name": "Angel One iTrade Prime (Standard)",
            "rate_per_executed_order": "20.00",
            "id": "standard"
        })

    brokerage_per_order = Decimal(str(plan_data["rate_per_executed_order"]))

    # STT rate (charged on sell-side turnover)
    if Segment.is_futures(segment):
        stt_rate = regime.futures_sell_rate
    else:
        stt_rate = regime.options_sell_rate

    # Stamp duty (charged on buy-side turnover)
    stamp_duty_dict = config.get("stamp_duty_rates", {})
    stamp_duty_rate = Decimal(str(stamp_duty_dict.get(segment, "0.00002" if Segment.is_futures(segment) else "0.00003")))

    # Exchange transaction charges (both sides)
    etc_dict = config.get("exchange_transaction_charge_rates", {})
    exchange_rates = etc_dict.get(exchange, {})
    if segment not in exchange_rates:
        raise KeyError(f"Exchange transaction charge rate not found for {exchange} - {segment}")
    exchange_txn_rate = Decimal(str(exchange_rates[segment]))

    # SEBI turnover charge (both sides)
    sebi_rate = Decimal(str(config.get("sebi_turnover_charge_rate", "0.000001")))

    # IPFT rate (both sides)
    ipft_dict = config.get("ipft_rates", {})
    exchange_ipft = ipft_dict.get(exchange, {})
    ipft_rate = Decimal(str(exchange_ipft.get(segment, "0.000000")))

    # GST rate (18%)
    gst_rate = Decimal(str(config.get("gst_rate", "0.18")))

    # Reconciliation note for 1 April 2026 onwards
    reconciliation_note = None
    if parsed_date >= date(2026, 4, 1):
        reconciliation_note = (
            "Statutory 1 April 2026 STT Revision Applied: Futures STT is 0.05% (increased from 0.02%) "
            "and Options sell premium STT is 0.15% (increased from 0.10%). Reconciled with Union Budget "
            "statutory schedule. If third-party or static broker pages display older 2024 rates, "
            "note that exchanges collect statutory gazetted rates."
        )

    return ResolvedChargeRules(
        broker_name=config.get("broker_name", "Angel One"),
        plan_name=plan_data.get("name", "Angel One iTrade Prime"),
        plan_id=plan_data.get("id", "standard"),
        brokerage_per_order=brokerage_per_order,
        stt_rate=stt_rate,
        stamp_duty_rate=stamp_duty_rate,
        exchange_txn_rate=exchange_txn_rate,
        sebi_rate=sebi_rate,
        ipft_rate=ipft_rate,
        gst_rate=gst_rate,
        regime=regime,
        is_verified=is_verified,
        verification_warning=verification_warning,
        reconciliation_note=reconciliation_note,
    )


def validate_inputs(
    buy_price: Any,
    sell_price: Any,
    quantity: Any,
    num_buy_orders: Any,
    num_sell_orders: Any,
    exchange: str,
    segment: str,
    position_type: str,
    trade_date: Any,
) -> Tuple[Decimal, Decimal, int, int, int, str, str, str, date]:
    """
    Validate and coerce user inputs for the calculator.
    Raises ValueError on invalid or out-of-range inputs.
    """
    try:
        dec_buy = Decimal(str(buy_price))
    except Exception as e:
        raise ValueError(f"Buy price must be a valid number: {e}")

    try:
        dec_sell = Decimal(str(sell_price))
    except Exception as e:
        raise ValueError(f"Sell price must be a valid number: {e}")

    if dec_buy <= Decimal("0"):
        raise ValueError(f"Buy price must be strictly greater than 0 (got {dec_buy}).")
    if dec_sell <= Decimal("0"):
        raise ValueError(f"Sell price must be strictly greater than 0 (got {dec_sell}).")

    try:
        int_qty = int(quantity)
    except Exception as e:
        raise ValueError(f"Quantity must be a valid integer: {e}")

    if int_qty <= 0:
        raise ValueError(f"Quantity must be strictly greater than 0 (got {int_qty}).")

    try:
        int_buy_orders = int(num_buy_orders)
    except Exception as e:
        raise ValueError(f"Buy orders count must be a valid integer: {e}")

    if int_buy_orders < 1:
        raise ValueError(f"Executed buy orders must be at least 1 (got {int_buy_orders}).")

    try:
        int_sell_orders = int(num_sell_orders)
    except Exception as e:
        raise ValueError(f"Sell orders count must be a valid integer: {e}")

    if int_sell_orders < 1:
        raise ValueError(f"Executed sell orders must be at least 1 (got {int_sell_orders}).")

    if exchange not in Exchange.ALL:
        raise ValueError(f"Invalid exchange: {exchange}. Must be one of {Exchange.ALL}")

    if segment not in Segment.ALL:
        raise ValueError(f"Invalid segment: {segment}. Must be one of {Segment.ALL}")

    if position_type not in PositionType.ALL:
        raise ValueError(f"Invalid position type: {position_type}. Must be one of {PositionType.ALL}")

    parsed_date = parse_date(trade_date)

    return (
        dec_buy,
        dec_sell,
        int_qty,
        int_buy_orders,
        int_sell_orders,
        exchange,
        segment,
        position_type,
        parsed_date,
    )
