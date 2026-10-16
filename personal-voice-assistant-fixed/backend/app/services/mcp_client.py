"""MCP client used by the LangGraph execution node.

Starts the bundled AVA MCP server over stdio for each request. If MCP is not installed
(e.g. a minimal test environment), it uses the same local API contract over HTTP.
"""
from __future__ import annotations
import json, os, sys
from pathlib import Path
from typing import Any
import httpx

ROOT = Path(__file__).resolve().parents[3]

async def _http_fallback(agent: str, arguments: dict[str, Any]) -> dict[str, Any]:
    base = os.getenv("AVA_API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
    timeout = float(os.getenv("MCP_TOOL_TIMEOUT", "90"))
    async with httpx.AsyncClient(base_url=base, timeout=timeout) as client:
        if agent == "calculator":
            from .local_tools import calculate
            try: return calculate(str(arguments.get("expression", "")))
            except ValueError as exc: return {"error": str(exc)}
        elif agent == "youtube":
            from .local_tools import youtube_search_url
            target = youtube_search_url(str(arguments.get("query", "")))
            response = await client.post("/api/desktop/actions", json={"action_type": "open_url", "target": target})
        elif agent == "research":
            response = await client.post("/api/research/search", json={"query": str(arguments.get("query", "")), "limit": int(arguments.get("limit", 5))})
        elif agent == "meetings":
            q = str(arguments.get("query", "")).strip()
            response = await client.get("/api/meetings/search", params={"q": q})
        elif agent == "email":
            response = await client.post("/api/email/drafts", json={"instruction": str(arguments.get("instruction", "")), "to_address": str(arguments.get("to_address", "")), "subject": str(arguments.get("subject", "")), "context": str(arguments.get("context", ""))})
        elif agent == "coding":
            response = await client.post("/api/coding/analyze", json={"issue": str(arguments.get("issue", "")), "path": str(arguments.get("path", "."))})
        elif agent == "documents":
            doc_id = str(arguments.get("document_id", ""))
            if not doc_id:
                docs_response = await client.get("/api/documents")
                docs_response.raise_for_status()
                docs = docs_response.json()
                if not docs: return {"needs_clarification": True, "message": "I couldn't find an uploaded document. Upload it in the Documents workspace and try again."}
                doc_id = str(docs[0].get("id", ""))
            response = await client.post("/api/documents/ask", json={"question": str(arguments.get("question", "Summarize this document")), "document_id": doc_id})
        elif agent == "presentations":
            response = await client.post("/api/presentations/generate", json={"topic": str(arguments.get("topic", "")), "slide_count": int(arguments.get("slide_count", 8)), "audience": str(arguments.get("audience", "general professional audience")), "style": str(arguments.get("style", "clean professional"))})
        elif agent == "desktop":
            response = await client.post("/api/desktop/actions", json={"action_type": str(arguments.get("action_type", "open_app")), "target": str(arguments.get("target", ""))})
        else:
            return {"error": f"Unsupported agent '{agent}'."}
        try: payload = response.json()
        except Exception: payload = {"detail": response.text[:2000]}
        if response.is_error: return {"error": payload.get("detail", f"Agent returned HTTP {response.status_code}"), "status_code": response.status_code}
        return payload

async def call_agent_tool(agent: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Invoke the `run_agent` MCP tool; retain an HTTP fallback for local tests."""
    try:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
    except ImportError:
        return await _http_fallback(agent, arguments)
    env = dict(os.environ)
    env.setdefault("AVA_API_BASE_URL", os.getenv("AVA_API_BASE_URL", "http://127.0.0.1:8000"))
    params = StdioServerParameters(command=sys.executable, args=["-m", "mcp_servers.ava_mcp.server"], env=env, cwd=str(ROOT))
    try:
        async with stdio_client(params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = await session.call_tool("run_agent", {"agent": agent, "arguments": arguments})
                if getattr(result, "isError", False):
                    detail = " ".join(getattr(c, "text", "") for c in result.content)
                    return {"error": detail or "MCP agent tool failed."}
                for item in getattr(result, "content", []):
                    raw = getattr(item, "text", "")
                    try:
                        parsed = json.loads(raw)
                        if isinstance(parsed, dict): return parsed
                        return {"result": parsed}
                    except (ValueError, TypeError):
                        if raw: return {"message": raw}
                return {"error": "MCP agent tool returned an empty result."}
    except Exception as exc:
        # MCP failure is visible and safe; use same local endpoint contract so the user can
        # continue working while installing/fixing MCP, rather than silently dropping intent.
        if os.getenv("MCP_HTTP_FALLBACK", "true").lower() in {"1", "true", "yes"}:
            return await _http_fallback(agent, arguments)
        return {"error": f"MCP connection failed: {exc}"}
