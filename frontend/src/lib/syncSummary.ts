import type { SyncResult } from './types';

export interface SyncSummary {
	/** Accounts with new transactions or newly created accounts */
	withNew: SyncResult[];
	/** Synced accounts without anything new */
	withoutNew: SyncResult[];
	/** Accounts that were not synced (reason in `skipped`) */
	skipped: SyncResult[];
	imported: number;
	categorized: number;
	duplicates: number;
	/** Number of synced (non-skipped) accounts */
	accounts: number;
	/** Start date shared by all synced accounts, otherwise null */
	since: string | null;
}

/** Totals and groups for the result of a bank sync. Skipped accounts are not counted. */
export function summarizeSync(results: SyncResult[]): SyncSummary {
	const synced = results.filter((r) => !r.skipped);
	const sinces = new Set(synced.map((r) => r.since));
	const since = sinces.size === 1 ? ([...sinces][0] ?? null) : null;
	const sum = (key: 'rows_imported' | 'rows_categorized' | 'rows_duplicate') => synced.reduce((n, r) => n + r[key], 0);
	return {
		withNew: synced.filter((r) => r.rows_imported > 0 || r.account_created),
		withoutNew: synced.filter((r) => r.rows_imported === 0 && !r.account_created),
		skipped: results.filter((r) => r.skipped),
		imported: sum('rows_imported'),
		categorized: sum('rows_categorized'),
		duplicates: sum('rows_duplicate'),
		accounts: synced.length,
		since
	};
}
