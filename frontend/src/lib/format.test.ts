import { describe, expect, it } from 'vitest';
import { categoryLabels, currentMonth, day, iban, money, monthLabel, number, percent, shiftMonth } from './format';
import type { Category } from './types';

// Intl uses non-breaking spaces; normalize them for readable assertions
const plain = (s: string) => s.replace(/[\u00a0\u202f]/g, ' ');

describe('money', () => {
	it('formats numbers and numeric strings as currency (default locale de)', () => {
		expect(plain(money(1234.5))).toBe('1.234,50 €');
		expect(plain(money('-12.3'))).toBe('-12,30 €');
	});

	it('supports other currencies', () => {
		expect(plain(money(5, 'USD'))).toContain('5,00');
	});

	it('shows a dash for null and undefined', () => {
		expect(money(null)).toBe('–');
		expect(money(undefined)).toBe('–');
	});
});

describe('number and percent', () => {
	it('formats plain numbers with locale separators', () => {
		expect(plain(number(1234567.891, { maximumFractionDigits: 1 }))).toBe('1.234.567,9');
	});

	it('formats shares as whole percentages', () => {
		expect(plain(percent(0.854))).toBe('85 %');
		expect(percent(null)).toBe('');
		expect(percent(undefined)).toBe('');
	});
});

describe('dates', () => {
	it('formats ISO dates as day.month.year without time zone shifts', () => {
		expect(day('2026-11-18')).toBe('18.11.2026');
		expect(day('2026-01-01T23:59:59Z')).toBe('01.01.2026');
	});

	it('labels months', () => {
		expect(monthLabel('2026-03')).toBe('März 2026');
	});

	it('returns the current month as YYYY-MM', () => {
		expect(currentMonth()).toMatch(/^\d{4}-\d{2}$/);
	});
});

describe('shiftMonth', () => {
	it('moves forward and backward', () => {
		expect(shiftMonth('2026-05', 1)).toBe('2026-06');
		expect(shiftMonth('2026-05', -2)).toBe('2026-03');
		expect(shiftMonth('2026-05', 0)).toBe('2026-05');
	});

	it('crosses year boundaries', () => {
		expect(shiftMonth('2026-12', 1)).toBe('2027-01');
		expect(shiftMonth('2026-01', -1)).toBe('2025-12');
		expect(shiftMonth('2026-01', 25)).toBe('2028-02');
	});
});

describe('iban', () => {
	it('groups in blocks of four and normalizes existing spaces', () => {
		expect(iban('DE85500105170648489890')).toBe('DE85 5001 0517 0648 4898 90');
		expect(iban('DE85 5001 0517 0648 4898 90')).toBe('DE85 5001 0517 0648 4898 90');
	});

	it('returns an empty string for empty values', () => {
		expect(iban(null)).toBe('');
		expect(iban(undefined)).toBe('');
		expect(iban('')).toBe('');
	});
});

describe('categoryLabels', () => {
	it('maps main categories and "Main › Sub" labels by id', () => {
		const tree = [
			{ id: 1, name: 'Living', children: [{ id: 2, name: 'Rent' }] },
			{ id: 3, name: 'Fun', children: [] }
		] as unknown as Category[];
		const labels = categoryLabels(tree);
		expect(labels.get(1)).toBe('Living');
		expect(labels.get(2)).toBe('Living › Rent');
		expect(labels.get(3)).toBe('Fun');
		expect(labels.size).toBe(3);
	});
});
