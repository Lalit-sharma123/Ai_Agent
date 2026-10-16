import type { VoiceCommandResult } from '../types';
const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';
export async function sendVoiceCommand(message: string, conversationId?: string, provider?: string): Promise<VoiceCommandResult> {
  const response = await fetch(`${API_BASE}/api/voice/command`, { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({transcript: message, conversation_id: conversationId || null, provider: provider || null}) });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || `Request failed (${response.status})`);
  return data as VoiceCommandResult;
}
export async function getHealth() {
  const response = await fetch(`${API_BASE}/health`);
  if (!response.ok) throw new Error('Backend health check failed');
  return response.json();
}
export { API_BASE };
