<!--
	Finds a bank in Budgie's FinTS bank directory by name, city, BLZ or BIC.
	Results are listed inline below the search field (no native <select>).
-->
<script lang="ts">
	import { api } from '$lib/api';
	import type { Bank } from '$lib/types';
	import Search from '@lucide/svelte/icons/search';
	import Landmark from '@lucide/svelte/icons/landmark';

	let { value = $bindable(null) }: { value: Bank | null } = $props();

	let query = $state('');
	let results = $state<Bank[]>([]);
	let active = $state(0);
	let searched = $state(false);
	let timer: ReturnType<typeof setTimeout> | undefined;
	let seq = 0;

	// Shortcuts for the most common banks
	const popular = ['ING', 'Sparkasse', 'Volksbank', 'DKB', 'comdirect', 'Postbank'];

	function search(q: string) {
		query = q;
		clearTimeout(timer);
		if (!q.trim()) {
			results = [];
			searched = false;
			return;
		}
		timer = setTimeout(async () => {
			const mine = ++seq;
			const found = await api<Bank[]>('/fints/banks', { params: { q } });
			if (mine !== seq) return;
			results = found.slice(0, 8);
			active = 0;
			searched = true;
		}, 180);
	}

	function pick(bank: Bank) {
		value = bank;
		query = '';
		results = [];
		searched = false;
	}

	function onkeydown(e: KeyboardEvent) {
		if (!results.length) return;
		if (e.key === 'ArrowDown') {
			e.preventDefault();
			active = (active + 1) % results.length;
		} else if (e.key === 'ArrowUp') {
			e.preventDefault();
			active = (active - 1 + results.length) % results.length;
		} else if (e.key === 'Enter') {
			e.preventDefault();
			pick(results[active]);
		}
	}
</script>

{#if value}
	<div class="picked">
		<span class="bank-icon"><Landmark size={18} /></span>
		<div class="who">
			<strong class="break-anywhere">{value.name}</strong>
			<span class="muted small">BLZ {value.bank_code}{value.location ? ` · ${value.location}` : ''}</span>
		</div>
		<button type="button" class="ghost small" onclick={() => (value = null)}>Ändern</button>
	</div>
{:else}
	<div class="picker">
		<div class="search">
			<Search size={16} />
			<input
				type="search"
				value={query}
				oninput={(e) => search(e.currentTarget.value)}
				{onkeydown}
				placeholder="Bank, Ort, BLZ oder BIC"
				style:padding-left="2.3rem"
				aria-label="Bank suchen"
				role="combobox"
				aria-expanded={results.length > 0}
				aria-controls="bank-results"
				autocomplete="off"
			/>
		</div>
		{#if results.length}
			<ul id="bank-results" class="results" role="listbox">
				{#each results as b, i (b.bank_code)}
					<li role="option" aria-selected={i === active}>
						<button type="button" class:active={i === active} onclick={() => pick(b)} onmouseenter={() => (active = i)}>
							<span class="name break-anywhere">{b.name}</span>
							<span class="muted small">
								{b.location} · BLZ {b.bank_code}
								{#if !b.server_url}· keine FinTS-Adresse bekannt{/if}
							</span>
						</button>
					</li>
				{/each}
			</ul>
		{:else if searched}
			<p class="muted small">Keine Bank gefunden. Tipp: Die Bankleitzahl steht in deiner IBAN an Stelle 5 bis 12.</p>
		{:else}
			<div class="chips">
				{#each popular as p (p)}
					<button type="button" class="chip" onclick={() => search(p)}>{p}</button>
				{/each}
			</div>
		{/if}
	</div>
{/if}

<style>
	.picker {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}
	.search {
		position: relative;
		display: flex;
		align-items: center;
	}
	.search :global(svg) {
		position: absolute;
		z-index: 1;
		left: 0.8rem;
		color: var(--muted);
		pointer-events: none;
	}
	.search input {
		width: 100%;
	}
	.results {
		list-style: none;
		margin: 0;
		padding: 0.3rem;
		border: 1px solid var(--border);
		border-radius: var(--radius-sm);
		background: var(--surface);
		max-height: 20rem;
		overflow-y: auto;
	}
	.results button {
		display: flex;
		flex-direction: column;
		align-items: flex-start;
		gap: 0.1rem;
		width: 100%;
		padding: 0.55rem 0.7rem;
		border: 0;
		border-radius: 8px;
		background: transparent;
		color: var(--text);
		text-align: left;
		font-weight: 500;
		box-shadow: none;
	}
	.results button.active {
		background: var(--surface-2);
	}
	.chips {
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem;
	}
	.chip {
		padding: 0.3rem 0.75rem;
		border: 1px solid var(--border);
		border-radius: 999px;
		background: var(--surface);
		color: var(--text);
		font-size: 0.85rem;
		font-weight: 500;
		box-shadow: none;
	}
	.chip:hover {
		background: var(--surface-2);
	}
	.picked {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		padding: 0.6rem 0.75rem;
		border-radius: var(--radius-sm);
		background: var(--surface-2);
	}
	.who strong {
		color: var(--text);
	}
	.who {
		display: flex;
		flex-direction: column;
		flex: 1;
		min-width: 0;
	}
	.bank-icon {
		display: grid;
		place-items: center;
		width: 2.2rem;
		height: 2.2rem;
		border-radius: 10px;
		background: var(--accent-soft);
		color: var(--accent-strong);
		flex: none;
	}
</style>
