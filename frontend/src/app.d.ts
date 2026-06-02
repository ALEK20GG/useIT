// See https://svelte.dev/docs/kit/types#app.d.ts
// for information about these interfaces
declare global {
	namespace App {
		interface Locals {
			user: {
				email: string;
				name?: string;
				googleId?: string;
				picture?: string;
				portalClaims?: Record<string, string | number | boolean | null>;
			} | null;
		}
	}
}

export {};
