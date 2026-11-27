import type { Account } from './types.ts';

export interface AccountGroup {
	bank: string;
	accounts: Account[];
}

const collator = new Intl.Collator(undefined, { sensitivity: 'base', numeric: true });

/** Group accounts by bank; groups and the accounts within them are sorted by name. */
export function groupAccountsByBank(accounts: Account[]): AccountGroup[] {
	const groups = new Map<string, Account[]>();
	for (const a of accounts) {
		const list = groups.get(a.bank);
		if (list) list.push(a);
		else groups.set(a.bank, [a]);
	}
	return [...groups]
		.map(([bank, list]) => ({ bank, accounts: [...list].sort((x, y) => collator.compare(x.name, y.name)) }))
		.sort((x, y) => collator.compare(x.bank, y.bank));
}
