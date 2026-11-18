<!--
	Styled on/off switch (real <input type="checkbox" role="switch"> underneath).
-->
<script lang="ts">
	import type { Snippet } from 'svelte';

	let {
		checked = $bindable(false),
		disabled = false,
		title,
		label,
		class: cls = '',
		onchange,
		children
	}: {
		checked: boolean;
		disabled?: boolean;
		title?: string;
		/** For screen readers when there is no visible text next to it */
		label?: string;
		class?: string;
		onchange?: (checked: boolean) => void;
		children?: Snippet;
	} = $props();
</script>

<label class="switch {cls}" class:disabled {title}>
	<input
		type="checkbox"
		role="switch"
		class="sr-only"
		bind:checked
		{disabled}
		aria-label={label}
		onchange={(e) => onchange?.(e.currentTarget.checked)}
	/>
	<span class="track" aria-hidden="true"><span class="thumb"></span></span>
	{#if children}<span class="text">{@render children()}</span>{/if}
</label>

<style>
	.switch {
		display: inline-flex;
		flex-direction: row;
		align-items: center;
		gap: 0.65rem;
		font-size: 0.9rem;
		font-weight: 450;
		color: var(--text);
		cursor: pointer;
		user-select: none;
		position: relative;
	}
	.track {
		position: relative;
		width: 2.5rem;
		height: 1.45rem;
		flex: none;
		border-radius: 999px;
		background: var(--surface-3);
		transition:
			background 0.2s,
			box-shadow 0.15s;
	}
	.thumb {
		position: absolute;
		left: 0.2rem;
		top: 0.2rem;
		width: 1.05rem;
		height: 1.05rem;
		border-radius: 999px;
		background: #fff;
		box-shadow: 0 1px 3px rgb(0 0 0 / 0.25);
		transition: transform 0.2s cubic-bezier(0.3, 1.3, 0.6, 1);
	}
	input:checked + .track {
		background: var(--gradient);
	}
	input:checked + .track .thumb {
		transform: translateX(1.05rem);
	}
	input:focus-visible + .track {
		box-shadow: var(--ring);
	}
	.switch:active .thumb {
		width: 1.3rem;
	}
	input:checked + .track:active .thumb,
	.switch:active input:checked + .track .thumb {
		transform: translateX(0.8rem);
	}
	.disabled {
		opacity: 0.5;
		cursor: default;
	}
</style>
