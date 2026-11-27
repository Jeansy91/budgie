import { describe, expect, it } from 'vitest';
import { groupAccountsByBank } from './accounts';
import type { Account } from './types';

const acc = (id: number, name: string, bank: string): Account => ({
	id,
	name,
	bank,
	iban: null,
	currency: 'EUR',
	shared: true,
	member_ids: [],
	balance: null,
	transaction_count: 0,
	bank_connection_id: null
});

describe('groupAccountsByBank', () => {
	it('groups by bank and sorts groups and accounts by name', () => {
		const groups = groupAccountsByBank([
			acc(1, 'Tagesgeld', 'ING'),
			acc(2, 'Giro', 'DKB'),
			acc(3, 'Girokonto', 'ING'),
			acc(4, 'Depot', 'ING')
		]);
		expect(groups.map((g) => g.bank)).toEqual(['DKB', 'ING']);
		expect(groups[1].accounts.map((a) => a.name)).toEqual(['Depot', 'Girokonto', 'Tagesgeld']);
	});

	it('returns an empty list for no accounts and does not mutate the input', () => {
		expect(groupAccountsByBank([])).toEqual([]);
		const input = [acc(1, 'b', 'X'), acc(2, 'a', 'X')];
		groupAccountsByBank(input);
		expect(input.map((a) => a.id)).toEqual([1, 2]);
	});
});
