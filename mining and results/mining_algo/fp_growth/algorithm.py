"""FP-Growth implementation with parallel top-level conditional mining."""

from __future__ import annotations

from collections import Counter, defaultdict
from multiprocessing import Pool

from mining_algo.models import Itemset, MiningResult, Transaction
from mining_algo.utils import chunked, min_support_count


class FPNode:
    def __init__(self, item: int | None, count: int, parent: "FPNode | None") -> None:
        self.item = item
        self.count = count
        self.parent = parent
        self.children: dict[int, FPNode] = {}


def _count_items(chunk: list[Transaction]) -> Counter[int]:
    counts: Counter[int] = Counter()
    for transaction in chunk:
        counts.update(transaction)
    return counts


def _merge_counters(counters) -> Counter:
    merged: Counter = Counter()
    for counter in counters:
        merged.update(counter)
    return merged


def _parallel_item_counts(transactions: list[Transaction], workers: int) -> Counter[int]:
    chunks = chunked(transactions, workers)
    if workers <= 1 or len(chunks) <= 1:
        return _merge_counters(_count_items(list(chunk)) for chunk in chunks)
    with Pool(processes=workers) as pool:
        return _merge_counters(pool.map(_count_items, chunks))


def _insert_transaction(root: FPNode, header: dict[int, list[FPNode]], items: list[int], count: int) -> None:
    node = root
    for item in items:
        child = node.children.get(item)
        if child is None:
            child = FPNode(item=item, count=0, parent=node)
            node.children[item] = child
            header[item].append(child)
        child.count += count
        node = child


def _build_tree(
    weighted_transactions: list[tuple[list[int], int]],
    support_floor: int,
) -> tuple[FPNode, dict[int, list[FPNode]], Counter[int]]:
    counts: Counter[int] = Counter()
    for items, count in weighted_transactions:
        for item in items:
            counts[item] += count

    frequent_counts = Counter({item: count for item, count in counts.items() if count >= support_floor})
    order = {item: index for index, (item, _) in enumerate(frequent_counts.most_common())}
    root = FPNode(item=None, count=0, parent=None)
    header: dict[int, list[FPNode]] = defaultdict(list)

    for items, count in weighted_transactions:
        filtered = [item for item in items if item in frequent_counts]
        filtered.sort(key=lambda item: (order[item], item))
        if filtered:
            _insert_transaction(root, header, filtered, count)

    return root, header, frequent_counts


def _conditional_pattern_base(nodes: list[FPNode]) -> list[tuple[list[int], int]]:
    patterns: list[tuple[list[int], int]] = []
    for node in nodes:
        path: list[int] = []
        parent = node.parent
        while parent is not None and parent.item is not None:
            path.append(parent.item)
            parent = parent.parent
        if path:
            patterns.append((path, node.count))
    return patterns


def _mine_conditional(
    weighted_transactions: list[tuple[list[int], int]],
    suffix: Itemset,
    support_floor: int,
    max_itemset_size: int,
) -> dict[Itemset, int]:
    _, header, counts = _build_tree(weighted_transactions, support_floor)
    found: dict[Itemset, int] = {}

    for item, support_count in sorted(counts.items(), key=lambda row: (row[1], row[0])):
        itemset = tuple(sorted((item, *suffix)))
        if len(itemset) <= max_itemset_size:
            found[itemset] = support_count

        if len(itemset) >= max_itemset_size:
            continue

        base = _conditional_pattern_base(header[item])
        if base:
            found.update(_mine_conditional(base, itemset, support_floor, max_itemset_size))

    return found


def _mine_top_branch(args) -> dict[Itemset, int]:
    item, support_count, base, support_floor, max_itemset_size = args
    suffix = (item,)
    found: dict[Itemset, int] = {suffix: support_count}
    if max_itemset_size > 1 and base:
        found.update(_mine_conditional(base, suffix, support_floor, max_itemset_size))
    return found


def run_fp_growth(
    transactions: list[Transaction],
    min_support: float,
    workers: int,
    max_itemset_size: int,
) -> MiningResult:
    transaction_count = len(transactions)
    support_floor = min_support_count(min_support, transaction_count)
    item_counts = _parallel_item_counts(transactions, workers)
    frequent_items = {item for item, count in item_counts.items() if count >= support_floor}
    order = {item: index for index, item in enumerate(
        item for item, _ in item_counts.most_common() if item in frequent_items
    )}

    weighted_transactions: list[tuple[list[int], int]] = []
    for transaction in transactions:
        filtered = [item for item in transaction if item in frequent_items]
        filtered.sort(key=lambda item: (order[item], item))
        if filtered:
            weighted_transactions.append((filtered, 1))

    _, header, counts = _build_tree(weighted_transactions, support_floor)
    branches = [
        (item, count, _conditional_pattern_base(header[item]), support_floor, max_itemset_size)
        for item, count in sorted(counts.items(), key=lambda row: (row[1], row[0]))
    ]

    itemsets: dict[Itemset, int] = {}
    if workers <= 1 or len(branches) <= 1:
        branch_results = [_mine_top_branch(branch) for branch in branches]
    else:
        with Pool(processes=workers) as pool:
            branch_results = pool.map(_mine_top_branch, branches)

    for result in branch_results:
        itemsets.update(result)

    return MiningResult(itemsets=itemsets, transaction_count=transaction_count)
