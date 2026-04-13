import { randomBytes } from 'node:crypto';
import type { Cookies } from '@sveltejs/kit';
import { dev } from '$app/environment';
import type { PageServerLoad } from './$types';
import { redirect, isRedirect, isHttpError } from '@sveltejs/kit';
import { COOKIE_NAME, signAppSession } from '$lib/server/sso/app_session';
import {
	getDevUserEmail,
	getJwtSecret,
	getPortalUrl,
	getSsoMode,
	useSecureCookies
} from '$lib/server/sso/config';
import { validatePortalJwt } from '$lib/server/sso/portal_jwt';
import { getRateLimiter } from '$lib/server/sso/rate_limiter';
import type { PortalUserPayload } from '$lib/server/sso/types';
import { getWhitelistManager } from '$lib/server/sso/whitelist';

function safeNext(next: string | null): string {
	if (!next) return '/';
	if (!next.startsWith('/') || next.startsWith('//')) return '/';
	return next;
}

function usernameFromEmail(email: string): string {
	const local = email.split('@')[0] ?? email;
	return local.replace(/\./g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

type LoginErrorView = {
	portalUrl: string;
	error: string;
	next: string;
};

async function establishSession(
	event: { cookies: Cookies; url: URL },
	user: PortalUserPayload,
	next: string,
	portalUrl: string
): Promise<LoginErrorView | undefined> {
	const email = user.email ?? '';
	const whitelist = getWhitelistManager();
	if (!whitelist.isAuthorized(email)) {
		return {
			portalUrl,
			error:
				`Il tuo account (${email}) non è autorizzato ad accedere a questa applicazione. ` +
				"Contatta l'amministratore se ritieni sia un errore.",
			next
		};
	}

	const sessionId = randomBytes(32).toString('hex');
	const rateLimiter = getRateLimiter();
	const reg = rateLimiter.registerSession(sessionId, email);
	if (!reg.ok) {
		return { portalUrl, error: reg.reason, next };
	}

	const sealed = await signAppSession({ ...user, session_id: sessionId });
	event.cookies.set(COOKIE_NAME, sealed, {
		path: '/',
		httpOnly: true,
		sameSite: 'lax',
		secure: useSecureCookies(event.url),
		maxAge: 60 * 60 * 8
	});

	redirect(303, next);
}

export const load: PageServerLoad = async (event) => {
	const portalUrl = getPortalUrl();
	const mode = getSsoMode();
	const token = event.url.searchParams.get('token');
	const next = safeNext(event.url.searchParams.get('next'));

	if (mode === 'dev' && !token) {
		const email = event.url.searchParams.get('email') ?? getDevUserEmail();
		const user: PortalUserPayload = {
			email,
			name: usernameFromEmail(email),
			googleId: 'dev-user-id',
			picture: '',
			portalClaims: {
				note: 'SSO_MODE=dev — nessun JWT portale; claims di esempio',
				iss: 'local-dev',
				email
			}
		};
		const devErr = await establishSession(event, user, next, portalUrl);
		if (devErr) return devErr;
	}

	if (!token) {
		return {
			portalUrl,
			error: 'Token SSO mancante. Accedi tramite il portale.',
			next
		};
	}

	if (mode === 'production' && !getJwtSecret()) {
		return {
			portalUrl,
			error: 'JWT_SECRET non configurato sul client.',
			next
		};
	}

	try {
		const user = await validatePortalJwt(token!);
		const err = await establishSession(event, user, next, portalUrl);
		if (err) return err;
	} catch (e) {
		// Re-throw SvelteKit redirects and HTTP errors — they are not real errors
		if (isRedirect(e) || isHttpError(e)) throw e;
		const detail = e instanceof Error ? e.message : String(e);
		console.error('[sso/login] JWT or session error:', e);
		return {
			portalUrl,
			error: dev
				? `Token SSO non valido: ${detail}`
				: 'Token SSO non valido o scaduto. Effettua nuovamente il login.',
			next
		};
	}
};
