/**
 * Sanitize HTML special characters to prevent XSS.
 * Escapes <, >, &, " and ' characters.
 *
 * Requirement 18.4: sanitize user input to prevent XSS and injection attacks.
 */
export function sanitizeHtml(text: string): string {
	return text
		.replace(/&/g, '&amp;')
		.replace(/</g, '&lt;')
		.replace(/>/g, '&gt;')
		.replace(/"/g, '&quot;')
		.replace(/'/g, '&#x27;');
}

/**
 * Sanitize a search query string.
 * - Strips leading/trailing whitespace
 * - Removes null bytes
 * - Truncates to maxLength characters
 *
 * Requirement 18.1 + 18.4.
 */
export function sanitizeSearchQuery(query: string, maxLength = 500): string {
	if (typeof query !== 'string') return '';
	// Remove null bytes
	let sanitized = query.replace(/\x00/g, '');
	// Strip whitespace
	sanitized = sanitized.trim();
	// Truncate
	if (sanitized.length > maxLength) {
		sanitized = sanitized.slice(0, maxLength);
	}
	return sanitized;
}

/**
 * Sanitize a filename to prevent path traversal and injection.
 * - Removes path separators and traversal sequences
 * - Replaces unsafe characters with underscores
 * - Limits length to 255 characters
 *
 * Requirement 18.4.
 */
export function sanitizeFilename(filename: string): string {
	if (typeof filename !== 'string') return '';
	// Remove null bytes
	let sanitized = filename.replace(/\x00|%00/g, '');
	// Remove path traversal sequences
	sanitized = sanitized.replace(/\.\.[/\\]/g, '').replace(/[/\\]/g, '_');
	// Replace unsafe characters (keep alphanumeric, spaces, hyphens, underscores, dots, parens)
	sanitized = sanitized.replace(/[^\w\s\-_.()\[\]]/g, '_');
	// Limit length
	if (sanitized.length > 255) {
		const lastDot = sanitized.lastIndexOf('.');
		if (lastDot > 0 && lastDot > sanitized.length - 16) {
			const ext = sanitized.slice(lastDot);
			sanitized = sanitized.slice(0, 240) + ext;
		} else {
			sanitized = sanitized.slice(0, 255);
		}
	}
	return sanitized.replace(/^[._]+/, '');
}

/**
 * Validate that a string does not contain SQL injection patterns.
 * Returns true if the input appears safe, false if suspicious.
 *
 * Requirement 18.4.
 */
export function isSafeInput(text: string): boolean {
	if (typeof text !== 'string') return false;
	const sqlPattern =
		/(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|UNION|SCRIPT)\b|--|;|\bOR\b\s+\d+\s*=\s*\d+)/i;
	const pathTraversalPattern = /\.\.[/\\]|%2e%2e%2f/i;
	return !sqlPattern.test(text) && !pathTraversalPattern.test(text);
}

/**
 * Validate a file before upload.
 * Returns an error message string if invalid, or null if valid.
 *
 * Requirement 18.1 + 18.2.
 */
export function validateFileForUpload(
	file: File,
	options: {
		allowedTypes?: string[];
		maxSizeBytes?: number;
	} = {}
): string | null {
	const {
		allowedTypes = [
			'application/pdf',
			'text/plain',
			'application/msword',
			'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
		],
		maxSizeBytes = 50 * 1024 * 1024 // 50 MB
	} = options;

	if (!file) return 'No file provided';

	// Check file size
	if (file.size === 0) return 'File is empty';
	if (file.size > maxSizeBytes) {
		const maxMB = (maxSizeBytes / 1024 / 1024).toFixed(0);
		const fileMB = (file.size / 1024 / 1024).toFixed(1);
		return `File size (${fileMB} MB) exceeds the maximum allowed size (${maxMB} MB)`;
	}

	// Check MIME type
	if (file.type && !allowedTypes.includes(file.type)) {
		return `File type '${file.type}' is not allowed`;
	}

	// Check filename
	const sanitized = sanitizeFilename(file.name);
	if (!sanitized) return 'Invalid filename';

	return null;
}

/**
 * Validate an image file before upload (for device recognition).
 * Returns an error message string if invalid, or null if valid.
 *
 * Requirement 18.1 + 18.2.
 */
export function validateImageForUpload(file: File): string | null {
	return validateFileForUpload(file, {
		allowedTypes: ['image/jpeg', 'image/png', 'image/webp', 'image/gif'],
		maxSizeBytes: 10 * 1024 * 1024 // 10 MB
	});
}
