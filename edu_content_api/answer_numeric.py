import re
from typing import Optional, Tuple


def _normalize_numeric_expression(value: str) -> str:
    expr = value.strip()
    if not expr:
        return ""

    expr = expr.replace("$", "")
    expr = re.sub(r"^\s*[a-zA-Z]\s*=\s*", "", expr)
    if "=" in expr:
        parts = [part.strip() for part in expr.split("=") if part.strip()]
        expr = parts[-1] if parts else expr

    expr = expr.replace(",", ".")
    expr = expr.replace("\\left", "").replace("\\right", "")
    expr = re.sub(r"\\text\{[^}]*\}", "", expr)
    expr = re.sub(r"\\mathrm\{([^}]*)\}", r"\1", expr)
    expr = expr.replace("\\cdot", "*").replace("\\times", "*").replace("\\div", "/")
    expr = expr.replace("\\pi", "math.pi")
    expr = re.sub(r"\bpi\b", "math.pi", expr, flags=re.IGNORECASE)
    expr = re.sub(r"\bsqrt\s*\(", "math.sqrt(", expr, flags=re.IGNORECASE)

    frac_pattern = re.compile(r"\\(?:d)?frac\s*\{([^{}]+)\}\{([^{}]+)\}")
    while frac_pattern.search(expr):
        expr = frac_pattern.sub(r"((\1)/(\2))", expr)

    sqrt_pattern = re.compile(r"\\sqrt\s*\{([^{}]+)\}")
    while sqrt_pattern.search(expr):
        expr = sqrt_pattern.sub(r"math.sqrt(\1)", expr)

    expr = expr.replace("{", "(").replace("}", ")")
    expr = re.sub(r"\s+", "", expr)
    return expr


def evaluate_numeric_answer(value: Optional[str]) -> Tuple[Optional[float], Optional[str]]:
    if not value:
        return None, None

    expr = _normalize_numeric_expression(value)
    if not expr:
        return None, None

    stripped = re.sub(r"math|pi|sqrt", "", expr, flags=re.IGNORECASE)
    if re.search(r"[a-zA-Z]", stripped):
        match = re.search(r"([\-]?\d+(?:\.\d+)?(?:\/[\-]?\d+(?:\.\d+)?)?)$", expr)
        if not match:
            return None, None
        return evaluate_numeric_answer(match.group(1))

    if not re.fullmatch(r"[0-9+\-*/().a-zA-Z]+", expr):
        return None, None

    try:
        result = eval(expr, {"__builtins__": {}}, {"math": __import__("math")})  # noqa: S307
    except Exception:
        return None, None

    if not isinstance(result, (int, float)):
        return None, None

    numeric = float(result)
    if not (numeric == numeric and abs(numeric) != float("inf")):
        return None, None
    return numeric, expr
