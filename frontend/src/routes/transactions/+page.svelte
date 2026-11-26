<script lang="ts">
	import { page } from '$app/state';
	import { goto, pushState } from '$app/navigation';
	import { api } from '#lib/api.ts';
	import CategorySelect from '#lib/CategorySelect.svelte';
	import BudgetMonthMenu from '#lib/BudgetMonthMenu.svelte';
	import TransactionDetail from '#lib/TransactionDetail.svelte';
	import { MonthPicker, Select, type SelectOption } from '#lib/ui/index.ts';
	import { categoryLabels, dateFormat, money, percent } from '#lib/format.ts';
	import { t } from '#lib/i18n/index.svelte.ts';
	import { avatarColor, colorFor, initials } from '#lib/colors.ts';
	import Search from '@lucide/svelte/icons/search';
	import Sparkles from '@lucide/svelte/icons/sparkles';
	import Check from '@lucide/svelte/icons/check';
	import Wand from '@lucide/svelte/icons/wand-sparkles';
	import type { Account, Category, Transaction } from '#lib/types.ts';

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
		// eslint-disable-next-line svelte/prefer-svelte-reactivity -- local, non-reactive value
		const map = new Map<number, string>();
		categories.forEach((main, i) => {
			map.set(main.id, colorFor(i));
			for (const sub of main.children) map.set(sub.id, colorFor(i));
		});
		return map;
	});
	let weekday = $derived(dateFormat({ weekday: 'long', day: 'numeric', month: 'long' }));
	let groups = $derived.by(() => {
		const out: { date: string; items: Transaction[]; sum: number }[] = [];
		for (const tx of items) {
			let g = out.at(-1);
			if (!g || g.date !== tx.booking_date) out.push((g = { date: tx.booking_date, items: [], sum: 0 }));
			g.items.push(tx);
			g.sum += Number(tx.amount);
		}
		return out;
	});

	api<Category[]>('/categories').then((c) => (categories = c));
	api<Account[]>('/accounts').then((a) => (accounts = a));

	let accountOptions = $derived<SelectOption<string>[]>([
		{ value: '', label: t('transactions.allAccounts') },
		...accounts.map((a) => ({ value: String(a.id), label: a.name }))
	]);
	let categoryOptions = $derived<SelectOption<number | null>[]>([
		{ value: null, label: t('transactions.allCategories') },
		...categories.flatMap((main, i) => [
			{ value: main.id, label: main.name, color: colorFor(i), hint: t('transactions.allOfMain') },
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
		// eslint-disable-next-line svelte/prefer-svelte-reactivity -- local, non-reactive value
		const qs = new URLSearchParams();
		for (const [k, v] of Object.entries(f)) if (v) qs.set(k, v === true ? '1' : String(v));
		goto(`?${qs}`, { replace: true, reset: false });
		const tx = setTimeout(() => load(), 200);
		return () => clearTimeout(tx);
	});

	async function setCategory(tx: Transaction, category_id: number | null, allowRule = true) {
		try {
			const res = await api<{ transaction: Transaction; rule: unknown; other_changed: number }>(`/transactions/${tx.id}`, {
				method: 'PATCH',
				body: { category_id, create_rule: allowRule && makeRule && category_id !== null }
			});
			Object.assign(tx, res.transaction);
			notice = res.rule ? t('transactions.ruleCreated', { payee: tx.payee, count: res.other_changed }) : '';
			if (res.other_changed) await load();
		} catch (e) {
			error = (e as Error).message;
		}
	}

	const pct = percent;
	function sourceLabel(tx: Transaction): string {
		if (tx.category_source === 'model') return `${t('source.ai')} ${pct(tx.category_confidence)}`;
		return t(`source.${tx.category_source!}`);
	}
	function sourceTitle(tx: Transaction): string {
		if (tx.category_source === 'model') return t('source.modelTitle', { confidence: pct(tx.category_confidence) });
		if (tx.category_source === 'llm') return t('source.llmTitle');
		return '';
	}
	const isAi = (tx: Transaction) => tx.category_source === 'model' || tx.category_source === 'llm';

	// Detail panel. Opening adds a history entry, so the back button/gesture closes it.
	let detailId = $derived(page.state.tx ?? null);
	function openDetail(tx: Transaction) {
		if (detailId === null) pushState('', { tx: tx.id });
	}
	function closeDetail() {
		history.back();
	}
	// Clicks on the controls inside a row (category, budget month, confirm) do not open the details
	const fromControl = (e: Event) => (e.target as Element).closest('button, a, input, textarea, [role="menu"], .select-trigger') !== null;
	function rowClick(e: MouseEvent, tx: Transaction) {
		if (!fromControl(e) && !window.getSelection()?.toString()) openDetail(tx);
	}
	function rowKey(e: KeyboardEvent, tx: Transaction) {
		if ((e.key === 'Enter' || e.key === ' ') && e.target === e.currentTarget) {
			e.preventDefault();
			openDetail(tx);
		}
	}
	function detailChanged(n: Transaction) {
		const item = items.find((x) => x.id === n.id);
		if (item) Object.assign(item, n);
	}
</script>

<div class="page-head">
	<div>
		<span class="eyebrow">{t('transactions.allAccounts')}</span>
		<h1>{t('nav.transactions')}</h1>
	</div>
	<span class="badge">{t('transactions.count', { count: total })}</span>
</div>

<div class="card filters">
	<div class="search">
		<Search size={18} />
		<input type="search" bind:value={q} placeholder={t('transactions.searchPlaceholder')} />
	</div>
	<div class="row">
		<div class="field">{t('common.month')} <MonthPicker bind:value={month} placeholder={t('ui.month.all')} /></div>
		{#if accounts.length > 1}
			<div class="field">{t('common.account')} <Select options={accountOptions} bind:value={accountId} label={t('common.account')} /></div>
		{/if}
		<div class="field">
			{t('common.category')}
			<Select
				options={categoryOptions}
				bind:value={categoryId}
				label={t('common.category')}
				searchable
				searchPlaceholder={t('categorySelect.search')}
			/>
		</div>
		<button class="pill" class:on={uncategorized} onclick={() => (uncategorized = !uncategorized)}>
			{#if uncategorized}<Check size={15} />{/if}
			{t('transactions.onlyUncategorized')}
		</button>
		<button class="pill" class:on={aiReview} onclick={() => (aiReview = !aiReview)} title={t('transactions.aiReviewTitle')}>
			{#if aiReview}<Check size={15} />{:else}<Wand size={15} />{/if}
			{t('transactions.aiReview')}
		</button>
		<button class="pill" class:on={makeRule} onclick={() => (makeRule = !makeRule)} title={t('transactions.learnRulesTitle')}>
			<Sparkles size={15} />
			{t('transactions.learnRules')}
		</button>
	</div>
</div>

{#if error}<div class="error">{error}</div>{/if}
{#if notice}<div class="ok"><Sparkles size={18} /> {notice}</div>{/if}

{#if items.length === 0}
	<div class="card muted">{t('transactions.empty')}</div>
{/if}

{#each groups as g (g.date)}
	<section class="day">
		<div class="day-head">
			<span>{weekday.format(new Date(g.date + 'T12:00:00'))}</span>
			<span class="amount">{money(g.sum)}</span>
		</div>
		<div class="card list">
			{#each g.items as tx (tx.id)}
				<!-- svelte-ignore a11y_no_noninteractive_tabindex, a11y_no_noninteractive_element_interactions -->
				<article
					class="tx"
					class:selected={detailId === tx.id}
					tabindex="0"
					aria-label={t('transactions.rowLabel', { payee: tx.payee || tx.booking_text, amount: money(tx.amount) })}
					onclick={(e) => rowClick(e, tx)}
					onkeydown={(e) => rowKey(e, tx)}
				>
					<span class="avatar" style:background={avatarColor(tx.payee || tx.booking_text)}>{initials(tx.payee || tx.booking_text)}</span>
					<div class="main">
						<div class="payee-row">
							<span class="payee" title={tx.payee || tx.booking_text}>{tx.payee || tx.booking_text}</span>
							<BudgetMonthMenu {tx} onchange={(n) => Object.assign(tx, n)} onerror={(m) => (error = m)} />
						</div>
						<div class="purpose" title={tx.purpose || tx.booking_text}>
							<!-- eslint-disable-next-line svelte/no-useless-mustaches -- explicit separator string keeps its surrounding spaces -->
							{tx.booking_text}{#if tx.purpose}{' · '}{tx.purpose}{/if}
							<!-- eslint-disable-next-line svelte/no-useless-mustaches -- explicit separator string keeps its surrounding spaces -->
							{#if accounts.length > 1}{' · '}{accountNames.get(tx.account_id)}{/if}
						</div>
					</div>
					{#if tx.category_id === null && tx.suggested_category_id !== null}
						<button
							class="suggest"
							onclick={() => setCategory(tx, tx.suggested_category_id, false)}
							title={t('transactions.suggestionTitle', { category: labels.get(tx.suggested_category_id) ?? '' })}
						>
							<Wand size={13} /> <span class="lbl">{t('transactions.suggestion')}</span>
							<strong>{labels.get(tx.suggested_category_id)?.split(' › ').pop()}</strong>
							<span class="conf">{pct(tx.suggestion_confidence)}</span>
							<span class="take">{t('transactions.accept')}</span>
						</button>
					{/if}
					<div
						class="cat"
						style:--c={tx.category_id ? catColor.get(tx.category_id) : 'var(--faint)'}
						title={tx.category_id ? labels.get(tx.category_id) : ''}
					>
						<CategorySelect {categories} value={tx.category_id} onchange={(v) => setCategory(tx, v)} />
						{#if tx.category_source}<span class="src" class:ai={isAi(tx)} title={sourceTitle(tx)}>{sourceLabel(tx)}</span>{/if}
						{#if isAi(tx)}
							<button
								class="confirm"
								onclick={() => setCategory(tx, tx.category_id, false)}
								title={t('transactions.confirmTitle')}
								aria-label={t('transactions.confirm')}
							>
								<Check size={15} />
							</button>
						{:else}
							<span class="confirm-slot"></span>
						{/if}
					</div>
					<div class="amount sum" class:pos={Number(tx.amount) > 0}>{money(tx.amount)}</div>
				</article>
			{/each}
		</div>
	</section>
{/each}

{#if items.length < total}
	<div class="more"><button class="secondary" onclick={() => load(true)}>{t('transactions.loadMore')}</button></div>
{/if}

{#if detailId !== null}
	<TransactionDetail id={detailId} {categories} onclose={closeDetail} onchange={detailChanged} onreload={() => load()} />
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
		grid-template-columns: auto minmax(0, 1fr) auto 8em;
		grid-template-areas: 'av main cat sum' 'av suggest cat sum';
		gap: 0 1rem;
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
		grid-area: av;
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
		grid-area: main;
		min-width: 0;
	}
	.cat {
		grid-area: cat;
	}
	.sum {
		grid-area: sum;
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
		grid-area: suggest;
		justify-self: start;
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
		max-width: 100%;
		min-width: 0;
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
		/* The global button style centres content; keep the start visible when it overflows */
		justify-content: flex-start;
	}
	.suggest > :global(*) {
		flex: none;
	}
	.suggest > strong {
		flex: 0 1 auto;
		min-width: 0;
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
			grid-template-columns: auto minmax(0, 1fr) auto;
			grid-template-areas: 'av main sum' 'av suggest suggest' 'av cat cat';
			gap: 0.5rem 0.85rem;
			padding: 0.8rem 1rem;
		}
		.avatar {
			align-self: start;
		}
		/* Narrow rows: allow the payee two lines instead of cutting it after a few letters */
		.payee {
			white-space: normal;
			display: -webkit-box;
			-webkit-box-orient: vertical;
			-webkit-line-clamp: 2;
			line-clamp: 2;
			overflow-wrap: break-word;
		}
		.cat :global(.select-trigger) {
			width: 100%;
		}
		.suggest .lbl {
			display: none;
		}
	}
</style>
