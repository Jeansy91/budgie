<!--
	Styled checkbox. A real, invisible <input type="checkbox"> sits underneath so that
	keyboard, forms and screen readers work as usual.
-->
<script lang="ts">
	import type { Snippet } from 'svelte';
	import Check from '@lucide/svelte/icons/check';

	let {
		checked = $bindable(false),
		disabled = false,
		title,
		class: cls = '',
		onchange,
		children
	}: {
		checked: boolean;
		disabled?: boolean;
		title?: string;
		class?: string;
		onchange?: (checked: boolean) => void;
		children?: Snippet;
	} = $props();
</script>

<label class="check {cls}" class:disabled {title}>
	<input
		type="checkbox"
		class="sr-only"
		bind:checked
		{disabled}
		onchange={(e) => onchange?.(e.currentTarget.checked)}
	/>
	<span class="box" aria-hidden="true"><Check size={14} strokeWidth={3} /></span>
	{#if children}<span class="text">{@render children()}</span>{/if}
</label>

<style>
	.check {
		display: inline-flex;
		flex-direction: row;
		align-items: center;
		gap: 0.6rem;
		font-size: 0.9rem;
		font-weight: 450;
		color: var(--text);
		cursor: pointer;
		user-select: none;
		position: relative;
	}
	.box {
		display: grid;
		place-items: center;
		width: 1.25rem;
		height: 1.25rem;
		flex: none;
		border-radius: 7px;
		background: var(--surface-2);
		border: 1.5px solid var(--border);
		color: #fff;
		transition:
			background 0.15s,
			border-color 0.15s,
			box-shadow 0.15s;
	}
	.box :global(svg) {
		opacity: 0;
		transform: scale(0.5);
		transition:
			opacity 0.12s,
			transform 0.15s cubic-bezier(0.3, 1.6, 0.6, 1);
	}
	.check:hover .box {
		border-color: var(--accent);
	}
	input:checked + .box {
		background: var(--gradient);
		border-color: transparent;
		box-shadow: 0 2px 8px rgb(16 185 129 / 0.3);
	}
	input:checked + .box :global(svg) {
		opacity: 1;
		transform: none;
	}
	input:focus-visible + .box {
		box-shadow: var(--ring);
	}
	.disabled {
		opacity: 0.5;
		cursor: default;
	}
	.disabled:hover .box {
		border-color: var(--border);
	}
</style>
