import { describe, expect, it } from 'vitest';
import { summarizeSync } from './syncSummary';
import type { SyncResult } from './types';

const res = (o: Partial<SyncResult>): SyncResult => ({
	iban: 'DE00',
	account_id: 1,
	account_name: 'Konto',
	account_created: false,
	since: '2026-11-01',
	rows_total: 0,
	rows_imported: 0,
	rows_duplicate: 0,
	rows_categorized: 0,
	skipped: null,
	...o
});

describe('summarizeSync', () => {
	it('sums totals and splits accounts into groups', () => {
		const s = summarizeSync([
			res({ iban: 'A', rows_imported: 25, rows_categorized: 5, rows_duplicate: 2 }),
			res({ iban: 'B', rows_duplicate: 7 }),
			res({ iban: 'C', account_created: true }),
			res({ iban: 'D', skipped: 'unknown', since: null, rows_imported: 99 })
		]);
		expect(s.imported).toBe(25);
		expect(s.categorized).toBe(5);
		expect(s.duplicates).toBe(9);
		expect(s.accounts).toBe(3);
		expect(s.withNew.map((r) => r.iban)).toEqual(['A', 'C']);
		expect(s.withoutNew.map((r) => r.iban)).toEqual(['B']);
		expect(s.skipped.map((r) => r.iban)).toEqual(['D']);
	});

	it('returns the common since date only if all synced accounts share it', () => {
		expect(summarizeSync([res({}), res({ skipped: 'x', since: null })]).since).toBe('2026-11-01');
		expect(summarizeSync([res({}), res({ since: '2026-10-01' })]).since).toBeNull();
		expect(summarizeSync([]).since).toBeNull();
	});
});
