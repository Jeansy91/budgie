<!--
	Styled number field with custom −/+ buttons instead of the browser spinners.
	The up/down arrow keys change the value as well.
-->
<script lang="ts">
	import { t } from '../i18n/index.svelte';
	import Minus from '@lucide/svelte/icons/minus';
	import Plus from '@lucide/svelte/icons/plus';

	let {
		value = $bindable(0),
		min,
		max,
		step = 1,
		disabled = false,
		label,
		id,
		class: cls = '',
		onchange
	}: {
		value: number;
		min?: number;
		max?: number;
		step?: number;
		disabled?: boolean;
		label?: string;
		id?: string;
		class?: string;
		onchange?: (value: number) => void;
	} = $props();

	let text = $state(String(value));
	$effect(() => {
		if (Number(text.replace(',', '.')) !== value) text = String(value);
	});

	const clamp = (n: number) => Math.min(max ?? Infinity, Math.max(min ?? -Infinity, n));
	function set(n: number) {
		if (Number.isNaN(n)) return;
		value = clamp(Math.round(n * 1e6) / 1e6);
		text = String(value);
		onchange?.(value);
	}
</script>

<div class="num {cls}" class:disabled>
	<button type="button" tabindex="-1" aria-label={t('ui.number.less')} onclick={() => set(value - step)} disabled={disabled || (min !== undefined && value <= min)}><Minus size={14} /></button>
	<input
		{id}
		type="text"
		inputmode="decimal"
		aria-label={label}
		role="spinbutton"
		aria-valuenow={value}
		aria-valuemin={min}
		aria-valuemax={max}
		{disabled}
		bind:value={text}
		onkeydown={(e) => {
			if (e.key === 'ArrowUp' || e.key === 'ArrowDown') {
				e.preventDefault();
				set(value + (e.key === 'ArrowUp' ? step : -step));
			}
		}}
		onchange={() => {
			const n = Number(text.replace(',', '.'));
			if (text.trim() === '' || Number.isNaN(n)) text = String(value);
			else set(n);
		}}
	/>
	<button type="button" tabindex="-1" aria-label={t('ui.number.more')} onclick={() => set(value + step)} disabled={disabled || (max !== undefined && value >= max)}><Plus size={14} /></button>
</div>

<style>
	.num {
		display: inline-flex;
		align-items: center;
		background: var(--surface-2);
		border: 1px solid transparent;
		border-radius: var(--radius-sm);
		transition:
			border-color 0.15s,
			box-shadow 0.15s,
			background 0.15s;
	}
	.num:hover {
		background: var(--surface-3);
	}
	.num:focus-within {
		border-color: var(--accent);
		box-shadow: var(--ring);
		background: var(--surface);
	}
	.num input {
		width: 3.5em;
		min-width: 0;
		flex: 1;
		text-align: center;
		font-variant-numeric: tabular-nums;
		background: transparent !important;
		border: 0 !important;
		box-shadow: none !important;
		padding-left: 0.2rem !important;
		padding-right: 0.2rem !important;
	}
	.num button {
		width: 2rem;
		height: 2rem;
		margin: 0 0.2rem;
		padding: 0;
		flex: none;
		border-radius: 9px;
		background: transparent;
		color: var(--muted);
		box-shadow: none;
	}
	.num button:hover:not(:disabled) {
		background: var(--surface);
		color: var(--accent-strong);
		filter: none;
		box-shadow: 0 1px 3px rgb(15 23 42 / 0.08);
	}
	.num button:disabled {
		opacity: 0.3;
	}
	.disabled {
		opacity: 0.5;
	}
</style>
