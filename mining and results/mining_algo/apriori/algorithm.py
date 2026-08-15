"""Parallel Apriori implementation for prepared baskets."""

from __future__ import annotations

from collections import Counter
from itertools import combinations
from multiprocessing import Pool

from mining_algo.models import Itemset, MiningResult, Transaction
from mining_algo.utils import chunked, min_support_count


_CANDIDATES: tuple[Itemset, ...] = ()


def _init_candidates(candidates: tuple[Itemset, ...]) -> None:
    global _CANDIDATES
    _CANDIDATES = candidates


def _count_singletons(chunk: list[Transaction]) -> Counter[int]:
    counts: Counter[int] = Counter()
    for transaction in chunk:
        counts.update(transaction)
    return counts


def _count_candidate_chunk(chunk: list[Transaction]) -> Counter[Itemset]:
    counts: Counter[Itemset] = Counter()
    candidate_sets = [(candidate, set(candidate)) for candidate in _CANDIDATES]
    for transaction in chunk:
        item_set = set(transaction)
        for candidate, candidate_set in candidate_sets:
            if candidate_set.issubset(item_set):
                counts[candidate] += 1
    return counts


def _merge_counters(counters) -> Counter:
    merged: Counter = Counter()
    for counter in counters:
        merged.update(counter)
    return merged


def _generate_candidates(previous_level: set[Itemset], size: int) -> tuple[Itemset, ...]:
    previous = sorted(previous_level)
    previous_lookup = set(previous)
    candidates: set[Itemset] = set()

    for left_index in range(len(previous)):
        for right_index in range(left_index + 1, len(previous)):
            left = previous[left_index]
            right = previous[right_index]
            if left[: size - 2] != right[: size - 2]:
                break

            candidate = tuple(sorted(set(left) | set(right)))
            if len(candidate) != size:
                continue

            if all(tuple(subset) in previous_lookup for subset in combinations(candidate, size - 1)):
                candidates.add(candidate)

    return tuple(sorted(candidates))


def _parallel_singleton_counts(transactions: list[Transaction], workers: int) -> Counter[int]:
    chunks = chunked(transactions, workers)
    if workers <= 1 or len(chunks) <= 1:
        return _merge_counters(_count_singletons(list(chunk)) for chunk in chunks)

    with Pool(processes=workers) as pool:
        return _merge_counters(pool.map(_count_singletons, chunks))


def _parallel_candidate_counts(
    transactions: list[Transaction],
    candidates: tuple[Itemset, ...],
    workers: int,
) -> Counter[Itemset]:
    chunks = chunked(transactions, workers)
    if workers <= 1 or len(chunks) <= 1:
        _init_candidates(candidates)
        return _merge_counters(_count_candidate_chunk(list(chunk)) for chunk in chunks)

    with Pool(processes=workers, initializer=_init_candidates, initargs=(candidates,)) as pool:
        return _merge_counters(pool.map(_count_candidate_chunk, chunks))


def run_apriori(
    transactions: list[Transaction],
    min_support: float,
    workers: int,
    max_itemset_size: int,
) -> MiningResult:
    transaction_count = len(transactions)
    support_floor = min_support_count(min_support, transaction_count)

    itemsets: dict[Itemset, int] = {}
    singleton_counts = _parallel_singleton_counts(transactions, workers)
    current_level = {
        (item_id,): count
        for item_id, count in singleton_counts.items()
        if count >= support_floor
    }
    itemsets.update(current_level)

    size = 2
    while current_level and size <= max_itemset_size:
        candidates = _generate_candidates(set(current_level), size)
        if not candidates:
            break

        counts = _parallel_candidate_counts(transactions, candidates, workers)
        current_level = {
            candidate: count
            for candidate, count in counts.items()
            if count >= support_floor
        }
        itemsets.update(current_level)
        size += 1

    return MiningResult(itemsets=itemsets, transaction_count=transaction_count)
