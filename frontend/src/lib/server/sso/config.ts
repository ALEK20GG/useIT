import path from 'node:path';
import { env } from '$env/dynamic/private';

export function getSsoMode(): 'production' | 'dev' {
	const m = (env.SSO_MODE ?? 'production').toLowerCase();
	return m === 'dev' ? 'dev' : 'production';
}

export function getPortalUrl(): string {
	return env.PORTAL_URL ?? 'http://localhost:5000';
}

export function getJwtSecret(): string | undefined {
	return env.JWT_SECRET;
}

export function getJwtIssuer(): string {
	return env.JWT_ISSUER ?? 'sso-portal';
}

/** Must match the portal JWT `aud` for this app (blueprint default: blueprint-app). */
export function getJwtAudience(): string {
	return env.APP_AUDIENCE?.trim() || 'blueprint-app';
}

export function getSessionSecretBytes(): Uint8Array {
	const raw = env.SESSION_SECRET;
	if (raw && raw.length >= 16) {
		return new TextEncoder().encode(raw);
	}
	if (getSsoMode() === 'dev') {
		return new TextEncoder().encode('dev-useit-session-secret-min-16');
	}
	throw new Error('SESSION_SECRET must be set (at least 16 characters) when SSO_MODE is production');
}

export function getWhitelistPath(): string {
	if (env.WHITELIST_PATH) {
		return env.WHITELIST_PATH;
	}
	return path.join(process.cwd(), 'data', 'whitelist.json');
}

export function getDevUserEmail(): string {
	return env.DEV_USER_EMAIL ?? 'demo@example.com';
}

export function getRateLimitConfig() {
	return {
		maxSessionsPerUser: Number.parseInt(env.MAX_SESSIONS_PER_USER ?? '3', 10) || 3,
		maxSessionsGlobal: Number.parseInt(env.MAX_SESSIONS_GLOBAL ?? '100', 10) || 100,
		sessionTtlSeconds: Number.parseInt(env.SESSION_TTL_SECONDS ?? '28800', 10) || 28800
	};
}

export function useSecureCookies(url: URL): boolean {
	if (env.FORCE_SECURE_COOKIES === 'true') return true;
	if (env.FORCE_SECURE_COOKIES === 'false') return false;
	return url.protocol === 'https:';
}
