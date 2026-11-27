<script lang="ts">
	import { DatePicker, PasswordInput, RadioGroup, Switch } from '#lib/ui/index.ts';
	import BankPicker from '#lib/BankPicker.svelte';
	import { onDestroy } from 'svelte';
	import { api } from '#lib/api.ts';
	import { dateTime, day } from '#lib/format.ts';
	import { t } from '#lib/i18n/index.svelte.ts';
	import type { Bank, BankConnection, FintsStatus, SyncJob } from '#lib/types.ts';
	import RefreshCw from '@lucide/svelte/icons/refresh-cw';
	import Smartphone from '@lucide/svelte/icons/smartphone';
	import KeyRound from '@lucide/svelte/icons/key-round';
	import LoaderCircle from '@lucide/svelte/icons/loader-circle';
	import CircleAlert from '@lucide/svelte/icons/circle-alert';
	import Check from '@lucide/svelte/icons/check';
	import ListChecks from '@lucide/svelte/icons/list-checks';
	import ChevronDown from '@lucide/svelte/icons/chevron-down';
	import ChevronRight from '@lucide/svelte/icons/chevron-right';
	import Clock from '@lucide/svelte/icons/clock';
	import Lock from '@lucide/svelte/icons/lock';

	let { onsynced }: { onsynced?: () => void } = $props();

	let status = $state<FintsStatus | null>(null);
	let connections = $state<BankConnection[]>([]);
	let error = $state('');

	// New connection
	let adding = $state(false);
	const emptyForm = () => ({ name: '', login: '', customer_id: '', server_url: '' });
	let bank = $state<Bank | null>(null);
	let form = $state(emptyForm());
	let advanced = $state(false);

	// Suggest name and server address when a bank is picked
	$effect(() => {
		if (!bank) return;
		form.name = bank.name.replace(/\s+(eG|AG|GmbH)$/i, '').slice(0, 100);
		form.server_url = bank.server_url ?? '';
		advanced = !bank.server_url;
	});

	// Choice of TAN mechanism or device
	let choice = $state('');
	// Sync
	let syncFor = $state<BankConnection | null>(null);
	let pin = $state('');
	let startDate = $state('');
	const today = new Date().toLocaleDateString('sv-SE'); // YYYY-MM-DD in local time
	let tan = $state('');
	let job = $state<SyncJob | null>(null);
	let timer: ReturnType<typeof setTimeout> | undefined;

	const active = $derived(job !== null && (job.state === 'running' || job.state === 'need_tan' || job.state === 'need_choice'));

	async function load() {
		status = await api<FintsStatus>('/fints/status');
		connections = await api<BankConnection[]>('/fints/connections');
		adding = status.enabled && connections.length === 0;
	}
	load().catch((e) => (error = (e as Error).message));

	async function addConnection(e: SubmitEvent) {
		e.preventDefault();
		error = '';
		if (!bank) {
			error = t('bank.chooseBankFirst');
			return;
		}
		try {
			await api('/fints/connections', {
				method: 'POST',
				body: {
					name: form.name,
					login: form.login,
					bank_code: bank.bank_code,
					server_url: form.server_url.trim() || null,
					customer_id: form.customer_id.trim() || null
				}
			});
			form = emptyForm();
			bank = null;
			advanced = false;
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

	async function resetTanMechanism(c: BankConnection) {
		error = '';
		try {
			await api(`/fints/connections/${c.id}`, { method: 'PATCH', body: { reset_tan_mechanism: true } });
			await load();
		} catch (err) {
			error = (err as Error).message;
		}
	}

	async function sendChoice(e: SubmitEvent) {
		e.preventDefault();
		if (!job || !choice) return;
		try {
			job = await api<SyncJob>(`/fints/jobs/${job.id}/choice`, { method: 'POST', body: { option: choice } });
			choice = '';
		} catch (err) {
			error = (err as Error).message;
		}
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
		if (job.state === 'need_choice' && !job.options.some((o) => o.id === choice)) {
			choice = (job.options.find((o) => o.decoupled) ?? job.options[0])?.id ?? '';
		}
		if (job.state === 'running' || job.state === 'need_tan' || job.state === 'need_choice') {
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

	// Automatic fetch
	const INTERVALS = [6, 12, 24];
	const intervalOptions = INTERVALS.map((h) => ({ value: h, label: t('bank.auto.every', { hours: h }) }));
	const pausedText = {
		tan_required: 'bank.auto.paused.tan_required',
		pin_rejected: 'bank.auto.paused.pin_rejected',
		locked: 'bank.auto.paused.locked',
		manual_sync_required: 'bank.auto.paused.manual_sync_required'
	} as const;
	// Connection for which the "turn on" form is open
	let autoFor = $state<number | null>(null);
	let autoPin = $state('');
	let autoInterval = $state(12);

	async function patchAuto(c: BankConnection, body: Record<string, unknown>) {
		error = '';
		try {
			await api(`/fints/connections/${c.id}`, { method: 'PATCH', body });
			autoFor = null;
			await load();
		} catch (err) {
			error = (err as Error).message;
		} finally {
			// Do not keep the PIN in the browser
			autoPin = '';
		}
	}

	function toggleAuto(c: BankConnection, on: boolean) {
		if (on) {
			autoFor = c.id;
			autoPin = '';
			autoInterval = c.auto_sync_interval_hours;
		} else if (autoFor === c.id && !c.auto_sync_enabled) {
			autoFor = null;
		} else {
			// Turning off also deletes the stored PIN on the server
			patchAuto(c, { auto_sync_enabled: false });
		}
	}

	function enableAuto(e: SubmitEvent, c: BankConnection) {
		e.preventDefault();
		patchAuto(c, { auto_sync_enabled: true, auto_sync_interval_hours: autoInterval, pin: autoPin });
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
					<span class="muted small accounts" title={c.accounts.map((a) => a.name).join(', ')}>
						{c.accounts.map((a) => a.name).join(', ')}
					</span>
				{/if}
				{#if c.last_error && syncFor?.id !== c.id && !c.auto_sync_paused_reason}<span class="small err break-anywhere">
						{c.last_error}
					</span>{/if}
			</div>
			{#if syncFor?.id !== c.id}
				<div class="actions">
					<button onclick={() => openSync(c)} disabled={!status?.enabled}>{t('bank.sync')}</button>
					{#if c.tan_mechanism_name}
						<button class="ghost small" onclick={() => resetTanMechanism(c)} title={t('bank.changeTanTitle')}>{t('bank.changeTan')}</button>
					{/if}
					<button class="ghost small" onclick={() => removeConnection(c)}>{t('bank.remove')}</button>
				</div>
			{/if}
		</div>

		{#if status?.enabled && syncFor?.id !== c.id}
			{@const needsPin = c.auto_sync_enabled && !c.has_stored_pin}
			{@const formOpen = autoFor === c.id || needsPin}
			<div class="auto">
				<div class="auto-head">
					<Switch checked={c.auto_sync_enabled || autoFor === c.id} label={t('bank.auto.title')} onchange={(on) => toggleAuto(c, on)}>
						<strong>{t('bank.auto.title')}</strong>
					</Switch>
					{#if c.auto_sync_enabled && c.has_stored_pin}
						<span class="muted small stamp">
							<Clock size={14} />
							{#if c.auto_sync_paused_reason}
								{t('bank.auto.last', { when: when(c.last_sync_at) })}
							{:else if c.next_auto_sync_at}
								{t('bank.auto.next', { when: when(c.next_auto_sync_at) })} · {t('bank.auto.last', { when: when(c.last_sync_at) })}
							{/if}
						</span>
					{/if}
				</div>
				{#if c.auto_sync_enabled && c.auto_sync_paused_reason}
					<div class="warn">
						<CircleAlert size={18} />
						<span>{t(pausedText[c.auto_sync_paused_reason])}</span>
					</div>
				{/if}
				{#if c.auto_sync_enabled && c.has_stored_pin}
					<RadioGroup
						options={intervalOptions}
						value={c.auto_sync_interval_hours}
						label={t('bank.auto.interval')}
						onchange={(h) => patchAuto(c, { auto_sync_interval_hours: h })}
					/>
				{/if}
				{#if formOpen}
					<form class="auto-form" onsubmit={(e) => enableAuto(e, c)}>
						{#if !c.tan_mechanism_name}<p class="muted small">{t('bank.auto.enableFirstHint')}</p>{/if}
						<div class="row">
							<label>
								{t('bank.auto.pin')}
								<PasswordInput bind:value={autoPin} required autocomplete="off" inputmode="numeric" />
							</label>
							{#if !needsPin}
								<div class="field">
									<span>{t('bank.auto.interval')}</span>
									<RadioGroup options={intervalOptions} bind:value={autoInterval} label={t('bank.auto.interval')} />
								</div>
							{/if}
							<button>{needsPin ? t('bank.auto.savePin') : t('bank.auto.enable')}</button>
							{#if !needsPin}
								<button type="button" class="ghost" onclick={() => (autoFor = null)}>{t('common.cancel')}</button>
							{/if}
						</div>
						<p class="muted small note"><Lock size={14} /> {t('bank.auto.pinNote')}</p>
					</form>
				{/if}
			</div>
		{/if}

		{#if syncFor?.id === c.id}
			<div class="sync">
				{#if !job}
					<form class="row" onsubmit={startSync}>
						<label>
							{t('bank.pin')}
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
				{:else if job.state === 'need_choice'}
					<div class="tan">
						<span class="pulse"><ListChecks size={24} /></span>
						<form onsubmit={sendChoice}>
							<strong>{job.choice_kind === 'tan_medium' ? t('bank.chooseMedium') : t('bank.chooseMechanism')}</strong>
							<p class="muted small">
								{job.choice_kind === 'tan_medium' ? t('bank.chooseMediumHint') : t('bank.chooseMechanismHint')}
							</p>
							<RadioGroup
								variant="list"
								label={job.choice_kind === 'tan_medium' ? t('bank.tanMedium') : t('bank.tanMechanism')}
								options={job.options.map((o) => ({
									value: o.id,
									label: o.decoupled ? `${o.name} (${t('bank.appApproval')})` : o.name
								}))}
								bind:value={choice}
							/>
							<div class="row choice-actions">
								<button disabled={!choice}>{t('bank.continue')}</button>
								<button type="button" class="ghost" onclick={cancel}>{t('common.cancel')}</button>
							</div>
						</form>
					</div>
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
							{#if job.challenge_hhduc && !job.challenge_image}
								<p class="muted small">
									{t('bank.flickerCode')} <code class="break-anywhere">{job.challenge_hhduc}</code>
								</p>
							{/if}
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
			<form class="add" onsubmit={addConnection}>
				<div class="field">
					<span>{t('bank.bank')}</span>
					<BankPicker bind:value={bank} />
				</div>
				{#if bank}
					<div class="row">
						<label>{t('common.name')} <input bind:value={form.name} required maxlength="100" /></label>
						<label>
							{t('bank.loginName')}
							<input
								bind:value={form.login}
								required
								autocomplete="off"
								placeholder={t('bank.loginNamePlaceholder')}
								title={t('bank.loginNameTitle')}
							/>
						</label>
					</div>
					<button type="button" class="link small toggle" onclick={() => (advanced = !advanced)} aria-expanded={advanced}>
						{t('bank.advanced')}
						{#if advanced}<ChevronDown size={16} />{:else}<ChevronRight size={16} />{/if}
					</button>
					{#if advanced}
						<div class="row">
							<label class="grow">
								{t('bank.serverUrl')}
								<input bind:value={form.server_url} type="url" placeholder="https://…" required={!bank.server_url} />
							</label>
							<label>
								{t('bank.customerId')}
								<input bind:value={form.customer_id} autocomplete="off" placeholder={t('common.optional')} />
							</label>
						</div>
						{#if !bank.server_url}
							<p class="muted small">
								{t('bank.noServerUrl')}
							</p>
						{/if}
					{/if}
					<div class="row">
						<button>{t('bank.saveLogin')}</button>
						{#if connections.length}<button type="button" class="ghost" onclick={() => (adding = false)}>{t('common.cancel')}</button>{/if}
					</div>
					<p class="muted small">{t('bank.encryptedHint')}</p>
				{:else if connections.length}
					<button type="button" class="ghost" onclick={() => (adding = false)}>{t('common.cancel')}</button>
				{/if}
			</form>
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
	.auto {
		display: flex;
		flex-direction: column;
		align-items: flex-start;
		gap: 0.6rem;
		padding: 0.2rem 0 1rem;
	}
	.auto :global(.warn) {
		align-self: stretch;
		margin: 0;
	}
	.auto-head {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.4rem 1rem;
	}
	.stamp {
		display: inline-flex;
		align-items: center;
		gap: 0.3rem;
	}
	.auto-form {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		width: 100%;
	}
	.auto-form p {
		margin: 0;
	}
	.auto-form :global(.pw) {
		width: 11rem;
	}
	.note {
		display: flex;
		align-items: flex-start;
		gap: 0.35rem;
	}
	.note :global(svg) {
		flex: none;
		margin-top: 0.15rem;
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
	.add {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
	}
	.add p {
		margin: 0;
	}
	.add .grow {
		flex: 1 1 18rem;
	}
	.add .grow input {
		width: 100%;
	}
	.toggle {
		align-self: flex-start;
		display: inline-flex;
		align-items: center;
		gap: 0.25rem;
	}
	.toggle :global(svg) {
		flex: none;
	}
	.add > button.ghost {
		align-self: flex-start;
	}
	.tan form {
		flex: 1;
		min-width: min(13rem, 100%);
	}
	.choice-actions {
		margin-top: 0.75rem;
	}
</style>
