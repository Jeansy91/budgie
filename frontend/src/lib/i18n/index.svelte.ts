/**
 * Minimal i18n for Budgie: German (default) and English.
 *
 * - `t('section.key', { name: 'x' })` looks up a message and fills in `{name}`.
 *   Messages may be plural objects (`{ one, other }`); the form is chosen from
 *   the `count` parameter.
 * - The current locale is reactive state, so markup that calls `t()` updates
 *   when the language changes.
 * - Preference order: the user's saved choice, then (before login) the choice
 *   remembered in this browser, then the browser language, then German.
 */
import de, { type Messages, type Plural } from './de';
import en from './en';

export type Locale = 'de' | 'en';

export const LOCALES: { code: Locale; label: string }[] = [
	{ code: 'de', label: 'Deutsch' },
	{ code: 'en', label: 'English' }
];

const catalogs: Record<Locale, Messages> = { de, en };
const STORAGE_KEY = 'budgie.locale';

type Leaves<T, P extends string = ''> = {
	[K in keyof T & string]: T[K] extends string | Plural ? `${P}${K}` : Leaves<T[K], `${P}${K}.`>;
}[keyof T & string];

export type MessageKey = Leaves<Messages>;
export type Params = Record<string, string | number>;

const isLocale = (v: unknown): v is Locale => v === 'de' || v === 'en';

function readStored(): Locale | null {
	try {
		const v = localStorage.getItem(STORAGE_KEY);
		return isLocale(v) ? v : null;
	} catch {
		return null;
	}
}

function writeStored(value: Locale | null) {
	try {
		if (value) localStorage.setItem(STORAGE_KEY, value);
		else localStorage.removeItem(STORAGE_KEY);
	} catch {
		// Storage unavailable (private mode): the choice simply isn't remembered
	}
}

/** First supported language from the browser settings, German otherwise. */
export function browserLocale(): Locale {
	const langs = typeof navigator === 'undefined' ? [] : (navigator.languages ?? [navigator.language]);
	for (const lang of langs) {
		const base = lang.toLowerCase().split('-')[0];
		if (isLocale(base)) return base;
	}
	return 'de';
}

let current = $state<Locale>(typeof window === 'undefined' ? 'de' : (readStored() ?? browserLocale()));

export function getLocale(): Locale {
	return current;
}

function apply(locale: Locale) {
	current = locale;
	if (typeof document !== 'undefined') document.documentElement.lang = locale;
}

/**
 * Applies the signed-in user's preference (`null` = follow the browser) and
 * remembers it for the login page.
 */
export function applyUserLocale(preference: Locale | null | undefined) {
	writeStored(preference ?? null);
	apply(preference ?? browserLocale());
}

/** Language switch before login: remembered in this browser only. */
export function setLocale(locale: Locale) {
	writeStored(locale);
	apply(locale);
}

/**
 * BCP 47 tag for number, currency and date formatting. English uses the
 * browser's English region if it has one (en-US, en-GB …), otherwise en-GB,
 * which matches the euro amounts and day-first dates of a German bank account.
 */
export function intlLocale(): string {
	if (current === 'de') return 'de-DE';
	const langs = typeof navigator === 'undefined' ? [] : (navigator.languages ?? [navigator.language]);
	return langs.find((l) => /^en-[a-z]{2}$/i.test(l)) ?? 'en-GB';
}

function lookup(catalog: Messages, key: string): string | Plural | undefined {
	let node: unknown = catalog;
	for (const part of key.split('.')) {
		if (node === null || typeof node !== 'object') return undefined;
		node = (node as Record<string, unknown>)[part];
	}
	return typeof node === 'string' || (node && typeof node === 'object' && 'other' in node) ? (node as string | Plural) : undefined;
}

const pluralRules = new Map<string, Intl.PluralRules>();
const numberFormats = new Map<string, Intl.NumberFormat>();

function cached<T>(map: Map<string, T>, key: string, make: () => T): T {
	let v = map.get(key);
	if (!v) map.set(key, (v = make()));
	return v;
}

/** Translates `key` into the current language. */
export function t(key: MessageKey, params: Params = {}): string {
	const locale = current;
	let msg = lookup(catalogs[locale], key) ?? lookup(de, key);
	if (msg === undefined) return key;
	if (typeof msg !== 'string') {
		const count = Number(params.count ?? 0);
		const form =
			count === 0 && msg.zero !== undefined ? 'zero' : cached(pluralRules, locale, () => new Intl.PluralRules(locale)).select(count);
		msg = (form === 'zero' ? msg.zero : form === 'one' ? msg.one : msg.other) ?? msg.other;
	}
	const nf = cached(numberFormats, intlLocale(), () => new Intl.NumberFormat(intlLocale()));
	return msg.replace(/\{(\w+)\}/g, (match, name: string) => {
		const v = params[name];
		if (v === undefined) return match;
		return typeof v === 'number' ? nf.format(v) : v;
	});
}
