import type { PageServerLoad } from './$types';
import { redirect } from '@sveltejs/kit';
import { COOKIE_NAME, verifyAppSession } from '$lib/server/sso/app_session';
import { getPortalUrl } from '$lib/server/sso/config';
import { getRateLimiter } from '$lib/server/sso/rate_limiter';

export const load: PageServerLoad = async ({ cookies }) => {
	const raw = cookies.get(COOKIE_NAME);
	if (raw) {
		const session = await verifyAppSession(raw);
		if (session) {
			getRateLimiter().removeSession(session.session_id);
		}
	}
	cookies.delete(COOKIE_NAME, { path: '/' });
	redirect(302, getPortalUrl());
};
