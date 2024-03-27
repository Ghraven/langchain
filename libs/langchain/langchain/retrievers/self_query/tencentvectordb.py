from __future__ import annotations

from typing import Optional, Sequence, Tuple

from langchain.chains.query_constructor.ir import (Visitor, Comparator, Operator, Comparison, StructuredQuery,
                                                   Operation)


class TencentVectorDBTranslator(Visitor):

    COMPARATOR_MAP = {
        Comparator.EQ: "=",
        Comparator.NE: "!=",
        Comparator.GT: ">",
        Comparator.GTE: ">=",
        Comparator.LT: "<",
        Comparator.LTE: "<=",
        Comparator.IN: "in",
        Comparator.NIN: "not in",
    }

    allowed_comparators: Optional[Sequence[Comparator]] = COMPARATOR_MAP.keys()
    allowed_operators: Optional[Sequence[Operator]] = [Operator.AND, Operator.OR, Operator.NOT]

    def __init__(self, meta_keys: Optional[Sequence[str]] = None):
        self.meta_keys = meta_keys or []

    def visit_operation(self, operation: Operation) -> str:
        if operation.operator in (Operator.AND, Operator.OR):
            ret = f' {operation.operator} '.join([arg.accept(self) for arg in operation.arguments])
            if operation.operator == Operator.OR:
                ret = f"({ret})"
            return ret
        elif operation.operator == Operator.NOT:
            return f"not ({operation.arguments[0].accept(self)})"

    def visit_comparison(self, comparison: Comparison) -> str:
        if self.meta_keys and comparison.attribute not in self.meta_keys:
            raise ValueError(f"Expr Filtering found Unsupported attribute: {comparison.attribute}")

        if comparison.comparator in self.COMPARATOR_MAP:
            if comparison.comparator in [Comparator.IN, Comparator.NIN]:
                value = map(lambda x: f'"{x}"' if isinstance(x, str) else x, comparison.value)
                return f"{comparison.attribute} {self.COMPARATOR_MAP[comparison.comparator]} ({', '.join(value)})"
            if isinstance(comparison.value, str):
                return f"{comparison.attribute} {self.COMPARATOR_MAP[comparison.comparator]} \"{comparison.value}\""
            return f"{comparison.attribute} {self.COMPARATOR_MAP[comparison.comparator]} {comparison.value}"
        else:
            raise ValueError(f"Unsupported comparator {comparison.comparator}")

    def visit_structured_query(self, structured_query: StructuredQuery) -> Tuple[str, dict]:
        if structured_query.filter is None:
            kwargs = {}
        else:
            kwargs = {"expr": structured_query.filter.accept(self)}
        return structured_query.query, kwargs
