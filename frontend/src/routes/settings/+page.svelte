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
	import { dateTime, iban, money, percent } from '#lib/format.ts';
	import { groupAccountsByBank } from '#lib/accounts.ts';
	import Landmark from '@lucide/svelte/icons/landmark';
	import Pencil from '@lucide/svelte/icons/pencil';
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

	// Inline editor: only one account is edited at a time, on a draft copy
	type AccountDraft = { id: number; name: string; shared: boolean; member_ids: number[]; transaction_count: number };
	let draft = $state<AccountDraft | null>(null);
	let groups = $derived(groupAccountsByBank(accounts));
	const startEdit = (a: Account) => {
		draft = { id: a.id, name: a.name, shared: a.shared, member_ids: [...a.member_ids], transaction_count: a.transaction_count };
	};
	const saveAccount = async (d: AccountDraft) => {
		draft = null;
		await run(
			() => api(`/accounts/${d.id}`, { method: 'PATCH', body: { name: d.name, shared: d.shared, member_ids: d.member_ids } }),
			t('settings.accountSaved')
		);
	};
	const deleteAccount = (d: AccountDraft) => {
		if (confirm(t('settings.confirmDeleteAccount', { name: d.name, count: d.transaction_count }))) {
			draft = null;
			run(() => api(`/accounts/${d.id}`, { method: 'DELETE' }), t('settings.accountDeleted'));
		}
	};
	const toggleMember = (d: AccountDraft, id: number) => {
		d.member_ids = d.member_ids.includes(id) ? d.member_ids.filter((m) => m !== id) : [...d.member_ids, id];
	};
	const visibility = (a: Account) => {
		if (a.shared) return t('settings.sharedBadge');
		const names = users.filter((u) => a.member_ids.includes(u.id)).map((u) => u.display_name);
		return names.length ? t('settings.privateBadge', { names: names.join(', ') }) : t('settings.privateNone');
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

<div>
	<div class="page-head">
		<div>
			<span class="eyebrow break-anywhere">{data.me?.household_name}</span>
			<h1>{t('nav.settings')}</h1>
		</div>
	</div>
	{#if error}<div class="error">{error}</div>{/if}
	{#if notice}<div class="ok">{notice}</div>{/if}

	<section class="card accounts">
		<div class="acc-head">
			<h2>{t('import.accounts')}</h2>
			{#if accounts.length}
				<span class="muted small">
					{t('settings.accountCount', { count: accounts.length })} · {t('settings.bankCount', { count: groups.length })}
				</span>
			{/if}
		</div>
		{#if accounts.length}
			<div class="acc-labels" aria-hidden="true">
				<span class="h-name">{t('common.name')}</span>
				<span class="h-iban">IBAN</span>
				<span class="h-count r">{t('nav.transactions')}</span>
				<span class="h-vis">{t('settings.visibility')}</span>
				<span class="h-bal r">{t('settings.balance')}</span>
			</div>
		{/if}
		{#each groups as g (g.bank)}
			<div class="group">
				<div class="group-head">
					<Landmark size={16} />
					<strong class="truncate" title={g.bank}>{g.bank}</strong>
					<span class="muted small">{g.accounts.length}</span>
				</div>
				{#each g.accounts as a (a.id)}
					<div class="acc-row">
						<strong class="name truncate" title={a.name}>{a.name}</strong>
						<span class="muted small iban">{a.iban ? iban(a.iban) : t('import.noIban')}</span>
						<span class="meta">
							<span class="muted small count">{t('transactions.count', { count: a.transaction_count })}</span>
							<span class="badge vis" class:accent={a.shared} title={visibility(a)}><span class="truncate">{visibility(a)}</span></span>
						</span>
						<span class="amount bal">{a.balance === null ? '–' : money(a.balance)}</span>
						<button
							class="ghost small edit"
							onclick={() => (draft?.id === a.id ? (draft = null) : startEdit(a))}
							aria-label={t('settings.editAccount', { name: a.name })}
							aria-expanded={draft?.id === a.id}
						>
							<Pencil size={16} />
						</button>
					</div>
					{#if draft && draft.id === a.id}
						<div class="editor">
							<label>{t('common.name')} <input bind:value={draft.name} /></label>
							<Switch bind:checked={draft.shared}>{t('settings.shared')}</Switch>
							{#if !draft.shared}
								<div class="row small">
									{t('settings.visibleFor')}
									{#each users as u (u.id)}
										<Checkbox
											checked={draft.member_ids.includes(u.id)}
											onchange={() => draft && toggleMember(draft, u.id)}
											disabled={u.id === data.me?.id}
										>
											{u.display_name}
										</Checkbox>
									{/each}
								</div>
							{/if}
							<div class="row actions">
								<button onclick={() => draft && saveAccount(draft)}>{t('common.save')}</button>
								<button class="secondary" onclick={() => (draft = null)}>{t('common.cancel')}</button>
								<button class="danger del" onclick={() => draft && deleteAccount(draft)}>{t('common.delete')}</button>
							</div>
						</div>
					{/if}
				{/each}
			</div>
		{:else}
			<p class="muted">{t('settings.noAccounts')} <a href="/import">{t('settings.noAccountsLink')}</a></p>
		{/each}
	</section>

	<div class="page-grid">
		<section class="card">
			<h2><Languages size={20} /> {t('settings.language')}</h2>
			<RadioGroup options={languageOptions} value={language} label={t('settings.language')} onchange={setLanguage} />
			<p class="muted small">{t('settings.languageHint', { browser: browserLanguage })}</p>
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
						<span
							class="dot"
							class:on={ai.llm.configured && ai.llm.model_available}
							class:off={ai.llm.configured && !ai.llm.model_available}
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
</div>

<style>
	/* Masonry-like columns so short cards fill the gaps next to tall ones */
	.page-grid {
		column-width: 34rem;
		column-gap: 1rem;
	}
	.page-grid > :global(*) {
		break-inside: avoid;
		margin: 0 0 1rem;
	}
	.accounts {
		container-type: inline-size;
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
	.acc-head {
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		gap: 0.25rem 1rem;
		margin-bottom: 0.75rem;
	}
	.acc-head h2 {
		margin: 0;
	}
	.group + .group {
		margin-top: 1rem;
	}
	.group-head {
		display: flex;
		align-items: center;
		gap: 0.45rem;
		padding: 0.3rem 0;
		border-bottom: 1px solid var(--border);
		color: var(--accent-strong);
		min-width: 0;
	}
	.acc-labels,
	.acc-row {
		display: grid;
		grid-template-columns: minmax(0, 1.6fr) minmax(0, 1.2fr) minmax(6.5rem, 0.5fr) minmax(0, 1fr) minmax(7.5rem, 0.6fr) 2rem;
		grid-template-areas: 'name iban count vis bal edit';
		align-items: center;
		gap: 0.5rem 1rem;
		padding: 0.55rem 0.25rem;
	}
	.acc-row {
		border-bottom: 1px solid var(--border);
	}
	.acc-labels {
		padding-block: 0.2rem;
		font-size: 0.75rem;
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.04em;
		color: var(--muted);
	}
	.r {
		text-align: right;
	}
	.h-name,
	.acc-row .name {
		grid-area: name;
	}
	.h-iban,
	.acc-row .iban {
		grid-area: iban;
	}
	.h-count,
	.acc-row .count {
		grid-area: count;
	}
	.h-vis,
	.acc-row .vis {
		grid-area: vis;
	}
	.h-bal,
	.acc-row .bal {
		grid-area: bal;
	}
	.acc-row .edit {
		grid-area: edit;
	}
	.iban {
		font-variant-numeric: tabular-nums;
		min-width: 0;
		overflow-wrap: anywhere;
	}
	/* On wide rows the meta wrapper dissolves into the grid columns */
	.meta {
		display: contents;
	}
	.count {
		white-space: nowrap;
		text-align: right;
		font-variant-numeric: tabular-nums;
	}
	.bal {
		text-align: right;
		font-weight: 600;
		white-space: nowrap;
		font-variant-numeric: tabular-nums;
	}
	.vis {
		justify-self: start;
		max-width: 100%;
		min-width: 0;
		display: inline-flex;
	}
	.edit {
		width: 2rem;
		height: 2rem;
		padding: 0;
		display: inline-grid;
		place-items: center;
	}
	.edit[aria-expanded='true'] {
		color: var(--accent-strong);
	}
	.editor {
		display: grid;
		gap: 0.75rem;
		padding: 0.85rem 0.75rem;
		border: 1px solid var(--border);
		border-radius: var(--radius-sm);
		background: var(--surface);
		margin: 0.25rem 0 0.5rem;
	}
	.editor label {
		max-width: min(28rem, 100%);
	}
	.editor > :global(.switch) {
		justify-self: start;
	}
	.actions .del {
		margin-left: auto;
	}
	/* Narrow card: name + edit, full IBAN, then count/badge left and balance right */
	@container (max-width: 640px) {
		.acc-labels {
			display: none;
		}
		.acc-row {
			grid-template-columns: minmax(0, 1fr) auto;
			grid-template-areas:
				'name edit'
				'iban iban'
				'meta bal';
			gap: 0.2rem 0.75rem;
		}
		.acc-row .edit {
			justify-self: end;
		}
		.acc-row .meta {
			grid-area: meta;
			display: flex;
			align-items: center;
			gap: 0.2rem 0.6rem;
			min-width: 0;
		}
		.acc-row .count {
			flex: none;
			text-align: left;
		}
		.acc-row .bal {
			justify-self: end;
		}
		.vis {
			flex: 0 1 auto;
		}
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
	form :global(.admin) {
		height: 2.6rem;
	}
</style>
