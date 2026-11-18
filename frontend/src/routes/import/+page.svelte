<script lang="ts">
	import { api } from '$lib/api';
	import { MiddleTruncate, Select, type SelectOption } from '$lib/ui';
	import BankSync from '$lib/BankSync.svelte';
	import { iban, money } from '$lib/format';
	import { t } from '$lib/i18n/index.svelte';
	import type { Account, ImportResult } from '$lib/types';
	import Upload from '@lucide/svelte/icons/upload';
	import Landmark from '@lucide/svelte/icons/landmark';
	import CircleAlert from '@lucide/svelte/icons/circle-alert';
	import Check from '@lucide/svelte/icons/check';

	let accounts = $state<Account[]>([]);
	let accountOptions = $derived<SelectOption<string>[]>([
		{ value: '', label: t('import.autoAccount') },
		...accounts.map((a) => ({ value: String(a.id), label: a.name, hint: a.iban ? '…' + a.iban.slice(-4) : undefined }))
	]);
	let accountId = $state('');
	let results = $state<{ name: string; result?: ImportResult; error?: string }[]>([]);
	let busy = $state(false);
	let dragging = $state(false);
	let input: HTMLInputElement;

	const loadAccounts = () => api<Account[]>('/accounts').then((a) => (accounts = a));
	loadAccounts();

	async function upload(files: FileList | File[]) {
		if (!files.length) return;
		busy = true;
		results = [];
		for (const file of files) {
			const form = new FormData();
			form.append('file', file);
			if (accountId) form.append('account_id', accountId);
			try {
				results.push({ name: file.name, result: await api<ImportResult>('/imports/ing-csv', { method: 'POST', form }) });
			} catch (err) {
				results.push({ name: file.name, error: (err as Error).message });
			}
		}
		busy = false;
		input.value = '';
		await loadAccounts();
	}
</script>

<div class="page-head">
	<div>
		<span class="eyebrow">{t('import.eyebrow')}</span>
		<h1>{t('import.title')}</h1>
		<p>{t('import.intro')}</p>
	</div>
</div>

<BankSync onsynced={loadAccounts} />

<h2 class="section first">{t('import.csvTitle')}</h2>
<p class="muted small hint">{t('import.csvHint')}</p>

<label
	class="drop"
	class:dragging
	class:busy
	ondragover={(e) => {
		e.preventDefault();
		dragging = true;
	}}
	ondragleave={() => (dragging = false)}
	ondrop={(e) => {
		e.preventDefault();
		dragging = false;
		if (e.dataTransfer?.files) upload(e.dataTransfer.files);
	}}
>
	<span class="icon"><Upload size={26} /></span>
	<strong>{busy ? t('import.importing') : t('import.drop')}</strong>
	<span class="muted">{t('import.orClick')}</span>
	<input
		bind:this={input}
		type="file"
		accept=".csv,text/csv"
		multiple
		onchange={(e) => e.currentTarget.files && upload(e.currentTarget.files)}
		disabled={busy}
	/>
</label>

<div class="target">
	<span class="muted">{t('import.into')}</span>
	<Select options={accountOptions} bind:value={accountId} label={t('common.account')} />
</div>

{#each results as r (r.name)}
	{#if r.error}
		<div class="error"><CircleAlert size={18} /> <span><strong class="break-anywhere">{r.name}:</strong> {r.error}</span></div>
	{:else if r.result}
		<div class="card result">
			<span class="ok-icon"><Check size={18} /></span>
			<div class="info">
				<strong class="file"><MiddleTruncate text={r.name} /></strong>
				{#if r.result.account_created}<span class="badge accent">{t('import.newAccount')}</span>{/if}
				<div class="stats">
					<span><b>{r.result.rows_imported}</b> {t('import.new')}</span>
					<span><b>{r.result.rows_duplicate}</b> {t('import.duplicate')}</span>
					<span><b>{r.result.rows_categorized}</b> {t('import.byRule')}</span>
				</div>
			</div>
			<a class="go" href="/transactions?uncategorized=1">{t('import.categorize')} →</a>
		</div>
	{/if}
{/each}

{#if accounts.length}
	<h2 class="section">{t('import.accounts')}</h2>
	<div class="accounts">
		{#each accounts as a (a.id)}
			<div class="card acc">
				<span class="bank"><Landmark size={20} /></span>
				<div class="who">
					<strong class="clamp-2" title={a.name}>{a.name}</strong>
					<span class="muted small">{a.iban ? iban(a.iban) : t('import.noIban')}</span>
				</div>
				<div class="bal">
					<span class="amount">{a.balance === null ? '–' : money(a.balance)}</span>
					<span class="muted small">{t('transactions.count', { count: a.transaction_count })}</span>
				</div>
			</div>
		{/each}
	</div>
{/if}

<style>
	.drop {
		position: relative;
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 0.4rem;
		padding: 2.75rem 1rem;
		border: 2px dashed var(--border);
		border-radius: var(--radius);
		background: var(--surface);
		color: var(--text);
		font-size: 1rem;
		cursor: pointer;
		transition:
			border-color 0.15s,
			background 0.15s;
	}
	.drop:hover,
	.drop.dragging {
		border-color: var(--accent);
		background: color-mix(in srgb, var(--accent-soft) 50%, var(--surface));
	}
	.drop.busy {
		opacity: 0.7;
	}
	.drop input {
		position: absolute;
		inset: 0;
		opacity: 0;
		cursor: pointer;
	}
	.icon {
		display: grid;
		place-items: center;
		width: 3.5rem;
		height: 3.5rem;
		border-radius: 18px;
		background: var(--gradient);
		color: #fff;
		margin-bottom: 0.4rem;
		box-shadow: 0 8px 20px rgb(16 185 129 / 0.3);
	}
	.target {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.5rem 0.75rem;
		margin: 1rem 0 1.5rem;
		font-size: 0.9rem;
	}
	.target :global(.select-trigger) {
		min-width: min(16rem, 100%);
	}
	.result {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.5rem 1rem;
	}
	.result .info {
		flex: 1 1 14rem;
		min-width: 0;
	}
	.file {
		display: block;
	}
	.go {
		flex: none;
		white-space: nowrap;
		margin-left: auto;
	}
	.ok-icon {
		display: grid;
		place-items: center;
		width: 2.4rem;
		height: 2.4rem;
		border-radius: 999px;
		background: var(--accent-soft);
		color: var(--accent-strong);
		flex: none;
	}
	.stats {
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem 1.2rem;
		font-size: 0.87rem;
		color: var(--muted);
		margin-top: 0.2rem;
	}
	.stats b {
		color: var(--text);
	}
	.section {
		margin-top: 2rem;
	}
	.section.first {
		margin-top: 0;
		margin-bottom: 0.25rem;
	}
	.hint {
		margin: 0 0 0.85rem;
	}
	.accounts {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(min(300px, 100%), 1fr));
		gap: 1rem;
	}
	.acc {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.4rem 0.9rem;
		margin: 0;
		container-type: inline-size;
	}
	.acc > div {
		display: flex;
		flex-direction: column;
	}
	.acc .who {
		flex: 1;
		min-width: 0;
	}
	.bal {
		flex: none;
		text-align: right;
		align-items: end;
	}
	/* Narrow cards: give the name the full width and put the balance below it */
	@container (max-width: 420px) {
		.acc > .bal {
			flex: 1 0 100%;
			flex-direction: row;
			align-items: baseline;
			gap: 0.6rem;
			padding-left: 3.5rem;
			text-align: left;
		}
	}
	.bal .amount {
		font-weight: 700;
		font-size: 1.05rem;
	}
	.bank {
		display: grid;
		place-items: center;
		width: 2.6rem;
		height: 2.6rem;
		border-radius: 14px;
		background: var(--surface-2);
		color: var(--accent-strong);
		flex: none;
	}
</style>
