import { afterEach, describe, expect, it, vi } from 'vitest';
import de from './de';
import en from './en';
import { browserLocale, getLocale, intlLocale, t } from './index.svelte';

type Node = string | { [k: string]: Node };

/** All leaf paths; plural objects ({ one, other }) count as one leaf. */
function leaves(node: Node, prefix = ''): Map<string, string[]> {
	const out = new Map<string, string[]>();
	for (const [k, v] of Object.entries(node)) {
		const path = prefix + k;
		if (typeof v === 'string') out.set(path, [v]);
		else if ('other' in v && typeof v.other === 'string') out.set(path, Object.values(v) as string[]);
		else for (const [p, s] of leaves(v, `${path}.`)) out.set(p, s);
	}
	return out;
}

const placeholders = (s: string) => [...s.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort();

describe('message catalogs', () => {
	const deLeaves = leaves(de as unknown as Node);
	const enLeaves = leaves(en as unknown as Node);

	it('have the same keys in German and English', () => {
		expect([...enLeaves.keys()].sort()).toEqual([...deLeaves.keys()].sort());
	});

	it('use the same placeholders in both languages', () => {
		for (const [key, deTexts] of deLeaves) {
			const enTexts = enLeaves.get(key) ?? [];
			const union = (texts: string[]) => [...new Set(texts.flatMap(placeholders))].sort();
			expect(union(enTexts), key).toEqual(union(deTexts));
		}
	});

	it('contain no empty messages', () => {
		for (const [key, texts] of [...deLeaves, ...enLeaves]) {
			for (const s of texts) expect(s.trim(), key).not.toBe('');
		}
	});
});

describe('t', () => {
	it('defaults to German outside the browser', () => {
		expect(getLocale()).toBe('de');
		expect(intlLocale()).toBe('de-DE');
	});

	it('returns the key for unknown messages', () => {
		expect(t('does.not.exist' as never)).toBe('does.not.exist');
	});

	it('fills in params, formats numbers and keeps unknown placeholders', () => {
		expect(t('errors.http', { status: '500' })).toBe(de.errors.http.replace('{status}', '500'));
		expect(t('errors.http')).toBe(de.errors.http);
	});
});

describe('browserLocale', () => {
	afterEach(() => vi.unstubAllGlobals());

	it('picks the first supported browser language', () => {
		vi.stubGlobal('navigator', { languages: ['fr-FR', 'en-US', 'de'] });
		expect(browserLocale()).toBe('en');
	});

	it('falls back to German for unsupported languages or no navigator', () => {
		vi.stubGlobal('navigator', { languages: ['fr-FR'] });
		expect(browserLocale()).toBe('de');
		vi.stubGlobal('navigator', undefined);
		expect(browserLocale()).toBe('de');
	});
});
