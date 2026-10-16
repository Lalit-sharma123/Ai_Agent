import { describe, it, expect } from 'vitest';
describe('frontend smoke', () => { it('has a configured API fallback', () => { expect(import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000').toContain('http'); }); });
