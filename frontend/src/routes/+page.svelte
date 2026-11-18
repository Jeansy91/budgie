<script lang="ts">
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import { api } from '$lib/api';
	import { Select, type SelectOption } from '$lib/ui';
	import { colorFor } from '$lib/colors';
	import { currentMonth, money, monthLabel, monthShortLabel, shiftMonth } from '$lib/format';
	import type { Account, Category, CategorySum, Overview } from '$lib/types';
	import ChevronLeft from '@lucide/svelte/icons/chevron-left';
	import ChevronRight from '@lucide/svelte/icons/chevron-right';
	import ChevronDown from '@lucide/svelte/icons/chevron-down';
	import TrendingUp from '@lucide/svelte/icons/trending-up';
	import TrendingDown from '@lucide/svelte/icons/trending-down';
	import Sparkles from '@lucide/svelte/icons/sparkles';
	import ArrowLeftRight from '@lucide/svelte/icons/arrow-left-right';

	let month = $derived(page.url.searchParams.get('month') ?? currentMonth());
	let accountId = $state('');
	let accounts = $state<Account[]>([]);
	let accountOptions = $derived<SelectOption<string>[]>([
		{ value: '', label: 'Alle Konten' },
		...accounts.map((a) => ({ value: String(a.id), label: a.name, hint: a.iban ? '…' + a.iban.slice(-4) : undefined }))
	]);
	let categoryIndex = $state(new Map<number, number>());
	let data = $state<Overview | null>(null);
	let error = $state('');
	let open = $state<Record<string, boolean>>({});

	api<Account[]>('/accounts').then((a) => (accounts = a));
	api<Category[]>('/categories').then((tree) => (categoryIndex = new Map(tree.map((c, i) => [c.id, i]))));

	$effect(() => {
		const m = month;
		const acc = accountId;
		api<Overview>('/overview', { params: { month: m, account_id: acc } })
			.then((d) => {
				data = d;
				error = '';
			})
			.catch((e) => (error = e.message));
	});

	const go = (m: string) => goto(`/?month=${m}`, { keepFocus: true, noScroll: true });
	const color = (c: CategorySum) => colorFor(c.category_id === null ? undefined : categoryIndex.get(c.category_id));
	const pct = (part: string | number, total: string | number) =>
		Number(total) > 0 ? Math.round((Number(part) / Number(total)) * 100) : 0;

	// Donut chart: segments as fractions of the circumference
	const R = 52;
	const C = 2 * Math.PI * R;
	let segments = $derived.by(() => {
		if (!data) return [];
		const total = data.expense_categories.reduce((s, c) => s + Number(c.amount), 0);
		let offset = 0;
		return data.expense_categories
			.filter((c) => Number(c.amount) > 0)
			.map((c) => {
				const len = total ? (Number(c.amount) / total) * C : 0;
				const seg = { c, len: Math.max(len - 2, 0.5), offset };
				offset += len;
				return seg;
			});
	});

	let historyMax = $derived(
		data ? Math.max(1, ...data.history.flatMap((h) => [Number(h.income), Number(h.expenses)])) : 1
	);
	let savingsRate = $derived(data && Number(data.income) > 0 ? pct(data.net, data.income) : null);
</script>

<div class="page-head">
	<div>
		<span class="eyebrow">Monatsübersicht</span>
		<h1>{monthLabel(month)}</h1>
	</div>
	<div class="controls">
		{#if accounts.length > 1}
			<Select options={accountOptions} bind:value={accountId} label="Konto" />
		{/if}
		<div class="switch">
			<button class="ghost icon" onclick={() => go(shiftMonth(month, -1))} aria-label="Vormonat"><ChevronLeft size={18} /></button>
			<button class="ghost today" onclick={() => go(currentMonth())} disabled={month === currentMonth()}>Heute</button>
			<button class="ghost icon" onclick={() => go(shiftMonth(month, 1))} aria-label="Nächster Monat"><ChevronRight size={18} /></button>
		</div>
	</div>
</div>

{#if error}<div class="error">{error}</div>{/if}

{#if data}
	{#if accounts.length === 0}
		<div class="card empty">
			<Sparkles size={22} />
			<div>
				<strong>Noch keine Buchungen.</strong>
				<a href="/import">Importiere deine erste ING-CSV-Datei</a>, dann füllt sich die Übersicht.
			</div>
		</div>
	{/if}

	<section class="kpis">
		<div class="hero">
			<span class="label">Saldo im Monat</span>
			<strong class="big">{money(data.net)}</strong>
			<span class="sub">
				{#if savingsRate !== null}{savingsRate} % der Einnahmen übrig{:else}Noch keine Einnahmen in diesem Monat{/if}
			</span>
			<div class="blob"></div>
		</div>
		<div class="card kpi">
			<span class="chip in"><TrendingUp size={18} /></span>
			<div>
				<span class="label">Einnahmen</span>
				<strong class="pos">{money(data.income)}</strong>
				{#if Number(data.income_from_previous_month) > 0}
					<a
						class="carry small"
						href={`/transactions?month=${month}`}
						title="Gehalt vom Monatsende zählt für den Folgemonat. Einstellbar unter Einstellungen › Budgetmonat."
						>davon {money(data.income_from_previous_month)} aus dem Vormonat</a
					>
				{/if}
			</div>
		</div>
		<div class="card kpi">
			<span class="chip out"><TrendingDown size={18} /></span>
			<div>
				<span class="label">Ausgaben</span>
				<strong>{money(data.expenses)}</strong>
			</div>
		</div>
	</section>

	{#if data.uncategorized_count > 0}
		<a class="warn nudge" href={`/transactions?month=${month}&uncategorized=1`}>
			<Sparkles size={18} />
			<span><strong>{data.uncategorized_count} Buchungen</strong> haben noch keine Kategorie.</span>
			<span class="go">Jetzt zuordnen <ChevronRight size={16} /></span>
		</a>
	{/if}

	<div class="grid">
		<section class="card">
			<h2>Ausgaben nach Kategorie</h2>
			{#if segments.length === 0}
				<p class="muted">Keine Ausgaben in diesem Monat.</p>
			{:else}
				<div class="split">
					<div class="donut">
						<svg viewBox="0 0 140 140">
							<circle cx="70" cy="70" r={R} fill="none" stroke="var(--surface-2)" stroke-width="16" />
							{#each segments as s (s.c.category_id ?? 'none')}
								<circle
									cx="70"
									cy="70"
									r={R}
									fill="none"
									stroke={color(s.c)}
									stroke-width="16"
									stroke-linecap="butt"
									stroke-dasharray="{s.len} {C}"
									stroke-dashoffset={-s.offset}
									transform="rotate(-90 70 70)"
								/>
							{/each}
						</svg>
						<div class="center">
							<span class="label">Gesamt</span>
							<strong>{money(data.expenses)}</strong>
						</div>
					</div>
					<div class="legend">
						{#each data.expense_categories as c (c.category_id ?? 'none')}
							{@const key = `e-${c.category_id}`}
							<button class="leg" onclick={() => (open[key] = !open[key])} disabled={!c.children.length}>
								<span class="dot" style:background={color(c)}></span>
								<span class="name">{c.name}</span>
								<span class="share">{pct(c.amount, data.expenses)} %</span>
								<span class="amount">{money(c.amount)}</span>
								{#if c.children.length}<span class="chev" class:rot={open[key]}><ChevronDown size={15} /></span>{/if}
							</button>
							{#if open[key]}
								<div class="children">
									{#each c.children as sub (sub.category_id)}
										<a href={`/transactions?month=${month}&category_id=${sub.category_id}`}>
											<span>{sub.name}</span>
											<span class="track"><span style:width="{pct(sub.amount, c.amount)}%" style:background={color(c)}></span></span>
											<span class="amount">{money(sub.amount)}</span>
										</a>
									{/each}
								</div>
							{/if}
						{/each}
					</div>
				</div>
			{/if}
		</section>

		<section class="card">
			<h2>Einnahmen</h2>
			{#if data.income_categories.length === 0}<p class="muted">Keine Einnahmen in diesem Monat.</p>{/if}
			{#each data.income_categories as c (c.category_id ?? 'none')}
				<div class="inc">
					<div class="inc-head">
						<span>{c.name}</span>
						<span class="amount pos">{money(c.amount)}</span>
					</div>
					{#each c.children as sub (sub.category_id)}
						<div class="inc-sub"><span>{sub.name}</span><span class="amount">{money(sub.amount)}</span></div>
					{/each}
				</div>
			{/each}
			{#if Number(data.transfers) !== 0}
				<div class="transfer small muted">
					<ArrowLeftRight size={15} /> Umbuchungen zwischen eigenen Konten: {money(data.transfers)} (nicht mitgezählt)
				</div>
			{/if}
		</section>
	</div>

	<section class="card">
		<div class="hist-head">
			<h2>Verlauf der letzten 12 Monate</h2>
			<div class="keys small muted">
				<span><span class="dot" style:background="var(--accent)"></span> Einnahmen</span>
				<span><span class="dot" style:background="var(--expense)"></span> Ausgaben</span>
			</div>
		</div>
		<div class="history">
			{#each data.history as h (h.month)}
				<button
					class="col"
					class:current={h.month === month}
					onclick={() => go(h.month)}
					title={`${monthLabel(h.month)}\nEinnahmen ${money(h.income)}\nAusgaben ${money(h.expenses)}`}
				>
					<span class="bars">
						<span class="b in" style:height="{(Number(h.income) / historyMax) * 100}%"></span>
						<span class="b out" style:height="{(Number(h.expenses) / historyMax) * 100}%"></span>
					</span>
					<span class="m">{monthShortLabel(h.month)}</span>
				</button>
			{/each}
		</div>
	</section>
{/if}

<style>
	.controls {
		display: flex;
		gap: 0.6rem;
		align-items: center;
	}
	.controls :global(.select-trigger:not(.open):not(:focus-visible)) {
		background: var(--surface);
		border-color: var(--border);
		border-radius: 999px;
		padding-left: 1rem;
		box-shadow: var(--shadow);
	}
	.switch {
		display: flex;
		align-items: center;
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: 999px;
		padding: 0.2rem;
		box-shadow: var(--shadow);
	}
	.today {
		font-size: 0.85rem;
	}
	.label {
		font-size: 0.8rem;
		font-weight: 550;
		color: var(--muted);
	}
	.empty {
		display: flex;
		gap: 0.9rem;
		align-items: center;
		color: var(--accent-strong);
	}
	.empty div {
		color: var(--text);
	}

	.kpis {
		display: grid;
		grid-template-columns: 1.4fr 1fr 1fr;
		gap: 1rem;
		margin-bottom: 1rem;
	}
	.hero {
		position: relative;
		overflow: hidden;
		display: flex;
		flex-direction: column;
		gap: 0.3rem;
		padding: 1.4rem 1.5rem;
		border-radius: var(--radius);
		background: var(--gradient);
		color: #fff;
		box-shadow: 0 12px 30px rgb(16 185 129 / 0.3);
	}
	.hero .label,
	.hero .sub {
		color: rgb(255 255 255 / 0.85);
	}
	.hero .big {
		font-size: 2.2rem;
		font-weight: 750;
		letter-spacing: -0.03em;
		font-variant-numeric: tabular-nums;
	}
	.hero .sub {
		font-size: 0.85rem;
	}
	.blob {
		position: absolute;
		right: -40px;
		top: -40px;
		width: 180px;
		height: 180px;
		border-radius: 999px;
		background: rgb(255 255 255 / 0.12);
	}
	.kpi {
		display: flex;
		align-items: center;
		gap: 1rem;
		margin: 0;
	}
	.kpi div {
		display: flex;
		flex-direction: column;
		gap: 0.15rem;
	}
	.kpi strong {
		font-size: 1.45rem;
		font-weight: 700;
		letter-spacing: -0.02em;
		font-variant-numeric: tabular-nums;
	}
	.carry {
		color: var(--muted);
		font-weight: 500;
		text-decoration: none;
	}
	.carry:hover {
		color: var(--accent-strong);
	}
	.chip {
		display: grid;
		place-items: center;
		width: 2.75rem;
		height: 2.75rem;
		border-radius: 14px;
		flex: none;
	}
	.chip.in {
		background: var(--accent-soft);
		color: var(--accent-strong);
	}
	.chip.out {
		background: var(--expense-soft);
		color: var(--expense);
	}

	.nudge {
		text-decoration: none;
	}
	.nudge .go {
		margin-left: auto;
		display: flex;
		align-items: center;
		font-weight: 600;
		white-space: nowrap;
	}

	.grid {
		display: grid;
		grid-template-columns: 1.7fr 1fr;
		gap: 1rem;
		margin-bottom: 1rem;
	}
	.grid .card {
		margin: 0;
	}
	.split {
		display: grid;
		grid-template-columns: 170px 1fr;
		gap: 1.5rem;
		align-items: start;
	}
	.donut {
		position: relative;
	}
	.donut svg {
		width: 100%;
		display: block;
	}
	.center {
		position: absolute;
		inset: 0;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
	}
	.center strong {
		font-size: 1.05rem;
		font-variant-numeric: tabular-nums;
	}
	.leg {
		display: flex;
		align-items: center;
		gap: 0.6rem;
		width: 100%;
		padding: 0.55rem 0.5rem;
		background: none;
		box-shadow: none;
		color: var(--text);
		font-weight: 500;
		border-radius: 10px;
		text-align: left;
	}
	.leg:hover:not(:disabled) {
		background: var(--surface-2);
		filter: none;
	}
	.leg:disabled {
		opacity: 1;
	}
	.leg .name {
		flex: 1;
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.leg .share {
		color: var(--faint);
		font-size: 0.8rem;
		width: 3em;
		text-align: right;
	}
	.leg .amount {
		width: 7.5em;
	}
	.chev {
		display: flex;
		color: var(--faint);
		transition: transform 0.15s;
	}
	.chev.rot {
		transform: rotate(180deg);
	}
	.children {
		padding: 0.2rem 0.5rem 0.6rem 1.7rem;
	}
	.children a {
		display: grid;
		grid-template-columns: 1fr 70px 7.5em;
		gap: 0.75rem;
		align-items: center;
		padding: 0.3rem 0;
		color: var(--muted);
		text-decoration: none;
		font-size: 0.87rem;
	}
	.children a:hover {
		color: var(--text);
	}
	.track {
		height: 5px;
		border-radius: 99px;
		background: var(--surface-2);
		overflow: hidden;
	}
	.track span {
		display: block;
		height: 100%;
		border-radius: 99px;
	}

	.inc {
		padding: 0.6rem 0;
		border-bottom: 1px solid var(--border);
	}
	.inc-head {
		display: flex;
		justify-content: space-between;
		font-weight: 600;
	}
	.inc-sub {
		display: flex;
		justify-content: space-between;
		color: var(--muted);
		font-size: 0.87rem;
		padding-top: 0.3rem;
	}
	.transfer {
		display: flex;
		align-items: center;
		gap: 0.45rem;
		margin-top: 1rem;
	}

	.hist-head {
		display: flex;
		justify-content: space-between;
		flex-wrap: wrap;
		gap: 0.5rem;
	}
	.keys {
		display: flex;
		gap: 1rem;
	}
	.keys > span {
		display: flex;
		align-items: center;
		gap: 0.4rem;
	}
	.history {
		display: flex;
		gap: 0.3rem;
		align-items: end;
		height: 200px;
		background: repeating-linear-gradient(
			to top,
			transparent 0,
			transparent calc(25% - 1px),
			var(--border) calc(25% - 1px),
			var(--border) 25%
		);
		background-size: 100% calc(100% - 1.6rem);
		background-repeat: no-repeat;
	}
	.col {
		flex: 1;
		display: flex;
		flex-direction: column;
		align-items: center;
		height: 100%;
		background: none;
		box-shadow: none;
		padding: 0.3rem 0 0;
		border-radius: 12px;
		font-weight: 500;
		color: var(--faint);
	}
	.col:hover {
		background: var(--surface-2);
		filter: none;
	}
	.col.current {
		background: var(--accent-soft);
		color: var(--accent-strong);
	}
	.bars {
		flex: 1;
		display: flex;
		align-items: end;
		gap: 3px;
		width: 100%;
		justify-content: center;
	}
	.b {
		width: 30%;
		max-width: 16px;
		border-radius: 6px 6px 2px 2px;
		min-height: 2px;
		transition: height 0.4s cubic-bezier(0.2, 0.8, 0.2, 1);
	}
	.b.in {
		background: linear-gradient(to top, #10b981, #34d399);
	}
	.b.out {
		background: linear-gradient(to top, #e11d48, #fb7185);
	}
	.m {
		font-size: 0.72rem;
		padding: 0.35rem 0;
	}

	@media (max-width: 1100px) {
		.split {
			grid-template-columns: 1fr;
		}
		.donut {
			max-width: 200px;
			margin: 0 auto;
		}
	}
	@media (max-width: 900px) {
		.kpis {
			grid-template-columns: 1fr 1fr;
		}
		.hero {
			grid-column: 1 / -1;
		}
		.grid {
			grid-template-columns: 1fr;
		}
	}
	@media (max-width: 480px) {
		.kpi {
			flex-direction: column;
			align-items: start;
			gap: 0.6rem;
			padding: 1rem;
		}
		.kpi strong {
			font-size: 1.15rem;
		}
		.leg .share {
			display: none;
		}
		.children a {
			grid-template-columns: 1fr 7em;
		}
		.track {
			display: none;
		}
		.nudge .go {
			display: none;
		}
	}
</style>
