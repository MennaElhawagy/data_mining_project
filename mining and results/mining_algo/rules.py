"""Association rule generation from frequent itemsets."""

from __future__ import annotations

from .models import AssociationRule, Itemset


def generate_single_consequent_rules(
    itemsets: dict[Itemset, int],
    transaction_count: int,
    min_confidence: float,
) -> list[AssociationRule]:
    """Generate rules with one consequent item.

    The DWH rule table stores a single `consequent_id`, so this project keeps
    rules in the common `A,B => C` form.
    """
    rules: list[AssociationRule] = []
    if transaction_count <= 0:
        return rules

    for itemset, support_count in itemsets.items():
        if len(itemset) < 2:
            continue

        itemset_support = support_count / transaction_count
        for consequent_id in itemset:
            antecedent = tuple(item for item in itemset if item != consequent_id)
            antecedent_count = itemsets.get(antecedent)
            consequent_count = itemsets.get((consequent_id,))
            if not antecedent_count or not consequent_count:
                continue

            confidence = support_count / antecedent_count
            if confidence < min_confidence:
                continue

            consequent_support = consequent_count / transaction_count
            if consequent_support <= 0:
                continue

            lift = confidence / consequent_support
            rules.append(
                AssociationRule(
                    antecedent=antecedent,
                    consequent_id=consequent_id,
                    support=itemset_support,
                    confidence=confidence,
                    lift=lift,
                )
            )

    rules.sort(key=lambda rule: (rule.lift, rule.confidence, rule.support), reverse=True)
    return rules
