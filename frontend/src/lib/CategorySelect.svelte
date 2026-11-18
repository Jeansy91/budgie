<script lang="ts">
	import Select from './ui/Select.svelte';
	import type { SelectOption } from './ui/types';
	import { colorFor } from './colors';
	import type { Category } from './types';

	let {
		categories,
		value = $bindable(),
		empty = '– ohne Kategorie –',
		onchange
	}: {
		categories: Category[];
		value: number | null;
		empty?: string;
		onchange?: (value: number | null) => void;
	} = $props();

	// Subcategories grouped under their main category; the search also matches the main category name.
	let options = $derived<SelectOption<number | null>[]>([
		{ value: null, label: empty },
		...categories.flatMap((main, i) =>
			main.children.map((sub) => ({ value: sub.id, label: sub.name, group: main.name, color: colorFor(i) }))
		)
	]);
</script>

<Select
	{options}
	bind:value
	label="Kategorie"
	placeholder={empty}
	searchable
	searchPlaceholder="Kategorie suchen …"
	onchange={(v) => onchange?.(v)}
/>
