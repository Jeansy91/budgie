<script lang="ts">
	import { api } from './api';
	import { monthLabel, shiftMonth } from './format';
	import type { Transaction } from './types';
	import { t } from './i18n/index.svelte';
	import CalendarArrowDown from '@lucide/svelte/icons/calendar-arrow-down';
	import CalendarDays from '@lucide/svelte/icons/calendar-days';
	import Check from '@lucide/svelte/icons/check';

	/** Shows a transaction's budget month and lets the user override it. */
	let {
		tx,
		onchange,
		onerror
	}: { tx: Transaction; onchange?: (tx: Transaction) => void; onerror?: (message: string) => void } = $props();

	let open = $state(false);
	let root = $state<HTMLElement>();

	let bookingMonth = $derived(tx.booking_date.slice(0, 7));
	let budgetMonth = $derived(tx.budget_date.slice(0, 7));
	let shifted = $derived(budgetMonth !== bookingMonth);
	let nextMonth = $derived(shiftMonth(bookingMonth, 1));
	let current = $derived(tx.budget_shift ?? 'auto');
	let short = $derived(monthLabel(budgetMonth).split(' ')[0]);

	const options = $derived([
		{ value: 'auto', label: t('budgetMenu.auto'), hint: t('budgetMenu.autoHint') },
		{ value: 'same', label: monthLabel(bookingMonth), hint: t('budgetMenu.bookingMonth') },
		{ value: 'next', label: monthLabel(nextMonth), hint: t('budgetMenu.nextMonth') }
	] as const);

	async function choose(value: 'auto' | 'same' | 'next') {
		open = false;
		if (value === current) return;
		try {
			const res = await api<{ transaction: Transaction }>(`/transactions/${tx.id}`, {
				method: 'PATCH',
				body: { budget_shift: value }
			});
			onchange?.(res.transaction);
		} catch (e) {
			onerror?.((e as Error).message);
		}
	}

	function outside(e: PointerEvent) {
		if (open && root && !root.contains(e.target as Node)) open = false;
	}
</script>

<svelte:window onpointerdown={outside} onkeydown={(e) => e.key === 'Escape' && (open = false)} />

<span class="bm" class:visible={shifted || tx.budget_shift || Number(tx.amount) > 0} bind:this={root}>
	<button
		type="button"
		class="trigger"
		class:shifted
		class:manual={tx.budget_shift !== null}
		aria-haspopup="menu"
		aria-expanded={open}
		title={shifted ? t('budgetMenu.countsFor', { month: monthLabel(budgetMonth) }) : t('budgetMenu.set')}
		onclick={() => (open = !open)}
	>
		{#if shifted}
			<CalendarArrowDown size={13} /> {t('budgetMenu.countsForShort', { month: short })}
		{:else}
			<CalendarDays size={13} />
			{#if tx.budget_shift === 'same'}<span>{short}</span>{/if}
		{/if}
	</button>
	{#if open}
		<div class="menu" role="menu">
			<div class="head">{t('budgetMenu.title')}</div>
			{#each options as o (o.value)}
				<button type="button" role="menuitemradio" aria-checked={current === o.value} onclick={() => choose(o.value)}>
					<span class="check">{#if current === o.value}<Check size={15} />{/if}</span>
					<span class="txt">
						<span class="lbl">{o.label}</span>
						<span class="hint">{o.hint}{#if o.value === 'auto'}{' · '}{t('budgetMenu.now', { month: monthLabel(budgetMonth) })}{/if}</span>
					</span>
				</button>
			{/each}
		</div>
	{/if}
</span>

<style>
	.bm {
		position: relative;
		display: inline-flex;
		vertical-align: middle;
	}
	.bm:not(.visible) .trigger {
		opacity: 0;
	}
	:global(.tx:hover) .bm .trigger,
	.bm .trigger:focus-visible,
	.bm .trigger[aria-expanded='true'] {
		opacity: 1;
	}
	.trigger {
		display: inline-flex;
		align-items: center;
		gap: 0.3rem;
		padding: 0.15rem 0.5rem;
		border-radius: 999px;
		background: var(--surface-2);
		color: var(--faint);
		box-shadow: none;
		font-size: 0.72rem;
		font-weight: 600;
		line-height: 1.4;
		transition: opacity 0.15s;
	}
	.trigger:hover {
		filter: none;
		box-shadow: none;
		color: var(--accent-strong);
		background: var(--accent-soft);
	}
	.trigger.shifted {
		background: var(--accent-soft);
		color: var(--accent-strong);
	}
	.trigger.manual:not(.shifted) {
		color: var(--muted);
	}
	.menu {
		position: absolute;
		z-index: 20;
		top: calc(100% + 0.35rem);
		left: 0;
		min-width: 15rem;
		padding: 0.35rem;
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: var(--radius-sm);
		box-shadow: var(--shadow-lg);
		font-weight: 400;
		white-space: normal;
	}
	.head {
		padding: 0.35rem 0.6rem 0.25rem;
		font-size: 0.7rem;
		font-weight: 650;
		text-transform: uppercase;
		letter-spacing: 0.05em;
		color: var(--faint);
	}
	.menu button {
		display: flex;
		align-items: flex-start;
		justify-content: flex-start;
		gap: 0.5rem;
		width: 100%;
		padding: 0.5rem 0.6rem;
		border-radius: 9px;
		background: transparent;
		color: var(--text);
		box-shadow: none;
		text-align: left;
		font-weight: 500;
	}
	.menu button:hover {
		background: var(--surface-2);
		filter: none;
		box-shadow: none;
	}
	.menu button[aria-checked='true'] .lbl {
		color: var(--accent-strong);
		font-weight: 650;
	}
	.check {
		display: grid;
		place-items: center;
		width: 1rem;
		height: 1.2rem;
		flex: none;
		color: var(--accent-strong);
	}
	.txt {
		display: grid;
		gap: 0.05rem;
	}
	.lbl {
		font-size: 0.88rem;
	}
	.hint {
		font-size: 0.75rem;
		color: var(--muted);
	}
</style>
