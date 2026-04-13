/** Serializable snapshot of portal JWT claims (after signature verification). */
export type PortalClaimRecord = Record<string, string | number | boolean | null>;

export type PortalUserPayload = {
	email: string;
	name?: string;
	googleId?: string;
	picture?: string;
	/** All primitive claims from the portal JWT (iss, aud, iat, exp, sub, custom, …). */
	portalClaims?: PortalClaimRecord;
};

export type AppSessionPayload = PortalUserPayload & {
	session_id: string;
};
