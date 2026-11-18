<script lang="ts">
	import { api } from '$lib/api';
	import type { Category, Kind } from '$lib/types';
	import { colorFor } from '$lib/colors';
	import { RadioGroup, Select } from '$lib/ui';
	import Plus from '@lucide/svelte/icons/plus';
	import Pencil from '@lucide/svelte/icons/pencil';
	import Trash2 from '@lucide/svelte/icons/trash-2';

	let categories = $state<Category[]>([]);
	let error = $state('');
	let newMain = $state('');
	let newMainKind = $state<Kind>('expense');
	let newSub = $state<Record<number, string>>({});

	const kindLabel: Record<Kind, string> = { expense: 'Ausgabe', income: 'Einnahme', transfer: 'Umbuchung' };
	const kindOptions = Object.entries(kindLabel).map(([value, label]) => ({ value: value as Kind, label }));

	async function run(fn: () => Promise<unknown>) {
		try {
			await fn();
			error = '';
		} catch (e) {
			error = (e as Error).message;
		}
		categories = await api<Category[]>('/categories');
	}
	run(async () => {});

	const addMain = () =>
		run(async () => {
			await api('/categories', { method: 'POST', body: { name: newMain, kind: newMainKind } });
			newMain = '';
		});
	const addSub = (parent: Category) =>
		run(async () => {
			await api('/categories', { method: 'POST', body: { name: newSub[parent.id], parent_id: parent.id } });
			newSub[parent.id] = '';
		});
	const rename = (c: Category) => {
		const name = prompt('Neuer Name', c.name);
		if (name && name !== c.name) run(() => api(`/categories/${c.id}`, { method: 'PATCH', body: { name } }));
	};
	const setKind = (c: Category, kind: Kind) => run(() => api(`/categories/${c.id}`, { method: 'PATCH', body: { kind } }));
	const remove = (c: Category) => {
		const what = c.children?.length ? `„${c.name}“ mit allen Unterkategorien` : `„${c.name}“`;
		if (confirm(`${what} löschen? Zugeordnete Buchungen werden wieder unkategorisiert, passende Regeln gelöscht.`))
			run(() => api(`/categories/${c.id}`, { method: 'DELETE' }));
	};
</script>

<div class="page-head">
	<div>
		<span class="eyebrow">Haushalt</span>
		<h1>Kategorien</h1>
		<p>Buchungen werden immer einer Unterkategorie zugeordnet. Die Art legt fest, ob sie als Ausgabe, Einnahme oder Umbuchung zählt.</p>
	</div>
</div>
{#if error}<div class="error">{error}</div>{/if}

<div class="grid">
	{#each categories as main, i (main.id)}
		<section class="card" style:--c={colorFor(i)}>
			<div class="head">
				<h2><span class="dot" style:background="var(--c)"></span>{main.name}</h2>
				<Select options={kindOptions} value={main.kind} onchange={(k) => setKind(main, k)} size="sm" label="Art" title="Art" />
			</div>
			<ul>
				{#each main.children as sub (sub.id)}
					<li>
						<span>{sub.name}</span>
						<span class="actions">
							<button class="ghost icon sm" onclick={() => rename(sub)} title="Umbenennen" aria-label="Umbenennen"><Pencil size={14} /></button>
							<button class="ghost icon sm" onclick={() => remove(sub)} title="Löschen" aria-label="Löschen"><Trash2 size={14} /></button>
						</span>
					</li>
				{/each}
			</ul>
			<form class="add" onsubmit={(e) => { e.preventDefault(); addSub(main); }}>
				<input placeholder="Neue Unterkategorie" bind:value={newSub[main.id]} required />
				<button class="secondary icon" aria-label="Hinzufügen"><Plus size={18} /></button>
			</form>
			<div class="foot">
				<button class="ghost small" onclick={() => rename(main)}><Pencil size={14} /> Umbenennen</button>
				<button class="ghost small" onclick={() => remove(main)}><Trash2 size={14} /> Löschen</button>
			</div>
		</section>
	{/each}
	<section class="card new">
		<h2><Plus size={18} /> Neue Hauptkategorie</h2>
		<form class="add col" onsubmit={(e) => { e.preventDefault(); addMain(); }}>
			<input placeholder="Name" bind:value={newMain} required />
			<RadioGroup options={kindOptions} bind:value={newMainKind} label="Art" class="kind" />
			<button>Anlegen</button>
		</form>
	</section>
</div>

<style>
	.grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(290px, 1fr));
		gap: 1rem;
	}
	.grid .card {
		margin: 0;
		border-top: 4px solid var(--c, var(--border));
	}
	.grid .card.new {
		border: 2px dashed var(--border);
		box-shadow: none;
		background: transparent;
	}
	h2 {
		display: flex;
		align-items: center;
		gap: 0.55rem;
	}
	.sm {
		width: 1.9rem;
		height: 1.9rem;
	}
	.head {
		display: flex;
		justify-content: space-between;
		align-items: start;
		gap: 0.5rem;
	}
	.head :global(.select-trigger) {
		font-size: 0.8rem;
		padding: 0.3rem 0.45rem 0.3rem 0.65rem;
		flex: none;
	}
	ul {
		list-style: none;
		padding: 0;
		margin: 0 0 0.75rem;
	}
	li {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 0.2rem 0.4rem 0.2rem 0.6rem;
		border-radius: 10px;
		min-height: 2.3rem;
		font-size: 0.93rem;
	}
	li:hover {
		background: var(--surface-2);
	}
	.actions {
		display: flex;
		gap: 0.1rem;
		opacity: 0;
		transition: opacity 0.15s;
	}
	@media (hover: none) {
		.actions {
			opacity: 1;
		}
	}
	li:hover .actions {
		opacity: 1;
	}
	.add {
		display: flex;
		gap: 0.4rem;
	}
	.add input {
		flex: 1;
		min-width: 0;
	}
	.add.col {
		flex-direction: column;
	}
	.add :global(.kind) {
		display: flex;
	}
	.foot {
		display: flex;
		gap: 0.25rem;
		margin-top: 0.6rem;
	}
	.foot button {
		font-size: 0.8rem;
	}
</style>
