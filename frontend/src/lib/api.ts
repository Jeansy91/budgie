import { goto } from '$app/navigation';

export class ApiError extends Error {
	constructor(
		public status: number,
		message: string,
		/** Machine-readable reason, when the API sends one (detail.code) */
		public code?: string
	) {
		super(message);
	}
}

function errorMessage(body: unknown, status: number): string {
	const detail = (body as { detail?: unknown })?.detail;
	if (typeof detail === 'string') return detail;
	if (detail && typeof detail === 'object' && 'message' in detail) return String(detail.message);
	if (Array.isArray(detail) && detail[0]?.msg) return detail.map((d) => d.msg).join(', ');
	return `Fehler ${status}`;
}

export async function api<T = unknown>(
	path: string,
	options: {
		method?: string;
		body?: unknown;
		form?: FormData;
		params?: Record<string, unknown>;
	} = {}
): Promise<T> {
	let url = `/api${path}`;
	if (options.params) {
		const qs = new URLSearchParams();
		for (const [k, v] of Object.entries(options.params)) {
			if (v !== undefined && v !== null && v !== '' && v !== false) qs.set(k, String(v));
		}
		if ([...qs].length) url += `?${qs}`;
	}
	const init: RequestInit = {
		method: options.method ?? 'GET',
		credentials: 'same-origin'
	};
	if (options.form) {
		init.body = options.form;
	} else if (options.body !== undefined) {
		init.body = JSON.stringify(options.body);
		init.headers = { 'Content-Type': 'application/json' };
	}
	const res = await fetch(url, init);
	if (res.status === 401 && !path.startsWith('/auth/')) {
		await goto('/login');
	}
	if (res.status === 204) return undefined as T;
	const body = await res.json().catch(() => null);
	if (!res.ok) {
		const code = (body as { detail?: { code?: string } })?.detail?.code;
		throw new ApiError(res.status, errorMessage(body, res.status), typeof code === 'string' ? code : undefined);
	}
	return body as T;
}
