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

<div class="card">
	<table class="rules">
		<thead>
			<tr><th>Bedingung</th><th>Kategorie</th><th class="amount">Prio</th><th class="amount">Treffer</th><th></th></tr>
		</thead>
		<tbody>
			{#each rules as r (r.id)}
				<tr class:inactive={!r.active}>
					<td class="cond"><span class="muted">{fieldLabel[r.field]} {matchLabel[r.match_type]}</span> <code>{r.pattern}</code></td>
					<td class="cat">
						<span class="catpill" style:--c={catColor.get(r.category_id)} title={labels.get(r.category_id)}
							><span class="dot" style:background="var(--c)"></span><span class="truncate">{labels.get(r.category_id)}</span></span
						>
					</td>
					<td class="amount" data-label="Prio">{r.priority}</td>
					<td class="amount" data-label="Treffer"><span class="badge">{r.match_count}</span></td>
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
	.rules {
		table-layout: fixed;
	}
	.rules th:nth-child(1) {
		width: 50%;
	}
	.rules th:nth-child(3) {
		width: 4rem;
	}
	.rules th:nth-child(4) {
		width: 5.5rem;
	}
	.rules th:nth-child(5) {
		width: 7rem;
	}
	code {
		/* Patterns can be long, unbroken strings (regexes, reference numbers) */
		overflow-wrap: anywhere;
		font-family: inherit;
		font-weight: 650;
		background: var(--surface-2);
		padding: 0.15rem 0.5rem;
		border-radius: 8px;
	}
	.catpill {
		display: inline-flex;
		max-width: 100%;
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
	.catpill .dot {
		flex: none;
	}
	/* Phones: each rule becomes a small card instead of a cramped table row */
	@media (max-width: 640px) {
		.rules,
		.rules tbody {
			display: block;
		}
		.rules thead {
			display: none;
		}
		.rules tr {
			display: grid;
			grid-template-columns: minmax(0, 1fr) auto auto;
			grid-template-areas: 'cond cond cond' 'cat cat cat' 'prio hits actions';
			align-items: center;
			gap: 0.5rem 1rem;
			padding: 0.85rem 0;
			border-bottom: 1px solid var(--border);
		}
		.rules tr:last-child {
			border-bottom: 0;
		}
		.rules td {
			padding: 0;
			border: 0;
			text-align: left;
		}
		.rules .cond {
			grid-area: cond;
		}
		.rules .cat {
			grid-area: cat;
			min-width: 0;
		}
		.rules td[data-label]::before {
			content: attr(data-label) ' ';
			color: var(--muted);
			font-size: 0.8rem;
		}
		.rules td[data-label='Prio'] {
			grid-area: prio;
		}
		.rules td[data-label='Treffer'] {
			grid-area: hits;
		}
		.rules .actions {
			grid-area: actions;
		}
	}
	.builder :global(.prio) {
		width: 8.5rem;
	}
</style>
