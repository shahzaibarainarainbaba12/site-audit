from __future__ import annotations

import ast
from typing import Any

from audit_types import Issue
from utils import nested_get


class DotDict(dict):
    def __getattr__(self, name):
        value = self.get(name)
        if isinstance(value, dict):
            return DotDict(value)
        return value


def _to_dot(value: Any) -> Any:
    if isinstance(value, dict):
        return DotDict({k: _to_dot(v) for k, v in value.items()})
    if isinstance(value, list):
        return [_to_dot(v) for v in value]
    return value


ALLOWED_AST = {
    ast.Expression, ast.BoolOp, ast.And, ast.Or, ast.UnaryOp, ast.Not,
    ast.Compare, ast.Name, ast.Load, ast.Attribute, ast.Constant,
    ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.Is, ast.IsNot,
    ast.In, ast.NotIn, ast.List, ast.Tuple,
}


def _safe_eval(expr: str, checks: dict[str, Any]) -> bool:
    expr = expr.replace(" true", " True").replace(" false", " False").replace(" null", " None")
    expr = expr.replace("== true", "== True").replace("== false", "== False").replace("!= true", "!= True").replace("!= false", "!= False").replace("== null", "== None").replace("!= null", "!= None")
    tree = ast.parse(expr, mode="eval")
    if any(type(node) not in ALLOWED_AST for node in ast.walk(tree)):
        raise ValueError(f"Unsupported expression: {expr}")
    env = {k: _to_dot(v) for k, v in checks.items()}
    return bool(eval(compile(tree, "<score-rule>", "eval"), {"__builtins__": {}}, env))


def score(checks: dict[str, Any], config: dict[str, Any]) -> tuple[dict[str, int], list[Issue]]:
    cfg = config.get("scoring", {})
    weights = cfg.get("category_weights", {})
    max_by_cat = {k: int(v) for k, v in weights.items()}
    deductions = {k: 0 for k in max_by_cat}
    issues: list[Issue] = []

    for _, rule in cfg.get("rules", {}).items():
        expr = rule.get("when", "")
        try:
            applies = _safe_eval(expr, checks)
        except Exception:
            applies = False
        if applies:
            cat = rule.get("category", "seo")
            points = int(rule.get("points", 0))
            deductions[cat] = deductions.get(cat, 0) + points
            evidence = _evidence_for_rule(expr, checks)
            issues.append(Issue(
                category=cat,
                level=rule.get("level", "info"),
                title=rule.get("title", "Issue detected"),
                fix=rule.get("fix", "Review and fix the detected issue."),
                points=points,
                evidence=evidence,
            ))

    category_scores: dict[str, int] = {}
    weighted_total = 0
    total_weight = sum(max_by_cat.values()) or 100
    for cat, weight in max_by_cat.items():
        raw = max(0, 100 - round(100 * min(deductions.get(cat, 0), weight) / max(weight, 1)))
        category_scores[cat] = raw
        weighted_total += raw * weight
    category_scores["overall"] = round(weighted_total / total_weight)
    order = {"critical": 0, "warning": 1, "info": 2}
    issues.sort(key=lambda x: (order.get(x.level, 9), -x.points, x.title))
    return category_scores, issues


def _evidence_for_rule(expr: str, checks: dict[str, Any]) -> str:
    paths = []
    for node in ast.walk(ast.parse(expr, mode="eval")):
        if isinstance(node, ast.Attribute):
            parts = []
            current = node
            while isinstance(current, ast.Attribute):
                parts.append(current.attr)
                current = current.value
            if isinstance(current, ast.Name):
                parts.append(current.id)
                paths.append(".".join(reversed(parts)))
    pairs = []
    for path in dict.fromkeys(paths):
        pairs.append(f"{path}={nested_get(checks, path)!r}")
    return "; ".join(pairs[:3])
