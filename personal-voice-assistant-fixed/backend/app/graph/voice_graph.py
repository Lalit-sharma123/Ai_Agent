"""LangGraph voice-intent router for AVA's seven specialist agents.

LangGraph is used when installed (it is a required production dependency). A small
pure-Python intent classifier remains available for tests and minimal environments.
"""
from __future__ import annotations
import json, re
from typing import Any, TypedDict

AGENTS = {
    "research": "Web Research Agent",
    "meetings": "Meeting Intelligence Agent",
    "email": "Email Agent",
    "coding": "Coding Agent",
    "documents": "Filesystem & Document Agent",
    "presentations": "Presentation Agent",
    "desktop": "Desktop Operator",
    "chat": "General Assistant",
    "calculator": "Calculator",
    "youtube": "YouTube Player",
}

class VoiceState(TypedDict, total=False):
    transcript: str
    provider: str | None
    intent: str
    arguments: dict[str, Any]
    reply: str
    result: dict[str, Any] | None
    needs_clarification: bool
    requires_approval: bool
    requires_confirmation: bool
    plan_only: bool


def deterministic_intent(text: str) -> tuple[str, dict[str, Any]]:
    """Fast local fallback; never invokes tools by itself."""
    t = text.strip()
    s = t.casefold()
    # Local utilities are detected before broad desktop/chat intents.
    if re.search(r"\b(open|launch|start)\s+(the\s+)?calculator\b", s):
        return "desktop", {"action_type": "open_app", "target": "calculator"}
    if "youtube" in s or re.search(r"\bplay\b.*\b(video|song|music)\b", s):
        play_match = re.search(r"\bplay\s+(.+?)(?:\s+on\s+youtube)?\s*[.!?]*$", t, re.I)
        if play_match:
            query = play_match.group(1).strip(" .?!")
        elif re.search(r"\b(open|launch)\s+(the\s+)?youtube\b", s):
            query = ""
        else:
            query = t
        query = re.sub(r"^(?:a\s+)?video\s+on\s+youtube\s+about\s+", "", query, flags=re.I).strip(" .?!")
        query = re.sub(r"^(a\s+)?(video|song|music)\s+(about|for|of)\s+", "", query, flags=re.I).strip(" .?!")
        query = re.sub(r"^and\s+", "", query, flags=re.I).strip(" .?!")
        if re.fullmatch(r"(?:a\s+)?(?:video|song|music)(?:\s+(?:according\s+to\s+)?my\s+preference)?", query, re.I):
            query = ""
        return "youtube", {"query": "" if query.casefold() in {"youtube", "the youtube"} else query, "play_requested": bool(play_match)}
    calc = re.search(r"(?:calculate|what is|what's|compute|work out)\s+(.+)$", t, re.I)
    if calc:
        expression = calc.group(1).strip().rstrip("?.!")
        if re.fullmatch(r"[0-9\s().,+*/%\-^×÷a-z]+", expression, flags=re.I) and re.search(r"\d", expression) and re.search(r"[+*/%\-^×÷]|\b(plus|minus|times|multiplied|divided|over|modulo)\b", expression, re.I):
            return "calculator", {"expression": expression}
    if re.fullmatch(r"\s*[0-9\s().,+*/%\-^×÷]+\s*", t) and re.search(r"[+*/%×÷^-]", t):
        return "calculator", {"expression": t.strip()}
    if any(x in s for x in ("research", "search the web", "look up", "find online", "compare sources", "browse website", "google")):
        query = re.sub(r"^(please\s+)?(research|search( the web)?( for)?|look up|find online|compare sources for|browse website)\s*", "", t, flags=re.I).strip(" .?!") or t
        return "research", {"query": query}
    if any(x in s for x in ("meeting", "transcript", "action items", "meeting notes", "what did we discuss")):
        match = re.search(r"(?:where we discussed|discussed|about|on the topic of)\s+(.+?)(?:[?.!]|$)", t, re.I)
        query = match.group(1).strip() if match else re.sub(r"^(please\s+)?(find|search|look up|summarize)\s+(my\s+)?(meeting|meetings|transcript|transcripts)?\s*", "", t, flags=re.I).strip(" .?!")
        return "meetings", {"query": query or t}
    if any(x in s for x in ("email", "e-mail", "mail to", "send an email", "draft an email")):
        recipient = re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", t)
        subject = re.search(r"(?:subject|about|regarding)\s+(.+?)(?:\s+to\s+|$)", t, re.I)
        return "email", {"instruction": t, "to_address": recipient.group(0) if recipient else "", "subject": subject.group(1).strip() if subject else ""}
    if any(x in s for x in ("code", "coding", "debug", "bug", "error", "stack trace", "fix my project", "pytest", "vscode", "vs code")):
        return "coding", {"issue": t}
    if any(x in s for x in ("pdf", "document", "file", "spreadsheet", "excel", "read my", "search my files", "explain this report")):
        return "documents", {"question": t}
    if any(x in s for x in ("presentation", "powerpoint", "power point", "slides", "pptx")):
        count = re.search(r"\b(\d{1,2})\s+slides?\b", s)
        topic = re.sub(r"^(please\s+)?(create|make|generate|build)\s+(an?\s+)?(\d{1,2}[- ]slide\s+)?(presentation|powerpoint|power point|slides?)\s+(about|on|for)\s+", "", t, flags=re.I).strip(" .?!")
        if topic == t:
            topic = re.sub(r"^(please\s+)?(create|make|generate|build)\s+", "", t, flags=re.I).strip(" .?!")
        return "presentations", {"topic": topic or t, "slide_count": max(3, min(20, int(count.group(1)))) if count else 8}
    if any(x in s for x in ("open app", "open browser", "open website", "open url", "launch", "open vscode", "open vs code", "open firefox", "open chromium")) or ("open " in s and bool(re.search(r"https?://\S+", t))):
        url = re.search(r"https?://\S+", t)
        app = next((a for a in ("code", "firefox", "chromium", "xdg-open") if a in s), "firefox")
        if url: return "desktop", {"action_type": "open_url", "target": url.group(0).rstrip(".,")}
        if "file" in s: return "desktop", {"action_type": "open_file", "target": "."}
        return "desktop", {"action_type": "open_app", "target": app}
    return "chat", {"message": t}


def _parse_model_json(text: str) -> tuple[str, dict[str, Any]] | None:
    try:
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start: return None
        obj = json.loads(text[start:end+1])
        intent = str(obj.get("intent", "chat")).lower().replace(" ", "_")
        aliases = {"meeting": "meetings", "meeting_intelligence": "meetings", "web_research": "research",
                   "document": "documents", "filesystem": "documents", "presentation": "presentations",
                   "desktop_operator": "desktop", "coding_agent": "coding", "email_agent": "email", "general": "chat",
                   "calculate": "calculator", "math": "calculator", "youtube_player": "youtube", "video": "youtube"}
        intent = aliases.get(intent, intent)
        if intent not in AGENTS: return None
        args = obj.get("arguments", {})
        return intent, args if isinstance(args, dict) else {}
    except Exception:
        return None

async def _classify(state: VoiceState, models: Any) -> dict[str, Any]:
    text = state["transcript"].strip()
    fallback = deterministic_intent(text)
    provider = state.get("provider")
    prompt = (
        "Classify this user's voice-assistant request into exactly one intent: research, meetings, email, coding, "
        "documents, presentations, desktop, calculator, youtube, chat. Return only JSON: {\"intent\":\"...\",\"arguments\":{...}}. "
        "Extract only explicit facts. For calculator use expression; for youtube use query (video/song/topic); for research use query; meetings use query; email use instruction, to_address, subject "
        "(email address must be explicit, else empty); coding use issue and optional path; documents use question and optional "
        "document_id; presentations use topic, slide_count (3-20), audience, style; desktop use action_type (open_app/open_url/open_file) "
        "and target. Never send email, execute shell commands, apply code edits, or execute desktop actions automatically. "
        "If uncertain choose chat.\nUSER REQUEST: " + text
    )
    try:
        result = await models.chat([{"role": "user", "content": prompt}], provider)
        parsed = _parse_model_json(result["content"])
        if parsed:
            intent, args = parsed
            # If the model returns a generic classification, keep useful deterministic extraction.
            if intent == "chat" and fallback[0] != "chat": intent, args = fallback
            elif intent == fallback[0]:
                for key, value in fallback[1].items():
                    if value not in (None, "") and args.get(key) in (None, "", []): args[key] = value
                if intent in {"youtube", "calculator"}:
                    args.update(fallback[1])
            return {"intent": intent, "arguments": args}
    except Exception:
        pass
    return {"intent": fallback[0], "arguments": fallback[1]}

async def build_voice_graph(models: Any):
    """Compile a LangGraph when available. Nodes keep planning and execution separate."""
    async def classify_node(state: VoiceState):
        return await _classify(state, models)
    async def prepare_node(state: VoiceState):
        intent, args = state.get("intent", "chat"), state.get("arguments", {})
        if intent == "email" and not args.get("to_address"):
            return {"needs_clarification": True, "reply": "Who should receive the email? Please say the recipient's email address. I will prepare a draft first and will not send it without your explicit approval."}
        if intent == "meetings" and not args.get("query"):
            return {"needs_clarification": True, "reply": "Which meeting, topic, or phrase should I search for?"}
        if intent == "desktop" and not args.get("target"):
            return {"needs_clarification": True, "reply": "What app, URL, or workspace file should I open?"}
        if intent == "calculator" and not args.get("expression"):
            return {"needs_clarification": True, "reply": "What calculation should I do? For example, 24 times 8."}
        if intent == "youtube" and args.get("play_requested") and not args.get("query"):
            return {"needs_clarification": True, "reply": "What would you like me to play on YouTube? Tell me a song, artist, video title, or topic."}
        return {"needs_clarification": False}
    async def execute_node(state: VoiceState):
        if state.get("needs_clarification"):
            return {"result": None, "requires_approval": False, "requires_confirmation": False}
        intent, args = state.get("intent", "chat"), state.get("arguments", {})
        if intent != "chat" and state.get("plan_only", True):
            preview = _confirmation_preview(intent, args)
            return {"result": None, "reply": f"I understood your request: {preview}. Should I do that? Say ‘OK, do that’ to confirm, or ‘cancel’ to stop.", "requires_approval": False, "requires_confirmation": True}
        if intent == "chat":
            try:
                res = await models.chat([{"role":"system","content":"You are AVA, a concise local-first voice assistant. Never claim actions were completed unless a tool result confirms it."},{"role":"user","content":state["transcript"]}], state.get("provider"))
                return {"result": {"content":res["content"], "provider":res.get("provider"), "model":res.get("model")}, "reply":res["content"], "requires_approval":False}
            except Exception as exc:
                return {"result":None,"reply":f"I couldn't reach the configured local model: {exc}","requires_approval":False}
        try:
            from ..services.mcp_client import call_agent_tool
            result = await call_agent_tool(intent, args)
            approval = intent == "desktop" or intent == "email"
            return {"result": result, "reply": _human_reply(intent, result), "requires_approval": approval, "requires_confirmation": False,
                    "needs_clarification": bool(isinstance(result, dict) and result.get("needs_clarification"))}
        except Exception as exc:
            return {"result": {"error": str(exc)}, "reply": f"I understood this as a {AGENTS.get(intent, intent)} request, but the tool did not complete: {exc}", "requires_approval": intent in {"desktop", "email"}, "requires_confirmation": False}
    def route_after_prepare(state: VoiceState):
        return "respond" if state.get("needs_clarification") else "execute"
    async def respond_node(state: VoiceState):
        return {"reply": state.get("reply", "What would you like me to do?")}
    try:
        from langgraph.graph import StateGraph, START, END
        graph = StateGraph(VoiceState)
        graph.add_node("classify", classify_node)
        graph.add_node("prepare", prepare_node)
        graph.add_node("execute", execute_node)
        graph.add_node("respond", respond_node)
        graph.add_edge(START, "classify")
        graph.add_edge("classify", "prepare")
        graph.add_conditional_edges("prepare", route_after_prepare, {"execute":"execute", "respond":"respond"})
        graph.add_edge("execute", END)
        graph.add_edge("respond", END)
        return graph.compile()
    except ImportError:
        return None

async def run_voice_graph(models: Any, transcript: str, provider: str | None = None, *, plan_only: bool = True) -> dict[str, Any]:
    state: VoiceState = {"transcript": transcript, "provider": provider, "plan_only": plan_only}
    graph = await build_voice_graph(models)
    if graph is not None:
        out = await graph.ainvoke(state)
    else:
        # Useful fallback for tests/minimal installs; production requirements include LangGraph.
        out = {**state, **(await _classify(state, models))}
        prep = await _prepare_fallback(out)
        out.update(prep)
        if not out.get("needs_clarification"):
            intent, args = out["intent"], out.get("arguments", {})
            if intent == "chat":
                try:
                    res = await models.chat([{"role":"user","content":transcript}], provider)
                    out.update(result=res, reply=res["content"], requires_approval=False)
                except Exception as exc: out.update(result=None, reply=f"I couldn't reach the configured local model: {exc}", requires_approval=False)
            elif plan_only:
                out.update(result=None, reply=f"I understood your request: {_confirmation_preview(intent, args)}. Should I do that? Say ‘OK, do that’ to confirm, or ‘cancel’ to stop.", requires_approval=False, requires_confirmation=True)
            else:
                try:
                    from ..services.mcp_client import call_agent_tool
                    result = await call_agent_tool(intent, args)
                    out.update(result=result, reply=_human_reply(intent, result), requires_approval=intent in {"email","desktop"}, requires_confirmation=False,
                               needs_clarification=bool(isinstance(result, dict) and result.get("needs_clarification")))
                except Exception as exc: out.update(result={"error":str(exc)}, reply=f"I understood this as a {AGENTS.get(intent,intent)} request, but the tool did not complete: {exc}", requires_approval=intent in {"email","desktop"})
    return {"transcript": transcript, "intent": out.get("intent", "chat"), "agent": AGENTS.get(out.get("intent", "chat"), "General Assistant"),
            "arguments": out.get("arguments", {}), "reply": out.get("reply", "Done."), "result": out.get("result"),
            "needs_clarification": bool(out.get("needs_clarification", False)), "requires_approval": bool(out.get("requires_approval", False)),
            "requires_confirmation": bool(out.get("requires_confirmation", False)),
            "orchestration": "langgraph" if graph is not None else "python-fallback"}

async def _prepare_fallback(state):
    intent,args=state.get("intent","chat"),state.get("arguments",{})
    if intent=="email" and not args.get("to_address"):
        return {"needs_clarification":True,"reply":"Who should receive the email? Please say the recipient's email address. I will prepare a draft first and will not send it without your explicit approval."}
    if intent=="meetings" and not args.get("query"):
        return {"needs_clarification":True,"reply":"Which meeting, topic, or phrase should I search for?"}
    if intent=="desktop" and not args.get("target"):
        return {"needs_clarification":True,"reply":"What app, URL, or workspace file should I open?"}
    if intent=="calculator" and not args.get("expression"):
        return {"needs_clarification":True,"reply":"What calculation should I do? For example, 24 times 8."}
    if intent=="youtube" and args.get("play_requested") and not args.get("query"):
        return {"needs_clarification":True,"reply":"What would you like me to play on YouTube? Tell me a song, artist, video title, or topic."}
    return {"needs_clarification":False}

def _confirmation_preview(intent: str, args: dict[str, Any]) -> str:
    if intent == "calculator": return f"calculate {args.get('expression', 'the requested expression')}"
    if intent == "youtube": return f"open YouTube and play/search for ‘{args.get('query') or 'the YouTube homepage'}’"
    if intent == "desktop": return f"open {args.get('target', 'the requested app or URL')}"
    if intent == "email": return f"prepare an email draft for {args.get('to_address') or 'the recipient you specify'}"
    if intent == "research": return f"research ‘{args.get('query', 'your topic')}’ on the web"
    if intent == "meetings": return f"search meeting records for ‘{args.get('query', 'your topic')}’"
    if intent == "coding": return f"analyze the coding task ‘{args.get('issue', 'your request')}’ without changing files automatically"
    if intent == "documents": return f"answer your document question ‘{args.get('question', 'your question')}’"
    if intent == "presentations": return f"create a {args.get('slide_count', 8)}-slide presentation about ‘{args.get('topic', 'your topic')}’"
    return "complete the requested task"

def _human_reply(intent: str, result: Any) -> str:
    if isinstance(result, dict) and result.get("error"): return str(result["error"])
    if isinstance(result, dict) and result.get("needs_clarification"): return str(result.get("message", "I need one more detail before I can continue."))
    if intent == "research": return f"Research search completed. I found {result.get('count', 0)} results." if isinstance(result,dict) else "Research request completed."
    if intent == "meetings": return f"Meeting search completed. I found {result.get('count', len(result.get('results', [])) if isinstance(result,dict) else 0)} matching records." if isinstance(result,dict) else "Meeting request completed."
    if intent == "email": return "I've prepared an email draft for review. I have not sent it; review it and explicitly approve sending." 
    if intent == "coding": return "I've analyzed the coding issue and prepared recommendations. No files were modified." 
    if intent == "documents": return str(result.get("answer", result.get("content", "Document request completed."))) if isinstance(result,dict) else "Document request completed."
    if intent == "presentations": return f"Presentation generated: {result.get('title', 'your presentation')} ({result.get('slides', '?')} slides)." if isinstance(result,dict) else "Presentation request completed."
    if intent == "desktop": return "Desktop action completed after your confirmation." 
    if intent == "calculator": return str(result.get("message", result.get("result", "Calculation completed."))) if isinstance(result,dict) else "Calculation completed."
    if intent == "youtube": return str(result.get("message", "YouTube launch requested.")) if isinstance(result,dict) else "YouTube launch requested."
    return "Request completed."
