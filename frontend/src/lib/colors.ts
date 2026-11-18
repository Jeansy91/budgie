/** Fixed color palette for main categories (by position in the category tree). */
export const PALETTE = [
	'#10b981', '#6366f1', '#f59e0b', '#ec4899', '#0ea5e9', '#8b5cf6', '#ef4444',
	'#14b8a6', '#f97316', '#84cc16', '#06b6d4', '#a855f7', '#64748b', '#eab308'
];
export const NONE_COLOR = '#94a3b8';

export function colorFor(index: number | undefined): string {
	return index === undefined || index < 0 ? NONE_COLOR : PALETTE[index % PALETTE.length];
}

/** Color for a payee avatar, derived deterministically from the name. */
export function avatarColor(name: string): string {
	let h = 0;
	for (const ch of name) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
	return PALETTE[h % PALETTE.length];
}

export function initials(name: string): string {
	const words = name.replace(/[^\p{L}\p{N} ]/gu, ' ').split(/\s+/).filter(Boolean);
	return ((words[0]?.[0] ?? '?') + (words[1]?.[0] ?? '')).toUpperCase();
}
