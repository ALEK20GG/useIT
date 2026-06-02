import { getRateLimitConfig } from './config';

type SessionEntry = {
	email: string;
	createdAt: number;
	lastSeen: number;
};

/**
 * In-memory session registry (same semantics as Flask blueprint).
 * Not suitable for multi-instance production without a shared store.
 */
export class RateLimiter {
	private sessions = new Map<string, SessionEntry>();
	private maxSessionsPerUser: number;
	private maxSessionsGlobal: number;
	private sessionTtlSeconds: number;

	constructor(
		maxSessionsPerUser?: number,
		maxSessionsGlobal?: number,
		sessionTtlSeconds?: number
	) {
		const c = getRateLimitConfig();
		this.maxSessionsPerUser = maxSessionsPerUser ?? c.maxSessionsPerUser;
		this.maxSessionsGlobal = maxSessionsGlobal ?? c.maxSessionsGlobal;
		this.sessionTtlSeconds = sessionTtlSeconds ?? c.sessionTtlSeconds;
	}

	private cleanup(now: number) {
		for (const [sid, data] of this.sessions) {
			if (now - data.lastSeen > this.sessionTtlSeconds) {
				this.sessions.delete(sid);
			}
		}
	}

	registerSession(sessionId: string, email: string): { ok: true } | { ok: false; reason: string } {
		const now = Date.now() / 1000;
		this.cleanup(now);
		const key = email.toLowerCase();

		if (this.sessions.size >= this.maxSessionsGlobal) {
			return {
				ok: false,
				reason: `Il servizio ha raggiunto il numero massimo di sessioni attive (${this.maxSessionsGlobal}). Riprova tra qualche minuto.`
			};
		}

		const userSessions = [...this.sessions.entries()].filter(([, d]) => d.email === key);
		if (userSessions.length >= this.maxSessionsPerUser) {
			return {
				ok: false,
				reason: `Hai raggiunto il numero massimo di sessioni simultanee (${this.maxSessionsPerUser}). Chiudi un'altra sessione e riprova.`
			};
		}

		this.sessions.set(sessionId, {
			email: key,
			createdAt: now,
			lastSeen: now
		});
		return { ok: true };
	}

	touchSession(sessionId: string) {
		const now = Date.now() / 1000;
		const row = this.sessions.get(sessionId);
		if (row) {
			row.lastSeen = now;
		}
	}

	removeSession(sessionId: string) {
		this.sessions.delete(sessionId);
	}

	isSessionValid(sessionId: string): boolean {
		const now = Date.now() / 1000;
		this.cleanup(now);
		return this.sessions.has(sessionId);
	}
}

let _singleton: RateLimiter | null = null;

export function getRateLimiter(): RateLimiter {
	if (!_singleton) {
		_singleton = new RateLimiter();
	}
	return _singleton;
}
