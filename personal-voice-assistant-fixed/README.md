# AVA Personal Voice Assistant — Voice Intent + LangGraph + MCP

A local-first core voice assistant with a FastAPI backend, React/TypeScript UI, persistent SQLite conversation history, configurable hosted Qwen and GPT-OSS model adapters, browser push-to-talk, and spoken responses through browser speech synthesis. No paid AI inference API is used.

The main voice assistant routes commands to seven specialist agents through LangGraph and an MCP tool server. For task commands, AVA first repeats the intended action and waits for “OK, do that” (or cancels on “cancel”) before executing. It also supports calculator arithmetic, opening a desktop calculator, and launching YouTube videos/searches. General conversational questions can be answered directly.

## Requirements
- Python 3.10+
- Node.js 20+ and npm
- A reachable hosted Qwen and/or GPT-OSS endpoint compatible with the selected API format. GPU server is not required on the client.

## Setup

### 1. Configure backend
```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env and set the two self-hosted model URLs/names shown below.
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```
The service starts without a configured model so `/health` and API docs remain available. Chat requests return HTTP 503 with a useful message until a provider is configured.

### 2. Run frontend (second terminal)
```bash
cd frontend
npm install
npm run dev
```
Open http://127.0.0.1:5173. Browser speech recognition support varies; Chrome/Edge are recommended. Spoken responses use the browser's built-in speech synthesis.

### API
- `GET /health` — app and default model reachability
- `POST /api/chat` — `{ "message": "Hello", "conversation_id": null, "provider": null }`
- `GET /api/conversations`
- `GET /api/conversations/{id}/messages`
- `POST /api/voice/transcribe` — optional server STT; install `faster-whisper` separately to enable it
- `GET /docs` — interactive API documentation

## Configure your two self-hosted models (no paid API keys)

Use the full OpenAI-compatible `.../v1/chat/completions` URL exactly as provided by your GPU host:

```dotenv
DEFAULT_MODEL_PROVIDER=qwen
QWEN_MODEL_URL=http://YOUR_QWEN_HOST:8100/v1/chat/completions
QWEN_MODEL_NAME=/home/expadmin/Mayank/Qwen
QWEN_API_FORMAT=openai
OLLAMA_URL=http://YOUR_OLLAMA_HOST:11435/v1/chat/completions
OLLAMA_MODEL=gpt-oss:120b
GPT_OSS_API_FORMAT=openai
AVA_API_BASE_URL=http://127.0.0.1:8000
```

Replace only the two host placeholders with your actual GPU server addresses. AVA recognizes full `/v1/chat/completions` URLs and will not append a duplicate path. The Model selector in the UI lets you choose Qwen or GPT-OSS 120B; Default routing uses Qwen. Do not add a paid provider key.

## Tests
```bash
cd backend
pytest -q
```
Frontend checks:
```bash
cd frontend
npm install
npm test
npm run build
```

## Security and limitations
- No unrestricted shell or filesystem tools are exposed.
- Browser microphone permissions are controlled by the browser. Push-to-talk is available, and Wake mode listens for “Hey AVA” while the app tab remains open and microphone permission stays granted. This is browser-level wake listening, not an OS background service.
- `SECRET_KEY` is a placeholder and is not used for user authentication in this phase.
- Do not expose the backend to a public network without authentication, rate limiting, TLS, and deployment hardening.
- Wake mode is off until you enable it in the UI.


## Specialist workspace modules
- Research: `POST /api/research/search` uses configured self-hosted SearXNG; `POST /api/research/fetch` extracts public HTML text with private-network URL blocking.
- Meetings: `POST/GET /api/meetings`, `POST /api/meetings/{id}/summarize`, speaker-label JSON update, and deletion. Current UI accepts transcripts; audio transcription/diarization is not yet integrated into the meetings workflow.
- Coding: workspace tree, code search, text-file read, model-assisted diagnosis, and bounded `pytest` execution. Configure `WORKSPACE_ROOTS` and `ALLOWED_COMMANDS`; no automatic patch application or arbitrary shell access.


## Full specialist-agent expansion

The navigation includes all seven requested workspaces:
1. **Web research** — self-hosted SearXNG search, optional Playwright-rendered pages, extracted source snippets, and model-written source-linked comparison summaries.
2. **Meeting intelligence** — browser microphone recording, local faster-whisper transcription, meeting history/search and model summaries. Optional pyannote diarization can label speaker turns after installing `backend/requirements-meeting-diarization.txt` and configuring `PYANNOTE_AUTH_TOKEN`.
3. **Email** — model-assisted draft generation, editable recipient/subject/body preview, explicit confirmation, SMTP send, and SMTP submission status. SMTP credentials are user-configured; sending is never automatic.
4. **Coding** — approved workspace inspection/search, model-assisted diagnosis, and time-limited pytest. It intentionally does not apply generated patches or expose arbitrary shell commands.
5. **Filesystem/documents** — approved-root filename search, document upload/indexing, PDF/DOCX/XLSX/CSV/text/image extraction and model Q&A with page references when available. OCR needs system Tesseract plus optional Python packages.
6. **Presentations** — model-generated editable PPTX files. PDF export is available if LibreOffice is installed.
7. **Desktop operator** — allowlisted application, URL and workspace-file launch requests. Voice-launched actions require the AVA confirmation phrase first; the desktop endpoint itself remains allowlisted and validates targets. This is not unrestricted remote desktop control.

## Setup for optional integrations
- Playwright browser: `pip install playwright && playwright install chromium`
- Local meeting transcription: `pip install faster-whisper`; then set `MEETING_RECORDING_ENABLED=true`.
- Optional speaker diarization: `pip install -r requirements-meeting-diarization.txt`; configure a Hugging Face token with access to the selected pyannote model.
- OCR: install system Tesseract, then `pip install Pillow pytesseract`.
- Email: configure SMTP_HOST, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD and EMAIL_FROM_ADDRESS in `backend/.env`.
- PDF export: install LibreOffice on the host.
- Web research: DuckDuckGo is the default provider and requires no API key. Install `duckduckgo_search` from requirements. The Research UI lets you choose DuckDuckGo or SearXNG, result count, region, SafeSearch, and date range. For SearXNG, configure `SEARXNG_BASE_URL` to your self-hosted instance.
- Desktop: configure ALLOWED_DESKTOP_APPS and WORKSPACE_ROOTS carefully. Do not expose the desktop API to untrusted networks.

All model inference uses the configured self-hosted Qwen/GPT-OSS endpoints. External services above are optional tool runtimes or user-configured infrastructure; no paid LLM API key is required.

## Voice intent routing with LangGraph + MCP

The main chat composer and microphone submit to `POST /api/voice/command`. AVA classifies the transcript using the configured self-hosted Qwen/GPT-OSS model (with a deterministic local fallback), then runs a LangGraph workflow. For task intents, it creates a pending plan and asks for confirmation; only “OK, do that” triggers the MCP tool call. “Cancel” discards the pending plan. The MCP server exposes `run_agent`, specialist tools (`research_search`, `meeting_search`, `email_create_draft`, `coding_analyze`, `document_ask`, `presentation_generate`, `desktop_propose`), plus `calculator_calculate` and `youtube_play`. Pending voice confirmations are kept in backend memory and are cleared when the backend restarts.

Install the complete backend requirements to enable the real LangGraph and MCP runtime:

```bash
cd backend
pip install -r requirements.txt
```

Configure `AVA_API_BASE_URL` to the address where FastAPI is listening (default `http://127.0.0.1:8000`). `MCP_HTTP_FALLBACK=true` allows the same local API contract to be used if the MCP package/server cannot start; set it to `false` if you want MCP failures to fail closed instead. The model URL is your self-hosted endpoint; no paid model API is used.

### Natural-language routing examples

- “Research the latest local-first agent frameworks” → Research Agent / SearXNG.
- “Find the meeting where we discussed sprint planning” → Meeting Intelligence / saved transcript search.
- “Draft an email to alex@example.com about the release” → Email Agent / draft only; sending remains an explicit approval action.
- “Debug this Python error” → Coding Agent / workspace diagnosis; no automatic file edits.
- “Explain this PDF” → asks for a document upload/ID if one is not already selected.
- “Create a 6-slide presentation about MCP” → editable PowerPoint generator.
- “Open https://example.com” → AVA summarizes the action and waits for “OK, do that”; only then does it launch the URL.
- “Calculate 25 times 6” → AVA asks for confirmation, then returns 150 using a safe arithmetic parser.
- “Open calculator” → AVA asks for confirmation, then launches an installed allowlisted calculator app.
- “Hey AVA, play a video about AI agents on YouTube” → Wake mode routes the request, asks for confirmation, then opens the first matching video if `yt-dlp` can resolve it; otherwise it opens YouTube search results. Browser autoplay policies may still require clicking Play.

The `POST /api/voice/command` response includes `intent`, `agent`, `arguments`, `result`, `needs_clarification`, `requires_confirmation`, `requires_approval`, and `orchestration`, so the frontend can show the selected agent and confirmation state. Agent integrations still require their own configured resources (SearXNG, SMTP, OCR/Tesseract, model endpoints, etc.); the graph does not bypass those setup requirements or the agents' safety checks.


## DuckDuckGo as a LangChain Custom Tool

AVA exposes the open-source DuckDuckGo scraper as `app.tools.duckduckgo_search_tool.duckduckgo_search`,
a LangChain `@tool` named `duckduckgo_search`. The Research API invokes the same tool through
its `.invoke()` interface, so UI-configured query, result limit, region, Safe Search, and time range
flow through the custom tool. The tool returns normalized JSON source records and needs no search API key.

Install with `pip install -r backend/requirements.txt`. Live search requires network access to DuckDuckGo;
the unit tests mock the scraper and do not make external requests.



##############

python -m playwright install chromium
