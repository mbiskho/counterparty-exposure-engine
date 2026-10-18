from __future__ import annotations

import math
from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping


def _text(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()


def _number(value: float, field_name: str, minimum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} must be a number")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{field_name} must be finite")
    if minimum is not None and result < minimum:
        raise ValueError(f"{field_name} must be at least {minimum}")
    return result


@dataclass(frozen=True)
class Trade:
    trade_id: str
    counterparty: str
    netting_set: str
    product: str
    mtm: float
    notional: float
    pfe_addon_rate: float

    def __post_init__(self) -> None:
        for field_name in ("trade_id", "counterparty", "netting_set", "product"):
            object.__setattr__(
                self,
                field_name,
                _text(getattr(self, field_name), field_name),
            )
        object.__setattr__(self, "mtm", _number(self.mtm, "mtm"))
        object.__setattr__(self, "notional", _number(self.notional, "notional", 0.0))
        rate = _number(self.pfe_addon_rate, "pfe_addon_rate", 0.0)
        if rate > 1:
            raise ValueError("pfe_addon_rate cannot exceed 1")
        object.__setattr__(self, "pfe_addon_rate", rate)


@dataclass(frozen=True)
class Collateral:
    collateral_id: str
    counterparty: str
    netting_set: str
    amount: float
    haircut: float

    def __post_init__(self) -> None:
        for field_name in ("collateral_id", "counterparty", "netting_set"):
            object.__setattr__(
                self,
                field_name,
                _text(getattr(self, field_name), field_name),
            )
        object.__setattr__(self, "amount", _number(self.amount, "amount", 0.0))
        haircut = _number(self.haircut, "haircut", 0.0)
        if haircut >= 1:
            raise ValueError("haircut must be less than 1")
        object.__setattr__(self, "haircut", haircut)

    @property
    def eligible_amount(self) -> float:
        return self.amount * (1 - self.haircut)


@dataclass(frozen=True)
class NettingSetResult:
    counterparty: str
    netting_set: str
    gross_positive_mtm: float
    net_mtm: float
    collateral_amount: float
    eligible_collateral: float
    current_exposure: float
    pfe_addon: float
    pfe: float
    trade_pnl: Mapping[str, float]
    product_exposure: Mapping[str, float]

    def __post_init__(self) -> None:
        object.__setattr__(self, "trade_pnl", MappingProxyType(dict(self.trade_pnl)))
        object.__setattr__(
            self,
            "product_exposure",
            MappingProxyType(dict(self.product_exposure)),
        )


@dataclass(frozen=True)
class CounterpartyResult:
    counterparty: str
    limit: float
    gross_positive_mtm: float
    net_mtm: float
    collateral_amount: float
    eligible_collateral: float
    current_exposure: float
    pfe_addon: float
    pfe: float
    limit_utilization: float
    limit_breached: bool
    netting_sets: Mapping[str, NettingSetResult]

    def __post_init__(self) -> None:
        object.__setattr__(self, "netting_sets", MappingProxyType(dict(self.netting_sets)))


@dataclass(frozen=True)
class ExposureReport:
    currency: str
    counterparties: Mapping[str, CounterpartyResult]
    netting_sets: tuple[NettingSetResult, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "counterparties",
            MappingProxyType(dict(self.counterparties)),
        )
