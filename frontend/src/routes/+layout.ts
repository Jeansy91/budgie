import { redirect } from '@sveltejs/kit';
import type { Me } from '$lib/types';
import type { LayoutLoad } from './$types';

// Client-only app: the API delivers all data, nothing is server-rendered
export const ssr = false;

const PUBLIC = ['/login', '/setup'];

export const load: LayoutLoad = async ({ fetch, url }) => {
	const res = await fetch('/api/auth/me');
	const me: Me | null = res.ok ? await res.json() : null;
	if (!me && !PUBLIC.includes(url.pathname)) {
		const status = await fetch('/api/auth/setup').then((r) => r.json());
		redirect(307, status.needs_setup ? '/setup' : '/login');
	}
	if (me && PUBLIC.includes(url.pathname)) redirect(307, '/');
	return { me };
};
