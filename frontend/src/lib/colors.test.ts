import { describe, expect, it } from 'vitest';
import { NONE_COLOR, PALETTE, avatarColor, colorFor, initials } from './colors';

describe('colorFor', () => {
	it('returns the neutral color for missing or negative indexes', () => {
		expect(colorFor(undefined)).toBe(NONE_COLOR);
		expect(colorFor(-1)).toBe(NONE_COLOR);
	});

	it('picks palette entries and wraps around', () => {
		expect(colorFor(0)).toBe(PALETTE[0]);
		expect(colorFor(PALETTE.length)).toBe(PALETTE[0]);
		expect(colorFor(PALETTE.length + 2)).toBe(PALETTE[2]);
	});
});

describe('avatarColor', () => {
	it('is deterministic and always a palette color', () => {
		expect(avatarColor('REWE Markt')).toBe(avatarColor('REWE Markt'));
		for (const name of ['', 'a', 'Müller & Söhne', 'x'.repeat(500)]) {
			expect(PALETTE).toContain(avatarColor(name));
		}
	});
});

describe('initials', () => {
	it('uses the first letters of the first two words, upper-cased', () => {
		expect(initials('rewe markt gmbh')).toBe('RM');
		expect(initials('Amazon')).toBe('A');
	});

	it('ignores punctuation and handles unicode letters', () => {
		expect(initials('  --Äpfel & Birnen--')).toBe('ÄB');
	});

	it('falls back to a question mark', () => {
		expect(initials('')).toBe('?');
		expect(initials('***')).toBe('?');
	});
});
