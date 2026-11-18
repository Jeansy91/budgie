<!--
	Styled password field with a custom show/hide button.
	All other attributes (required, minlength, autocomplete, inputmode …) are passed through.
-->
<script lang="ts">
	import type { HTMLInputAttributes } from 'svelte/elements';
	import Eye from '@lucide/svelte/icons/eye';
	import EyeOff from '@lucide/svelte/icons/eye-off';

	let { value = $bindable(''), class: cls = '', ...rest }: HTMLInputAttributes & { value: string } = $props();
	let visible = $state(false);
</script>

<span class="pw {cls}">
	<input {...rest} type={visible ? 'text' : 'password'} bind:value />
	<button
		type="button"
		class="eye"
		tabindex="-1"
		aria-label={visible ? 'Passwort verbergen' : 'Passwort anzeigen'}
		aria-pressed={visible}
		onclick={() => (visible = !visible)}
	>
		{#if visible}<EyeOff size={16} />{:else}<Eye size={16} />{/if}
	</button>
</span>

<style>
	.pw {
		position: relative;
		display: inline-flex;
		align-items: center;
		max-width: 100%;
	}
	.pw input {
		width: 100%;
		padding-right: 2.5rem !important;
	}
	.eye {
		position: absolute;
		right: 0.3rem;
		width: 2rem;
		height: 2rem;
		padding: 0;
		border-radius: 9px;
		background: transparent;
		color: var(--faint);
		box-shadow: none;
	}
	.eye:hover {
		background: var(--surface-3);
		color: var(--text);
		filter: none;
		box-shadow: none;
	}
	.eye:active {
		transform: none;
	}
</style>
