import type { Category } from './types';
import { intlLocale } from './i18n/index.svelte';

// Formatters follow the current UI language (see #lib/i18n)
const cache = new Map<string, Intl.NumberFormat | Intl.DateTimeFormat>();

function numberFormat(options: Intl.NumberFormatOptions): Intl.NumberFormat {
	const key = `n|${intlLocale()}|${JSON.stringify(options)}`;
	let f = cache.get(key) as Intl.NumberFormat | undefined;
	if (!f) cache.set(key, (f = new Intl.NumberFormat(intlLocale(), options)));
	return f;
}

export function dateFormat(options: Intl.DateTimeFormatOptions): Intl.DateTimeFormat {
	const key = `d|${intlLocale()}|${JSON.stringify(options)}`;
	let f = cache.get(key) as Intl.DateTimeFormat | undefined;
	if (!f) cache.set(key, (f = new Intl.DateTimeFormat(intlLocale(), options)));
	return f;
}

export const money = (value: string | number | null | undefined, currency = 'EUR') =>
	value === null || value === undefined ? '–' : numberFormat({ style: 'currency', currency }).format(Number(value));

/** Plain number in the current locale, e.g. for counts and percentages. */
export const number = (value: number, options: Intl.NumberFormatOptions = {}) => numberFormat(options).format(value);

/** Local noon, so time zones never shift the calendar day. */
const parseDay = (iso: string) => {
	const [y, m, d] = iso.slice(0, 10).split('-').map(Number);
	return new Date(y, m - 1, d, 12);
};

/** Short numeric date, e.g. 18.11.2026 or 18/11/2026. */
export const day = (iso: string) => dateFormat({ day: '2-digit', month: '2-digit', year: 'numeric' }).format(parseDay(iso));

/** Date and time of a timestamp, e.g. 18.11.2026, 14:05. */
export const dateTime = (iso: string) => dateFormat({ dateStyle: 'medium', timeStyle: 'short' }).format(new Date(iso));

/** IBAN in groups of four ("DE85 5001 0517 …"), so it reads well and wraps cleanly. */
export const iban = (value: string | null | undefined) => (value ? value.replace(/\s+/g, '').replace(/(.{4})(?=.)/g, '$1 ') : '');

export const monthLabel = (ym: string) => dateFormat({ month: 'long', year: 'numeric' }).format(parseDay(`${ym}-01`));
export const monthShortLabel = (ym: string) => dateFormat({ month: 'short' }).format(parseDay(`${ym}-01`));

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

/** Share 0–1 as a whole percentage, e.g. "85 %" (de) or "85%" (en). Empty for null. */
export const percent = (value: number | null | undefined) =>
	value === null || value === undefined ? '' : numberFormat({ style: 'percent', maximumFractionDigits: 0 }).format(value);
