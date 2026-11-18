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
	import { categoryLabels, day, money, monthLabel, shiftMonth } from './format';
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
		onchange?: (t: Transaction) => void;
		/** Other transactions may have changed too (a rule was applied) */
		onreload?: () => void;
	} = $props();

	let t = $state<TransactionDetail | null>(null);
	let error = $state('');
	let notice = $state('');
	let note = $state('');
	let panel = $state<HTMLElement>();
	let labels = $derived(categoryLabels(categories));

	async function load() {
		try {
			t = await api<TransactionDetail>(`/transactions/${id}`);
			note = t.note;
			error = '';
		} catch (e) {
			error = (e as Error).message;
		}
	}

	$effect(() => {
		void id;
		t = null;
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
		if (!t) return;
		try {
			const res = await api<{ transaction: Transaction }>(`/transactions/${t.id}`, { method: 'PATCH', body });
			Object.assign(t, res.transaction);
			if (res.transaction.category_source !== 'rule') t.rule = null;
			onchange?.(res.transaction);
			error = '';
		} catch (e) {
			error = (e as Error).message;
		}
	}

	// --- Category -----------------------------------------------------------
	const pct = (v: number | null) => (v === null ? '' : `${Math.round(v * 100)} %`);
	let isAi = $derived(t?.category_source === 'model' || t?.category_source === 'llm');
	const fieldLabel: Record<Rule['field'], string> = {
		payee: 'Empfänger',
		purpose: 'Verwendungszweck',
		any: 'Empfänger oder Zweck'
	};
	const matchLabel: Record<Rule['match_type'], string> = {
		contains: 'enthält',
		equals: 'ist genau',
		starts_with: 'beginnt mit',
		regex: 'passt zu Regex'
	};

	// --- Budget month -------------------------------------------------------
	let bookingMonth = $derived(t ? t.booking_date.slice(0, 7) : '');
	let budgetMonth = $derived(t ? t.budget_date.slice(0, 7) : '');
	let budgetValue = $derived<'auto' | 'same' | 'next'>(t?.budget_shift ?? 'auto');
	let budgetOptions = $derived<SelectOption<'auto' | 'same' | 'next'>[]>(
		t
			? [
					{ value: 'auto', label: 'Automatisch' },
					{ value: 'same', label: `${monthLabel(bookingMonth)} (Buchungsmonat)` },
					{ value: 'next', label: `${monthLabel(shiftMonth(bookingMonth, 1))} (Folgemonat)` }
				]
			: []
	);

	// --- Note ---------------------------------------------------------------
	function saveNote() {
		if (t && note !== t.note) patch({ note });
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
	const fieldOptions = Object.entries(fieldLabel).map(([value, label]) => ({ value, label })) as SelectOption<
		Rule['field']
	>[];
	const matchOptions = Object.entries(matchLabel).map(([value, label]) => ({ value, label })) as SelectOption<
		Rule['match_type']
	>[];
	const defaultPattern = (field: Rule['field']) =>
		!t ? '' : field === 'purpose' ? t.purpose : t.payee || t.purpose;

	function openRule() {
		if (!t) return;
		rule = {
			field: t.payee ? 'payee' : 'purpose',
			match_type: 'contains',
			pattern: '',
			category_id: t.category_id ?? t.suggested_category_id,
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
		if (!t) return false;
		const pattern = rule.pattern.trim();
		if (!pattern) return false;
		const texts = rule.field === 'payee' ? [t.payee] : rule.field === 'purpose' ? [t.purpose] : [t.payee, t.purpose];
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
		if (!t || rule.category_id === null) return;
		try {
			const { apply, ...body } = rule;
			const created = await api<Rule>('/rules', {
				method: 'POST',
				body,
				params: { apply: apply ? undefined : 'false' }
			});
			ruleOpen = false;
			notice = apply
				? `Regel angelegt, ${created.match_count} ${created.match_count === 1 ? 'Buchung' : 'Buchungen'} zugeordnet.`
				: 'Regel angelegt. Sie gilt ab dem nächsten Import.';
			error = '';
			await load();
			if (t) onchange?.(t);
			onreload?.();
		} catch (err) {
			error = (err as Error).message;
		}
	}

	// --- Formatting -----------------------------------------------------------
	const iban = (v: string) => v.replace(/(.{4})/g, '$1 ').trim();
	const dateTime = new Intl.DateTimeFormat('de-DE', { dateStyle: 'medium', timeStyle: 'short' });
	const longDay = new Intl.DateTimeFormat('de-DE', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
	let counterpartLabel = $derived(t && Number(t.amount) > 0 ? 'Auftraggeber' : 'Empfänger');
	let hasSepa = $derived(
		!!t && !!(t.counterparty_iban || t.counterparty_bic || t.mandate_id || t.creditor_id || t.end_to_end_ref)
	);
	let sourceName = $derived(
		!t?.import_batch ? 'Unbekannt' : t.import_batch.source === 'fints' ? 'FinTS-Abruf' : 'CSV-Import'
	);
</script>

<svelte:window {onkeydown} />

<div class="tx-layer">
	<button class="backdrop" type="button" tabindex="-1" aria-label="Details schließen" onclick={onclose}></button>
	<div
		class="panel"
		role="dialog"
		aria-modal="true"
		aria-labelledby="tx-detail-title"
		tabindex="-1"
		bind:this={panel}
	>
		<div class="grip" aria-hidden="true"></div>
		<header>
			{#if t}
				<span class="avatar" style:background={avatarColor(t.payee || t.booking_text)}>
					{initials(t.payee || t.booking_text)}
				</span>
				<div class="title">
					<h2 id="tx-detail-title">{t.payee || t.booking_text || 'Buchung'}</h2>
					<span class="sub">{longDay.format(new Date(t.booking_date + 'T12:00:00'))}</span>
				</div>
			{:else}
				<div class="title"><h2 id="tx-detail-title">Buchung</h2></div>
			{/if}
			<button class="ghost icon close" type="button" onclick={onclose} aria-label="Schließen" title="Schließen (Esc)">
				<X size={20} />
			</button>
		</header>

		<div class="body">
			{#if error}<div class="error">{error}</div>{/if}
			{#if notice}<div class="ok"><Sparkles size={18} /> {notice}</div>{/if}

			{#if !t}
				{#if !error}<div class="loading" aria-busy="true"><span></span><span></span><span></span></div>{/if}
			{:else}
				<div class="hero">
					<span class="big amount" class:pos={Number(t.amount) > 0}>{money(t.amount)}</span>
					{#if t.booking_text}<span class="chip">{t.booking_text}</span>{/if}
				</div>

				<!-- Category -->
				<section>
					<h3>Kategorie</h3>
					<div class="cat-select">
						<CategorySelect {categories} value={t.category_id} onchange={(v) => patch({ category_id: v })} />
					</div>
					<div class="origin" class:ai={isAi}>
						{#if t.category_source === 'manual'}
							<Hand size={16} />
							<span>Manuell zugeordnet</span>
						{:else if t.category_source === 'rule'}
							<WandSparkles size={16} />
							<span>
								Per Regel zugeordnet
								{#if t.rule}
									<span class="rule-text">
										{fieldLabel[t.rule.field]} {matchLabel[t.rule.match_type]} „{t.rule.pattern}“
									</span>
								{/if}
								<a href="/rules">Regeln verwalten</a>
							</span>
						{:else if t.category_source === 'model'}
							<Sparkles size={16} />
							<span class="grow">
								Von der KI zugeordnet
								{#if t.category_confidence !== null}
									<span class="meter" title="Sicherheit der KI">
										<span class="bar"><span style:width={pct(t.category_confidence).replace(' ', '')}></span></span>
										{pct(t.category_confidence)} sicher
									</span>
								{/if}
							</span>
						{:else if t.category_source === 'llm'}
							<Bot size={16} />
							<span class="grow">Vom lokalen Sprachmodell zugeordnet</span>
						{:else}
							<Info size={16} />
							<span>Noch keine Kategorie</span>
						{/if}
						{#if isAi}
							<button class="confirm" type="button" onclick={() => patch({ category_id: t!.category_id })}>
								<Check size={15} /> Passt
							</button>
						{/if}
					</div>
					{#if t.category_id === null && t.suggested_category_id !== null}
						<button
							class="suggest"
							type="button"
							onclick={() => patch({ category_id: t!.suggested_category_id })}
						>
							<WandSparkles size={14} />
							<span class="txt">Vorschlag: <strong>{labels.get(t.suggested_category_id)}</strong></span>
							<span class="conf">{pct(t.suggestion_confidence)}</span>
							<span class="take">Übernehmen</span>
						</button>
					{/if}
				</section>

				<!-- Budget month -->
				<section>
					<h3>Zählt im Monat</h3>
					<RadioGroup
						options={budgetOptions}
						value={budgetValue}
						label="Budgetmonat"
						variant="list"
						onchange={(v) => patch({ budget_shift: v })}
					/>
					<p class="hint">
						{#if t.budget_shift === null}
							Automatisch: zählt für {monthLabel(budgetMonth)}.
						{/if}
						Gehalt zum Monatsende kann automatisch dem Folgemonat zugerechnet werden.
					</p>
				</section>

				<!-- Purpose -->
				{#if t.purpose}
					<section>
						<h3>Verwendungszweck</h3>
						<p class="purpose">{t.purpose}</p>
					</section>
				{/if}

				<!-- Details -->
				<section>
					<h3>Details</h3>
					<dl>
						<dt>Buchungstag</dt>
						<dd>{day(t.booking_date)}</dd>
						{#if t.value_date}
							<dt>Wertstellung</dt>
							<dd>{day(t.value_date)}</dd>
						{/if}
						<dt>Budgetmonat</dt>
						<dd>{monthLabel(budgetMonth)}</dd>
						{#if t.balance_after !== null}
							<dt>Saldo danach</dt>
							<dd>{money(t.balance_after)}</dd>
						{/if}
						{#if t.booking_text}
							<dt>Buchungstext</dt>
							<dd>{t.booking_text}</dd>
						{/if}
						{#if t.payee}
							<dt>{counterpartLabel}</dt>
							<dd>{t.payee}</dd>
						{/if}
						{#if t.counterparty_iban}
							<dt>IBAN</dt>
							<dd class="mono">{iban(t.counterparty_iban)}</dd>
						{/if}
						{#if t.counterparty_bic}
							<dt>BIC</dt>
							<dd class="mono">{t.counterparty_bic}</dd>
						{/if}
						{#if t.mandate_id}
							<dt>Mandatsreferenz</dt>
							<dd class="mono">{t.mandate_id}</dd>
						{/if}
						{#if t.creditor_id}
							<dt>Gläubiger-ID</dt>
							<dd class="mono">{t.creditor_id}</dd>
						{/if}
						{#if t.end_to_end_ref}
							<dt>End-to-End-Referenz</dt>
							<dd class="mono">{t.end_to_end_ref}</dd>
						{/if}
						<dt>Konto</dt>
						<dd>
							{t.account.name}
							{#if t.account.iban}<span class="mono faint">{iban(t.account.iban)}</span>{/if}
						</dd>
						<dt>Quelle</dt>
						<dd class="source">
							{#if t.import_batch?.source === 'fints'}<CloudDownload size={15} />{:else}<FileSpreadsheet size={15} />{/if}
							<span>
								{sourceName}
								{#if t.import_batch?.filename}<span class="faint">{t.import_batch.filename}</span>{/if}
							</span>
						</dd>
						<dt>Importiert am</dt>
						<dd>{dateTime.format(new Date(t.import_batch?.created_at ?? t.created_at))}</dd>
					</dl>
					{#if !hasSepa && t.import_batch?.source === 'ing_csv'}
						<p class="hint">
							Der CSV-Export der ING enthält keine IBAN und keine SEPA-Referenzen. Per FinTS abgerufene Buchungen
							zeigen sie hier an.
						</p>
					{/if}
				</section>

				<!-- Note -->
				<section>
					<h3><label for="tx-note">Notiz</label></h3>
					<textarea
						id="tx-note"
						rows="2"
						placeholder="Eigene Notiz zu dieser Buchung"
						bind:value={note}
						onblur={saveNote}
					></textarea>
				</section>

				<!-- Rule -->
				<section>
					{#if !ruleOpen}
						<button class="secondary wide" type="button" onclick={openRule}>
							<Plus size={17} /> Regel aus dieser Buchung erstellen
						</button>
					{:else}
						<h3>Neue Regel</h3>
						<form class="rule" onsubmit={createRule}>
							<div class="rule-row">
								<div class="field">
									Feld
									<Select
										options={fieldOptions}
										bind:value={rule.field}
										label="Feld"
										onchange={changeField}
									/>
								</div>
								<div class="field">
									Bedingung
									<Select options={matchOptions} bind:value={rule.match_type} label="Bedingung" />
								</div>
							</div>
							<label>
								Text
								<input bind:value={rule.pattern} required maxlength="255" placeholder="z. B. REWE" />
							</label>
							<span class="match" class:no={!ruleMatchesThis}>
								{#if ruleMatchesThis}<Check size={14} /> Passt auf diese Buchung{:else}<Info size={14} /> Passt nicht auf diese Buchung{/if}
							</span>
							<div class="field">
								Kategorie
								<CategorySelect {categories} bind:value={rule.category_id} empty="Kategorie wählen" />
							</div>
							<Switch bind:checked={rule.apply}>Gleich auf passende Buchungen anwenden</Switch>
							<p class="hint">Manuell zugeordnete Buchungen werden nie überschrieben.</p>
							<div class="actions">
								<button class="ghost" type="button" onclick={() => (ruleOpen = false)}>Abbrechen</button>
								<button type="submit" disabled={rule.category_id === null || !rule.pattern.trim()}>
									Regel anlegen
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
