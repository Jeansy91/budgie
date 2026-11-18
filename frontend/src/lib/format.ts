import type { Category } from './types';

const eur = new Intl.NumberFormat('de-DE', { style: 'currency', currency: 'EUR' });

export const money = (value: string | number | null | undefined) =>
	value === null || value === undefined ? '–' : eur.format(Number(value));

export const day = (iso: string) => {
	const [y, m, d] = iso.split('-');
	return `${d}.${m}.${y}`;
};

/** IBAN in groups of four ("DE85 5001 0517 …"), so it reads well and wraps cleanly. */
export const iban = (value: string | null | undefined) => (value ? value.replace(/\s+/g, '').replace(/(.{4})(?=.)/g, '$1 ') : '');

const monthFmt = new Intl.DateTimeFormat('de-DE', { month: 'long', year: 'numeric' });
const monthShort = new Intl.DateTimeFormat('de-DE', { month: 'short' });

export const monthLabel = (ym: string) => monthFmt.format(new Date(`${ym}-01T12:00:00`));
export const monthShortLabel = (ym: string) => monthShort.format(new Date(`${ym}-01T12:00:00`));

export const currentMonth = () => new Date().toISOString().slice(0, 7);

export function shiftMonth(ym: string, delta: number): string {
	const [y, m] = ym.split('-').map(Number);
	const d = new Date(Date.UTC(y, m - 1 + delta, 1));
	return d.toISOString().slice(0, 7);
}

/** Category names for select lists: "Main › Sub". */
export function categoryLabels(tree: Category[]): Map<number, string> {
	const map = new Map<number, string>();
	for (const main of tree) {
		map.set(main.id, main.name);
		for (const sub of main.children) map.set(sub.id, `${main.name} › ${sub.name}`);
	}
	return map;
}
