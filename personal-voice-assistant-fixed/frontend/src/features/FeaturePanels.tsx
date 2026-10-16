import { useEffect, useRef, useState } from 'react';
import type { FormEvent, ReactNode } from 'react';
import { API_BASE } from '../services/api';
import { LiveMeetingsPanel } from './LiveMeetingsPanel';

type ResearchResult = { title: string; url: string; snippet: string; retrieved_at: string };
type Meeting = { id: string; title: string; transcript: string; summary: string; action_items: string[]; created_at: string };

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || `Request failed (${response.status})`);
  return data as T;
}

function Panel({ title, subtitle, children }: {title: string; subtitle: string; children: ReactNode}) {
  return <section className="feature-panel"><div className="feature-heading"><div className="eyebrow">AVA WORKSPACE</div><h2>{title}</h2><p>{subtitle}</p></div>{children}</section>;
}

export function ResearchPanel() {
  const [query, setQuery] = useState('');
  const [provider, setProvider] = useState<'duckduckgo'|'searxng'>('duckduckgo');
  const [limit, setLimit] = useState(5);
  const [region, setRegion] = useState('wt-wt');
  const [safesearch, setSafesearch] = useState<'on'|'moderate'|'off'>('moderate');
  const [timelimit, setTimelimit] = useState('');
  const [results, setResults] = useState<ResearchResult[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [pageUrl, setPageUrl] = useState('');
  const [pageText, setPageText] = useState('');
  const [summary, setSummary] = useState('');
  const [sourceTexts, setSourceTexts] = useState<Record<string,string>>({});
  async function search(e: FormEvent) {
    e.preventDefault(); setBusy(true); setError(''); setPageText(''); setSummary('');
    try { const data = await api<{results: ResearchResult[]}>('/api/research/search', {method:'POST', body:JSON.stringify({query, provider, limit, region, safesearch, timelimit: timelimit || null})}); setResults(data.results); }
    catch (err) { setError(err instanceof Error ? err.message : 'Research search failed'); }
    finally { setBusy(false); }
  }
  async function fetchPage(url: string) {
    setPageUrl(url); setPageText('Loading page…'); setError('');
    try { const data = await api<{title:string;text:string}>('/api/research/browse', {method:'POST', body:JSON.stringify({url})}); setPageText(`${data.title}\n\n${data.text}`); setSourceTexts(old=>({...old,[url]:data.text})); }
    catch (err) { setPageText(''); setError(err instanceof Error ? err.message : 'Could not retrieve page'); }
  }
  async function synthesize() {
    setBusy(true); setError(''); setSummary('');
    try { const data = await api<{summary:string}>('/api/research/synthesize', {method:'POST',body:JSON.stringify({query,sources:results.map(r=>({title:r.title,url:r.url,snippet:sourceTexts[r.url] || r.snippet}))})}); setSummary(data.summary); }
    catch(err) { setError(err instanceof Error ? err.message : 'Could not synthesize research'); }
    finally { setBusy(false); }
  }
  return <Panel title="Research agent" subtitle="Configure web search, inspect results, extract public webpages, and generate cited research briefs.">
    <form className="feature-form vertical" onSubmit={search}>
      <input value={query} onChange={e=>setQuery(e.target.value)} placeholder="Research a topic…" required minLength={2}/>
      <div className="settings-grid">
        <label className="field-label">Search provider<select value={provider} onChange={e=>setProvider(e.target.value as 'duckduckgo'|'searxng')}><option value="duckduckgo">DuckDuckGo (no API key)</option><option value="searxng">Self-hosted SearXNG</option></select></label>
        <label className="field-label">Number of results: {limit}<input type="range" min="1" max="20" value={limit} onChange={e=>setLimit(Number(e.target.value))}/></label>
        <label className="field-label">Region<select value={region} onChange={e=>setRegion(e.target.value)}><option value="wt-wt">Worldwide</option><option value="in-en">India (English)</option><option value="us-en">United States</option><option value="uk-en">United Kingdom</option><option value="de-de">Germany</option><option value="fr-fr">France</option></select></label>
        <label className="field-label">Safe search<select value={safesearch} onChange={e=>setSafesearch(e.target.value as 'on'|'moderate'|'off')}><option value="moderate">Moderate</option><option value="on">Strict</option><option value="off">Off</option></select></label>
        <label className="field-label">Date range<select value={timelimit} onChange={e=>setTimelimit(e.target.value)}><option value="">Any time</option><option value="d">Past day</option><option value="w">Past week</option><option value="m">Past month</option><option value="y">Past year</option></select></label>
      </div>
      <button disabled={busy}>{busy ? 'Searching…' : `Search ${provider === 'duckduckgo' ? 'DuckDuckGo' : 'SearXNG'}`}</button>
    </form>
    {results.length>0 && <button className="small-action" disabled={busy} onClick={()=>void synthesize()}>Compare sources & write cited summary</button>}
    {error && <div className="error-banner">{error}</div>}
    {summary && <article className="result-card"><div className="result-title">Cited research summary</div><pre className="feature-pre">{summary}</pre></article>}
    <div className="feature-results">{results.map((r,i)=><article className="result-card" key={`${r.url}-${i}`}><div className="result-title">{r.title}</div><a href={r.url} target="_blank" rel="noreferrer">{r.url}</a><p>{r.snippet}</p><button className="small-action" onClick={()=>void fetchPage(r.url)}>Browse & extract</button></article>)}</div>
    {pageText && <div className="result-card"><strong>{pageUrl}</strong><pre className="feature-pre">{pageText}</pre></div>}
    {!results.length && !error && <p className="empty-note">DuckDuckGo works without an API key. To use SearXNG, configure SEARXNG_BASE_URL in backend/.env.</p>}
  </Panel>;
}

export function MeetingsPanel() { return <LiveMeetingsPanel />; }

export function CodingPanel() {
  const [path, setPath] = useState('.');
  const [query, setQuery] = useState('');
  const [issue, setIssue] = useState('');
  const [results, setResults] = useState<any[]>([]);
  const [analysis, setAnalysis] = useState('');
  const [testResult, setTestResult] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  async function doSearch(e: FormEvent) {
    e.preventDefault(); setBusy(true); setError('');
    try { const data=await api<{matches:any[]}>('/api/coding/search',{method:'POST',body:JSON.stringify({query,path})}); setResults(data.matches); }
    catch(err) { setError(err instanceof Error ? err.message : 'Search failed'); }
    finally { setBusy(false); }
  }
  async function analyze(e: FormEvent) {
    e.preventDefault(); setBusy(true); setError(''); setAnalysis('');
    try { const data=await api<{analysis:string}>('/api/coding/analyze',{method:'POST',body:JSON.stringify({issue,path})}); setAnalysis(data.analysis); }
    catch(err) { setError(err instanceof Error ? err.message : 'Analysis failed'); }
    finally { setBusy(false); }
  }
  async function runTests() {
    setBusy(true); setError(''); setTestResult('');
    try { const data=await api<{returncode:number;passed:boolean;stdout:string;stderr:string}>('/api/coding/run-tests',{method:'POST',body:JSON.stringify({path})}); setTestResult(`Passed: ${data.passed}\nExit code: ${data.returncode}\n\n${data.stdout}\n${data.stderr}`); }
    catch(err) { setError(err instanceof Error ? err.message : 'Tests failed'); }
    finally { setBusy(false); }
  }
  return <Panel title="Coding agent" subtitle="Inspect approved workspace files, search code, ask your hosted model to diagnose issues, and run pytest with a bounded timeout.">
    <label className="field-label">Workspace path (must be inside WORKSPACE_ROOTS)<input value={path} onChange={e=>setPath(e.target.value)}/></label>
    <form className="feature-form" onSubmit={doSearch}><input value={query} onChange={e=>setQuery(e.target.value)} placeholder="Search code for a function or error…" required/><button disabled={busy}>{busy?'Searching…':'Search code'}</button></form>
    <form className="feature-form vertical" onSubmit={analyze}><textarea value={issue} onChange={e=>setIssue(e.target.value)} placeholder="Describe the error or coding task…" rows={3} required/><button disabled={busy || issue.trim().length<3}>{busy?'Analyzing…':'Analyze issue with AI'}</button></form>
    <div className="button-row"><button className="small-action" disabled={busy} onClick={()=>void runTests()}>Run pytest</button></div>
    {error && <div className="error-banner">{error}</div>}
    {analysis && <article className="result-card"><div className="result-title">AI diagnosis</div><pre className="feature-pre">{analysis}</pre><p className="empty-note">This action analyzes and suggests changes; it does not automatically edit project files.</p></article>}
    {testResult && <article className="result-card"><div className="result-title">Actual test output</div><pre className="feature-pre">{testResult}</pre></article>}
    {results.map((r,i)=><article className="result-card" key={`${r.path}-${r.line}-${i}`}><strong>{r.path}:{r.line}</strong><pre className="feature-pre">{r.text}</pre></article>)}
    <p className="empty-note">For safety, this agent does not provide arbitrary shell access or automatically apply model-generated patches. Configure WORKSPACE_ROOTS and ALLOWED_COMMANDS in backend/.env.</p>
  </Panel>;
}
