<!--
	Styled choice between a few options (real radio buttons underneath, arrow keys work).
	variant="segmented": segments side by side (like a toggle)
	variant="list": round option buttons stacked vertically
-->
<script lang="ts" generics="T">
	import type { SelectOption } from './types';

	let {
		options,
		value = $bindable(),
		label,
		variant = 'segmented',
		disabled = false,
		class: cls = '',
		onchange
	}: {
		options: SelectOption<T>[];
		value: T;
		label: string;
		variant?: 'segmented' | 'list';
		disabled?: boolean;
		class?: string;
		onchange?: (value: T) => void;
	} = $props();

	const name = $props.id();
</script>

<div class="radios {variant} {cls}" role="radiogroup" aria-label={label}>
	{#each options as o, i (i)}
		<label class="opt" class:on={o.value === value} class:disabled={disabled || o.disabled}>
			<input
				type="radio"
				class="sr-only"
				{name}
				checked={o.value === value}
				disabled={disabled || o.disabled}
				onchange={() => {
					value = o.value;
					onchange?.(o.value);
				}}
			/>
			{#if variant === 'list'}<span class="ring" aria-hidden="true"></span>{/if}
			{#if o.color}<span class="dot" style:background={o.color}></span>{/if}
			<span>{o.label}</span>
		</label>
	{/each}
</div>

<style>
	.radios {
		display: inline-flex;
	}
	.opt {
		display: inline-flex;
		flex-direction: row;
		align-items: center;
		gap: 0.5rem;
		font-size: 0.9rem;
		font-weight: 500;
		color: var(--muted);
		cursor: pointer;
		user-select: none;
		position: relative;
	}
	.disabled {
		opacity: 0.5;
		cursor: default;
	}

	/* Segments */
	.segmented {
		background: var(--surface-2);
		border-radius: var(--radius-sm);
		padding: 0.2rem;
		gap: 0.2rem;
		max-width: 100%;
	}
	.segmented .opt {
		flex: 1 1 0;
		min-width: 0;
		justify-content: center;
		padding: 0.45rem 0.6rem;
		font-size: 0.85rem;
		border-radius: 9px;
		white-space: nowrap;
		transition:
			background 0.15s,
			color 0.15s,
			box-shadow 0.15s;
	}
	.segmented .opt:hover {
		color: var(--text);
	}
	.segmented .opt.on {
		background: var(--surface);
		color: var(--text);
		font-weight: 600;
		box-shadow:
			0 1px 2px rgb(15 23 42 / 0.08),
			0 2px 8px rgb(15 23 42 / 0.06);
	}
	.segmented .opt:has(input:focus-visible) {
		box-shadow: var(--ring);
	}

	/* List */
	.list {
		flex-direction: column;
		gap: 0.6rem;
	}
	.list .opt {
		color: var(--text);
		font-weight: 450;
	}
	.ring {
		width: 1.25rem;
		height: 1.25rem;
		flex: none;
		border-radius: 999px;
		background: var(--surface-2);
		border: 1.5px solid var(--border);
		display: grid;
		place-items: center;
		transition:
			border-color 0.15s,
			box-shadow 0.15s;
	}
	.ring::after {
		content: '';
		width: 0.55rem;
		height: 0.55rem;
		border-radius: 999px;
		background: #fff;
		transform: scale(0);
		transition: transform 0.15s cubic-bezier(0.3, 1.6, 0.6, 1);
	}
	.list .opt:hover .ring {
		border-color: var(--accent);
	}
	.list .opt.on .ring {
		background: var(--gradient);
		border-color: transparent;
	}
	.list .opt.on .ring::after {
		transform: scale(1);
	}
	.list .opt:has(input:focus-visible) .ring {
		box-shadow: var(--ring);
	}
</style>
