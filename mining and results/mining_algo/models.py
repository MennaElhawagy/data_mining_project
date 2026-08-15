"""Shared data structures for mining algorithms."""

from __future__ import annotations

from dataclasses import dataclass


Itemset = tuple[int, ...]
Transaction = tuple[int, ...]


@dataclass(frozen=True)
class MiningResult:
    itemsets: dict[Itemset, int]
    transaction_count: int


@dataclass(frozen=True)
class AssociationRule:
    antecedent: Itemset
    consequent_id: int
    support: float
    confidence: float
    lift: float
