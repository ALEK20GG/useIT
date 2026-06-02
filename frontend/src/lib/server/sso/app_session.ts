import { SignJWT, jwtVerify } from 'jose';
import { getSessionSecretBytes } from './config';
import type { AppSessionPayload, PortalClaimRecord } from './types';

const COOKIE_NAME = 'useit_session';
const SESSION_ISSUER = 'useit-frontend';
const SESSION_MAX_AGE_SEC = 60 * 60 * 8;

export { COOKIE_NAME };

function parsePortalClaimsJson(raw: unknown): PortalClaimRecord | undefined {
	if (typeof raw !== 'string' || !raw) return undefined;
	try {
		const v = JSON.parse(raw) as unknown;
		if (!v || typeof v !== 'object' || Array.isArray(v)) return undefined;
		return v as PortalClaimRecord;
	} catch {
		return undefined;
	}
}

export async function signAppSession(payload: AppSessionPayload): Promise<string> {
	const secret = getSessionSecretBytes();
	const portalClaimsJson = JSON.stringify(payload.portalClaims ?? {});
	return new SignJWT({
		email: payload.email,
		name: payload.name ?? '',
		googleId: payload.googleId ?? '',
		picture: payload.picture ?? '',
		session_id: payload.session_id,
		portal_claims_json: portalClaimsJson
	})
		.setProtectedHeader({ alg: 'HS256' })
		.setIssuer(SESSION_ISSUER)
		.setIssuedAt()
		.setExpirationTime(`${SESSION_MAX_AGE_SEC}s`)
		.sign(secret);
}

export async function verifyAppSession(token: string): Promise<AppSessionPayload | null> {
	try {
		const secret = getSessionSecretBytes();
		const { payload } = await jwtVerify(token, secret, {
			algorithms: ['HS256'],
			issuer: SESSION_ISSUER
		});
		const email = typeof payload.email === 'string' ? payload.email : '';
		const session_id = typeof payload.session_id === 'string' ? payload.session_id : '';
		if (!email || !session_id) return null;
		return {
			email,
			name: typeof payload.name === 'string' ? payload.name : undefined,
			googleId: typeof payload.googleId === 'string' ? payload.googleId : undefined,
			picture: typeof payload.picture === 'string' ? payload.picture : undefined,
			portalClaims: parsePortalClaimsJson(payload.portal_claims_json),
			session_id
		};
	} catch {
		return null;
	}
}
