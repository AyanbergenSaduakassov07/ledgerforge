"""Arithmetic-only calculator: decimal literals, + - * / ( ) and unary minus. No names or calls."""

from __future__ import annotations

import ast
from decimal import Decimal, DivisionByZero, InvalidOperation, localcontext

from ledgerforge.contracts.schemas import CALC_MAX_CHARS

_OPS = {
    ast.Add: lambda a, b: a + b,
    ast.Sub: lambda a, b: a - b,
    ast.Mult: lambda a, b: a * b,
    ast.Div: lambda a, b: a / b,
}
MAX_DEPTH = 32


class CalcError(ValueError):
    pass


def _eval(node: ast.AST, depth: int = 0) -> Decimal:
    if depth > MAX_DEPTH:
        raise CalcError("expression too deep")
    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        return Decimal(str(node.value))
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub | ast.UAdd):
        value = _eval(node.operand, depth + 1)
        return -value if isinstance(node.op, ast.USub) else value
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval(node.left, depth + 1), _eval(node.right, depth + 1))
    raise CalcError("only numbers, + - * / and parentheses are allowed")


def calculate(expression: object) -> str:
    if not isinstance(expression, str) or not expression.strip():
        raise CalcError("expression must be a non-empty string")
    if len(expression) > CALC_MAX_CHARS:
        raise CalcError(f"expression longer than {CALC_MAX_CHARS} characters")
    try:
        tree = ast.parse(expression.strip(), mode="eval")
    except SyntaxError as e:
        raise CalcError("invalid expression") from e
    with localcontext() as ctx:
        ctx.prec = 34
        ctx.traps[DivisionByZero] = True
        try:
            return str(_eval(tree.body).normalize())
        except (DivisionByZero, InvalidOperation) as e:
            raise CalcError("arithmetic error") from e
