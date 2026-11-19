<!--
	Styled date picker replacing <input type="date">.
	Value as ISO text "YYYY-MM-DD" ('' = empty). Weeks start on Monday.
	Calendar keyboard: arrows (day/week), PageUp/PageDown (month), Home/End (start/end of week), Enter, Esc.
-->
<script lang="ts">
	import CalendarDays from '@lucide/svelte/icons/calendar-days';
	import ChevronLeft from '@lucide/svelte/icons/chevron-left';
	import ChevronRight from '@lucide/svelte/icons/chevron-right';
	import Popover from './Popover.svelte';
	import { t } from '../i18n/index.svelte';
	import { dateFormat } from '../format';

	let {
		value = $bindable(''),
		placeholder,
		label: labelProp,
		clearable = true,
		min,
		max,
		disabled = false,
		id,
		class: cls = '',
		onchange
	}: {
		value: string;
		placeholder?: string;
		label?: string;
		clearable?: boolean;
		min?: string;
		max?: string;
		disabled?: boolean;
		id?: string;
		class?: string;
		onchange?: (value: string) => void;
	} = $props();

	const pad = (n: number) => String(n).padStart(2, '0');
	const iso = (d: Date) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
	const parse = (s: string) => {
		const [y, m, d] = s.split('-').map(Number);
		return new Date(y, m - 1, d, 12);
	};
	const today = () => iso(new Date());
	const addDays = (s: string, n: number) => {
		const d = parse(s);
		d.setDate(d.getDate() + n);
		return iso(d);
	};
	const addMonths = (s: string, n: number) => {
		const d = parse(s);
		const day = d.getDate();
		d.setDate(1);
		d.setMonth(d.getMonth() + n);
		const last = new Date(d.getFullYear(), d.getMonth() + 1, 0).getDate();
		d.setDate(Math.min(day, last));
		return iso(d);
	};
	const outOfRange = (s: string) => (!!min && s < min) || (!!max && s > max);

	let label = $derived(labelProp ?? t('ui.date.label'));
	let placeholderText = $derived(placeholder ?? t('ui.date.placeholder'));
	let display = $derived(dateFormat({ day: '2-digit', month: '2-digit', year: 'numeric' }));
	let monthTitle = $derived(dateFormat({ month: 'long', year: 'numeric' }));
	let longDay = $derived(dateFormat({ weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' }));
	// Monday to Sunday (2024-01-01 was a Monday)
	let weekdays = $derived.by(() => {
		const f = dateFormat({ weekday: 'short' });
		return Array.from({ length: 7 }, (_, i) => f.format(new Date(2024, 0, 1 + i, 12)).replace('.', '').slice(0, 2));
	});

	let open = $state(false);
	let focused = $state(today());
	let trigger = $state<HTMLButtonElement>();
	let grid = $state<HTMLDivElement>();

	let view = $derived(parse(focused));
	let days = $derived.by(() => {
		const first = new Date(view.getFullYear(), view.getMonth(), 1, 12);
		const offset = (first.getDay() + 6) % 7;
		const start = new Date(first);
		start.setDate(1 - offset);
		const out: { iso: string; day: number; inMonth: boolean }[] = [];
		for (let i = 0; i < 42; i++) {
			const d = new Date(start);
			d.setDate(start.getDate() + i);
			out.push({ iso: iso(d), day: d.getDate(), inMonth: d.getMonth() === view.getMonth() });
		}
		// Drop the last row if it lies entirely in the next month
		return out.slice(35).every((d) => !d.inMonth) ? out.slice(0, 35) : out;
	});

	function show() {
		if (disabled) return;
		focused = value || today();
		open = true;
		requestAnimationFrame(focusDay);
	}
	function hide(refocus = true) {
		open = false;
		if (refocus) trigger?.focus();
	}
	function focusDay() {
		grid?.querySelector<HTMLElement>('[tabindex="0"]')?.focus();
	}
	function set(v: string) {
		if (v && outOfRange(v)) return;
		value = v;
		onchange?.(v);
		hide();
	}
	function go(next: string) {
		focused = next;
		requestAnimationFrame(focusDay);
	}

	function onGridKey(e: KeyboardEvent) {
		const map: Record<string, () => string> = {
			ArrowLeft: () => addDays(focused, -1),
			ArrowRight: () => addDays(focused, 1),
			ArrowUp: () => addDays(focused, -7),
			ArrowDown: () => addDays(focused, 7),
			PageUp: () => addMonths(focused, e.shiftKey ? -12 : -1),
			PageDown: () => addMonths(focused, e.shiftKey ? 12 : 1),
			Home: () => addDays(focused, -((parse(focused).getDay() + 6) % 7)),
			End: () => addDays(focused, 6 - ((parse(focused).getDay() + 6) % 7))
		};
		if (map[e.key]) {
			e.preventDefault();
			go(map[e.key]());
		} else if (e.key === 'Enter' || e.key === ' ') {
			e.preventDefault();
			set(focused);
		}
	}
</script>

<button
	bind:this={trigger}
	type="button"
	{id}
	class="select-trigger {cls}"
	class:open
	class:placeholder={!value}
	{disabled}
	aria-haspopup="dialog"
	aria-expanded={open}
	aria-label="{label}: {value ? longDay.format(parse(value)) : placeholderText}"
	onclick={() => (open ? hide() : show())}
	onkeydown={(e) => {
		if (e.key === 'ArrowDown') {
			e.preventDefault();
			show();
		}
	}}
>
	<span class="chev"><CalendarDays size={16} /></span>
	<span class="value">{value ? display.format(parse(value)) : placeholderText}</span>
</button>

<Popover bind:open anchor={trigger} {label} matchWidth={false} minWidth={288}>
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div
		class="cal"
		role="dialog"
		aria-label={label}
		tabindex="-1"
		onkeydown={(e) => {
			if (e.key === 'Escape') {
				e.preventDefault();
				hide();
			}
		}}
	>
		<div class="head">
			<button type="button" class="ghost icon" aria-label={t('ui.date.prevMonth')} onclick={() => go(addMonths(focused, -1))}><ChevronLeft size={18} /></button>
			<strong aria-live="polite">{monthTitle.format(view)}</strong>
			<button type="button" class="ghost icon" aria-label={t('ui.date.nextMonth')} onclick={() => go(addMonths(focused, 1))}><ChevronRight size={18} /></button>
		</div>
		<div class="grid" role="grid" bind:this={grid} tabindex="-1" onkeydown={onGridKey}>
			<div class="row" role="row">
				{#each weekdays as w (w)}<span class="wd" role="columnheader">{w}</span>{/each}
			</div>
			{#each { length: days.length / 7 } as _, r (r)}
				<div class="row" role="row">
					{#each days.slice(r * 7, r * 7 + 7) as d (d.iso)}
						<button
							type="button"
							role="gridcell"
							class="day"
							class:out={!d.inMonth}
							class:today={d.iso === today()}
							class:selected={d.iso === value}
							disabled={outOfRange(d.iso)}
							tabindex={d.iso === focused ? 0 : -1}
							aria-selected={d.iso === value}
							aria-label={longDay.format(parse(d.iso))}
							onclick={() => set(d.iso)}
							onfocus={() => (focused = d.iso)}>{d.day}</button
						>
					{/each}
				</div>
			{/each}
		</div>
		<div class="foot">
			<button type="button" class="link" onclick={() => set(today())} disabled={outOfRange(today())}>{t('ui.date.today')}</button>
			{#if clearable && value}<button type="button" class="link muted" onclick={() => set('')}>{t('ui.date.clear')}</button>{/if}
		</div>
	</div>
</Popover>

<style>
	.cal {
		padding: 0.75rem;
		outline: none;
	}
	.head {
		display: flex;
		align-items: center;
		justify-content: space-between;
		margin-bottom: 0.5rem;
	}
	.head strong {
		font-weight: 650;
		text-transform: capitalize;
	}
	.head :global(button.icon) {
		width: 2.1rem;
		height: 2.1rem;
	}
	.grid {
		display: grid;
		gap: 2px;
		outline: none;
	}
	.row {
		display: grid;
		grid-template-columns: repeat(7, 1fr);
		gap: 2px;
	}
	.wd {
		text-align: center;
		font-size: 0.7rem;
		font-weight: 650;
		text-transform: uppercase;
		color: var(--faint);
		padding: 0.25rem 0;
	}
	.day {
		aspect-ratio: 1;
		min-width: 2.25rem;
		padding: 0;
		border-radius: 10px;
		background: transparent;
		color: var(--text);
		box-shadow: none;
		font-weight: 500;
		font-size: 0.88rem;
		font-variant-numeric: tabular-nums;
	}
	.day:hover {
		background: var(--surface-2);
		filter: none;
		box-shadow: none;
	}
	.day:active {
		transform: none;
	}
	.day:focus-visible {
		box-shadow: var(--ring);
	}
	.day.out {
		color: var(--faint);
	}
	.day.today {
		color: var(--accent-strong);
		font-weight: 700;
		box-shadow: inset 0 0 0 1.5px var(--accent);
	}
	.day.selected {
		background: var(--gradient);
		color: #fff;
		font-weight: 700;
		box-shadow: 0 4px 12px rgb(16 185 129 / 0.3);
	}
	.foot {
		display: flex;
		justify-content: space-between;
		padding: 0.6rem 0.25rem 0;
		margin-top: 0.5rem;
		border-top: 1px solid var(--border);
	}
	.foot .muted {
		color: var(--muted);
	}
	@media (max-width: 640px) {
		.cal {
			padding: 0.5rem 1rem 1rem;
		}
		.day {
			font-size: 1rem;
		}
	}
</style>
