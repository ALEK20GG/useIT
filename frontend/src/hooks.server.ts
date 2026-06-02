import type { Handle } from '@sveltejs/kit';
import { redirect } from '@sveltejs/kit';
import { COOKIE_NAME, verifyAppSession } from '$lib/server/sso/app_session';
import { getPortalUrl, getSsoMode } from '$lib/server/sso/config';
import { getRateLimiter } from '$lib/server/sso/rate_limiter';
import { isPublicPath } from '$lib/server/sso/paths';

function redirectToLogin(eventUrl: URL): never {
	if (getSsoMode() === 'dev') {
		const next = eventUrl.pathname + eventUrl.search;
		redirect(302, `/sso/login?next=${encodeURIComponent(next)}`);
	}
	redirect(302, getPortalUrl());
}

export const handle: Handle = async ({ event, resolve }) => {
	event.locals.user = null;

	const { url, cookies } = event;

	if (isPublicPath(url.pathname)) {
		return resolve(event);
	}

	const raw = cookies.get(COOKIE_NAME);
	const session = raw ? await verifyAppSession(raw) : null;

	if (!session) {
		return redirectToLogin(url);
	}

	const rateLimiter = getRateLimiter();
	if (!rateLimiter.isSessionValid(session.session_id)) {
		cookies.delete(COOKIE_NAME, { path: '/' });
		return redirectToLogin(url);
	}

	rateLimiter.touchSession(session.session_id);

	event.locals.user = {
		email: session.email,
		name: session.name,
		googleId: session.googleId,
		picture: session.picture,
		portalClaims: session.portalClaims
	};

	return resolve(event);
};
