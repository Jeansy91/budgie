<!--
	Column assignment for a CSV export Budgie does not recognize yet.
	Shows the first rows of the file and lets the user say which column is what.
-->
<script lang="ts">
	import { RadioGroup, Select, type SelectOption } from '$lib/ui';
	import type { CsvField, CsvPreview } from '$lib/types';
	import Columns3 from '@lucide/svelte/icons/columns-3';
	import { untrack } from 'svelte';
	import { t } from '$lib/i18n/index.svelte';

	let {
		filename,
		preview,
		busy = false,
		onsubmit,
		oncancel
	}: {
		filename: string;
		preview: CsvPreview;
		busy?: boolean;
		onsubmit: (mapping: object, saveAs: string) => void;
		oncancel: () => void;
	} = $props();

	const fields: { key: CsvField; required?: boolean }[] = [
		{ key: 'booking_date', required: true },
		{ key: 'value_date' },
		{ key: 'payee' },
		{ key: 'purpose' },
		{ key: 'booking_text' },
		{ key: 'amount' },
		{ key: 'debit' },
		{ key: 'credit' },
		{ key: 'balance' },
		{ key: 'counterparty_iban' }
	];
	const fieldLabel = (key: CsvField) => t(`csv.field.${key}`);

	const columnOptions = $derived<SelectOption<string>[]>([
		{ value: '', label: t('csv.notPresent') },
		...preview.columns.map((c, i) => ({ value: String(i), label: c.trim() || t('csv.column', { n: String(i + 1) }) }))
	]);

	// Starts from Budgie's guess; the parent re-creates the component for the next file.
	// Select works with strings; '' = not mapped.
	const initial = untrack(() => preview.suggestion);
	let chosen = $state<Record<CsvField, string>>(
		Object.fromEntries(
			fields.map((f) => [f.key, initial.columns[f.key] !== undefined ? String(initial.columns[f.key]) : ''])
		) as Record<CsvField, string>
	);
	let dateFormat = $state(initial.date_format);
	let decimal = $state<'comma' | 'point'>(initial.decimal);
	let saveAs = $state('');

	const dateOptions: SelectOption<string>[] = [
		{ value: 'dd.mm.yyyy', label: '31.12.2026' },
		{ value: 'dd.mm.yy', label: '31.12.26' },
		{ value: 'yyyy-mm-dd', label: '2026-12-31' },
		{ value: 'dd/mm/yyyy', label: '31/12/2026' },
		{ value: 'mm/dd/yyyy', label: '12/31/2026' }
	];
	const decimalOptions: SelectOption<'comma' | 'point'>[] = [
		{ value: 'comma', label: '1.234,56' },
		{ value: 'point', label: '1,234.56' }
	];

	const hasAmount = $derived(chosen.amount !== '' || chosen.debit !== '' || chosen.credit !== '');
	const valid = $derived(chosen.booking_date !== '' && hasAmount);
	const mappedIndexes = $derived(new Set(Object.values(chosen).filter((v) => v !== '').map(Number)));

	function submit(e: SubmitEvent) {
		e.preventDefault();
		if (!valid) return;
		const columns = Object.fromEntries(
			Object.entries(chosen)
				.filter(([, v]) => v !== '')
				.map(([k, v]) => [k, Number(v)])
		);
		onsubmit(
			{ delimiter: preview.delimiter, header_row: preview.header_row, columns, date_format: dateFormat, decimal },
			saveAs.trim()
		);
	}
</script>

<form class="card mapping" onsubmit={submit}>
	<div class="head">
		<span class="icon"><Columns3 size={20} /></span>
		<div>
			<h2>{t('csv.title')}</h2>
			<p class="muted small break-anywhere">
				{t('csv.introBefore')} <strong>{filename}</strong> {t('csv.introAfter')}
			</p>
		</div>
	</div>

	<div class="table-wrap">
		<table>
			<thead>
				<tr>
					{#each preview.columns as c, i (i)}<th class:unmapped={!mappedIndexes.has(i)}>{c}</th>{/each}
				</tr>
			</thead>
			<tbody>
				{#each preview.rows as row, r (r)}
					<tr>
						{#each preview.columns as _, i (i)}<td class:unmapped={!mappedIndexes.has(i)}>{row[i] ?? ''}</td>{/each}
					</tr>
				{/each}
			</tbody>
		</table>
	</div>

	<div class="grid">
		{#each fields as f (f.key)}
			<div class="field">
				<span>{fieldLabel(f.key)}{#if f.required}<span class="req"> *</span>{/if}</span>
				<Select options={columnOptions} bind:value={chosen[f.key]} label={fieldLabel(f.key)} />
			</div>
		{/each}
		<div class="field">
			<span>{t('csv.dateFormat')}</span>
			<Select options={dateOptions} bind:value={dateFormat} label={t('csv.dateFormat')} />
		</div>
		<div class="field">
			<span>{t('csv.numberFormat')}</span>
			<RadioGroup options={decimalOptions} bind:value={decimal} label={t('csv.numberFormat')} />
		</div>
	</div>
	{#if !hasAmount}
		<p class="muted small">{t('csv.needAmount')}</p>
	{/if}

	<div class="row save">
		<label class="grow"
			>{t('csv.saveAs')}
			<input bind:value={saveAs} maxlength="100" placeholder={t('csv.saveAsPlaceholder')} />
		</label>
	</div>
	<p class="muted small">{t('csv.saveAsHint')}</p>

	<div class="row">
		<button disabled={!valid || busy}>{busy ? t('import.importing') : t('csv.import')}</button>
		<button type="button" class="ghost" onclick={oncancel}>{t('common.cancel')}</button>
	</div>
</form>

<style>
	.mapping {
		display: flex;
		flex-direction: column;
		gap: 1rem;
		margin-bottom: 1.5rem;
	}
	.mapping p {
		margin: 0;
	}
	.head {
		display: flex;
		gap: 0.9rem;
		align-items: center;
	}
	.head h2 {
		margin: 0;
		font-size: 1.05rem;
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
	.table-wrap {
		overflow-x: auto;
		border: 1px solid var(--border);
		border-radius: var(--radius-sm);
	}
	table {
		border-collapse: collapse;
		font-size: 0.82rem;
		min-width: 100%;
	}
	th,
	td {
		padding: 0.45rem 0.65rem;
		text-align: left;
		white-space: nowrap;
		max-width: 16rem;
		overflow: hidden;
		text-overflow: ellipsis;
		border-bottom: 1px solid var(--border);
	}
	th {
		background: var(--surface-2);
		font-weight: 600;
	}
	tr:last-child td {
		border-bottom: 0;
	}
	/* Columns nobody assigned yet are dimmed */
	.unmapped {
		opacity: 0.45;
	}
	.grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(min(15rem, 100%), 1fr));
		gap: 0.85rem 1rem;
	}
	.grid :global(.select-trigger) {
		width: 100%;
	}
	.req {
		color: var(--expense);
	}
	.grow {
		flex: 1 1 18rem;
	}
	.grow input {
		width: 100%;
	}
</style>
