"""AVA MCP server: exposes the specialist agent dispatcher as a standard MCP tool."""
from __future__ import annotations
import os
import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("ava-specialist-agents")

@mcp.tool()
async def run_agent(agent: str, arguments: dict) -> dict:
    """Run one of AVA's seven specialist agents using validated local API routes.

    Supported agents: research, meetings, email, coding, documents, presentations, desktop, calculator, youtube.
    This tool never sends email or executes a desktop action automatically; it only creates
    a draft or a pending-approval desktop action.
    """
    if agent == "calculator":
        from app.services.local_tools import calculate
        try: return calculate(str(arguments.get("expression", "")))
        except ValueError as exc: return {"error": str(exc)}
    base = os.getenv("AVA_API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
    timeout = float(os.getenv("MCP_TOOL_TIMEOUT", "90"))
    async with httpx.AsyncClient(base_url=base, timeout=timeout) as client:
        if agent == "youtube":
            from app.services.local_tools import youtube_search_url
            response = await client.post("/api/desktop/actions", json={"action_type": "open_url", "target": youtube_search_url(str(arguments.get("query", "")))})
        elif agent == "research":
            response = await client.post("/api/research/search", json={"query": str(arguments.get("query", "")), "limit": int(arguments.get("limit", 5))})
        elif agent == "meetings":
            query = str(arguments.get("query", "")).strip()
            if not query: return {"needs_clarification": True, "message": "Tell me the meeting title, topic, or phrase to search for."}
            response = await client.get("/api/meetings/search", params={"q": query})
        elif agent == "email":
            recipient = str(arguments.get("to_address", "")).strip()
            instruction = str(arguments.get("instruction", "")).strip()
            if "@" not in recipient or len(instruction) < 3:
                return {"needs_clarification": True, "message": "Please provide a recipient email address and what the email should say."}
            response = await client.post("/api/email/drafts", json={"instruction": instruction, "to_address": recipient, "subject": str(arguments.get("subject", "")), "context": str(arguments.get("context", ""))})
        elif agent == "coding":
            issue = str(arguments.get("issue", "")).strip()
            if len(issue) < 3: return {"needs_clarification": True, "message": "Describe the coding error or project change you need help with."}
            response = await client.post("/api/coding/analyze", json={"issue": issue, "path": str(arguments.get("path", "."))})
        elif agent == "documents":
            doc_id = str(arguments.get("document_id", "")).strip()
            if not doc_id:
                docs_response = await client.get("/api/documents")
                docs_response.raise_for_status()
                docs = docs_response.json()
                if not docs: return {"needs_clarification": True, "message": "I couldn't find an uploaded document. Upload it in the Documents workspace and try again."}
                doc_id = str(docs[0].get("id", ""))
            response = await client.post("/api/documents/ask", json={"question": str(arguments.get("question", "Summarize this document")), "document_id": doc_id})
        elif agent == "presentations":
            topic = str(arguments.get("topic", "")).strip()
            if len(topic) < 3: return {"needs_clarification": True, "message": "What topic should the presentation cover?"}
            response = await client.post("/api/presentations/generate", json={"topic": topic, "slide_count": max(3, min(20, int(arguments.get("slide_count", 8)))), "audience": str(arguments.get("audience", "general professional audience")), "style": str(arguments.get("style", "clean professional"))})
        elif agent == "desktop":
            action_type, target = str(arguments.get("action_type", "")), str(arguments.get("target", "")).strip()
            if action_type not in {"open_app", "open_url", "open_file"} or not target:
                return {"needs_clarification": True, "message": "Specify an app, complete URL, or file in the approved workspace."}
            response = await client.post("/api/desktop/actions", json={"action_type": action_type, "target": target})
        else:
            return {"error": f"Unsupported agent '{agent}'. Supported agents: research, meetings, email, coding, documents, presentations, desktop."}
        try: result = response.json()
        except Exception: result = {"detail": response.text[:2000]}
        if response.is_error: return {"error": result.get("detail", f"HTTP {response.status_code}"), "status_code": response.status_code}
        return result


@mcp.tool()
async def research_search(query: str, limit: int = 5) -> dict:
    """Search the configured self-hosted SearXNG instance for web research."""
    return await run_agent("research", {"query": query, "limit": limit})

@mcp.tool()
async def meeting_search(query: str) -> dict:
    """Search saved AVA meeting transcripts, summaries, and action items."""
    return await run_agent("meetings", {"query": query})

@mcp.tool()
async def email_create_draft(instruction: str, to_address: str, subject: str = "", context: str = "") -> dict:
    """Create an email draft for review; this tool never sends the email."""
    return await run_agent("email", {"instruction": instruction, "to_address": to_address, "subject": subject, "context": context})

@mcp.tool()
async def coding_analyze(issue: str, path: str = ".") -> dict:
    """Analyze a coding issue in the approved workspace without changing files."""
    return await run_agent("coding", {"issue": issue, "path": path})

@mcp.tool()
async def document_ask(question: str, document_id: str) -> dict:
    """Ask a question about a document already uploaded to AVA."""
    return await run_agent("documents", {"question": question, "document_id": document_id})

@mcp.tool()
async def presentation_generate(topic: str, slide_count: int = 8, audience: str = "general professional audience", style: str = "clean professional") -> dict:
    """Generate an editable PowerPoint deck on a specified topic."""
    return await run_agent("presentations", {"topic": topic, "slide_count": slide_count, "audience": audience, "style": style})

@mcp.tool()
async def desktop_propose(action_type: str, target: str) -> dict:
    """Create a pending-approval desktop action; never execute it automatically."""
    return await run_agent("desktop", {"action_type": action_type, "target": target})

@mcp.tool()
async def calculator_calculate(expression: str) -> dict:
    """Safely calculate a basic arithmetic expression without evaluating arbitrary code."""
    return await run_agent("calculator", {"expression": expression})

@mcp.tool()
async def youtube_play(query: str = "") -> dict:
    """Open the first matching YouTube video when yt-dlp is installed, otherwise open YouTube search results."""
    return await run_agent("youtube", {"query": query})

if __name__ == "__main__":
    mcp.run(transport="stdio")
