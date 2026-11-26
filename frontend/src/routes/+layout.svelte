<script lang="ts">
	import '../app.css';
	import { page } from '$app/state';
	import { goto, invalidateAll } from '$app/navigation';
	import { api } from '$lib/api';
	import { initials } from '$lib/colors';
	import Logo from '$lib/Logo.svelte';
	import { getLocale, t, type MessageKey } from '$lib/i18n/index.svelte';
	import LayoutDashboard from '@lucide/svelte/icons/layout-dashboard';
	import Receipt from '@lucide/svelte/icons/receipt';
	import FileUp from '@lucide/svelte/icons/file-up';
	import Tags from '@lucide/svelte/icons/tags';
	import WandSparkles from '@lucide/svelte/icons/wand-sparkles';
	import Settings from '@lucide/svelte/icons/settings';
	import LogOut from '@lucide/svelte/icons/log-out';

	let { data, children } = $props();

	const nav: { href: string; key: MessageKey; icon: typeof LayoutDashboard }[] = [
		{ href: '/', key: 'nav.overview', icon: LayoutDashboard },
		{ href: '/transactions', key: 'nav.transactions', icon: Receipt },
		{ href: '/import', key: 'nav.import', icon: FileUp },
		{ href: '/categories', key: 'nav.categories', icon: Tags },
		{ href: '/rules', key: 'nav.rules', icon: WandSparkles }
	];

	const active = (href: string) => (href === '/' ? page.url.pathname === '/' : page.url.pathname.startsWith(href));

	async function logout() {
		await api('/auth/logout', { method: 'POST' });
		await invalidateAll();
		await goto('/login');
	}
</script>

{#if data.me}
	<div class="shell">
		<aside class="sidebar">
			<a class="brand" href="/"><Logo size={34} /> <span>Budgie</span></a>
			<nav>
				{#each nav as item (item.href)}
					<a href={item.href} class:active={active(item.href)}>
						<item.icon size={19} strokeWidth={2} />
						{t(item.key)}
					</a>
				{/each}
			</nav>
			<div class="spacer"></div>
			<a href="/settings" class="navlink" class:active={active('/settings')}>
				<Settings size={19} />
				{t('nav.settings')}
			</a>
			<div class="me">
				<span class="avatar">{initials(data.me.display_name)}</span>
				<div class="who">
					<strong title={data.me.display_name}>{data.me.display_name}</strong>
					<span title={data.me.household_name}>{data.me.household_name}</span>
				</div>
				<button class="ghost icon" onclick={logout} title={t('nav.logout')} aria-label={t('nav.logout')}><LogOut size={18} /></button>
			</div>
		</aside>

		<header class="topbar">
			<a class="brand" href="/"><Logo size={30} /> <span>Budgie</span></a>
			<a href="/settings" class="avatar" title={t('nav.settings')}>{initials(data.me.display_name)}</a>
		</header>

		<main>
			<!-- Remount the page when the language changes, so data the API translates (category names) reloads -->
			{#key getLocale()}
				{@render children()}
			{/key}
		</main>

		<nav class="tabbar">
			{#each nav as item (item.href)}
				<a href={item.href} class:active={active(item.href)}>
					<item.icon size={21} />
					<span>{t(item.key)}</span>
				</a>
			{/each}
		</nav>
	</div>
{:else}
	{@render children()}
{/if}

<style>
	.shell {
		min-height: 100vh;
	}
	.sidebar {
		position: fixed;
		inset: 0 auto 0 0;
		width: 248px;
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
		padding: 1.25rem 1rem;
		background: var(--surface);
		border-right: 1px solid var(--border);
	}
	.brand {
		display: flex;
		align-items: center;
		gap: 0.65rem;
		font-weight: 750;
		font-size: 1.2rem;
		letter-spacing: -0.02em;
		color: var(--text);
		text-decoration: none;
		padding: 0 0.5rem 1.5rem;
	}
	nav {
		display: flex;
		flex-direction: column;
		gap: 0.2rem;
	}
	.sidebar a:not(.brand) {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		padding: 0.65rem 0.8rem;
		border-radius: var(--radius-sm);
		color: var(--muted);
		text-decoration: none;
		font-weight: 550;
		font-size: 0.93rem;
		transition:
			background 0.15s,
			color 0.15s;
	}
	.sidebar a:not(.brand):hover {
		background: var(--surface-2);
		color: var(--text);
	}
	.sidebar a.active {
		background: var(--accent-soft);
		color: var(--accent-strong);
	}
	.spacer {
		flex: 1;
	}
	.me {
		display: flex;
		align-items: center;
		gap: 0.7rem;
		margin-top: 0.75rem;
		padding: 0.75rem 0.5rem 0;
		border-top: 1px solid var(--border);
	}
	.who {
		display: flex;
		flex-direction: column;
		min-width: 0;
		flex: 1;
		font-size: 0.85rem;
	}
	.who strong {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.who span {
		color: var(--muted);
		font-size: 0.78rem;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.avatar {
		display: grid;
		place-items: center;
		width: 2.2rem;
		height: 2.2rem;
		border-radius: 999px;
		background: var(--gradient);
		color: #fff;
		font-weight: 700;
		font-size: 0.8rem;
		text-decoration: none;
		flex: none;
	}
	main {
		margin-left: 248px;
		max-width: 1180px;
		padding: 2rem 2.5rem 4rem;
	}
	.topbar,
	.tabbar {
		display: none;
	}

	@media (max-width: 900px) {
		.sidebar {
			display: none;
		}
		.topbar {
			display: flex;
			position: sticky;
			top: 0;
			z-index: 10;
			justify-content: space-between;
			align-items: center;
			padding: 0.75rem 1rem;
			background: color-mix(in srgb, var(--bg) 82%, transparent);
			backdrop-filter: blur(14px);
		}
		.topbar .brand {
			padding: 0;
		}
		main {
			margin: 0;
			padding: 0.5rem 1rem 6.5rem;
		}
		.tabbar {
			display: flex;
			flex-direction: row;
			position: fixed;
			z-index: 10;
			left: 0.75rem;
			right: 0.75rem;
			bottom: calc(0.75rem + env(safe-area-inset-bottom));
			justify-content: space-around;
			padding: 0.4rem;
			border-radius: 22px;
			background: color-mix(in srgb, var(--surface) 88%, transparent);
			backdrop-filter: blur(16px);
			border: 1px solid var(--border);
			box-shadow: var(--shadow-lg);
		}
		.tabbar a {
			flex: 1;
			display: flex;
			flex-direction: column;
			align-items: center;
			gap: 0.15rem;
			padding: 0.45rem 0;
			border-radius: 16px;
			color: var(--faint);
			text-decoration: none;
			font-size: 0.66rem;
			font-weight: 600;
		}
		.tabbar a.active {
			color: var(--accent-strong);
			background: var(--accent-soft);
		}
	}
</style>
