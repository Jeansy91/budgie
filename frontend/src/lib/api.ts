import { goto } from '$app/navigation';
import { getLocale, t } from './i18n/index.svelte';

export class ApiError extends Error {
	constructor(
		public status: number,
		message: string
	) {
		super(message);
	}
}

interface ValidationIssue {
	type: string;
	loc?: (string | number)[];
	msg: string;
	ctx?: Record<string, unknown>;
}

/** Request validation errors (422) come from Pydantic in English; translate the common ones. */
function validationMessage(issue: ValidationIssue): string {
	const field = String(issue.loc?.at(-1) ?? '');
	const params = { field, min: String(issue.ctx?.min_length ?? ''), max: String(issue.ctx?.max_length ?? '') };
	switch (issue.type) {
		case 'missing':
			return t('errors.validation.missing', params);
		case 'string_too_short':
			return t('errors.validation.tooShort', params);
		case 'string_too_long':
			return t('errors.validation.tooLong', params);
		case 'string_pattern_mismatch':
			return t('errors.validation.pattern', params);
		default:
			return issue.msg;
	}
}

function errorMessage(body: unknown, status: number): string {
	const detail = (body as { detail?: unknown })?.detail;
	if (typeof detail === 'string') return detail;
	if (Array.isArray(detail) && detail[0]?.msg) return (detail as ValidationIssue[]).map(validationMessage).join(', ');
	return t('errors.http', { status: String(status) });
}

export async function api<T = unknown>(
	path: string,
	options: { method?: string; body?: unknown; form?: FormData; params?: Record<string, unknown> } = {}
): Promise<T> {
	let url = `/api${path}`;
	if (options.params) {
		const qs = new URLSearchParams();
		for (const [k, v] of Object.entries(options.params)) {
			if (v !== undefined && v !== null && v !== '' && v !== false) qs.set(k, String(v));
		}
		if ([...qs].length) url += `?${qs}`;
	}
	// The API answers in the UI language (error messages, default category names)
	const headers: Record<string, string> = { 'Accept-Language': getLocale() };
	const init: RequestInit = { method: options.method ?? 'GET', credentials: 'same-origin', headers };
	if (options.form) {
		init.body = options.form;
	} else if (options.body !== undefined) {
		init.body = JSON.stringify(options.body);
		headers['Content-Type'] = 'application/json';
	}
	const res = await fetch(url, init);
	if (res.status === 401 && !path.startsWith('/auth/')) {
		await goto('/login');
	}
	if (res.status === 204) return undefined as T;
	const body = await res.json().catch(() => null);
	if (!res.ok) throw new ApiError(res.status, errorMessage(body, res.status));
	return body as T;
}
