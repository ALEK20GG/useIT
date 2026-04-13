// Feature: pdf-semantic-search-platform, Property 8: Preview text sanitization safety
// Validates: Requirements 12.4

import { describe, it, expect } from 'vitest';
import { sanitizeHtml } from './sanitize';

describe('sanitizeHtml', () => {
	it('escapes script tags', () => {
		const result = sanitizeHtml('<script>alert("xss")</script>');
		expect(result).not.toContain('<script');
		expect(result).not.toContain('</script>');
		expect(result).toContain('&lt;script');
	});

	it('escapes iframe tags', () => {
		const result = sanitizeHtml('<iframe src="evil.com"></iframe>');
		expect(result).not.toContain('<iframe');
		expect(result).toContain('&lt;iframe');
	});

	it('handles empty string', () => {
		expect(sanitizeHtml('')).toBe('');
	});

	it('preserves normal text', () => {
		const text = 'Hello world, this is normal text.';
		expect(sanitizeHtml(text)).toBe(text);
	});

	it('escapes ampersands', () => {
		expect(sanitizeHtml('a & b')).toBe('a &amp; b');
	});

	it('escapes double quotes', () => {
		expect(sanitizeHtml('"quoted"')).toBe('&quot;quoted&quot;');
	});

	it('handles complex XSS payload', () => {
		const payload = '<img src=x onerror="alert(1)">';
		const result = sanitizeHtml(payload);
		expect(result).not.toContain('<img');
		expect(result).not.toContain('<');
	});
});
