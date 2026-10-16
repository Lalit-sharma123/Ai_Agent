"""Safe local tools used by AVA and its MCP server."""
from __future__ import annotations
import ast
import math
import operator
from urllib.parse import quote_plus

_BINARY = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod, ast.Pow: operator.pow,
}
_UNARY = {ast.UAdd: operator.pos, ast.USub: operator.neg}


def calculate(expression: str) -> dict:
    """Evaluate arithmetic only; never use eval or allow names/attributes/calls."""
    expression = expression.strip().replace("×", "*").replace("÷", "/").replace("^", "**")
    replacements = [
        (r"\bmultiplied\s+by\b", "*"), (r"\btimes\b", "*"),
        (r"\bdivided\s+by\b", "/"), (r"\bover\b", "/"),
        (r"\bplus\b", "+"), (r"\bminus\b", "-"),
        (r"\bmod(?:ulo)?\b", "%"), (r"\bto\s+the\s+power\s+of\b", "**"),
    ]
    import re
    for pattern, replacement in replacements:
        expression = re.sub(pattern, replacement, expression, flags=re.I)
    if not expression or len(expression) > 300:
        raise ValueError("Provide a short arithmetic expression.")
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise ValueError("I couldn't parse that calculation. Try something like 24 * (8 + 2).") from exc

    def visit(node):
        if isinstance(node, ast.Expression): return visit(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            if abs(node.value) > 1e100: raise ValueError("That number is too large.")
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in _BINARY:
            left, right = visit(node.left), visit(node.right)
            if isinstance(node.op, ast.Pow) and abs(right) > 100: raise ValueError("Exponent is too large.")
            value = _BINARY[type(node.op)](left, right)
            if isinstance(value, complex) or not math.isfinite(float(value)) or abs(value) > 1e100:
                raise ValueError("The result is outside the supported numeric range.")
            return value
        if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY: return _UNARY[type(node.op)](visit(node.operand))
        raise ValueError("Only basic arithmetic (+, -, *, /, //, %, **, and parentheses) is supported.")
    try:
        result = visit(tree)
    except ZeroDivisionError as exc:
        raise ValueError("Division by zero is not allowed.") from exc
    if isinstance(result, float) and result.is_integer(): result = int(result)
    return {"expression": expression, "result": result, "message": f"{expression} = {result}"}


def youtube_search_url(query: str) -> str:
    query = query.strip()
    if not query:
        return "https://www.youtube.com/"
    # yt-dlp is optional; if installed it resolves the first search result to a watch URL.
    try:
        import yt_dlp
        opts = {"quiet": True, "no_warnings": True, "skip_download": True, "extract_flat": True, "noplaylist": True, "socket_timeout": 8, "extractor_retries": 1}
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(f"ytsearch1:{query}", download=False)
        entries = (info or {}).get("entries") or []
        if entries:
            video_id = entries[0].get("id")
            if video_id:
                return f"https://www.youtube.com/watch?v={video_id}"
    except Exception:
        pass
    return f"https://www.youtube.com/results?search_query={quote_plus(query)}"
