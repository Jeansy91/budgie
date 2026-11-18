<!--
	Styled month picker replacing <input type="month">.
	Value as "YYYY-MM" ('' = no month, e.g. "all months" in a filter).
	Keyboard: arrows (month/quarter), PageUp/PageDown (year), Enter, Esc.
-->
<script lang="ts">
	import Calendar from '@lucide/svelte/icons/calendar';
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
		clearLabel,
		disabled = false,
		id,
		class: cls = '',
		onchange
	}: {
		value: string;
		placeholder?: string;
		label?: string;
		clearable?: boolean;
		clearLabel?: string;
		disabled?: boolean;
		id?: string;
		class?: string;
		onchange?: (value: string) => void;
	} = $props();

	const pad = (n: number) => String(n).padStart(2, '0');
	const now = () => {
		const d = new Date();
		return `${d.getFullYear()}-${pad(d.getMonth() + 1)}`;
	};
	const shift = (ym: string, n: number) => {
		const [y, m] = ym.split('-').map(Number);
		const total = y * 12 + (m - 1) + n;
		return `${Math.floor(total / 12)}-${pad((total % 12) + 1)}`;
	};
	let label = $derived(labelProp ?? t('ui.month.label'));
	let placeholderText = $derived(placeholder ?? t('ui.month.placeholder'));
	const labelOf = (ym: string) => dateFormat({ month: 'long', year: 'numeric' }).format(new Date(`${ym}-01T12:00:00`));
	let months = $derived.by(() => {
		const short = dateFormat({ month: 'short' });
		return Array.from({ length: 12 }, (_, i) => ({
			m: pad(i + 1),
			name: short.format(new Date(2024, i, 1, 12)).replace('.', '')
		}));
	});

	let open = $state(false);
	let focused = $state(now());
	let trigger = $state<HTMLButtonElement>();
	let grid = $state<HTMLDivElement>();
	let year = $derived(focused.slice(0, 4));

	function show() {
		if (disabled) return;
		focused = value || now();
		open = true;
		requestAnimationFrame(focusCell);
	}
	function hide(refocus = true) {
		open = false;
		if (refocus) trigger?.focus();
	}
	function focusCell() {
		grid?.querySelector<HTMLElement>('[tabindex="0"]')?.focus();
	}
	function set(v: string) {
		value = v;
		onchange?.(v);
		hide();
	}
	function go(next: string) {
		focused = next;
		requestAnimationFrame(focusCell);
	}
	function onGridKey(e: KeyboardEvent) {
		const step: Record<string, number> = { ArrowLeft: -1, ArrowRight: 1, ArrowUp: -3, ArrowDown: 3, PageUp: -12, PageDown: 12 };
		if (e.key in step) {
			e.preventDefault();
			go(shift(focused, step[e.key]));
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
	aria-label="{label}: {value ? labelOf(value) : placeholderText}"
	onclick={() => (open ? hide() : show())}
	onkeydown={(e) => {
		if (e.key === 'ArrowDown') {
			e.preventDefault();
			show();
		}
	}}
>
	<span class="chev"><Calendar size={16} /></span>
	<span class="value">{value ? labelOf(value) : placeholderText}</span>
</button>

<Popover bind:open anchor={trigger} {label} matchWidth={false} minWidth={272}>
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div
		class="pick"
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
			<button type="button" class="ghost icon" aria-label={t('ui.month.prevYear')} onclick={() => go(shift(focused, -12))}><ChevronLeft size={18} /></button>
			<strong aria-live="polite">{year}</strong>
			<button type="button" class="ghost icon" aria-label={t('ui.month.nextYear')} onclick={() => go(shift(focused, 12))}><ChevronRight size={18} /></button>
		</div>
		<!-- svelte-ignore a11y_interactive_supports_focus -->
		<div class="grid" role="grid" bind:this={grid} onkeydown={onGridKey}>
			{#each months as mo (mo.m)}
				{@const ym = `${year}-${mo.m}`}
				<button
					type="button"
					class="cell"
					class:now={ym === now()}
					class:selected={ym === value}
					tabindex={ym === focused ? 0 : -1}
					aria-pressed={ym === value}
					aria-label={labelOf(ym)}
					onclick={() => set(ym)}
					onfocus={() => (focused = ym)}>{mo.name}</button
				>
			{/each}
		</div>
		<div class="foot">
			<button type="button" class="link" onclick={() => set(now())}>{t('ui.month.thisMonth')}</button>
			{#if clearable}<button type="button" class="link muted" onclick={() => set('')}>{clearLabel ?? t('ui.month.all')}</button>{/if}
		</div>
	</div>
</Popover>

<style>
	.pick {
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
		font-variant-numeric: tabular-nums;
	}
	.head :global(button.icon) {
		width: 2.1rem;
		height: 2.1rem;
	}
	.grid {
		display: grid;
		grid-template-columns: repeat(3, 1fr);
		gap: 0.35rem;
	}
	.cell {
		padding: 0.65rem 0;
		border-radius: 10px;
		background: transparent;
		color: var(--text);
		box-shadow: none;
		font-weight: 500;
	}
	.cell:hover {
		background: var(--surface-2);
		filter: none;
		box-shadow: none;
	}
	.cell:active {
		transform: none;
	}
	.cell:focus-visible {
		box-shadow: var(--ring);
	}
	.cell.now {
		color: var(--accent-strong);
		font-weight: 700;
		box-shadow: inset 0 0 0 1.5px var(--accent);
	}
	.cell.selected {
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
		.pick {
			padding: 0.5rem 1rem 1rem;
		}
		.cell {
			padding: 0.9rem 0;
		}
	}
</style>
