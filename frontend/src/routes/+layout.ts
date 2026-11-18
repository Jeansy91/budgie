import { redirect } from '@sveltejs/kit';
import type { Me } from '$lib/types';
import { applyUserLocale } from '$lib/i18n/index.svelte';
import type { LayoutLoad } from './$types';

// Client-only app: the API delivers all data, nothing is server-rendered
export const ssr = false;

const PUBLIC = ['/login', '/setup'];

export const load: LayoutLoad = async ({ fetch, url }) => {
	const res = await fetch('/api/auth/me');
	const me: Me | null = res.ok ? await res.json() : null;
	// Signed in: the user's saved language. Before login the login page's choice stays.
	if (me) applyUserLocale(me.language);
	if (!me && !PUBLIC.includes(url.pathname)) {
		const status = await fetch('/api/auth/setup').then((r) => r.json());
		redirect(307, status.needs_setup ? '/setup' : '/login');
	}
	if (me && PUBLIC.includes(url.pathname)) redirect(307, '/');
	return { me };
};
