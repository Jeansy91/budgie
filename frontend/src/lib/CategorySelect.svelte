<script lang="ts">
	import { t } from './i18n/index.svelte';
	import Select from './ui/Select.svelte';
	import type { SelectOption } from './ui/types';
	import { colorFor } from './colors';
	import type { Category } from './types';

	let {
		categories,
		value = $bindable(),
		empty,
		onchange
	}: {
		categories: Category[];
		value: number | null;
		empty?: string;
		onchange?: (value: number | null) => void;
	} = $props();

	let emptyLabel = $derived(empty ?? t('categorySelect.none'));

	// Subcategories grouped under their main category; the search also matches the main category name.
	let options = $derived<SelectOption<number | null>[]>([
		{ value: null, label: emptyLabel },
		...categories.flatMap((main, i) =>
			main.children.map((sub) => ({ value: sub.id, label: sub.name, group: main.name, color: colorFor(i) }))
		)
	]);
</script>

<Select
	{options}
	bind:value
	label={t('common.category')}
	placeholder={emptyLabel}
	searchable
	searchPlaceholder={t('categorySelect.search')}
	onchange={(v) => onchange?.(v)}
/>
