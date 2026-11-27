<script lang="ts">
	import { api } from '#lib/api.ts';
	import CategorySelect from '#lib/CategorySelect.svelte';
	import { NumberInput, Select, Switch } from '#lib/ui/index.ts';
	import { categoryLabels } from '#lib/format.ts';
	import type { Category, Rule } from '#lib/types.ts';
	import { colorFor } from '#lib/colors.ts';
	import { t } from '#lib/i18n/index.svelte.ts';
	import Trash2 from '@lucide/svelte/icons/trash-2';
	import WandSparkles from '@lucide/svelte/icons/wand-sparkles';

	let rules = $state<Rule[]>([]);
	let categories = $state<Category[]>([]);
	let labels = $derived(categoryLabels(categories));
	let catColor = $derived.by(() => {
		// eslint-disable-next-line svelte/prefer-svelte-reactivity -- local, non-reactive value
		const map = new Map<number, string>();
		categories.forEach((main, i) => main.children.forEach((sub) => map.set(sub.id, colorFor(i))));
		return map;
	});
	let error = $state('');
	let notice = $state('');

	let draft = $state({
		field: 'payee' as Rule['field'],
		match_type: 'contains' as Rule['match_type'],
		pattern: '',
		category_id: null as number | null,
		priority: 0
	});

	const fieldLabel = (field: Rule['field']) => t(`rules.field.${field}`);
	const matchLabel = (match: Rule['match_type']) => t(`rules.match.${match}`);
	let fieldOptions = $derived(
		(['payee', 'recipient', 'sender', 'purpose', 'any'] as const).map((value) => ({ value, label: fieldLabel(value) }))
	);
	let matchOptions = $derived(
		(['contains', 'equals', 'starts_with', 'regex'] as const).map((value) => ({ value, label: matchLabel(value) }))
	);

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
			notice = t('rules.created', { count: r.match_count });
			draft.pattern = '';
		});
	};
	const toggle = (r: Rule) => run(() => api(`/rules/${r.id}`, { method: 'PATCH', body: { active: !r.active } }));
	const remove = (r: Rule) => {
		if (confirm(t('rules.confirmDelete', { pattern: r.pattern }))) run(() => api(`/rules/${r.id}`, { method: 'DELETE' }));
	};
	const applyAll = (overwrite: boolean) =>
		run(async () => {
			const res = await api<{ changed: number }>('/rules/apply', { method: 'POST', body: { overwrite_rule_results: overwrite } });
			notice = t('rules.reapplied', { count: res.changed });
		});
</script>

<div class="page-head">
	<div>
		<span class="eyebrow">{t('rules.eyebrow')}</span>
		<h1>{t('nav.rules')}</h1>
		<p>{t('rules.intro')}</p>
	</div>
	<div class="row">
		<button class="secondary" onclick={() => applyAll(false)}>{t('rules.applyOpen')}</button>
		<button class="secondary" onclick={() => applyAll(true)} title={t('rules.recomputeTitle')}>{t('rules.recompute')}</button>
	</div>
</div>

{#if error}<div class="error">{error}</div>{/if}
{#if notice}<div class="ok">{notice}</div>{/if}

<form class="card row builder" onsubmit={create}>
	<span class="wand"><WandSparkles size={20} /></span>
	<div class="field">{t('rules.if')} <Select options={fieldOptions} bind:value={draft.field} label={t('rules.fieldLabel')} /></div>
	<div class="field">&nbsp;<Select options={matchOptions} bind:value={draft.match_type} label={t('rules.condition')} /></div>
	<label>{t('rules.text')} <input bind:value={draft.pattern} required placeholder={t('rules.textPlaceholder')} /></label>
	<div class="field">
		{t('rules.then')}
		<CategorySelect {categories} bind:value={draft.category_id} empty={t('categorySelect.choose')} />
	</div>
	<div class="field">{t('rules.priority')} <NumberInput bind:value={draft.priority} label={t('rules.priority')} class="prio" /></div>
	<button disabled={!draft.category_id}>{t('rules.create')}</button>
</form>

<div class="card">
	<table class="rules">
		<thead>
			<tr>
				<th>{t('rules.condition')}</th><th>{t('common.category')}</th><th class="amount">{t('rules.prio')}</th><th class="amount">
					{t('rules.hits')}
				</th><th></th>
			</tr>
		</thead>
		<tbody>
			{#each rules as r (r.id)}
				<tr class:inactive={!r.active}>
					<td class="cond"><span class="muted">{fieldLabel(r.field)} {matchLabel(r.match_type)}</span> <code>{r.pattern}</code></td>
					<td class="cat">
						<span class="catpill" style:--c={catColor.get(r.category_id)} title={labels.get(r.category_id)}>
							<span class="dot" style:background="var(--c)"></span><span class="truncate">{labels.get(r.category_id)}</span>
						</span>
					</td>
					<td class="amount" data-label={t('rules.prio')}>{r.priority}</td>
					<td class="amount" data-label={t('rules.hits')}><span class="badge">{r.match_count}</span></td>
					<td class="actions">
						<Switch
							checked={r.active}
							onchange={() => toggle(r)}
							title={r.active ? t('rules.active') : t('rules.inactive')}
							label={t('rules.activeLabel')}
						/>
						<button class="ghost icon" onclick={() => remove(r)} title={t('common.delete')} aria-label={t('common.delete')}>
							<Trash2 size={16} />
						</button>
					</td>
				</tr>
			{:else}
				<tr><td colspan="5" class="muted">{t('rules.empty')}</td></tr>
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
