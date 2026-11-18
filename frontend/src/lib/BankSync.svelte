<script lang="ts">
	import { DatePicker, PasswordInput } from '$lib/ui';
	import { onDestroy } from 'svelte';
	import { api } from '$lib/api';
	import { dateTime, day } from '$lib/format';
	import { t } from '$lib/i18n/index.svelte';
	import type { BankConnection, FintsStatus, SyncJob } from '$lib/types';
	import RefreshCw from '@lucide/svelte/icons/refresh-cw';
	import Smartphone from '@lucide/svelte/icons/smartphone';
	import KeyRound from '@lucide/svelte/icons/key-round';
	import LoaderCircle from '@lucide/svelte/icons/loader-circle';
	import CircleAlert from '@lucide/svelte/icons/circle-alert';
	import Check from '@lucide/svelte/icons/check';

	let { onsynced }: { onsynced?: () => void } = $props();

	let status = $state<FintsStatus | null>(null);
	let connections = $state<BankConnection[]>([]);
	let error = $state('');

	// New connection
	let adding = $state(false);
	let form = $state({ name: 'ING', login: '' });

	// Sync
	let syncFor = $state<BankConnection | null>(null);
	let pin = $state('');
	let startDate = $state('');
	const today = new Date().toLocaleDateString('sv-SE'); // YYYY-MM-DD in local time
	let tan = $state('');
	let job = $state<SyncJob | null>(null);
	let timer: ReturnType<typeof setTimeout> | undefined;

	const active = $derived(job !== null && (job.state === 'running' || job.state === 'need_tan'));

	async function load() {
		status = await api<FintsStatus>('/fints/status');
		connections = await api<BankConnection[]>('/fints/connections');
		adding = status.enabled && connections.length === 0;
	}
	load().catch((e) => (error = (e as Error).message));

	async function addConnection(e: SubmitEvent) {
		e.preventDefault();
		error = '';
		try {
			await api('/fints/connections', { method: 'POST', body: form });
			form = { name: 'ING', login: '' };
			await load();
		} catch (err) {
			error = (err as Error).message;
		}
	}

	async function removeConnection(c: BankConnection) {
		if (!confirm(t('bank.confirmRemove', { name: c.name }))) return;
		await api(`/fints/connections/${c.id}`, { method: 'DELETE' });
		await load();
	}

	function openSync(c: BankConnection) {
		syncFor = c;
		job = null;
		pin = '';
		tan = '';
		startDate = '';
		error = '';
	}

	async function startSync(e: SubmitEvent) {
		e.preventDefault();
		if (!syncFor) return;
		error = '';
		try {
			job = await api<SyncJob>(`/fints/connections/${syncFor.id}/sync`, {
				method: 'POST',
				body: { pin, start_date: startDate || null }
			});
			poll();
		} catch (err) {
			error = (err as Error).message;
		} finally {
			// Do not keep the PIN in the browser
			pin = '';
		}
	}

	async function poll() {
		if (!job) return;
		try {
			job = await api<SyncJob>(`/fints/jobs/${job.id}`);
		} catch (err) {
			error = (err as Error).message;
			return;
		}
		if (job.state === 'running' || job.state === 'need_tan') {
			timer = setTimeout(poll, 1500);
		} else {
			await load();
			if (job.state === 'done') onsynced?.();
		}
	}

	async function sendTan(e: SubmitEvent) {
		e.preventDefault();
		if (!job) return;
		try {
			job = await api<SyncJob>(`/fints/jobs/${job.id}/tan`, { method: 'POST', body: { tan } });
			tan = '';
		} catch (err) {
			error = (err as Error).message;
		}
	}

	async function cancel() {
		if (job) job = await api<SyncJob>(`/fints/jobs/${job.id}/cancel`, { method: 'POST' });
	}

	function close() {
		syncFor = null;
		job = null;
	}

	const when = (iso: string | null) => (iso ? dateTime(iso) : t('bank.never'));

	onDestroy(() => clearTimeout(timer));
</script>

<section class="card fints">
	<div class="head">
		<span class="icon"><RefreshCw size={20} /></span>
		<div>
			<h2>{t('bank.title')}</h2>
			<p class="muted small">{t('bank.intro')}</p>
		</div>
	</div>

	{#if error}<div class="error"><CircleAlert size={18} /> {error}</div>{/if}

	{#if status && !status.enabled}
		<div class="warn">
			<CircleAlert size={18} />
			<span>{t('bank.notConfigured')} <code>.env</code>: {status.missing.join(', ')}</span>
		</div>
	{/if}

	{#each connections as c (c.id)}
		<div class="conn">
			<div class="who">
				<strong class="break-anywhere">{c.name}</strong>
				<span class="muted small">
					{t('bank.login', { hint: c.login_hint })} · {t('bank.lastSync', { when: when(c.last_sync_at) })}
					{#if c.tan_mechanism_name}· {c.tan_mechanism_name}{/if}
				</span>
				{#if c.accounts.length}
					<span class="muted small accounts" title={c.accounts.map((a) => a.name).join(', ')}>{c.accounts.map((a) => a.name).join(', ')}</span>
				{/if}
				{#if c.last_error && syncFor?.id !== c.id}<span class="small err break-anywhere">{c.last_error}</span>{/if}
			</div>
			{#if syncFor?.id !== c.id}
				<div class="actions">
					<button onclick={() => openSync(c)} disabled={!status?.enabled}>{t('bank.sync')}</button>
					<button class="ghost small" onclick={() => removeConnection(c)}>{t('bank.remove')}</button>
				</div>
			{/if}
		</div>

		{#if syncFor?.id === c.id}
			<div class="sync">
				{#if !job}
					<form class="row" onsubmit={startSync}>
						<label
							>{t('bank.pin')}
							<PasswordInput bind:value={pin} required autocomplete="off" inputmode="numeric" />
						</label>
						<div class="field">
							<span>{t('bank.since')} <span class="muted small">({t('common.optional')})</span></span>
							<DatePicker bind:value={startDate} label={t('bank.since')} placeholder={t('budgetMenu.auto')} max={today} />
						</div>
						<button>{t('bank.fetch')}</button>
						<button type="button" class="ghost" onclick={close}>{t('common.cancel')}</button>
					</form>
					<p class="muted small">
						{t('bank.sinceHint')}
					</p>
				{:else if job.state === 'need_tan' && job.decoupled}
					<div class="tan">
						<span class="pulse"><Smartphone size={26} /></span>
						<div>
							<strong>{t('bank.approveInApp')}</strong>
							{#if job.challenge}<p class="muted small">{job.challenge}</p>{/if}
							<p class="muted small">{t('bank.waiting')}</p>
						</div>
						<button class="ghost" onclick={cancel}>{t('common.cancel')}</button>
					</div>
				{:else if job.state === 'need_tan'}
					<div class="tan">
						<span class="pulse"><KeyRound size={24} /></span>
						<div>
							<strong>{t('bank.enterTan')}</strong>
							{#if job.challenge}<p class="muted small">{job.challenge}</p>{/if}
							{#if job.challenge_image}<img src={job.challenge_image} alt={t('bank.tanImage')} />{/if}
							<form class="row" onsubmit={sendTan}>
								<input bind:value={tan} required autocomplete="one-time-code" inputmode="numeric" />
								<button>{t('bank.send')}</button>
								<button type="button" class="ghost" onclick={cancel}>{t('common.cancel')}</button>
							</form>
						</div>
					</div>
				{:else if active}
					<div class="tan">
						<span class="spin"><LoaderCircle size={24} /></span>
						<span>{job.message}</span>
					</div>
				{:else if job.state === 'error'}
					<div class="error"><CircleAlert size={18} /> {job.error}</div>
					<button class="secondary" onclick={() => openSync(c)}>{t('bank.retry')}</button>
				{:else if job.state === 'cancelled'}
					<p class="muted">{t('bank.cancelled')}</p>
					<button class="secondary" onclick={close}>{t('common.close')}</button>
				{:else}
					{#each job.results as r (r.iban)}
						<div class="result">
							<span class="ok-icon"><Check size={16} /></span>
							<div class="info">
								<strong class="break-anywhere">{r.account_name ?? r.iban}</strong>
								{#if r.account_created}<span class="badge accent">{t('import.newAccount')}</span>{/if}
								{#if r.skipped}
									<span class="muted small">{r.skipped}</span>
								{:else}
									<div class="stats">
										<span><b>{r.rows_imported}</b> {t('import.new')}</span>
										<span><b>{r.rows_duplicate}</b> {t('import.duplicate')}</span>
										<span><b>{r.rows_categorized}</b> {t('import.byRule')}</span>
										{#if r.since}<span>{t('bank.from', { date: day(r.since) })}</span>{/if}
									</div>
								{/if}
							</div>
						</div>
					{/each}
					<div class="row">
						<a href="/transactions?uncategorized=1">{t('import.categorize')} →</a>
						<button class="ghost" onclick={close}>{t('common.close')}</button>
					</div>
				{/if}
			</div>
		{/if}
	{/each}

	{#if status?.enabled}
		{#if adding}
			<form class="row add" onsubmit={addConnection}>
				<label>{t('common.name')} <input bind:value={form.name} required /></label>
				<label
					>{t('bank.loginNumber')}
					<input bind:value={form.login} required autocomplete="off" placeholder={t('bank.loginPlaceholder')} />
				</label>
				<button>{t('bank.saveLogin')}</button>
				{#if connections.length}<button type="button" class="ghost" onclick={() => (adding = false)}>{t('common.cancel')}</button>{/if}
			</form>
			<p class="muted small">
				{t('bank.ingHint')}
			</p>
		{:else}
			<button class="link small" onclick={() => (adding = true)}>+ {t('bank.addAnother')}</button>
		{/if}
	{/if}
</section>

<style>
	.fints {
		margin-bottom: 1.5rem;
	}
	.head {
		display: flex;
		gap: 0.9rem;
		align-items: center;
		margin-bottom: 1rem;
	}
	.head h2 {
		margin: 0;
		font-size: 1.05rem;
	}
	.head p {
		margin: 0.1rem 0 0;
	}
	.icon {
		display: grid;
		place-items: center;
		width: 2.6rem;
		height: 2.6rem;
		border-radius: 14px;
		background: var(--gradient);
		color: #fff;
		flex: none;
	}
	.conn {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.75rem;
		padding: 0.85rem 0;
		border-top: 1px solid var(--border);
	}
	.who {
		display: flex;
		flex-direction: column;
		/* Grow next to the buttons, but wrap them below before getting squeezed */
		flex: 1 1 16rem;
		min-width: 0;
	}
	.accounts {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.actions {
		flex-wrap: wrap;
	}
	.err {
		color: var(--expense);
	}
	.actions {
		display: flex;
		gap: 0.5rem;
		align-items: center;
	}
	.sync {
		padding: 0.25rem 0 1rem;
	}
	.sync form :global(.pw) {
		width: 11rem;
	}
	.sync form :global(.select-trigger) {
		min-width: 10rem;
	}
	.tan {
		display: flex;
		align-items: flex-start;
		gap: 1rem;
		padding: 1rem;
		border-radius: var(--radius-sm);
		background: var(--surface-2);
	}
	.tan {
		flex-wrap: wrap;
	}
	.tan > div {
		flex: 1;
		min-width: min(13rem, 100%);
		overflow-wrap: anywhere;
	}
	.tan p {
		margin: 0.25rem 0 0.5rem;
		white-space: pre-line;
	}
	.tan img {
		max-width: 220px;
		margin: 0.5rem 0;
		border-radius: 8px;
		background: #fff;
	}
	.pulse,
	.spin {
		display: grid;
		place-items: center;
		width: 3rem;
		height: 3rem;
		border-radius: 999px;
		background: var(--accent-soft);
		color: var(--accent-strong);
		flex: none;
	}
	.pulse {
		animation: pulse 1.6s ease-in-out infinite;
	}
	.spin :global(svg) {
		animation: spin 1s linear infinite;
	}
	@keyframes pulse {
		50% {
			box-shadow: 0 0 0 10px transparent;
			transform: scale(1.06);
		}
		0%,
		100% {
			box-shadow: 0 0 0 0 color-mix(in srgb, var(--accent) 35%, transparent);
		}
	}
	@keyframes spin {
		to {
			transform: rotate(360deg);
		}
	}
	.result {
		display: flex;
		align-items: flex-start;
		gap: 0.75rem;
		margin-bottom: 0.75rem;
	}
	.result .info {
		flex: 1;
		min-width: 0;
	}
	.ok-icon {
		display: grid;
		place-items: center;
		width: 2rem;
		height: 2rem;
		border-radius: 999px;
		background: var(--accent-soft);
		color: var(--accent-strong);
		flex: none;
	}
	.stats {
		display: flex;
		flex-wrap: wrap;
		gap: 0.3rem 1.1rem;
		font-size: 0.87rem;
		color: var(--muted);
	}
	.stats b {
		color: var(--text);
	}
	.add {
		padding-top: 0.85rem;
		border-top: 1px solid var(--border);
	}
	.add + p {
		margin-bottom: 0;
	}
</style>
