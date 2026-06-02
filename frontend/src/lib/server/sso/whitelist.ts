import fs from 'node:fs';
import path from 'node:path';
import { getWhitelistPath } from './config';

type WhitelistFile = {
	enabled?: boolean;
	emails?: string[];
};

function defaultDoc(): WhitelistFile {
	return { enabled: false, emails: [] };
}

export class WhitelistManager {
	constructor(private readonly filePath: string) {
		this.ensureFile();
	}

	private ensureFile() {
		const dir = path.dirname(this.filePath);
		if (!fs.existsSync(dir)) {
			fs.mkdirSync(dir, { recursive: true });
		}
		if (!fs.existsSync(this.filePath)) {
			fs.writeFileSync(this.filePath, JSON.stringify(defaultDoc(), null, 2), 'utf8');
		}
	}

	private load(): WhitelistFile {
		try {
			const raw = fs.readFileSync(this.filePath, 'utf8');
			return { ...defaultDoc(), ...JSON.parse(raw) };
		} catch {
			return defaultDoc();
		}
	}

	isAuthorized(email: string): boolean {
		const data = this.load();
		if (!data.enabled) return true;
		const list = (data.emails ?? []).map((e) => e.toLowerCase().trim());
		return list.includes(email.toLowerCase().trim());
	}
}

let _whitelist: WhitelistManager | null = null;

export function getWhitelistManager(): WhitelistManager {
	if (!_whitelist) {
		_whitelist = new WhitelistManager(getWhitelistPath());
	}
	return _whitelist;
}
