<!--
	Detail view of a single transaction.
	Desktop: side panel on the right. Mobile (narrower than 760 px): bottom sheet.
	Shows every stored field and offers the actions that belong to one
	transaction: change the category, override the budget month, edit the note
	and create a rule from it.
-->
<script lang="ts">
	import { onMount } from 'svelte';
	import { api } from './api';
	import CategorySelect from './CategorySelect.svelte';
	import { RadioGroup, Select, Switch, type SelectOption } from './ui';
	import { avatarColor, initials } from './colors';
	import { categoryLabels, dateFormat, dateTime, day, money, monthLabel, percent, shiftMonth } from './format';
	import { t } from './i18n/index.svelte';
	import type { Category, Rule, Transaction, TransactionDetail } from './types';
	import X from '@lucide/svelte/icons/x';
	import Check from '@lucide/svelte/icons/check';
	import Hand from '@lucide/svelte/icons/hand';
	import WandSparkles from '@lucide/svelte/icons/wand-sparkles';
	import Sparkles from '@lucide/svelte/icons/sparkles';
	import Bot from '@lucide/svelte/icons/bot';
	import Info from '@lucide/svelte/icons/info';
	import Plus from '@lucide/svelte/icons/plus';
	import CloudDownload from '@lucide/svelte/icons/cloud-download';
	import FileSpreadsheet from '@lucide/svelte/icons/file-spreadsheet';

	let {
		id,
		categories,
		onclose,
		onchange,
		onreload
	}: {
		id: number;
		categories: Category[];
		onclose: () => void;
		/** The transaction changed (category, budget month, note) */
		onchange?: (tx: Transaction) => void;
		/** Other transactions may have changed too (a rule was applied) */
		onreload?: () => void;
	} = $props();

	let tx = $state<TransactionDetail | null>(null);
	let error = $state('');
	let notice = $state('');
	let note = $state('');
	let panel = $state<HTMLElement>();
	let labels = $derived(categoryLabels(categories));

	async function load() {
		try {
			tx = await api<TransactionDetail>(`/transactions/${id}`);
			note = tx.note;
			error = '';
		} catch (e) {
			error = (e as Error).message;
		}
	}

	$effect(() => {
		void id;
		tx = null;
		notice = '';
		ruleOpen = false;
		load();
	});

	onMount(() => {
		panel?.focus();
		// The page behind the panel must not scroll on mobile
		const prev = document.body.style.overflow;
		document.body.style.overflow = 'hidden';
		return () => (document.body.style.overflow = prev);
	});

	function onkeydown(e: KeyboardEvent) {
		if (e.key !== 'Escape') return;
		// A dropdown of the panel is open: let it close first
		if (document.querySelector('body > .layer')) return;
		onclose();
	}

	async function patch(body: Record<string, unknown>) {
		if (!tx) return;
		try {
			const res = await api<{ transaction: Transaction }>(`/transactions/${tx.id}`, { method: 'PATCH', body });
			Object.assign(tx, res.transaction);
			if (res.transaction.category_source !== 'rule') tx.rule = null;
			onchange?.(res.transaction);
			error = '';
		} catch (e) {
			error = (e as Error).message;
		}
	}

	// --- Category -----------------------------------------------------------
	const pct = percent;
	let isAi = $derived(tx?.category_source === 'model' || tx?.category_source === 'llm');
	const fieldLabel = (field: Rule['field']) => t(`rules.field.${field}`);
	const matchLabel = (match: Rule['match_type']) => t(`rules.match.${match}`);

	// --- Budget month -------------------------------------------------------
	let bookingMonth = $derived(tx ? tx.booking_date.slice(0, 7) : '');
	let budgetMonth = $derived(tx ? tx.budget_date.slice(0, 7) : '');
	let budgetValue = $derived<'auto' | 'same' | 'next'>(tx?.budget_shift ?? 'auto');
	let budgetOptions = $derived<SelectOption<'auto' | 'same' | 'next'>[]>(
		tx
			? [
					{ value: 'auto', label: t('budgetMenu.auto') },
					{ value: 'same', label: `${monthLabel(bookingMonth)} (${t('detail.bookingMonthNote')})` },
					{ value: 'next', label: `${monthLabel(shiftMonth(bookingMonth, 1))} (${t('detail.nextMonthNote')})` }
				]
			: []
	);

	// --- Note ---------------------------------------------------------------
	function saveNote() {
		if (tx && note !== tx.note) patch({ note });
	}

	// --- Rule from this transaction ------------------------------------------
	let ruleOpen = $state(false);
	let rule = $state({
		field: 'payee' as Rule['field'],
		match_type: 'contains' as Rule['match_type'],
		pattern: '',
		category_id: null as number | null,
		apply: true
	});
	let fieldOptions = $derived<SelectOption<Rule['field']>[]>(
		(['payee', 'purpose', 'any'] as const).map((value) => ({ value, label: fieldLabel(value) }))
	);
	let matchOptions = $derived<SelectOption<Rule['match_type']>[]>(
		(['contains', 'equals', 'starts_with', 'regex'] as const).map((value) => ({ value, label: matchLabel(value) }))
	);
	const defaultPattern = (field: Rule['field']) => (!tx ? '' : field === 'purpose' ? tx.purpose : tx.payee || tx.purpose);

	function openRule() {
		if (!tx) return;
		rule = {
			field: tx.payee ? 'payee' : 'purpose',
			match_type: 'contains',
			pattern: '',
			category_id: tx.category_id ?? tx.suggested_category_id,
			apply: true
		};
		rule.pattern = defaultPattern(rule.field);
		ruleOpen = true;
	}

	let previousField: Rule['field'] = 'payee';
	function changeField(field: Rule['field']) {
		// Swap the prefilled text along with the field, unless it was edited
		if (rule.pattern === defaultPattern(previousField)) rule.pattern = defaultPattern(field);
		previousField = field;
	}

	/** Same matching as the backend (app/rules.py), for a live hint. */
	let ruleMatchesThis = $derived.by(() => {
		if (!tx) return false;
		const pattern = rule.pattern.trim();
		if (!pattern) return false;
		const texts = rule.field === 'payee' ? [tx.payee] : rule.field === 'purpose' ? [tx.purpose] : [tx.payee, tx.purpose];
		const norm = (s: string) => s.split(/\s+/).filter(Boolean).join(' ').toLocaleLowerCase('de');
		return texts.some((text) => {
			if (rule.match_type === 'regex') {
				try {
					return new RegExp(pattern, 'i').test(text);
				} catch {
					return false;
				}
			}
			const a = norm(text);
			const b = norm(pattern);
			if (rule.match_type === 'contains') return a.includes(b);
			if (rule.match_type === 'equals') return a === b;
			return a.startsWith(b);
		});
	});

	async function createRule(e: SubmitEvent) {
		e.preventDefault();
		if (!tx || rule.category_id === null) return;
		try {
			const { apply, ...body } = rule;
			const created = await api<Rule>('/rules', {
				method: 'POST',
				body,
				params: { apply: apply ? undefined : 'false' }
			});
			ruleOpen = false;
			notice = apply ? t('rules.created', { count: created.match_count }) : t('detail.ruleCreatedLater');
			error = '';
			await load();
			if (tx) onchange?.(tx);
			onreload?.();
		} catch (err) {
			error = (err as Error).message;
		}
	}

	// --- Formatting -----------------------------------------------------------
	const iban = (v: string) => v.replace(/(.{4})/g, '$1 ').trim();
	let longDay = $derived(dateFormat({ weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' }));
	let counterpartLabel = $derived(tx && Number(tx.amount) > 0 ? t('detail.payer') : t('detail.payee'));
	let hasSepa = $derived(!!tx && !!(tx.counterparty_iban || tx.counterparty_bic || tx.mandate_id || tx.creditor_id || tx.end_to_end_ref));
	let sourceName = $derived(
		!tx?.import_batch ? t('detail.sourceUnknown') : tx.import_batch.source === 'fints' ? t('detail.sourceFints') : t('detail.sourceCsv')
	);
</script>

<svelte:window {onkeydown} />

<div class="tx-layer">
	<button class="backdrop" type="button" tabindex="-1" aria-label={t('detail.closeDetails')} onclick={onclose}></button>
	<div class="panel" role="dialog" aria-modal="true" aria-labelledby="tx-detail-title" tabindex="-1" bind:this={panel}>
		<div class="grip" aria-hidden="true"></div>
		<header>
			{#if tx}
				<span class="avatar" style:background={avatarColor(tx.payee || tx.booking_text)}>
					{initials(tx.payee || tx.booking_text)}
				</span>
				<div class="title">
					<h2 id="tx-detail-title">{tx.payee || tx.booking_text || t('detail.transaction')}</h2>
					<span class="sub">{longDay.format(new Date(tx.booking_date + 'T12:00:00'))}</span>
				</div>
			{:else}
				<div class="title"><h2 id="tx-detail-title">{t('detail.transaction')}</h2></div>
			{/if}
			<button class="ghost icon close" type="button" onclick={onclose} aria-label={t('common.close')} title={t('detail.closeEsc')}>
				<X size={20} />
			</button>
		</header>

		<div class="body">
			{#if error}<div class="error">{error}</div>{/if}
			{#if notice}<div class="ok"><Sparkles size={18} /> {notice}</div>{/if}

			{#if !tx}
				{#if !error}<div class="loading" aria-busy="true"><span></span><span></span><span></span></div>{/if}
			{:else}
				<div class="hero">
					<span class="big amount" class:pos={Number(tx.amount) > 0}>{money(tx.amount)}</span>
					{#if tx.booking_text}<span class="chip">{tx.booking_text}</span>{/if}
				</div>

				<!-- Category -->
				<section>
					<h3>{t('common.category')}</h3>
					<div class="cat-select">
						<CategorySelect {categories} value={tx.category_id} onchange={(v) => patch({ category_id: v })} />
					</div>
					<div class="origin" class:ai={isAi}>
						{#if tx.category_source === 'manual'}
							<Hand size={16} />
							<span>{t('detail.manual')}</span>
						{:else if tx.category_source === 'rule'}
							<WandSparkles size={16} />
							<span>
								{t('detail.byRule')}
								{#if tx.rule}
									<span class="rule-text">
										{fieldLabel(tx.rule.field)}
										{matchLabel(tx.rule.match_type)}
										{t('common.quoted', { text: tx.rule.pattern })}
									</span>
								{/if}
								<a href="/rules">{t('detail.manageRules')}</a>
							</span>
						{:else if tx.category_source === 'model'}
							<Sparkles size={16} />
							<span class="grow">
								{t('detail.byAi')}
								{#if tx.category_confidence !== null}
									<span class="meter" title={t('detail.aiConfidence')}>
										<span class="bar"><span style:width="{Math.round(tx.category_confidence * 100)}%"></span></span>
										{t('detail.confident', { confidence: pct(tx.category_confidence) })}
									</span>
								{/if}
							</span>
						{:else if tx.category_source === 'llm'}
							<Bot size={16} />
							<span class="grow">{t('source.llmTitle')}</span>
						{:else}
							<Info size={16} />
							<span>{t('detail.noCategory')}</span>
						{/if}
						{#if isAi}
							<button class="confirm" type="button" onclick={() => patch({ category_id: tx!.category_id })}>
								<Check size={15} />
								{t('detail.looksRight')}
							</button>
						{/if}
					</div>
					{#if tx.category_id === null && tx.suggested_category_id !== null}
						<button class="suggest" type="button" onclick={() => patch({ category_id: tx!.suggested_category_id })}>
							<WandSparkles size={14} />
							<span class="txt">{t('transactions.suggestion')} <strong>{labels.get(tx.suggested_category_id)}</strong></span>
							<span class="conf">{pct(tx.suggestion_confidence)}</span>
							<span class="take">{t('transactions.accept')}</span>
						</button>
					{/if}
				</section>

				<!-- Budget month -->
				<section>
					<h3>{t('budgetMenu.title')}</h3>
					<RadioGroup
						options={budgetOptions}
						value={budgetValue}
						label={t('detail.budgetMonth')}
						variant="list"
						onchange={(v) => patch({ budget_shift: v })}
					/>
					<p class="hint">
						{#if tx.budget_shift === null}
							{t('detail.autoCountsFor', { month: monthLabel(budgetMonth) })}
						{/if}
						{t('detail.budgetHint')}
					</p>
				</section>

				<!-- Purpose -->
				{#if tx.purpose}
					<section>
						<h3>{t('detail.purpose')}</h3>
						<p class="purpose">{tx.purpose}</p>
					</section>
				{/if}

				<!-- Details -->
				<section>
					<h3>{t('detail.details')}</h3>
					<dl>
						<dt>{t('detail.bookingDate')}</dt>
						<dd>{day(tx.booking_date)}</dd>
						{#if tx.value_date}
							<dt>{t('detail.valueDate')}</dt>
							<dd>{day(tx.value_date)}</dd>
						{/if}
						<dt>{t('detail.budgetMonth')}</dt>
						<dd>{monthLabel(budgetMonth)}</dd>
						{#if tx.balance_after !== null}
							<dt>{t('detail.balanceAfter')}</dt>
							<dd>{money(tx.balance_after)}</dd>
						{/if}
						{#if tx.booking_text}
							<dt>{t('detail.bookingText')}</dt>
							<dd>{tx.booking_text}</dd>
						{/if}
						{#if tx.payee}
							<dt>{counterpartLabel}</dt>
							<dd>{tx.payee}</dd>
						{/if}
						{#if tx.counterparty_iban}
							<dt>IBAN</dt>
							<dd class="mono">{iban(tx.counterparty_iban)}</dd>
						{/if}
						{#if tx.counterparty_bic}
							<dt>BIC</dt>
							<dd class="mono">{tx.counterparty_bic}</dd>
						{/if}
						{#if tx.mandate_id}
							<dt>{t('detail.mandateId')}</dt>
							<dd class="mono">{tx.mandate_id}</dd>
						{/if}
						{#if tx.creditor_id}
							<dt>{t('detail.creditorId')}</dt>
							<dd class="mono">{tx.creditor_id}</dd>
						{/if}
						{#if tx.end_to_end_ref}
							<dt>{t('detail.endToEnd')}</dt>
							<dd class="mono">{tx.end_to_end_ref}</dd>
						{/if}
						<dt>{t('common.account')}</dt>
						<dd>
							{tx.account.name}
							{#if tx.account.iban}<span class="mono faint">{iban(tx.account.iban)}</span>{/if}
						</dd>
						<dt>{t('detail.source')}</dt>
						<dd class="source">
							{#if tx.import_batch?.source === 'fints'}<CloudDownload size={15} />{:else}<FileSpreadsheet size={15} />{/if}
							<span>
								{sourceName}
								{#if tx.import_batch?.filename}<span class="faint">{tx.import_batch.filename}</span>{/if}
							</span>
						</dd>
						<dt>{t('detail.importedAt')}</dt>
						<dd>{dateTime(tx.import_batch?.created_at ?? tx.created_at)}</dd>
					</dl>
					{#if !hasSepa && tx.import_batch?.source === 'ing_csv'}
						<p class="hint">
							{t('detail.csvNoSepa')}
						</p>
					{/if}
				</section>

				<!-- Note -->
				<section>
					<h3><label for="tx-note">{t('detail.note')}</label></h3>
					<textarea id="tx-note" rows="2" placeholder={t('detail.notePlaceholder')} bind:value={note} onblur={saveNote}></textarea>
				</section>

				<!-- Rule -->
				<section>
					{#if !ruleOpen}
						<button class="secondary wide" type="button" onclick={openRule}>
							<Plus size={17} />
							{t('detail.createRule')}
						</button>
					{:else}
						<h3>{t('detail.newRule')}</h3>
						<form class="rule" onsubmit={createRule}>
							<div class="rule-row">
								<div class="field">
									{t('rules.fieldLabel')}
									<Select options={fieldOptions} bind:value={rule.field} label={t('rules.fieldLabel')} onchange={changeField} />
								</div>
								<div class="field">
									{t('rules.condition')}
									<Select options={matchOptions} bind:value={rule.match_type} label={t('rules.condition')} />
								</div>
							</div>
							<label>
								{t('rules.text')}
								<input bind:value={rule.pattern} required maxlength="255" placeholder={t('rules.textPlaceholder')} />
							</label>
							<span class="match" class:no={!ruleMatchesThis}>
								{#if ruleMatchesThis}<Check size={14} /> {t('detail.matchesThis')}{:else}<Info size={14} />
									{t('detail.notMatchesThis')}{/if}
							</span>
							<div class="field">
								{t('common.category')}
								<CategorySelect {categories} bind:value={rule.category_id} empty={t('categorySelect.choose')} />
							</div>
							<Switch bind:checked={rule.apply}>{t('detail.applyNow')}</Switch>
							<p class="hint">{t('detail.manualNeverOverwritten')}</p>
							<div class="actions">
								<button class="ghost" type="button" onclick={() => (ruleOpen = false)}>{t('common.cancel')}</button>
								<button type="submit" disabled={rule.category_id === null || !rule.pattern.trim()}>
									{t('rules.create')}
								</button>
							</div>
						</form>
					{/if}
				</section>
			{/if}
		</div>
	</div>
</div>

<style>
	.tx-layer {
		position: fixed;
		inset: 0;
		z-index: 50;
	}
	.backdrop {
		position: absolute;
		inset: 0;
		width: 100%;
		padding: 0;
		border-radius: 0;
		background: rgb(15 23 42 / 0.28);
		box-shadow: none;
		cursor: default;
		animation: fade 0.15s ease-out;
	}
	.backdrop:hover {
		filter: none;
		box-shadow: none;
	}
	.panel {
		position: absolute;
		top: 0;
		right: 0;
		bottom: 0;
		width: min(460px, 100%);
		display: flex;
		flex-direction: column;
		background: var(--surface);
		border-left: 1px solid var(--border);
		box-shadow: var(--shadow-lg);
		outline: none;
		animation: slide-in 0.22s cubic-bezier(0.2, 0.9, 0.3, 1);
	}
	.grip {
		display: none;
	}
	header {
		display: flex;
		align-items: flex-start;
		gap: 0.85rem;
		padding: 1.25rem 1.25rem 1rem;
		border-bottom: 1px solid var(--border);
	}
	.avatar {
		flex: none;
		display: grid;
		place-items: center;
		width: 2.75rem;
		height: 2.75rem;
		border-radius: 14px;
		color: #fff;
		font-weight: 700;
		font-size: 0.9rem;
	}
	.title {
		flex: 1;
		min-width: 0;
	}
	h2 {
		margin: 0;
		font-size: 1.1rem;
		line-height: 1.3;
		overflow-wrap: anywhere;
	}
	.sub {
		font-size: 0.83rem;
		color: var(--muted);
	}
	.close {
		flex: none;
		margin: -0.3rem -0.4rem 0 0;
	}
	.body {
		flex: 1;
		overflow-y: auto;
		overscroll-behavior: contain;
		padding: 1rem 1.25rem 1.5rem;
	}
	.hero {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.6rem;
		margin-bottom: 0.5rem;
	}
	.big {
		font-size: 1.9rem;
		font-weight: 750;
		letter-spacing: -0.02em;
	}
	.chip {
		padding: 0.2rem 0.6rem;
		border-radius: 999px;
		background: var(--surface-2);
		color: var(--muted);
		font-size: 0.78rem;
		font-weight: 600;
	}
	section {
		padding: 1rem 0;
	}
	section + section {
		border-top: 1px solid var(--border);
	}
	h3 {
		margin: 0 0 0.65rem;
		font-size: 0.72rem;
		font-weight: 650;
		text-transform: uppercase;
		letter-spacing: 0.06em;
		color: var(--faint);
	}
	h3 label {
		font: inherit;
		color: inherit;
		margin: 0;
	}
	.cat-select :global(.select-trigger) {
		width: 100%;
	}
	.origin {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		margin-top: 0.6rem;
		font-size: 0.85rem;
		color: var(--muted);
	}
	.origin > :global(svg) {
		flex: none;
	}
	.origin.ai > :global(svg) {
		color: var(--accent-strong);
	}
	.origin .grow {
		flex: 1;
		min-width: 0;
	}
	.rule-text {
		display: block;
		color: var(--text);
		font-weight: 550;
		overflow-wrap: anywhere;
	}
	.origin a {
		font-size: 0.8rem;
	}
	.meter {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		margin-top: 0.3rem;
		color: var(--text);
		font-weight: 600;
		font-size: 0.8rem;
	}
	.bar {
		flex: 1;
		max-width: 9rem;
		height: 0.4rem;
		border-radius: 999px;
		background: var(--surface-3);
		overflow: hidden;
	}
	.bar span {
		display: block;
		height: 100%;
		border-radius: inherit;
		background: var(--gradient);
	}
	.confirm {
		flex: none;
		display: inline-flex;
		align-items: center;
		gap: 0.3rem;
		padding: 0.35rem 0.75rem;
		border-radius: 999px;
		background: var(--accent-soft);
		color: var(--accent-strong);
		box-shadow: none;
		font-size: 0.82rem;
	}
	.confirm:hover {
		background: var(--accent);
		color: #fff;
		filter: none;
	}
	.suggest {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		width: 100%;
		margin-top: 0.6rem;
		padding: 0.45rem 0.45rem 0.45rem 0.75rem;
		border-radius: var(--radius-sm);
		background: var(--warn-soft);
		color: var(--warn);
		box-shadow: none;
		font-size: 0.85rem;
		font-weight: 500;
		text-align: left;
	}
	.suggest .txt {
		flex: 1;
		min-width: 0;
		overflow-wrap: anywhere;
	}
	.suggest strong {
		font-weight: 650;
	}
	.suggest .take {
		flex: none;
		padding: 0.2rem 0.65rem;
		border-radius: 999px;
		background: var(--surface);
		color: var(--text);
		font-weight: 600;
	}
	.suggest:hover {
		filter: none;
	}
	.suggest:hover .take {
		background: var(--accent);
		color: #fff;
	}
	.hint {
		margin: 0.6rem 0 0;
		font-size: 0.8rem;
		color: var(--muted);
	}
	.purpose {
		margin: 0;
		white-space: pre-wrap;
		overflow-wrap: anywhere;
		font-size: 0.92rem;
		line-height: 1.5;
		user-select: text;
	}
	dl {
		display: grid;
		grid-template-columns: minmax(7.5rem, auto) 1fr;
		gap: 0.55rem 1rem;
		margin: 0;
		font-size: 0.88rem;
	}
	dt {
		color: var(--muted);
	}
	dd {
		margin: 0;
		min-width: 0;
		overflow-wrap: anywhere;
		user-select: text;
	}
	.mono {
		font-family: ui-monospace, 'SF Mono', 'Cascadia Mono', Menlo, Consolas, monospace;
		font-size: 0.84rem;
		letter-spacing: 0.01em;
	}
	.faint {
		display: block;
		color: var(--muted);
		font-size: 0.8rem;
	}
	.source {
		display: flex;
		align-items: flex-start;
		gap: 0.4rem;
	}
	.source :global(svg) {
		flex: none;
		margin-top: 0.15rem;
		color: var(--muted);
	}
	.source > span {
		min-width: 0;
	}
	textarea {
		width: 100%;
		resize: vertical;
		min-height: 4rem;
	}
	.wide {
		width: 100%;
		display: inline-flex;
		justify-content: center;
		gap: 0.4rem;
	}
	.rule {
		display: grid;
		gap: 0.85rem;
	}
	.rule-row {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 0.75rem;
	}
	.rule :global(.select-trigger),
	.rule input {
		width: 100%;
	}
	.match {
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
		margin-top: -0.4rem;
		font-size: 0.8rem;
		font-weight: 550;
		color: var(--accent-strong);
	}
	.match.no {
		color: var(--warn);
	}
	.rule .hint {
		margin-top: -0.4rem;
	}
	.actions {
		display: flex;
		justify-content: flex-end;
		gap: 0.5rem;
	}
	.loading {
		display: grid;
		gap: 0.8rem;
		padding-top: 0.5rem;
	}
	.loading span {
		height: 1.1rem;
		border-radius: 8px;
		background: var(--surface-2);
		animation: pulse 1.2s ease-in-out infinite;
	}
	.loading span:first-child {
		width: 45%;
		height: 2rem;
	}
	.loading span:last-child {
		width: 70%;
	}
	@keyframes pulse {
		50% {
			opacity: 0.5;
		}
	}
	@keyframes fade {
		from {
			opacity: 0;
		}
	}
	@keyframes slide-in {
		from {
			transform: translateX(100%);
		}
	}
	@keyframes slide-up {
		from {
			transform: translateY(100%);
		}
	}

	/* Mobile: bottom sheet above the tab bar */
	@media (max-width: 760px) {
		.panel {
			top: auto;
			left: 0;
			width: 100%;
			max-height: 92dvh;
			border-left: 0;
			border-radius: 22px 22px 0 0;
			animation: slide-up 0.24s cubic-bezier(0.2, 0.9, 0.3, 1);
		}
		.grip {
			display: block;
			width: 2.5rem;
			height: 0.3rem;
			border-radius: 999px;
			background: var(--surface-3);
			margin: 0.6rem auto 0;
			flex: none;
		}
		header {
			padding: 0.75rem 1rem 0.85rem;
		}
		.body {
			padding: 0.75rem 1rem calc(1.5rem + env(safe-area-inset-bottom));
		}
		dl {
			grid-template-columns: minmax(0, 7.5rem) 1fr;
			gap: 0.5rem 0.75rem;
		}
		.mono {
			font-size: 0.8rem;
		}
	}
	@media (max-width: 380px) {
		dl {
			grid-template-columns: 1fr;
			gap: 0.1rem;
		}
		dd + dt {
			margin-top: 0.55rem;
		}
	}
	@media (prefers-reduced-motion: reduce) {
		.panel,
		.backdrop {
			animation: none;
		}
	}
</style>
