<script lang="ts">
	import { api } from '#lib/api.ts';
	import { Checkbox, PasswordInput, RadioGroup, Switch } from '#lib/ui/index.ts';
	import { invalidateAll } from '$app/navigation';
	import { LOCALES, browserLocale, t, type Locale } from '#lib/i18n/index.svelte.ts';
	import Languages from '@lucide/svelte/icons/languages';
	import type { Account, AiStatus, User } from '#lib/types.ts';
	import { onDestroy } from 'svelte';
	import Wand from '@lucide/svelte/icons/wand-sparkles';
	import { initials } from '#lib/colors.ts';
	import { dateTime, iban, percent } from '#lib/format.ts';
	import BudgetMonthSettings from '#lib/BudgetMonthSettings.svelte';

	let { data } = $props();
	let users = $state<User[]>([]);
	let accounts = $state<Account[]>([]);
	let error = $state('');
	let notice = $state('');
	let newUser = $state({ username: '', display_name: '', password: '', is_admin: false });
	let pw = $state({ current_password: '', new_password: '' });

	async function run(fn: () => Promise<unknown>, ok = '') {
		try {
			await fn();
			error = '';
			notice = ok;
		} catch (e) {
			error = (e as Error).message;
			notice = '';
		}
		[users, accounts] = await Promise.all([api<User[]>('/users'), api<Account[]>('/accounts')]);
	}
	run(async () => {});

	// --- Language (per user; "auto" follows the browser) ---
	let language = $derived<Locale | 'auto'>(data.me?.language ?? 'auto');
	let languageOptions = $derived([
		{ value: 'auto' as const, label: t('settings.languageAuto') },
		...LOCALES.map((l) => ({ value: l.code, label: l.label }))
	]);
	const browserLanguage = LOCALES.find((l) => l.code === browserLocale())!.label;
	async function setLanguage(value: Locale | 'auto') {
		const preference = value === 'auto' ? null : value;
		try {
			await api('/auth/me', { method: 'PATCH', body: { language: preference } });
			// The layout load applies the new preference (see +layout.ts)
			await invalidateAll();
		} catch (e) {
			error = (e as Error).message;
		}
	}

	// --- AI categorization ---
	let ai = $state<AiStatus | null>(null);
	let aiBusy = $state(false);
	let poll: ReturnType<typeof setTimeout> | undefined;
	const pct = percent;
	const when = dateTime;

	async function loadAi() {
		clearTimeout(poll);
		try {
			ai = await api<AiStatus>('/ai/status');
		} catch (e) {
			error = (e as Error).message;
		}
		// Keep polling progress while the language model works in the background
		if (ai?.llm.running) poll = setTimeout(loadAi, 4000);
	}
	loadAi();
	onDestroy(() => clearTimeout(poll));

	async function aiAction<R = unknown>(path: string, ok: (r: R) => string) {
		aiBusy = true;
		try {
			const r = await api<R>(path, { method: 'POST', body: path.endsWith('recategorize') ? { use_llm: true } : undefined });
			notice = ok(r);
			error = '';
		} catch (e) {
			error = (e as Error).message;
			notice = '';
		}
		aiBusy = false;
		await loadAi();
	}
	const train = () => aiAction('/ai/train', () => t('ai.trained'));
	const recategorize = () =>
		aiAction('/ai/recategorize', (r: { assigned: number; suggested: number; llm_queued: number }) =>
			r.llm_queued
				? t('ai.recategorizedLlm', { assigned: r.assigned, suggested: r.suggested, queued: r.llm_queued })
				: t('ai.recategorized', { assigned: r.assigned, suggested: r.suggested })
		);

	const saveAccount = (a: Account) =>
		run(
			() => api(`/accounts/${a.id}`, { method: 'PATCH', body: { name: a.name, shared: a.shared, member_ids: a.member_ids } }),
			t('settings.accountSaved')
		);
	const deleteAccount = (a: Account) => {
		if (confirm(t('settings.confirmDeleteAccount', { name: a.name, count: a.transaction_count })))
			run(() => api(`/accounts/${a.id}`, { method: 'DELETE' }), t('settings.accountDeleted'));
	};
	const toggleMember = (a: Account, id: number) => {
		a.member_ids = a.member_ids.includes(id) ? a.member_ids.filter((m) => m !== id) : [...a.member_ids, id];
	};
	const addUser = (e: SubmitEvent) => {
		e.preventDefault();
		run(async () => {
			await api('/users', { method: 'POST', body: newUser });
			newUser = { username: '', display_name: '', password: '', is_admin: false };
		}, t('settings.userCreated'));
	};
	const deleteUser = (u: User) => {
		if (confirm(t('settings.confirmDeleteUser', { name: u.display_name })))
			run(() => api(`/users/${u.id}`, { method: 'DELETE' }), t('settings.userDeleted'));
	};
	const changePassword = (e: SubmitEvent) => {
		e.preventDefault();
		run(async () => {
			await api('/auth/password', { method: 'POST', body: pw });
			pw = { current_password: '', new_password: '' };
		}, t('settings.passwordChanged'));
	};
</script>

<div class="readable">
	<div class="page-head">
		<div>
			<span class="eyebrow break-anywhere">{data.me?.household_name}</span>
			<h1>{t('nav.settings')}</h1>
		</div>
	</div>
	{#if error}<div class="error">{error}</div>{/if}
	{#if notice}<div class="ok">{notice}</div>{/if}

	<section class="card">
		<h2><Languages size={20} /> {t('settings.language')}</h2>
		<RadioGroup options={languageOptions} value={language} label={t('settings.language')} onchange={setLanguage} />
		<p class="muted small">{t('settings.languageHint', { browser: browserLanguage })}</p>
	</section>

	<section class="card">
		<h2>{t('import.accounts')}</h2>
		{#each accounts as a (a.id)}
			<div class="account">
				<div class="row">
					<label>{t('common.name')} <input bind:value={a.name} /></label>
					<span class="small muted">
						{a.iban ? iban(a.iban) : t('import.noIban')} · {t('transactions.count', { count: a.transaction_count })}
					</span>
				</div>
				<Switch bind:checked={a.shared}>{t('settings.shared')}</Switch>
				{#if !a.shared}
					<div class="row small">
						{t('settings.visibleFor')}
						{#each users as u (u.id)}
							<Checkbox checked={a.member_ids.includes(u.id)} onchange={() => toggleMember(a, u.id)} disabled={u.id === data.me?.id}>
								{u.display_name}
							</Checkbox>
						{/each}
					</div>
				{/if}
				<div class="row">
					<button class="secondary" onclick={() => saveAccount(a)}>{t('common.save')}</button>
					<button class="danger" onclick={() => deleteAccount(a)}>{t('common.delete')}</button>
				</div>
			</div>
		{:else}
			<p class="muted">{t('settings.noAccounts')} <a href="/import">{t('settings.noAccountsLink')}</a></p>
		{/each}
	</section>

	<BudgetMonthSettings />

	<section class="card">
		<h2><Wand size={20} /> {t('ai.title')}</h2>
		{#if ai}
			{#if !ai.enabled}
				<p class="muted">{t('ai.disabled')} (BUDGIE_AI_ENABLED=false).</p>
			{:else}
				<p class="muted small">
					{t('ai.intro', { threshold: pct(ai.auto_threshold) })}
				</p>
				<div class="stats">
					<div>
						<span class="label">{t('ai.learnedFrom')}</span>
						<strong>{ai.model ? ai.model.samples : 0}</strong>
						<span class="small muted">
							{t('ai.ownTransactions')}{#if ai.model}{t('ai.manualShare', { count: ai.model.corrections })}{/if}
						</span>
					</div>
					<div>
						<span class="label">{t('ai.accuracy')}</span>
						<strong>{ai.model?.accuracy != null ? pct(ai.model.accuracy) : '–'}</strong>
						<span class="small muted">{ai.model?.accuracy != null ? t('ai.accuracyHint') : t('ai.accuracyLater')}</span>
					</div>
					<a class="stat-link" href="/transactions?ai_review=1">
						<span class="label">{t('ai.toReview')}</span>
						<strong>{ai.ai_categorized + ai.suggestions}</strong>
						<span class="small muted">{t('ai.toReviewHint', { assigned: ai.ai_categorized, suggestions: ai.suggestions })}</span>
					</a>
					<a class="stat-link" href="/transactions?uncategorized=1">
						<span class="label">{t('ai.uncategorized')}</span>
						<strong>{ai.uncategorized}</strong>
						<span class="small muted">{t('ai.transactions', { count: ai.uncategorized })}</span>
					</a>
				</div>
				<p class="small muted">
					{#if ai.model}{t('ai.lastTrained', { when: when(ai.model.trained_at) })}{:else}{t('ai.notTrained')}{/if}
				</p>

				<div class="llm">
					<span class="dot" class:on={ai.llm.configured && ai.llm.model_available} class:off={ai.llm.configured && !ai.llm.model_available}
					></span>
					<div>
						<strong>{t('ai.llmTitle')}</strong>
						{#if !ai.llm.configured}
							<div class="small muted">
								{t('ai.llmOff')}
							</div>
						{:else if ai.llm.error}
							<div class="small warn-text">{ai.llm.error}</div>
						{:else}
							<div class="small muted">{t('ai.llmReady', { model: ai.llm.model })}</div>
						{/if}
						{#if ai.llm.running}
							<div class="small">{t('ai.llmRunning', { done: ai.llm.done, total: ai.llm.total })}</div>
						{/if}
					</div>
				</div>

				<div class="row">
					<button class="secondary" onclick={train} disabled={aiBusy}>{t('ai.train')}</button>
					<button class="secondary" onclick={recategorize} disabled={aiBusy}>{t('ai.recategorize')}</button>
				</div>
			{/if}
		{/if}
	</section>

	<section class="card">
		<h2>{t('settings.users')}</h2>
		<table class="users">
			<tbody>
				{#each users as u (u.id)}
					<tr>
						<td>
							<span class="user">
								<span class="av">{initials(u.display_name)}</span>
								<span class="who">
									<strong class="truncate" title={u.display_name}>{u.display_name}</strong>
									<span class="muted small truncate" title="@{u.username}">@{u.username}</span>
								</span>
								{#if u.is_admin}<span class="badge accent">Admin</span>{/if}
							</span>
						</td>
						<td class="amount">
							{#if data.me?.is_admin && u.id !== data.me.id}<button class="link small" onclick={() => deleteUser(u)}>
									{t('settings.deleteUser')}
								</button>{/if}
						</td>
					</tr>
				{/each}
			</tbody>
		</table>
		{#if data.me?.is_admin}
			<form class="row" style="margin-top: 1rem" onsubmit={addUser}>
				<label>{t('common.name')} <input bind:value={newUser.display_name} required /></label>
				<label>{t('auth.username')} <input bind:value={newUser.username} required pattern="[A-Za-z0-9._\-]+" /></label>
				<label>
					{t('auth.password')}
					<PasswordInput bind:value={newUser.password} minlength={8} required autocomplete="new-password" />
				</label>
				<Checkbox bind:checked={newUser.is_admin} class="admin">Admin</Checkbox>
				<button>{t('settings.createUser')}</button>
			</form>
		{/if}
	</section>

	<section class="card">
		<h2>{t('settings.changePassword')}</h2>
		<form class="row" onsubmit={changePassword}>
			<label>
				{t('settings.currentPassword')}
				<PasswordInput bind:value={pw.current_password} required autocomplete="current-password" />
			</label>
			<label>
				{t('settings.newPassword')}
				<PasswordInput bind:value={pw.new_password} minlength={8} required autocomplete="new-password" />
			</label>
			<button>{t('settings.change')}</button>
		</form>
	</section>
</div>

<style>
	/* Forms and text stay readable on very wide screens */
	.readable {
		max-width: 60rem;
	}
	/* Let the name cell take the remaining width and shrink instead of widening the table */
	.users td:first-child {
		width: 100%;
		max-width: 0;
	}
	.users td:last-child {
		width: 1%;
	}
	.user {
		display: flex;
		align-items: center;
		gap: 0.7rem;
		min-width: 0;
	}
	.user .who {
		display: flex;
		flex-direction: column;
		min-width: 0;
	}
	.user .badge {
		flex: none;
	}
	.av {
		flex: none;
		display: grid;
		place-items: center;
		width: 2.2rem;
		height: 2.2rem;
		border-radius: 999px;
		background: var(--gradient);
		color: #fff;
		font-weight: 700;
		font-size: 0.78rem;
	}
	.account {
		display: grid;
		gap: 0.6rem;
		padding: 0.75rem 0;
		border-bottom: 1px solid var(--border);
	}
	.account:last-child {
		border-bottom: 0;
	}
	h2 {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}
	.stats {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
		gap: 0.75rem;
		margin: 1rem 0 0.5rem;
	}
	.stats > * {
		display: grid;
		align-content: start;
		gap: 0.15rem;
		padding: 0.85rem 1rem;
		border-radius: var(--radius-sm);
		background: var(--surface-2);
		color: inherit;
		text-decoration: none;
	}
	.stats strong {
		font-size: 1.5rem;
	}
	.stat-link:hover {
		background: var(--surface-3);
	}
	.label {
		font-size: 0.75rem;
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.04em;
		color: var(--muted);
	}
	.llm {
		display: flex;
		gap: 0.75rem;
		align-items: flex-start;
		margin: 1rem 0;
		padding: 0.85rem 1rem;
		border: 1px solid var(--border);
		border-radius: var(--radius-sm);
	}
	.llm > div {
		flex: 1;
		min-width: 0;
		/* Error messages from the model server contain long URLs */
		overflow-wrap: anywhere;
	}
	.llm .dot {
		flex: none;
		width: 0.7rem;
		height: 0.7rem;
		margin-top: 0.35rem;
		border-radius: 999px;
		background: var(--faint);
	}
	.llm .dot.on {
		background: var(--accent);
	}
	.llm .dot.off {
		background: var(--warn);
	}
	.warn-text {
		color: var(--warn);
	}
	.account > :global(.switch) {
		justify-self: start;
	}
	form :global(.admin) {
		height: 2.6rem;
	}
</style>
