"""Parallel Eclat implementation using vertical transaction id sets."""

from __future__ import annotations

from collections import defaultdict
from multiprocessing import Pool

from mining_algo.models import Itemset, MiningResult, Transaction
from mining_algo.utils import min_support_count


VerticalItem = tuple[Itemset, set[int]]


def _expand_prefix(
    prefix: Itemset,
    prefix_tids: set[int],
    suffixes: list[VerticalItem],
    support_floor: int,
    max_itemset_size: int,
) -> dict[Itemset, int]:
    found: dict[Itemset, int] = {}

    for index, (itemset, tids) in enumerate(suffixes):
        combined = tuple(sorted((*prefix, *itemset)))
        combined_tids = prefix_tids & tids
        support_count = len(combined_tids)
        if support_count < support_floor:
            continue

        found[combined] = support_count
        if len(combined) >= max_itemset_size:
            continue

        next_suffixes: list[VerticalItem] = []
        for next_itemset, next_tids in suffixes[index + 1 :]:
            intersected = combined_tids & next_tids
            if len(intersected) >= support_floor:
                next_suffixes.append((next_itemset, intersected))

        if next_suffixes:
            found.update(
                _expand_prefix(combined, combined_tids, next_suffixes, support_floor, max_itemset_size)
            )

    return found


def _mine_branch(args) -> dict[Itemset, int]:
    itemset, tids, suffixes, support_floor, max_itemset_size = args
    found = {itemset: len(tids)}
    if max_itemset_size > 1:
        found.update(_expand_prefix(itemset, tids, suffixes, support_floor, max_itemset_size))
    return found


def run_eclat(
    transactions: list[Transaction],
    min_support: float,
    workers: int,
    max_itemset_size: int,
) -> MiningResult:
    transaction_count = len(transactions)
    support_floor = min_support_count(min_support, transaction_count)

    tidsets: dict[int, set[int]] = defaultdict(set)
    for transaction_id, transaction in enumerate(transactions):
        for item in transaction:
            tidsets[item].add(transaction_id)

    vertical: list[VerticalItem] = [
        ((item,), tids)
        for item, tids in sorted(tidsets.items(), key=lambda row: (len(row[1]), row[0]))
        if len(tids) >= support_floor
    ]

    branches = [
        (itemset, tids, vertical[index + 1 :], support_floor, max_itemset_size)
        for index, (itemset, tids) in enumerate(vertical)
    ]

    if workers <= 1 or len(branches) <= 1:
        branch_results = [_mine_branch(branch) for branch in branches]
    else:
        with Pool(processes=workers) as pool:
            branch_results = pool.map(_mine_branch, branches)

    itemsets: dict[Itemset, int] = {}
    for result in branch_results:
        itemsets.update(result)

    return MiningResult(itemsets=itemsets, transaction_count=transaction_count)
