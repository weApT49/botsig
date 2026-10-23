"""
Position Sizer
Calculates lot size based on risk parameters
"""

import logging
from typing import Dict, Any, Optional


class PositionSizer:
    """
    Calculate position size based on:
    - Account capital
    - Risk percentage per trade
    - Stop loss distance
    - Symbol specifications
    """

    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger("PositionSizer")

        # Settings
        self.capital = config.get("risk.capital_usc", 5500)
        self.default_risk_pct = config.get("risk.risk_per_trade_pct", 1.0)
        self.max_risk_pct = config.get("risk.max_risk_per_trade_pct", 1.5)

    def calculate(
        self,
        entry: float,
        sl: float,
        symbol_info: Dict[str, Any],
        risk_pct: Optional[float] = None
    ) -> float:
        """
        Calculate lot size

        Args:
            entry: Entry price
            sl: Stop loss price
            symbol_info: Symbol specifications (point, contract_size, min_lot, max_lot, lot_step)
            risk_pct: Risk percentage (uses default if None)

        Returns:
            Lot size rounded to broker specifications
        """
        if risk_pct is None:
            risk_pct = self.default_risk_pct

        # Cap at max risk
        risk_pct = min(risk_pct, self.max_risk_pct)

        # Calculate risk amount in USC
        risk_usc = self.capital * (risk_pct / 100)

        # Get symbol specs
        point = symbol_info.get("point", 0.00001)
        contract_size = symbol_info.get("trade_contract_size", 1000)  # Cent account = 1000
        min_lot = symbol_info.get("min_lot", 0.01)
        max_lot = symbol_info.get("max_lot", 0.5)
        lot_step = symbol_info.get("lot_step", 0.01)

        # Calculate SL distance in points
        sl_distance = abs(entry - sl)
        sl_points = sl_distance / point

        # Calculate lot size
        # Risk = Lot × SL_Points × Point × Contract_Size
        # Lot = Risk / (SL_Points × Point × Contract_Size)

        pip_value = point * contract_size

        if sl_points > 0 and pip_value > 0:
            lot = risk_usc / (sl_points * pip_value)

            # Round to lot step
            lot = round(lot / lot_step) * lot_step

            # Clamp to min/max
            lot = max(min_lot, min(lot, max_lot))

            self.logger.debug(
                f"Position size: {lot:.2f} lot | "
                f"Risk: {risk_usc:.1f} USC ({risk_pct}%) | "
                f"SL: {sl_points:.0f} points"
            )

            return lot

        return min_lot

    def calculate_risk_usc(
        self,
        lot: float,
        entry: float,
        sl: float,
        symbol_info: Dict[str, Any]
    ) -> float:
        """
        Calculate actual risk in USC for given lot size

        Returns:
            Risk amount in USC
        """
        point = symbol_info.get("point", 0.00001)
        contract_size = symbol_info.get("trade_contract_size", 1000)

        sl_distance = abs(entry - sl)
        sl_points = sl_distance / point

        risk_usc = lot * sl_points * point * contract_size
        return risk_usc

    def validate_lot_size(
        self,
        lot: float,
        symbol_info: Dict[str, Any]
    ) -> float:
        """Validate and adjust lot size to broker limits"""
        min_lot = symbol_info.get("min_lot", 0.01)
        max_lot = symbol_info.get("max_lot", 0.5)
        lot_step = symbol_info.get("lot_step", 0.01)

        # Round to lot step
        lot = round(lot / lot_step) * lot_step

        # Clamp
        lot = max(min_lot, min(lot, max_lot))

        return lot
