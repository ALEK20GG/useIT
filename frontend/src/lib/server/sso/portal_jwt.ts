import { jwtVerify, type JWTPayload } from 'jose';
import { getJwtAudience, getJwtIssuer, getJwtSecret } from './config';
import type { PortalClaimRecord, PortalUserPayload } from './types';

function pickString(payload: JWTPayload, key: string): string | undefined {
	const v = payload[key];
	return typeof v === 'string' ? v : undefined;
}

function serializePortalClaims(payload: JWTPayload): PortalClaimRecord {
	const out: PortalClaimRecord = {};
	for (const [key, value] of Object.entries(payload)) {
		if (value === undefined) continue;
		if (value === null) {
			out[key] = null;
			continue;
		}
		if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
			out[key] = value;
			continue;
		}
		if (value instanceof Date) {
			out[key] = Math.floor(value.getTime() / 1000);
			continue;
		}
		if (Array.isArray(value)) {
			out[key] = value.map((x) => String(x)).join(',');
			continue;
		}
	}
	return out;
}

/**
 * Validates the JWT issued by the SSO portal (same rules as Flask SSOMiddleware.validate_jwt).
 * Returns user fields plus a flat snapshot of JWT claims for UI / auditing.
 */
export async function validatePortalJwt(token: string): Promise<PortalUserPayload> {
	const secret = getJwtSecret();
	if (!secret) {
		throw new Error('JWT_SECRET is not configured');
	}
	const key = new TextEncoder().encode(secret);
	const issuer = getJwtIssuer();
	const audience = getJwtAudience();

	const { payload } = await jwtVerify(token, key, {
		algorithms: ['HS256'],
		issuer,
		audience
	});

	const email = pickString(payload, 'email');
	if (!email) {
		throw new Error('JWT missing email claim');
	}

	const portalClaims = serializePortalClaims(payload);

	return {
		email,
		name: pickString(payload, 'name'),
		googleId: pickString(payload, 'googleId'),
		picture: pickString(payload, 'picture'),
		portalClaims
	};
}
