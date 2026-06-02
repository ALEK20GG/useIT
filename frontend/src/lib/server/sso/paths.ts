/**
 * Paths that must not require an authenticated app session.
 * Keep this tight: everything else redirects to the SSO portal.
 */
export function isPublicPath(pathname: string): boolean {
	if (pathname.startsWith('/_app/')) return true;
	if (pathname.startsWith('/@')) return true;
	if (pathname === '/favicon.ico' || pathname === '/robots.txt') return true;
	if (pathname === '/sso/login' || pathname.startsWith('/sso/login/')) return true;
	if (pathname === '/logout' || pathname.startsWith('/logout/')) return true;
	return false;
}
