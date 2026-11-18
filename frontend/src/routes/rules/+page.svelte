<script lang="ts">
	import { api } from '$lib/api';
	import CategorySelect from '$lib/CategorySelect.svelte';
	import { NumberInput, Select, Switch } from '$lib/ui';
	import { categoryLabels } from '$lib/format';
	import type { Category, Rule } from '$lib/types';
	import { colorFor } from '$lib/colors';
	import Trash2 from '@lucide/svelte/icons/trash-2';
	import WandSparkles from '@lucide/svelte/icons/wand-sparkles';

	let rules = $state<Rule[]>([]);
	let categories = $state<Category[]>([]);
	let labels = $derived(categoryLabels(categories));
	let catColor = $derived.by(() => {
		const map = new Map<number, string>();
		categories.forEach((main, i) => main.children.forEach((sub) => map.set(sub.id, colorFor(i))));
		return map;
	});
	let error = $state('');
	let notice = $state('');

	let draft = $state({ field: 'payee', match_type: 'contains', pattern: '', category_id: null as number | null, priority: 0 });

	const fieldLabel = { payee: 'Empfänger', purpose: 'Verwendungszweck', any: 'Empfänger oder Zweck' };
	const matchLabel = { contains: 'enthält', equals: 'ist genau', starts_with: 'beginnt mit', regex: 'passt zu Regex' };
	const fieldOptions = Object.entries(fieldLabel).map(([value, label]) => ({ value, label }));
	const matchOptions = Object.entries(matchLabel).map(([value, label]) => ({ value, label }));

	async function run(fn: () => Promise<unknown>) {
		try {
			await fn();
			error = '';
		} catch (e) {
			error = (e as Error).message;
		}
		rules = await api<Rule[]>('/rules');
	}
	api<Category[]>('/categories').then((c) => (categories = c));
	run(async () => {});

	const create = (e: SubmitEvent) => {
		e.preventDefault();
		run(async () => {
			const r = await api<Rule>('/rules', { method: 'POST', body: draft });
			notice = `Regel angelegt, ${r.match_count} Buchungen zugeordnet.`;
			draft.pattern = '';
		});
	};
	const toggle = (r: Rule) => run(() => api(`/rules/${r.id}`, { method: 'PATCH', body: { active: !r.active } }));
	const remove = (r: Rule) => {
		if (confirm(`Regel „${r.pattern}“ löschen? Bereits zugeordnete Buchungen behalten ihre Kategorie.`))
			run(() => api(`/rules/${r.id}`, { method: 'DELETE' }));
	};
	const applyAll = (overwrite: boolean) =>
		run(async () => {
			const res = await api<{ changed: number }>('/rules/apply', { method: 'POST', body: { overwrite_rule_results: overwrite } });
			notice = `${res.changed} Buchungen neu zugeordnet.`;
		});
</script>

<div class="page-head">
	<div>
		<span class="eyebrow">Automatisch zuordnen</span>
		<h1>Regeln</h1>
		<p>Regeln ordnen Buchungen beim Import zu. Höhere Priorität gewinnt, manuelle Zuordnungen bleiben unangetastet.</p>
	</div>
	<div class="row">
		<button class="secondary" onclick={() => applyAll(false)}>Auf offene Buchungen anwenden</button>
		<button class="secondary" onclick={() => applyAll(true)} title="Auch Zuordnungen durch Regeln neu berechnen, manuelle bleiben">Alles neu berechnen</button>
	</div>
</div>

{#if error}<div class="error">{error}</div>{/if}
{#if notice}<div class="ok">{notice}</div>{/if}

<form class="card row builder" onsubmit={create}>
	<span class="wand"><WandSparkles size={20} /></span>
	<div class="field">Wenn <Select options={fieldOptions} bind:value={draft.field} label="Feld" /></div>
	<div class="field">&nbsp;<Select options={matchOptions} bind:value={draft.match_type} label="Vergleich" /></div>
	<label>Text <input bind:value={draft.pattern} required placeholder="z. B. REWE" /></label>
	<div class="field">dann <CategorySelect {categories} bind:value={draft.category_id} empty="Kategorie wählen" /></div>
	<div class="field">Priorität <NumberInput bind:value={draft.priority} label="Priorität" class="prio" /></div>
	<button disabled={!draft.category_id}>Regel anlegen</button>
</form>

<div class="card" style="overflow-x: auto">
	<table>
		<thead>
			<tr><th>Bedingung</th><th>Kategorie</th><th class="amount">Prio</th><th class="amount">Treffer</th><th></th></tr>
		</thead>
		<tbody>
			{#each rules as r (r.id)}
				<tr class:inactive={!r.active}>
					<td><span class="muted">{fieldLabel[r.field]} {matchLabel[r.match_type]}</span> <code>{r.pattern}</code></td>
					<td><span class="catpill" style:--c={catColor.get(r.category_id)}><span class="dot" style:background="var(--c)"></span>{labels.get(r.category_id)}</span></td>
					<td class="amount">{r.priority}</td>
					<td class="amount"><span class="badge">{r.match_count}</span></td>
					<td class="actions">
						<Switch checked={r.active} onchange={() => toggle(r)} title={r.active ? 'Aktiv' : 'Inaktiv'} label="Regel aktiv" />
						<button class="ghost icon" onclick={() => remove(r)} title="Löschen" aria-label="Löschen"><Trash2 size={16} /></button>
					</td>
				</tr>
			{:else}
				<tr><td colspan="5" class="muted">Noch keine Regeln. Lege eine an oder ordne unter „Buchungen“ zu und setze dort den Haken für Regeln.</td></tr>
			{/each}
		</tbody>
	</table>
</div>

<style>
	.builder {
		align-items: end;
	}
	.wand {
		display: grid;
		place-items: center;
		width: 2.6rem;
		height: 2.6rem;
		border-radius: 14px;
		background: var(--gradient);
		color: #fff;
		align-self: center;
	}
	.inactive td:not(.actions) {
		opacity: 0.45;
	}
	code {
		font-family: inherit;
		font-weight: 650;
		background: var(--surface-2);
		padding: 0.15rem 0.5rem;
		border-radius: 8px;
	}
	.catpill {
		display: inline-flex;
		align-items: center;
		gap: 0.45rem;
		padding: 0.25rem 0.7rem;
		border-radius: 999px;
		font-size: 0.85rem;
		background: color-mix(in srgb, var(--c) 12%, var(--surface));
	}
	.actions {
		white-space: nowrap;
		display: flex;
		gap: 0.5rem;
		align-items: center;
		justify-content: end;
	}
	.field :global(.select-trigger) {
		min-width: 9rem;
	}
	.builder :global(.prio) {
		width: 8.5rem;
	}
</style>
