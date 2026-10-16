export type ChatMessage = { id: string; role: 'user' | 'assistant'; content: string; created_at: string };
export type ChatResult = { conversation_id: string; message: ChatMessage; assistant: ChatMessage; provider: string; model: string };

export type VoiceCommandResult = {
  conversation_id: string; message: ChatMessage; assistant: ChatMessage; transcript: string; intent: string; agent: string;
  arguments: Record<string, unknown>; reply: string; result: Record<string, unknown> | null; needs_clarification: boolean;
  requires_confirmation: boolean; requires_approval: boolean; orchestration: string;
};
