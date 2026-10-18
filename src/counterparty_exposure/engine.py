from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Mapping, Sequence

from .models import (
    Collateral,
    CounterpartyResult,
    ExposureReport,
    NettingSetResult,
    Trade,
)


class CounterpartyExposureEngine:
    def __init__(
        self,
        currency: str,
        trades: Sequence[Trade],
        collateral: Sequence[Collateral],
        limits: Mapping[str, float],
    ) -> None:
        if not isinstance(currency, str) or not currency.strip():
            raise ValueError("currency must be a non-empty string")
        self.currency = currency.strip()
        self.trades = tuple(trades)
        self.collateral = tuple(collateral)
        if not self.trades:
            raise ValueError("at least one trade is required")
        if not isinstance(limits, Mapping):
            raise ValueError("limits must be an object of counterparty limits")

        cleaned_limits: dict[str, float] = {}
        for name, limit in limits.items():
            if not isinstance(name, str) or not name.strip():
                raise ValueError("counterparty limit names must be non-empty strings")
            if isinstance(limit, bool) or not isinstance(limit, (int, float)):
                raise ValueError(f"limit for {name!r} must be a number")
            amount = float(limit)
            if not math.isfinite(amount) or amount <= 0:
                raise ValueError(f"limit for {name!r} must be positive and finite")
            cleaned_limits[name.strip()] = amount
        self.limits = cleaned_limits
        self._validate_inputs()

    @staticmethod
    def _key(counterparty: str, netting_set: str) -> tuple[str, str]:
        return counterparty, netting_set

    def _validate_inputs(self) -> None:
        trade_ids = [trade.trade_id for trade in self.trades]
        if len(trade_ids) != len(set(trade_ids)):
            raise ValueError("trade identifiers must be unique")
        collateral_ids = [item.collateral_id for item in self.collateral]
        if len(collateral_ids) != len(set(collateral_ids)):
            raise ValueError("collateral identifiers must be unique")

        counterparties = {trade.counterparty for trade in self.trades}
        missing_limits = counterparties - set(self.limits)
        if missing_limits:
            raise ValueError(
                "missing limits for counterparties: "
                + ", ".join(sorted(missing_limits))
            )
        unknown_limits = set(self.limits) - counterparties
        if unknown_limits:
            raise ValueError(
                "limits supplied for counterparties with no trades: "
                + ", ".join(sorted(unknown_limits))
            )

        trade_keys = {
            self._key(trade.counterparty, trade.netting_set) for trade in self.trades
        }
        for item in self.collateral:
            if self._key(item.counterparty, item.netting_set) not in trade_keys:
                raise ValueError(
                    f"collateral {item.collateral_id!r} refers to an unknown "
                    f"netting set {item.netting_set!r} for {item.counterparty!r}"
                )

    def run(self) -> ExposureReport:
        trades_by_set: dict[tuple[str, str], list[Trade]] = defaultdict(list)
        collateral_by_set: dict[tuple[str, str], list[Collateral]] = defaultdict(list)
        for trade in self.trades:
            trades_by_set[self._key(trade.counterparty, trade.netting_set)].append(trade)
        for item in self.collateral:
            collateral_by_set[self._key(item.counterparty, item.netting_set)].append(item)

        set_results: list[NettingSetResult] = []
        results_by_counterparty: dict[str, dict[str, NettingSetResult]] = defaultdict(dict)
        for (counterparty, netting_set), trades in sorted(trades_by_set.items()):
            net_mtm = math.fsum(trade.mtm for trade in trades)
            gross_positive_mtm = math.fsum(max(trade.mtm, 0.0) for trade in trades)
            collateral_items = collateral_by_set.get((counterparty, netting_set), [])
            nominal_collateral = math.fsum(item.amount for item in collateral_items)
            eligible_collateral = math.fsum(
                item.eligible_amount for item in collateral_items
            )
            current_exposure = max(net_mtm - eligible_collateral, 0.0)
            pfe_addon = math.fsum(
                trade.notional * trade.pfe_addon_rate for trade in trades
            )
            pfe = current_exposure + pfe_addon
            product_exposure: dict[str, list[float]] = defaultdict(list)
            for trade in trades:
                product_exposure[trade.product].append(trade.mtm)
            result = NettingSetResult(
                counterparty=counterparty,
                netting_set=netting_set,
                gross_positive_mtm=gross_positive_mtm,
                net_mtm=net_mtm,
                collateral_amount=nominal_collateral,
                eligible_collateral=eligible_collateral,
                current_exposure=current_exposure,
                pfe_addon=pfe_addon,
                pfe=pfe,
                trade_pnl={trade.trade_id: trade.mtm for trade in trades},
                product_exposure={
                    product: math.fsum(amounts)
                    for product, amounts in product_exposure.items()
                },
            )
            set_results.append(result)
            results_by_counterparty[counterparty][netting_set] = result

        counterparty_results: dict[str, CounterpartyResult] = {}
        for counterparty, netting_sets in sorted(results_by_counterparty.items()):
            sets = tuple(netting_sets.values())
            current_exposure = math.fsum(item.current_exposure for item in sets)
            limit = self.limits[counterparty]
            counterparty_results[counterparty] = CounterpartyResult(
                counterparty=counterparty,
                limit=limit,
                gross_positive_mtm=math.fsum(item.gross_positive_mtm for item in sets),
                net_mtm=math.fsum(item.net_mtm for item in sets),
                collateral_amount=math.fsum(item.collateral_amount for item in sets),
                eligible_collateral=math.fsum(
                    item.eligible_collateral for item in sets
                ),
                current_exposure=current_exposure,
                pfe_addon=math.fsum(item.pfe_addon for item in sets),
                pfe=math.fsum(item.pfe for item in sets),
                limit_utilization=current_exposure / limit,
                limit_breached=current_exposure > limit,
                netting_sets=netting_sets,
            )

        return ExposureReport(
            currency=self.currency,
            counterparties=counterparty_results,
            netting_sets=tuple(set_results),
        )
