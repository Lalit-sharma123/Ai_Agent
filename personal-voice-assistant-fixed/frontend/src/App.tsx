import { useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { API_BASE, getHealth, sendVoiceCommand } from './services/api';
import type { ChatMessage } from './types';
import { ResearchPanel, MeetingsPanel, CodingPanel } from './features/FeaturePanels';
import { EmailPanel, DocumentsPanel, PresentationsPanel, DesktopPanel } from './features/ExtendedPanels';

declare global { interface Window { SpeechRecognition?: new () => SpeechRecognition; webkitSpeechRecognition?: new () => SpeechRecognition; } }
interface SpeechRecognition extends EventTarget { lang: string; interimResults: boolean; continuous: boolean; onresult: ((event: any) => void) | null; onerror: ((event: any) => void) | null; onend: (() => void) | null; start(): void; stop(): void; }

export default function App() {
  const [activeView, setActiveView] = useState<'assistant' | 'research' | 'meetings' | 'email' | 'coding' | 'documents' | 'presentations' | 'desktop'>('assistant');
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState('');
  const [conversationId, setConversationId] = useState<string>();
  const [provider, setProvider] = useState('default');
  const [busy, setBusy] = useState(false);
  const [listening, setListening] = useState(false);
  const [status, setStatus] = useState('Checking backend…');
  const [modelStatus, setModelStatus] = useState('Model status not checked');
  const [error, setError] = useState('');
  const [voiceEnabled, setVoiceEnabled] = useState(true);
  const [wakeMode, setWakeMode] = useState(false);
  const wakeModeRef = useRef(false);
  const wakeBusyRef = useRef(false);
  const awaitingConfirmationRef = useRef(false);
  const awaitingDetailRef = useRef(false);
  const recognition = useRef<SpeechRecognition | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => { getHealth().then((h) => { setStatus('Backend connected'); setModelStatus(h.model?.reachable ? 'Model reachable' : h.model?.error || 'Model not configured'); }).catch(() => setStatus('Backend offline')); }, []);
  useEffect(() => { endRef.current?.scrollIntoView({behavior:'smooth'}); }, [messages, busy]);

  function speak(text: string): Promise<void> {
    if (!voiceEnabled || !('speechSynthesis' in window)) return Promise.resolve();
    window.speechSynthesis.cancel();
    return new Promise((resolve) => {
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.lang = 'en-IN';
      utterance.onend = () => resolve();
      utterance.onerror = () => resolve();
      window.speechSynthesis.speak(utterance);
    });
  }
  function startWakeListener() {
    if (!wakeModeRef.current || wakeBusyRef.current) return;
    const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!Recognition) { setError('Wake mode requires Chrome/Edge speech recognition.'); setWakeMode(false); wakeModeRef.current = false; return; }
    const instance = new Recognition();
    instance.lang = 'en-IN'; instance.interimResults = false; instance.continuous = true;
    instance.onresult = (event) => {
      for (let i = event.resultIndex || 0; i < event.results.length; i++) {
        if (!event.results[i].isFinal) continue;
        const heard = String(event.results[i][0]?.transcript || '').trim();
        const match = heard.match(/^(?:hey\s+)?ava\b[\s,.:;-]*(.*)$/i);
        let command = '';
        if (match) command = match[1].trim();
        else if (awaitingDetailRef.current) command = heard;
        else if (awaitingConfirmationRef.current && /^(?:ok(?:ay)?|yes|yeah|do it|do that|confirm|proceed|go ahead|cancel|stop|haan|han|kar do|theek hai|नहीं|हाँ)(?:[\s,.!?].*)?$/i.test(heard)) command = heard;
        else continue;
        if (!command) { void speak("Yes, I'm listening. What would you like me to do?"); continue; }
        wakeBusyRef.current = true;
        try { instance.stop(); } catch { /* browser may already have stopped */ }
        setListening(false);
        void sendMessage(command).finally(() => {
          wakeBusyRef.current = false;
          if (wakeModeRef.current) startWakeListener();
        });
        return;
      }
    };
    instance.onerror = (event) => { if (event.error !== 'no-speech' && event.error !== 'aborted') setError(`Wake mode microphone error: ${event.error || 'unknown error'}`); };
    instance.onend = () => {
      setListening(false);
      if (wakeModeRef.current && !wakeBusyRef.current) window.setTimeout(() => startWakeListener(), 700);
    };
    recognition.current = instance;
    setListening(true);
    try { instance.start(); } catch { setListening(false); setError('Could not start wake mode. Check microphone permissions.'); }
  }
  function toggleWakeMode() {
    if (wakeModeRef.current) {
      wakeModeRef.current = false; setWakeMode(false); setListening(false);
      try { recognition.current?.stop(); } catch { /* already stopped */ }
      return;
    }
    wakeModeRef.current = true; setWakeMode(true); setError(''); startWakeListener();
  }
  function toggleListening() {
    if (listening) { recognition.current?.stop(); setListening(false); return; }
    const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!Recognition) { setError('Speech recognition is not available in this browser. Use Chrome/Edge or type your message.'); return; }
    const instance = new Recognition();
    instance.lang = 'en-IN'; instance.interimResults = true; instance.continuous = false;
    instance.onresult = (event) => {
      let transcript = '';
      let finalTranscript = '';
      for (let i = 0; i < event.results.length; i++) {
        transcript += event.results[i][0].transcript;
        if (event.results[i].isFinal) finalTranscript += event.results[i][0].transcript;
      }
      setDraft(transcript.trim());
      // A completed spoken command is sent straight to the intent router; no second click needed.
      if (finalTranscript.trim()) {
        setListening(false);
        instance.stop();
        void sendMessage(finalTranscript.trim());
      }
    };
    instance.onerror = (event) => { setError(`Microphone error: ${event.error || 'unknown error'}`); setListening(false); };
    instance.onend = () => setListening(false);
    recognition.current = instance; setError(''); setListening(true);
    try { instance.start(); } catch { setListening(false); setError('Could not start microphone. Check browser permissions.'); }
  }
  async function sendMessage(rawText: string) {
    const text = rawText.trim();
    if (!text || busy) return;
    setError(''); setBusy(true);
    const optimistic: ChatMessage = {id: crypto.randomUUID(), role:'user', content:text, created_at:new Date().toISOString()};
    setMessages((old) => [...old, optimistic]); setDraft('');
    try {
      const result = await sendVoiceCommand(text, conversationId, provider === 'default' ? undefined : provider);
      setConversationId(result.conversation_id);
      setMessages((old) => [...old, result.assistant]);
      setModelStatus(`Routed to ${result.agent} · ${result.orchestration}${result.requires_confirmation ? ' · awaiting your confirmation' : ''}${result.requires_approval ? ' · approval required' : ''}`);
      awaitingConfirmationRef.current = result.requires_confirmation;
      awaitingDetailRef.current = result.needs_clarification;
      await speak(result.assistant.content);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Request failed';
      setError(message);
      setMessages((old) => old.filter((m) => m.id !== optimistic.id));
      setDraft(text);
    } finally { setBusy(false); }
  }
  async function submit(event?: FormEvent) {
    event?.preventDefault();
    await sendMessage(draft);
  }
  function newConversation() { window.speechSynthesis?.cancel(); setMessages([]); setConversationId(undefined); setError(''); setDraft(''); awaitingConfirmationRef.current = false; awaitingDetailRef.current = false; }
  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand"><div className="brand-mark">✦</div><div><strong>AVA</strong><small>PERSONAL ASSISTANT</small></div></div>
      <button className="new-chat" onClick={newConversation}>＋ New conversation</button>
      <div className="side-label">WORKSPACE</div>
      <button className={`side-item ${activeView === 'assistant' ? 'active' : ''}`} onClick={() => setActiveView('assistant')}>◉ <span>Voice assistant</span></button>
      <button className={`side-item ${activeView === 'research' ? 'active' : ''}`} onClick={() => setActiveView('research')}>⌕ <span>Research agent</span></button>
      <button className={`side-item ${activeView === 'meetings' ? 'active' : ''}`} onClick={() => setActiveView('meetings')}>▤ <span>Meetings</span></button>
      <button className={`side-item ${activeView === 'email' ? 'active' : ''}`} onClick={() => setActiveView('email')}>✉ <span>Email agent</span></button>
      <button className={`side-item ${activeView === 'coding' ? 'active' : ''}`} onClick={() => setActiveView('coding')}>⌘ <span>Coding agent</span></button>
      <button className={`side-item ${activeView === 'documents' ? 'active' : ''}`} onClick={() => setActiveView('documents')}>▤ <span>Documents</span></button>
      <button className={`side-item ${activeView === 'presentations' ? 'active' : ''}`} onClick={() => setActiveView('presentations')}>▧ <span>Presentations</span></button>
      <button className={`side-item ${activeView === 'desktop' ? 'active' : ''}`} onClick={() => setActiveView('desktop')}>▣ <span>Desktop operator</span></button>
      <div className="side-bottom"><span className={status === 'Backend connected' ? 'dot good' : 'dot bad'} />{status}<small>{modelStatus}</small></div>
    </aside>
    <main className="main">
      <header className="topbar"><div><div className="eyebrow">YOUR LOCAL-FIRST AI</div><h1>{activeView === 'assistant' ? 'How can I help today?' : activeView === 'research' ? 'Research workspace' : activeView === 'meetings' ? 'Meeting intelligence' : activeView === 'email' ? 'Email assistant' : activeView === 'coding' ? 'Coding workspace' : activeView === 'documents' ? 'Documents & files' : activeView === 'presentations' ? 'Presentation studio' : 'Desktop operator'}</h1></div><div className="top-actions"><label className="model-select">Model <select value={provider} onChange={(e) => setProvider(e.target.value)}><option value="default">Default routing</option><option value="qwen">Qwen</option><option value="gpt-oss">GPT-OSS 120B</option></select></label><button className={`voice-toggle ${voiceEnabled ? 'selected' : ''}`} onClick={() => setVoiceEnabled(!voiceEnabled)} title="Toggle spoken responses">◖ {voiceEnabled ? 'Voice on' : 'Voice off'}</button><button className={`voice-toggle ${wakeMode ? 'selected' : ''}`} onClick={toggleWakeMode} title="Listen for Hey AVA while this tab stays open">{wakeMode ? '● Wake mode on' : '○ Wake mode'}</button></div></header>
      {activeView === 'research' && <ResearchPanel />}
      {activeView === 'meetings' && <MeetingsPanel />}
      {activeView === 'coding' && <CodingPanel />}
      {activeView === 'email' && <EmailPanel />}
      {activeView === 'documents' && <DocumentsPanel />}
      {activeView === 'presentations' && <PresentationsPanel />}
      {activeView === 'desktop' && <DesktopPanel />}
      {activeView === 'assistant' && <>
      <section className="chat-area">
        {messages.length === 0 ? <div className="welcome"><div className="orb"><span>✦</span></div><h2>A capable assistant, on your terms.</h2><p>Talk naturally or type a message. Your model runs on your configured hosted infrastructure.</p><div className="suggestions"><button onClick={() => setDraft('Help me plan my day and ask any questions you need.')}>✧ <span>Plan my day</span></button><button onClick={() => setDraft('Explain how this personal voice assistant is structured.')}>⌘ <span>Explain the project</span></button><button onClick={() => setDraft('Help me troubleshoot a Python backend error.')}>⌁ <span>Debug an issue</span></button></div></div> : <div className="messages">{messages.map((m) => <article className={`message ${m.role}`} key={m.id}><div className="avatar">{m.role === 'user' ? 'Y' : '✦'}</div><div className="message-body"><div className="message-role">{m.role === 'user' ? 'YOU' : 'AVA'}</div><p>{m.content}</p></div>{m.role === 'assistant' && <button className="speak-btn" onClick={() => speak(m.content)} title="Read aloud">▶</button>}</article>)}{busy && <div className="thinking"><span/><span/><span/> Thinking with your model…</div>}<div ref={endRef}/></div>}
      </section>
      {error && <div className="error-banner" role="alert">{error}<button onClick={() => setError('')}>Dismiss</button></div>}
      <form className="composer" onSubmit={submit}><button type="button" className={`mic-btn ${listening ? 'recording' : ''}`} onClick={toggleListening} title="Push to talk" aria-label="Push to talk">{listening ? '■' : '🎙'}</button><textarea value={draft} onChange={(e) => setDraft(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); void submit(); } }} placeholder={listening ? 'Listening… speak now' : 'Message AVA…'} rows={1} aria-label="Message" /><button className="send-btn" type="submit" disabled={busy || !draft.trim()}>{busy ? '…' : '↑'}</button></form>
      <footer>Say ‘Hey AVA’ in Wake mode, or use the microphone. AVA previews tasks first; say ‘OK, do that’ to confirm or ‘cancel’ to stop. Wake mode needs this browser tab open.<span>API: {API_BASE}</span></footer>
      </>}
    </main>
  </div>;
}
