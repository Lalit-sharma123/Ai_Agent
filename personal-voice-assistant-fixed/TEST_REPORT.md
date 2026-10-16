# AVA Voice Intent + LangGraph + MCP — Verification Report

## Integrated in this update
- AVA accepts the user's exact OpenAI-compatible model URL format: `QWEN_MODEL_URL=.../v1/chat/completions` with `QWEN_MODEL_NAME=/home/expadmin/Mayank/Qwen`, and `OLLAMA_URL=.../v1/chat/completions` with `OLLAMA_MODEL=gpt-oss:120b`.
- Model adapter preserves full `/v1/chat/completions` URLs and does not append the endpoint twice. Default provider is Qwen; the UI lets the user choose GPT-OSS 120B.
- All specialist task intents first produce a confirmation preview. Only “OK, do that” (including supported Hindi confirmations) invokes the selected MCP agent. “Cancel” clears the pending task. General conversational questions can be answered immediately.
- Pending voice confirmation is scoped to a conversation in backend memory and is cleared when the backend restarts.
- Added a safe arithmetic calculator (AST allowlist; no `eval`), calculator-app launching through an allowlisted installed app, and YouTube video/search launch based on the user's query. `yt-dlp` is optional at runtime; if video resolution fails, AVA opens YouTube search results. Browser autoplay may require a click.
- Added browser Wake mode: while enabled in the UI and the tab remains open with microphone permission, AVA listens for “Hey AVA”, extracts the command, routes it, then listens again after its response. This is not an OS-level background service.
- MCP server exposes `calculator_calculate` and `youtube_play` in addition to the seven specialist agent tools.

## Specialist agents
- Web research: self-hosted SearXNG search, Playwright browser rendering with HTTP fallback, and source-linked synthesis.
- Meetings: transcript persistence/search, summaries, local faster-whisper transcription, and optional pyannote speaker diarization.
- Email: model-generated drafts and explicit approval before SMTP send. Voice intent only creates a draft; it never sends automatically.
- Coding: approved workspace inspection/search, model-assisted diagnosis, and bounded pytest execution. It does not auto-apply patches.
- Filesystem/documents: approved-root search/indexing, PDF/DOCX/XLSX/CSV/text/image extraction, OCR hooks, and document Q&A.
- Presentations: editable PPTX generation and optional LibreOffice PDF conversion.
- Desktop operator: allowlisted app/URL/file actions. Voice actions execute only after the voice confirmation; direct desktop workspace actions retain their explicit approval flow.

## Tests
- Backend pytest: **32 passed, 0 failed**.
- Python compilation: passed for backend app, MCP server, and tests.
- Frontend production build: not verified because `node_modules` is absent in this environment. Run `npm install` and `npm run build` locally.
- The actual LangGraph/MCP runtime was not exercised in this environment because the packages are not installed here; they are declared in `backend/requirements.txt`. Install requirements to run the real graph and stdio MCP client/server path. Tests exercised the deterministic fallback and route contract.
- Live Qwen/GPT-OSS endpoints, SMTP, SearXNG, Playwright browser, transcription, diarization, OCR and desktop launching require the user's own environment/configuration and were not live-tested.

## Configuration and safety
- Configure the two self-hosted model endpoints in `backend/.env`; no paid model API key is required.
- Set `AVA_API_BASE_URL` to the FastAPI URL (default `http://127.0.0.1:8000`). `MCP_HTTP_FALLBACK=true` uses the same local API contracts if MCP cannot start; set it to `false` to fail closed on MCP errors.
- Email sends only after explicit approval and configured SMTP.
- Calculator only evaluates arithmetic syntax. Desktop actions are limited to allowlisted applications, validated HTTP/HTTPS URLs, and approved workspace files.
- Audio transcription requires faster-whisper. Speaker diarization is optional and requires pyannote setup. OCR for scanned files requires system Tesseract. PDF export requires LibreOffice.
