/**
 * Sanitize HTML special characters to prevent XSS.
 * Escapes <, >, &, " characters.
 */
export function sanitizeHtml(text: string): string {
	return text
		.replace(/&/g, '&amp;')
		.replace(/</g, '&lt;')
		.replace(/>/g, '&gt;')
		.replace(/"/g, '&quot;');
}
