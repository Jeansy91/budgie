<script lang="ts">
	import { page } from '$app/state';
	import { goto, pushState } from '$app/navigation';
	import { api } from '$lib/api';
	import CategorySelect from '$lib/CategorySelect.svelte';
	import BudgetMonthMenu from '$lib/BudgetMonthMenu.svelte';
	import TransactionDetail from '$lib/TransactionDetail.svelte';
	import { MonthPicker, Select, type SelectOption } from '$lib/ui';
	import { categoryLabels, money } from '$lib/format';
	import { avatarColor, colorFor, initials } from '$lib/colors';
	import Search from '@lucide/svelte/icons/search';
	import Sparkles from '@lucide/svelte/icons/sparkles';
	import Check from '@lucide/svelte/icons/check';
	import Wand from '@lucide/svelte/icons/wand-sparkles';
	import type { Account, Category, Transaction } from '$lib/types';

	const PAGE = 100;
	const params = page.url.searchParams;

	let month = $state(params.get('month') ?? '');
	let accountId = $state(params.get('account_id') ?? '');
	let categoryId = $state<number | null>(params.get('category_id') ? Number(params.get('category_id')) : null);
	let uncategorized = $state(params.get('uncategorized') === '1');
	let aiReview = $state(params.get('ai_review') === '1');
	let q = $state(params.get('q') ?? '');
	let makeRule = $state(false);

	let items = $state<Transaction[]>([]);
	let total = $state(0);
	let categories = $state<Category[]>([]);
	let accounts = $state<Account[]>([]);
	let error = $state('');
	let notice = $state('');
	let labels = $derived(categoryLabels(categories));
	let accountNames = $derived(new Map(accounts.map((a) => [a.id, a.name])));
	// Color per category: the color of its main category
	let catColor = $derived.by(() => {
		const map = new Map<number, string>();
		categories.forEach((main, i) => {
			map.set(main.id, colorFor(i));
			for (const sub of main.children) map.set(sub.id, colorFor(i));
		});
		return map;
	});
	const weekday = new Intl.DateTimeFormat('de-DE', { weekday: 'long', day: 'numeric', month: 'long' });
	let groups = $derived.by(() => {
		const out: { date: string; items: Transaction[]; sum: number }[] = [];
		for (const t of items) {
			let g = out.at(-1);
			if (!g || g.date !== t.booking_date) out.push((g = { date: t.booking_date, items: [], sum: 0 }));
			g.items.push(t);
			g.sum += Number(t.amount);
		}
		return out;
	});

	api<Category[]>('/categories').then((c) => (categories = c));
	api<Account[]>('/accounts').then((a) => (accounts = a));

	let accountOptions = $derived<SelectOption<string>[]>([
		{ value: '', label: 'Alle Konten' },
		...accounts.map((a) => ({ value: String(a.id), label: a.name }))
	]);
	let categoryOptions = $derived<SelectOption<number | null>[]>([
		{ value: null, label: 'Alle Kategorien' },
		...categories.flatMap((main, i) => [
			{ value: main.id, label: main.name, color: colorFor(i), hint: 'alle' },
			...main.children.map((sub) => ({ value: sub.id, label: sub.name, color: colorFor(i), indent: true }))
		])
	]);

	const filters = () => ({ month, account_id: accountId, category_id: categoryId, uncategorized, ai_review: aiReview, q });

	async function load(append = false) {
		try {
			const res = await api<{ items: Transaction[]; total: number }>('/transactions', {
				params: { ...filters(), limit: PAGE, offset: append ? items.length : 0 }
			});
			items = append ? [...items, ...res.items] : res.items;
			total = res.total;
			error = '';
		} catch (e) {
			error = (e as Error).message;
		}
	}

	$effect(() => {
		const f = filters();
		const qs = new URLSearchParams();
		for (const [k, v] of Object.entries(f)) if (v) qs.set(k, v === true ? '1' : String(v));
		goto(`?${qs}`, { replaceState: true, keepFocus: true, noScroll: true });
		const t = setTimeout(() => load(), 200);
		return () => clearTimeout(t);
	});

	async function setCategory(t: Transaction, category_id: number | null, allowRule = true) {
		try {
			const res = await api<{ transaction: Transaction; rule: unknown; other_changed: number }>(
				`/transactions/${t.id}`,
				{ method: 'PATCH', body: { category_id, create_rule: allowRule && makeRule && category_id !== null } }
			);
			Object.assign(t, res.transaction);
			notice = res.rule
				? `Regel für „${t.payee}“ angelegt, ${res.other_changed} weitere Buchungen zugeordnet.`
				: '';
			if (res.other_changed) await load();
		} catch (e) {
			error = (e as Error).message;
		}
	}

	const pct = (v: number | null) => (v === null ? '' : `${Math.round(v * 100)} %`);
	function sourceLabel(t: Transaction): string {
		if (t.category_source === 'model') return `KI ${pct(t.category_confidence)}`;
		return { manual: 'manuell', rule: 'Regel', llm: 'KI', model: 'KI' }[t.category_source!];
	}
	function sourceTitle(t: Transaction): string {
		if (t.category_source === 'model') return `Von der KI zugeordnet, ${pct(t.category_confidence)} sicher`;
		if (t.category_source === 'llm') return 'Vom lokalen Sprachmodell zugeordnet';
		return '';
	}
	const isAi = (t: Transaction) => t.category_source === 'model' || t.category_source === 'llm';

	// Detail panel. Opening adds a history entry, so the back button/gesture closes it.
	let detailId = $derived(page.state.tx ?? null);
	function openDetail(t: Transaction) {
		if (detailId === null) pushState('', { tx: t.id });
	}
	function closeDetail() {
		history.back();
	}
	// Clicks on the controls inside a row (category, budget month, confirm) do not open the details
	const fromControl = (e: Event) =>
		(e.target as Element).closest('button, a, input, textarea, [role="menu"], .select-trigger') !== null;
	function rowClick(e: MouseEvent, t: Transaction) {
		if (!fromControl(e) && !window.getSelection()?.toString()) openDetail(t);
	}
	function rowKey(e: KeyboardEvent, t: Transaction) {
		if ((e.key === 'Enter' || e.key === ' ') && e.target === e.currentTarget) {
			e.preventDefault();
			openDetail(t);
		}
	}
	function detailChanged(n: Transaction) {
		const item = items.find((x) => x.id === n.id);
		if (item) Object.assign(item, n);
	}
</script>

<div class="page-head">
	<div>
		<span class="eyebrow">Alle Konten</span>
		<h1>Buchungen</h1>
	</div>
	<span class="badge">{total} Buchungen</span>
</div>

<div class="card filters">
	<div class="search">
		<Search size={18} />
		<input type="search" bind:value={q} placeholder="Empfänger oder Verwendungszweck suchen" />
	</div>
	<div class="row">
		<div class="field">Monat <MonthPicker bind:value={month} placeholder="Alle Monate" /></div>
		{#if accounts.length > 1}
			<div class="field">Konto <Select options={accountOptions} bind:value={accountId} label="Konto" /></div>
		{/if}
		<div class="field">
			Kategorie
			<Select options={categoryOptions} bind:value={categoryId} label="Kategorie" searchable searchPlaceholder="Kategorie suchen …" />
		</div>
		<button class="pill" class:on={uncategorized} onclick={() => (uncategorized = !uncategorized)}>
			{#if uncategorized}<Check size={15} />{/if} Nur ohne Kategorie
		</button>
		<button
			class="pill"
			class:on={aiReview}
			onclick={() => (aiReview = !aiReview)}
			title="Zuordnungen und Vorschläge der KI, die noch niemand bestätigt hat"
		>
			{#if aiReview}<Check size={15} />{:else}<Wand size={15} />{/if} KI prüfen
		</button>
		<button
			class="pill"
			class:on={makeRule}
			onclick={() => (makeRule = !makeRule)}
			title="Beim Zuordnen eine Regel „Empfänger enthält …“ anlegen und auf ähnliche Buchungen anwenden"
		>
			<Sparkles size={15} /> Regeln lernen
		</button>
	</div>
</div>

{#if error}<div class="error">{error}</div>{/if}
{#if notice}<div class="ok"><Sparkles size={18} /> {notice}</div>{/if}

{#if items.length === 0}
	<div class="card muted">Keine Buchungen für diese Filter.</div>
{/if}

{#each groups as g (g.date)}
	<section class="day">
		<div class="day-head">
			<span>{weekday.format(new Date(g.date + 'T12:00:00'))}</span>
			<span class="amount">{money(g.sum)}</span>
		</div>
		<div class="card list">
			{#each g.items as t (t.id)}
				<!-- svelte-ignore a11y_no_noninteractive_tabindex, a11y_no_noninteractive_element_interactions -->
				<article
					class="tx"
					class:selected={detailId === t.id}
					tabindex="0"
					aria-label="{t.payee || t.booking_text}, {money(t.amount)} – Details anzeigen"
					onclick={(e) => rowClick(e, t)}
					onkeydown={(e) => rowKey(e, t)}
				>
					<span class="avatar" style:background={avatarColor(t.payee || t.booking_text)}>{initials(t.payee || t.booking_text)}</span>
					<div class="main">
						<div class="payee-row">
							<span class="payee">{t.payee || t.booking_text}</span>
							<BudgetMonthMenu {t} onchange={(n) => Object.assign(t, n)} onerror={(m) => (error = m)} />
						</div>
						<div class="purpose">
							{t.booking_text}{#if t.purpose}{' · '}{t.purpose}{/if}
							{#if accounts.length > 1}{' · '}{accountNames.get(t.account_id)}{/if}
						</div>
						{#if t.category_id === null && t.suggested_category_id !== null}
							<button
								class="suggest"
								onclick={() => setCategory(t, t.suggested_category_id, false)}
								title="Vorschlag der KI mit einem Klick übernehmen"
							>
								<Wand size={13} /> Vorschlag: <strong>{labels.get(t.suggested_category_id)}</strong>
								<span class="conf">{pct(t.suggestion_confidence)}</span>
								<span class="take">Übernehmen</span>
							</button>
						{/if}
					</div>
					<div class="cat" style:--c={t.category_id ? catColor.get(t.category_id) : 'var(--faint)'} title={t.category_id ? labels.get(t.category_id) : ''}>
						<CategorySelect {categories} value={t.category_id} onchange={(v) => setCategory(t, v)} />
						{#if t.category_source}<span class="src" class:ai={isAi(t)} title={sourceTitle(t)}>{sourceLabel(t)}</span>{/if}
						{#if isAi(t)}
							<button
								class="confirm"
								onclick={() => setCategory(t, t.category_id, false)}
								title="Passt – Zuordnung bestätigen. Die KI lernt daraus."
								aria-label="Zuordnung bestätigen"
							>
								<Check size={15} />
							</button>
						{:else}
							<span class="confirm-slot"></span>
						{/if}
					</div>
					<div class="amount sum" class:pos={Number(t.amount) > 0}>{money(t.amount)}</div>
				</article>
			{/each}
		</div>
	</section>
{/each}

{#if items.length < total}
	<div class="more"><button class="secondary" onclick={() => load(true)}>Weitere laden</button></div>
{/if}

{#if detailId !== null}
	<TransactionDetail
		id={detailId}
		{categories}
		onclose={closeDetail}
		onchange={detailChanged}
		onreload={() => load()}
	/>
{/if}

<style>
	.filters {
		display: grid;
		gap: 1rem;
	}
	.search {
		position: relative;
		display: flex;
		align-items: center;
		color: var(--faint);
	}
	.search :global(svg) {
		position: absolute;
		left: 0.9rem;
	}
	.search input {
		width: 100%;
		padding-left: 2.6rem !important;
		font-size: 1rem;
	}
	.field {
		flex: 1 1 160px;
		min-width: 0;
	}
	.field :global(.select-trigger) {
		width: 100%;
	}
	.pill {
		background: var(--surface-2);
		color: var(--muted);
		box-shadow: none;
		font-weight: 550;
		padding: 0.6rem 1rem;
	}
	.pill:hover {
		background: var(--surface-3);
		filter: none;
		box-shadow: none;
	}
	.pill.on {
		background: var(--accent-soft);
		color: var(--accent-strong);
	}
	.day {
		margin-bottom: 1.25rem;
	}
	.day-head {
		display: flex;
		justify-content: space-between;
		padding: 0 0.5rem 0.5rem;
		font-size: 0.8rem;
		font-weight: 600;
		color: var(--muted);
	}
	.list {
		padding: 0.25rem 0;
		margin: 0;
	}
	.tx {
		display: grid;
		grid-template-columns: auto 1fr auto 8em;
		gap: 1rem;
		align-items: center;
		padding: 0.8rem 1.25rem;
	}
	.tx + .tx {
		border-top: 1px solid var(--border);
	}
	.tx {
		cursor: pointer;
	}
	.tx:hover {
		background: color-mix(in srgb, var(--surface-2) 50%, transparent);
	}
	.tx.selected {
		background: color-mix(in srgb, var(--accent-soft) 55%, transparent);
	}
	.tx:focus-visible {
		outline: none;
		box-shadow: inset 0 0 0 2px var(--accent);
	}
	.avatar {
		display: grid;
		place-items: center;
		width: 2.6rem;
		height: 2.6rem;
		border-radius: 14px;
		color: #fff;
		font-weight: 700;
		font-size: 0.85rem;
	}
	.main {
		min-width: 0;
	}
	.payee-row {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		min-width: 0;
	}
	.payee {
		min-width: 0;
		font-weight: 600;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.purpose {
		color: var(--muted);
		font-size: 0.83rem;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.cat {
		position: relative;
		display: flex;
		align-items: center;
	}
	.cat :global(.select-trigger) {
		width: 220px;
		border-radius: 999px;
		font-size: 0.85rem;
		font-weight: 500;
		padding: 0.5rem 0.7rem 0.5rem 0.85rem;
		background: color-mix(in srgb, var(--c) 12%, var(--surface));
	}
	.cat :global(.select-trigger:hover) {
		background: color-mix(in srgb, var(--c) 20%, var(--surface));
	}
	.cat:has(.src) :global(.select-trigger .value) {
		padding-right: 3.4rem;
	}
	.src {
		position: absolute;
		right: 2.1rem;
		font-size: 0.65rem;
		font-weight: 650;
		text-transform: uppercase;
		letter-spacing: 0.04em;
		color: var(--faint);
		pointer-events: none;
	}
	.src.ai {
		color: var(--accent-strong);
	}
	/* Reserve space for the confirm button so all rows line up */
	.cat .src {
		right: 4.45rem;
	}
	.confirm-slot {
		flex: none;
		width: 2rem;
		margin-left: 0.35rem;
	}
	.confirm {
		flex: none;
		display: grid;
		place-items: center;
		width: 2rem;
		height: 2rem;
		margin-left: 0.35rem;
		padding: 0;
		border-radius: 999px;
		background: var(--accent-soft);
		color: var(--accent-strong);
		box-shadow: none;
	}
	.confirm:hover {
		background: var(--accent);
		color: #fff;
		filter: none;
	}
	.suggest {
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
		max-width: 100%;
		margin-top: 0.35rem;
		padding: 0.25rem 0.4rem 0.25rem 0.65rem;
		border-radius: 999px;
		background: var(--warn-soft);
		color: var(--warn);
		box-shadow: none;
		font-size: 0.78rem;
		font-weight: 500;
		white-space: nowrap;
		overflow: hidden;
	}
	.suggest strong {
		overflow: hidden;
		text-overflow: ellipsis;
		font-weight: 650;
	}
	.suggest .conf {
		opacity: 0.8;
	}
	.suggest .take {
		padding: 0.1rem 0.55rem;
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
	.sum {
		font-weight: 650;
	}
	.more {
		display: flex;
		justify-content: center;
	}
	@media (max-width: 760px) {
		.tx {
			grid-template-columns: auto 1fr auto;
			grid-template-areas: 'av main sum' 'av cat cat';
			gap: 0.5rem 0.85rem;
			padding: 0.8rem 1rem;
		}
		.avatar {
			grid-area: av;
			align-self: start;
		}
		.main {
			grid-area: main;
		}
		.sum {
			grid-area: sum;
		}
		.cat {
			grid-area: cat;
		}
		.cat :global(.select-trigger) {
			width: 100%;
		}
	}
</style>
