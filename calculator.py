"""
calculator.py
-------------
Core trading charges and P&L calculator using Python Decimal arithmetic.
Configured for Angel One brokerage and Indian derivatives statutory regulations.
"""

from dataclasses import dataclass, asdict
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional, Tuple

from charge_rules import (
    Exchange,
    PositionType,
    ResolvedChargeRules,
    Segment,
    resolve_charge_rules,
    validate_inputs,
)

TWO_PLACES = Decimal("0.01")
FOUR_PLACES = Decimal("0.0001")


def round_curr(val: Decimal) -> Decimal:
    """Quantize to 2 decimal places with ROUND_HALF_UP."""
    return val.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class ChargeLineItem:
    charge_name: str
    basis: str
    rate_display: str
    buy_component: Decimal
    sell_component: Decimal
    total_amount: Decimal
    statutory_authority: str
    description: str


@dataclass(frozen=True)
class CalculationResult:
    # Inputs summary
    exchange: str
    segment: str
    position_type: str
    trade_date: date
    buy_price: Decimal
    sell_price: Decimal
    quantity: int
    num_buy_orders: int
    num_sell_orders: int
    total_orders: int
    introductory_offer: bool

    # Turnovers
    buy_turnover: Decimal
    sell_turnover: Decimal
    total_turnover: Decimal
    turnover_basis_description: str

    # Charges
    brokerage_buy: Decimal
    brokerage_sell: Decimal
    total_brokerage: Decimal
    stt: Decimal
    exchange_txn_charge: Decimal
    sebi_turnover_charge: Decimal
    stamp_duty: Decimal
    ipft: Decimal
    gst: Decimal
    total_charges: Decimal

    # P&L
    gross_pnl: Decimal
    net_pnl: Decimal
    is_profitable: bool

    # Break-even
    breakeven_exit_price: Decimal
    breakeven_diff_points: Decimal
    breakeven_diff_pct: Decimal

    # Rules & verification
    rules: ResolvedChargeRules
    line_items: List[ChargeLineItem]

    def to_dict(self) -> Dict[str, Any]:
        """Convert calculation results to serializable dictionary."""
        return {
            "inputs": {
                "exchange": self.exchange,
                "segment": self.segment,
                "position_type": self.position_type,
                "trade_date": self.trade_date.isoformat(),
                "buy_price": str(self.buy_price),
                "sell_price": str(self.sell_price),
                "quantity": self.quantity,
                "num_buy_orders": self.num_buy_orders,
                "num_sell_orders": self.num_sell_orders,
                "total_orders": self.total_orders,
                "introductory_offer": self.introductory_offer,
                "brokerage_plan": self.rules.plan_name,
            },
            "turnover": {
                "buy_turnover": str(self.buy_turnover),
                "sell_turnover": str(self.sell_turnover),
                "total_turnover": str(self.total_turnover),
                "basis_description": self.turnover_basis_description,
            },
            "charges": {
                "brokerage_buy": str(self.brokerage_buy),
                "brokerage_sell": str(self.brokerage_sell),
                "total_brokerage": str(self.total_brokerage),
                "stt": str(self.stt),
                "exchange_txn_charge": str(self.exchange_txn_charge),
                "sebi_turnover_charge": str(self.sebi_turnover_charge),
                "stamp_duty": str(self.stamp_duty),
                "ipft": str(self.ipft),
                "gst": str(self.gst),
                "total_charges": str(self.total_charges),
            },
            "pnl": {
                "gross_pnl": str(self.gross_pnl),
                "net_pnl": str(self.net_pnl),
                "is_profitable": self.is_profitable,
                "breakeven_exit_price": str(self.breakeven_exit_price),
                "breakeven_diff_points": str(self.breakeven_diff_points),
                "breakeven_diff_pct": str(self.breakeven_diff_pct),
            },
            "regime": {
                "regime_id": self.rules.regime.regime_id,
                "regime_name": self.rules.regime.name,
                "is_verified": self.rules.is_verified,
                "verification_warning": self.rules.verification_warning,
                "reconciliation_note": self.rules.reconciliation_note,
            },
        }


class AngelOneCalculator:
    """
    Dedicated Angel One F&O Charges & P&L Calculator.
    Uses exact Decimal arithmetic.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config

    def calculate(
        self,
        exchange: str,
        segment: str,
        buy_price: Any,
        sell_price: Any,
        quantity: Any,
        num_buy_orders: Any = 1,
        num_sell_orders: Any = 1,
        trade_date: Any = None,
        position_type: str = PositionType.LONG,
        introductory_offer: bool = False,
    ) -> CalculationResult:
        """
        Execute comprehensive charges, gross P&L, net P&L, and break-even calculations.
        """
        if trade_date is None:
            trade_date = date.today()

        # Validate and sanitize all inputs
        (
            dec_buy,
            dec_sell,
            int_qty,
            int_buy_orders,
            int_sell_orders,
            validated_exchange,
            validated_segment,
            validated_position,
            parsed_date,
        ) = validate_inputs(
            buy_price=buy_price,
            sell_price=sell_price,
            quantity=quantity,
            num_buy_orders=num_buy_orders,
            num_sell_orders=num_sell_orders,
            exchange=exchange,
            segment=segment,
            position_type=position_type,
            trade_date=trade_date,
        )

        # Resolve rates for specific date & segment
        rules = resolve_charge_rules(
            exchange=validated_exchange,
            segment=validated_segment,
            trade_date=parsed_date,
            introductory_offer=introductory_offer,
            config=self.config,
        )

        dec_qty = Decimal(str(int_qty))
        dec_buy_orders = Decimal(str(int_buy_orders))
        dec_sell_orders = Decimal(str(int_sell_orders))
        total_orders = int_buy_orders + int_sell_orders

        # Turnover calculations
        # Options turnover is premium turnover (Price * Qty)
        # Futures turnover is contract turnover (Price * Qty)
        buy_turnover_raw = dec_buy * dec_qty
        sell_turnover_raw = dec_sell * dec_qty
        total_turnover_raw = buy_turnover_raw + sell_turnover_raw

        buy_turnover = round_curr(buy_turnover_raw)
        sell_turnover = round_curr(sell_turnover_raw)
        total_turnover = round_curr(total_turnover_raw)

        turnover_basis_desc = (
            "Premium Turnover (Option Premium × Quantity)"
            if Segment.is_options(validated_segment)
            else "Futures Contract Turnover (Futures Price × Quantity)"
        )

        # 1. Angel One Brokerage: ₹20 per executed order (or ₹0 if introductory)
        brokerage_buy_raw = dec_buy_orders * rules.brokerage_per_order
        brokerage_sell_raw = dec_sell_orders * rules.brokerage_per_order
        total_brokerage_raw = brokerage_buy_raw + brokerage_sell_raw

        brokerage_buy = round_curr(brokerage_buy_raw)
        brokerage_sell = round_curr(brokerage_sell_raw)
        total_brokerage = round_curr(total_brokerage_raw)

        # 2. STT (Securities Transaction Tax)
        # Charged ONLY on Sell-side turnover
        stt_raw = sell_turnover_raw * rules.stt_rate
        stt = round_curr(stt_raw)

        # 3. Stamp Duty
        # Charged ONLY on Buy-side turnover
        stamp_duty_raw = buy_turnover_raw * rules.stamp_duty_rate
        stamp_duty = round_curr(stamp_duty_raw)

        # 4. Exchange Transaction Charges (ETC)
        # Levied on BOTH Buy and Sell turnover
        etc_buy_raw = buy_turnover_raw * rules.exchange_txn_rate
        etc_sell_raw = sell_turnover_raw * rules.exchange_txn_rate
        exchange_txn_charge_raw = etc_buy_raw + etc_sell_raw
        exchange_txn_charge = round_curr(exchange_txn_charge_raw)

        # 5. SEBI Turnover Charges
        # Levied on BOTH Buy and Sell turnover (₹10/crore = 0.0001%)
        sebi_buy_raw = buy_turnover_raw * rules.sebi_rate
        sebi_sell_raw = sell_turnover_raw * rules.sebi_rate
        sebi_charge_raw = sebi_buy_raw + sebi_sell_raw
        sebi_turnover_charge = round_curr(sebi_charge_raw)

        # 6. IPFT (Investor Protection Fund Trust) Charges
        # Levied on BOTH Buy and Sell turnover on NSE; ₹0 on BSE
        ipft_buy_raw = buy_turnover_raw * rules.ipft_rate
        ipft_sell_raw = sell_turnover_raw * rules.ipft_rate
        ipft_raw = ipft_buy_raw + ipft_sell_raw
        ipft = round_curr(ipft_raw)

        # 7. GST (18%)
        # Levied on (Brokerage + Exchange Txn Charges + SEBI Turnover Charges + IPFT)
        taxable_services_raw = (
            total_brokerage_raw + exchange_txn_charge_raw + sebi_charge_raw + ipft_raw
        )
        gst_raw = taxable_services_raw * rules.gst_rate
        gst = round_curr(gst_raw)

        # Total Charges
        total_charges_raw = (
            total_brokerage_raw
            + stt_raw
            + stamp_duty_raw
            + exchange_txn_charge_raw
            + sebi_charge_raw
            + ipft_raw
            + gst_raw
        )
        total_charges = round_curr(total_charges_raw)

        # P&L calculations
        # Gross P&L: (Sell Price - Buy Price) * Quantity for both long and short roundtrips
        gross_pnl_raw = (dec_sell - dec_buy) * dec_qty
        gross_pnl = round_curr(gross_pnl_raw)

        net_pnl_raw = gross_pnl_raw - total_charges_raw
        net_pnl = round_curr(net_pnl_raw)
        is_profitable = net_pnl > Decimal("0")

        # Break-Even Exit Price Calculation
        breakeven_exit_price, diff_pts, diff_pct = self._calculate_breakeven(
            buy_price=dec_buy,
            sell_price=dec_sell,
            quantity=dec_qty,
            position_type=validated_position,
            rules=rules,
            total_brokerage_raw=total_brokerage_raw,
        )

        # Generate detailed line-item breakdown
        line_items = self._build_line_items(
            rules=rules,
            brokerage_buy=brokerage_buy,
            brokerage_sell=brokerage_sell,
            stt=stt,
            stamp_duty=stamp_duty,
            etc_buy=round_curr(etc_buy_raw),
            etc_sell=round_curr(etc_sell_raw),
            exchange_txn_charge=exchange_txn_charge,
            sebi_buy=round_curr(sebi_buy_raw),
            sebi_sell=round_curr(sebi_sell_raw),
            sebi_turnover_charge=sebi_turnover_charge,
            ipft_buy=round_curr(ipft_buy_raw),
            ipft_sell=round_curr(ipft_sell_raw),
            ipft=ipft,
            gst=gst,
        )

        return CalculationResult(
            exchange=validated_exchange,
            segment=validated_segment,
            position_type=validated_position,
            trade_date=parsed_date,
            buy_price=dec_buy,
            sell_price=dec_sell,
            quantity=int_qty,
            num_buy_orders=int_buy_orders,
            num_sell_orders=int_sell_orders,
            total_orders=total_orders,
            introductory_offer=introductory_offer,
            buy_turnover=buy_turnover,
            sell_turnover=sell_turnover,
            total_turnover=total_turnover,
            turnover_basis_description=turnover_basis_desc,
            brokerage_buy=brokerage_buy,
            brokerage_sell=brokerage_sell,
            total_brokerage=total_brokerage,
            stt=stt,
            exchange_txn_charge=exchange_txn_charge,
            sebi_turnover_charge=sebi_turnover_charge,
            stamp_duty=stamp_duty,
            ipft=ipft,
            gst=gst,
            total_charges=total_charges,
            gross_pnl=gross_pnl,
            net_pnl=net_pnl,
            is_profitable=is_profitable,
            breakeven_exit_price=breakeven_exit_price,
            breakeven_diff_points=diff_pts,
            breakeven_diff_pct=diff_pct,
            rules=rules,
            line_items=line_items,
        )

    def _calculate_breakeven(
        self,
        buy_price: Decimal,
        sell_price: Decimal,
        quantity: Decimal,
        position_type: str,
        rules: ResolvedChargeRules,
        total_brokerage_raw: Decimal,
    ) -> Tuple[Decimal, Decimal, Decimal]:
        """
        Analytically solve for the exact exit price where Net P&L = 0.

        Formula Derivation:
        Turnover fee factor with GST:
            k = (etc_rate + sebi_rate + ipft_rate) * (1 + gst_rate)
        Buy-side turnover rate factor:
            rate_buy = stamp_duty_rate + k
        Sell-side turnover rate factor:
            rate_sell = stt_rate + k
        Total fixed charges with GST:
            B_total = total_brokerage * (1 + gst_rate)

        1. Long Position (Bought at buy_price; solve for required sell exit price P_exit):
            P_exit * Q * (1 - rate_sell) = buy_price * Q * (1 + rate_buy) + B_total
            P_exit = [buy_price * Q * (1 + rate_buy) + B_total] / [Q * (1 - rate_sell)]

        2. Short Position (Shorted at sell_price; solve for required buy exit price P_exit):
            P_exit * Q * (1 + rate_buy) = sell_price * Q * (1 - rate_sell) - B_total
            P_exit = [sell_price * Q * (1 - rate_sell) - B_total] / [Q * (1 + rate_buy)]
        """
        gst_factor = Decimal("1") + rules.gst_rate
        turnover_regulatory_rate = rules.exchange_txn_rate + rules.sebi_rate + rules.ipft_rate
        k = turnover_regulatory_rate * gst_factor

        rate_buy = rules.stamp_duty_rate + k
        rate_sell = rules.stt_rate + k
        b_total = total_brokerage_raw * gst_factor

        if position_type == PositionType.LONG:
            denom = quantity * (Decimal("1") - rate_sell)
            if denom <= Decimal("0"):
                return Decimal("0.00"), Decimal("0.00"), Decimal("0.00")
            numer = (buy_price * quantity * (Decimal("1") + rate_buy)) + b_total
            exit_price = numer / denom
            diff_pts = exit_price - buy_price
            diff_pct = (diff_pts / buy_price) * Decimal("100")
        else:
            denom = quantity * (Decimal("1") + rate_buy)
            if denom <= Decimal("0"):
                return Decimal("0.00"), Decimal("0.00"), Decimal("0.00")
            numer = (sell_price * quantity * (Decimal("1") - rate_sell)) - b_total
            exit_price = numer / denom
            # For short position, profit comes from exiting LOWER than entry sell price
            diff_pts = exit_price - sell_price
            diff_pct = (diff_pts / sell_price) * Decimal("100")

        return (
            round_curr(exit_price),
            round_curr(diff_pts),
            round_curr(diff_pct),
        )

    def _build_line_items(
        self,
        rules: ResolvedChargeRules,
        brokerage_buy: Decimal,
        brokerage_sell: Decimal,
        stt: Decimal,
        stamp_duty: Decimal,
        etc_buy: Decimal,
        etc_sell: Decimal,
        exchange_txn_charge: Decimal,
        sebi_buy: Decimal,
        sebi_sell: Decimal,
        sebi_turnover_charge: Decimal,
        ipft_buy: Decimal,
        ipft_sell: Decimal,
        ipft: Decimal,
        gst: Decimal,
    ) -> List[ChargeLineItem]:
        """Construct structured line items for reporting and contract notes."""
        brokerage_rate_str = f"₹{rules.brokerage_per_order:.2f} / order"
        stt_rate_pct = rules.stt_rate * Decimal("100")
        stamp_pct = rules.stamp_duty_rate * Decimal("100")
        etc_pct = rules.exchange_txn_rate * Decimal("100")
        sebi_per_cr = rules.sebi_rate * Decimal("10000000")
        ipft_per_cr = rules.ipft_rate * Decimal("10000000")

        return [
            ChargeLineItem(
                charge_name="Brokerage (Angel One)",
                basis="Per Executed Order",
                rate_display=brokerage_rate_str,
                buy_component=brokerage_buy,
                sell_component=brokerage_sell,
                total_amount=brokerage_buy + brokerage_sell,
                statutory_authority="Angel One Ltd.",
                description="Flat brokerage fee under Angel One tariff.",
            ),
            ChargeLineItem(
                charge_name="Securities Transaction Tax (STT)",
                basis="Sell Turnover Only",
                rate_display=f"{stt_rate_pct:.4f}%",
                buy_component=Decimal("0.00"),
                sell_component=stt,
                total_amount=stt,
                statutory_authority="CBDT / Ministry of Finance",
                description="Levied by Central Government on sell-side F&O transactions.",
            ),
            ChargeLineItem(
                charge_name="Exchange Transaction Charges (ETC)",
                basis="Buy & Sell Turnover",
                rate_display=f"{etc_pct:.5f}%",
                buy_component=etc_buy,
                sell_component=etc_sell,
                total_amount=exchange_txn_charge,
                statutory_authority="Stock Exchange (NSE/BSE)",
                description="Exchange operating charge mandated under SEBI True-to-Label.",
            ),
            ChargeLineItem(
                charge_name="SEBI Turnover Charges",
                basis="Buy & Sell Turnover",
                rate_display=f"₹{sebi_per_cr:.2f}/Cr",
                buy_component=sebi_buy,
                sell_component=sebi_sell,
                total_amount=sebi_turnover_charge,
                statutory_authority="SEBI",
                description="Regulatory fee for market supervision.",
            ),
            ChargeLineItem(
                charge_name="Stamp Duty",
                basis="Buy Turnover Only",
                rate_display=f"{stamp_pct:.4f}%",
                buy_component=stamp_duty,
                sell_component=Decimal("0.00"),
                total_amount=stamp_duty,
                statutory_authority="State Govt / Indian Stamp Act",
                description="Mandatory stamp duty on purchase of securities.",
            ),
            ChargeLineItem(
                charge_name="IPFT Charges",
                basis="Buy & Sell Turnover",
                rate_display=f"₹{ipft_per_cr:.2f}/Cr",
                buy_component=ipft_buy,
                sell_component=ipft_sell,
                total_amount=ipft,
                statutory_authority="Exchange IPFT Trust",
                description="Investor Protection Fund Trust contribution.",
            ),
            ChargeLineItem(
                charge_name="Goods and Services Tax (GST)",
                basis="Brokerage + ETC + SEBI + IPFT",
                rate_display="18.00%",
                buy_component=Decimal("0.00"),
                sell_component=Decimal("0.00"),
                total_amount=gst,
                statutory_authority="CBIC / GST Council",
                description="18% tax on service and regulatory platform charges.",
            ),
        ]
