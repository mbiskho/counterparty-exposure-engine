from __future__ import annotations

import argparse
import json
import math
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .engine import CounterpartyExposureEngine
from .models import Collateral, ExposureReport, Trade
from .visualization import render_flow_screenshot, render_project_screenshot


def _object(value: Any, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be a JSON object")
    return value


def _number(value: Any, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} must be a number")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{field_name} must be finite")
    return result


def load_engine(path: Path) -> CounterpartyExposureEngine:
    with path.open(encoding="utf-8") as source:
        document = _object(json.load(source), "input")
    currency = document.get("currency")
    if not isinstance(currency, str) or not currency.strip():
        raise ValueError("input.currency must be a non-empty string")

    raw_trades = document.get("trades")
    raw_collateral = document.get("collateral")
    if not isinstance(raw_trades, list):
        raise ValueError("input.trades must be a JSON array")
    if not isinstance(raw_collateral, list):
        raise ValueError("input.collateral must be a JSON array")
    trades = []
    for index, raw_trade in enumerate(raw_trades):
        trade = _object(raw_trade, f"trades[{index}]")
        trades.append(
            Trade(
                trade_id=trade.get("id"),
                counterparty=trade.get("counterparty"),
                netting_set=trade.get("netting_set"),
                product=trade.get("product"),
                mtm=_number(trade.get("mtm"), f"trades[{index}].mtm"),
                notional=_number(
                    trade.get("notional"),
                    f"trades[{index}].notional",
                ),
                pfe_addon_rate=_number(
                    trade.get("pfe_addon_rate"),
                    f"trades[{index}].pfe_addon_rate",
                ),
            )
        )
    collateral = []
    for index, raw_item in enumerate(raw_collateral):
        item = _object(raw_item, f"collateral[{index}]")
        collateral.append(
            Collateral(
                collateral_id=item.get("id"),
                counterparty=item.get("counterparty"),
                netting_set=item.get("netting_set"),
                amount=_number(item.get("amount"), f"collateral[{index}].amount"),
                haircut=_number(item.get("haircut"), f"collateral[{index}].haircut"),
            )
        )
    raw_limits = _object(document.get("limits"), "limits")
    limits = {
        name: _number(value, f"limits.{name}") for name, value in raw_limits.items()
    }
    return CounterpartyExposureEngine(
        currency=currency,
        trades=trades,
        collateral=collateral,
        limits=limits,
    )


def report_document(report: ExposureReport) -> dict[str, Any]:
    return {
        "currency": report.currency,
        "counterparties": [
            {
                "counterparty": result.counterparty,
                "limit": result.limit,
                "gross_positive_mtm": result.gross_positive_mtm,
                "net_mtm": result.net_mtm,
                "collateral_amount": result.collateral_amount,
                "eligible_collateral": result.eligible_collateral,
                "current_exposure": result.current_exposure,
                "pfe_addon": result.pfe_addon,
                "pfe": result.pfe,
                "limit_utilization": result.limit_utilization,
                "limit_breached": result.limit_breached,
                "netting_sets": [
                    {
                        "netting_set": item.netting_set,
                        "gross_positive_mtm": item.gross_positive_mtm,
                        "net_mtm": item.net_mtm,
                        "collateral_amount": item.collateral_amount,
                        "eligible_collateral": item.eligible_collateral,
                        "current_exposure": item.current_exposure,
                        "pfe_addon": item.pfe_addon,
                        "pfe": item.pfe,
                        "trade_mtm": dict(item.trade_pnl),
                        "product_mtm": dict(item.product_exposure),
                    }
                    for item in result.netting_sets.values()
                ],
            }
            for result in report.counterparties.values()
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Calculate netting-aware counterparty exposure and limit utilization."
    )
    parser.add_argument("input", type=Path, help="path to exposure portfolio JSON")
    parser.add_argument(
        "--format",
        choices=("text", "json", "svg"),
        default="text",
        help="output format: text, JSON, or SVG report (default: text)",
    )
    parser.add_argument(
        "--chart",
        choices=("project", "flow"),
        default="project",
        help="SVG report: project overview or exposure workflow",
    )
    args = parser.parse_args(argv)
    try:
        report = load_engine(args.input).run()
    except (OSError, json.JSONDecodeError, ValueError) as error:
        parser.error(str(error))

    if args.format == "json":
        print(json.dumps(report_document(report), indent=2, sort_keys=True))
    elif args.format == "svg":
        renderer = (
            render_flow_screenshot
            if args.chart == "flow"
            else render_project_screenshot
        )
        print(renderer(report))
    else:
        print(f"Counterparty exposure report ({report.currency})")
        print(
            f"{'Counterparty':<24} {'Current exposure':>20} "
            f"{'PFE':>20} {'Limit usage':>14} {'Status':>10}"
        )
        for item in sorted(
            report.counterparties.values(),
            key=lambda result: result.current_exposure,
            reverse=True,
        ):
            status = "BREACH" if item.limit_breached else "OK"
            print(
                f"{item.counterparty:<24} {item.current_exposure:>20,.2f} "
                f"{item.pfe:>20,.2f} {item.limit_utilization:>13.1%} "
                f"{status:>10}"
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
