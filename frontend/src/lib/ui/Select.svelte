<!--
	Custom styled dropdown replacing <select>.
	Keyboard: arrows, Home/End, Enter/Space, Esc, type to search or jump.
	Long lists (10+ entries) get a search field; the search also matches the group
	("Wohnen" shows all subcategories of Wohnen).
-->
<script lang="ts" generics="T">
	import { t } from '../i18n/index.svelte';
	import ChevronDown from '@lucide/svelte/icons/chevron-down';
	import Check from '@lucide/svelte/icons/check';
	import Search from '@lucide/svelte/icons/search';
	import Popover from './Popover.svelte';
	import type { SelectOption } from './types';

	let {
		options,
		value = $bindable(),
		placeholder,
		searchable = 'auto',
		searchPlaceholder,
		label = '',
		disabled = false,
		size = 'md',
		id,
		class: cls = '',
		title,
		onchange
	}: {
		options: SelectOption<T>[];
		value: T;
		placeholder?: string;
		searchable?: boolean | 'auto';
		searchPlaceholder?: string;
		/** For screen readers and as the bottom sheet heading */
		label?: string;
		disabled?: boolean;
		size?: 'sm' | 'md';
		id?: string;
		class?: string;
		title?: string;
		onchange?: (value: T) => void;
	} = $props();
	let placeholderText = $derived(placeholder ?? t('ui.select.placeholder'));

	const uid = $props.id();
	let open = $state(false);
	let query = $state('');
	let active = $state(0);
	let trigger = $state<HTMLButtonElement>();
	let list = $state<HTMLDivElement>();
	let search = $state<HTMLInputElement>();
	let typeBuffer = '';
	let typeTimer: ReturnType<typeof setTimeout>;

	let withSearch = $derived(searchable === 'auto' ? options.length >= 10 : searchable);
	let selected = $derived(options.find((o) => o.value === value));

	const norm = (s: string) =>
		s
			.normalize('NFD')
			.replace(/[̀-ͯ]/g, '')
			.toLowerCase();

	let filtered = $derived.by(() => {
		const q = norm(query.trim());
		if (!q) return options;
		return options.filter((o) => norm(o.label).includes(q) || (o.group && norm(o.group).includes(q)));
	});

	const optId = (i: number) => `${uid}-o${i}`;

	function firstEnabled(from: number, dir: 1 | -1) {
		for (let i = from; i >= 0 && i < filtered.length; i += dir) if (!filtered[i].disabled) return i;
		return -1;
	}

	function show(initialQuery = '') {
		if (disabled) return;
		query = initialQuery;
		open = true;
		const idx = initialQuery ? -1 : filtered.findIndex((o) => o.value === value);
		active = idx >= 0 ? idx : Math.max(0, firstEnabled(0, 1));
		// On mobile, do not open the keyboard right away unless the user has already typed
		const mobile = window.matchMedia('(max-width: 640px)').matches;
		requestAnimationFrame(() => (withSearch && (!mobile || initialQuery) ? search : list)?.focus());
	}

	function hide(refocus = true) {
		open = false;
		query = '';
		if (refocus) trigger?.focus();
	}

	function choose(o: SelectOption<T> | undefined) {
		if (!o || o.disabled) return;
		value = o.value;
		onchange?.(o.value);
		hide();
	}

	function move(dir: 1 | -1) {
		const next = firstEnabled(active + dir, dir);
		if (next >= 0) active = next;
	}

	function typeahead(ch: string) {
		clearTimeout(typeTimer);
		typeBuffer += norm(ch);
		typeTimer = setTimeout(() => (typeBuffer = ''), 600);
		const start = typeBuffer.length === 1 ? active + 1 : active;
		for (let k = 0; k < filtered.length; k++) {
			const i = (start + k) % filtered.length;
			if (!filtered[i].disabled && norm(filtered[i].label).startsWith(typeBuffer)) {
				active = i;
				return;
			}
		}
	}

	function onTriggerKey(e: KeyboardEvent) {
		if (['ArrowDown', 'ArrowUp', 'Enter', ' '].includes(e.key)) {
			e.preventDefault();
			show();
		} else if (e.key.length === 1 && !e.ctrlKey && !e.metaKey && !e.altKey) {
			e.preventDefault();
			if (withSearch) show(e.key);
			else {
				show();
				typeahead(e.key);
			}
		}
	}

	function onListKey(e: KeyboardEvent) {
		switch (e.key) {
			case 'ArrowDown':
				e.preventDefault();
				move(1);
				break;
			case 'ArrowUp':
				e.preventDefault();
				move(-1);
				break;
			case 'Home':
			case 'PageUp':
				if (e.target === search && e.key === 'Home') return;
				e.preventDefault();
				active = Math.max(0, firstEnabled(0, 1));
				break;
			case 'End':
			case 'PageDown':
				if (e.target === search && e.key === 'End') return;
				e.preventDefault();
				active = Math.max(0, firstEnabled(filtered.length - 1, -1));
				break;
			case 'Enter':
				e.preventDefault();
				choose(filtered[active]);
				break;
			case ' ':
				if (e.target === search) return;
				e.preventDefault();
				choose(filtered[active]);
				break;
			case 'Escape':
				e.preventDefault();
				e.stopPropagation();
				hide();
				break;
			case 'Tab':
				hide(false);
				break;
			default:
				if (e.target !== search && e.key.length === 1 && !e.ctrlKey && !e.metaKey) typeahead(e.key);
		}
	}

	// Keep the active entry in view
	$effect(() => {
		if (!open) return;
		const el = list?.querySelector<HTMLElement>(`#${CSS.escape(optId(active))}`);
		el?.scrollIntoView({ block: 'nearest' });
	});

	// Jump to the first match after filtering
	$effect(() => {
		query;
		if (open && query) active = Math.max(0, firstEnabled(0, 1));
	});
</script>

<button
	bind:this={trigger}
	type="button"
	{id}
	title={title ?? selected?.label}
	class="select-trigger {size} {cls}"
	class:open
	class:placeholder={!selected}
	{disabled}
	aria-haspopup="listbox"
	aria-expanded={open}
	aria-controls={open ? `${uid}-list` : undefined}
	aria-label={label ? `${label}: ${selected?.label ?? placeholderText}` : undefined}
	onclick={() => (open ? hide() : show())}
	onkeydown={onTriggerKey}
>
	{#if selected?.color}<span class="dot" style:background={selected.color}></span>{/if}
	<span class="value">{selected?.label ?? placeholderText}</span>
	<span class="chev"><ChevronDown size={16} /></span>
</button>

<Popover bind:open anchor={trigger} {label} minWidth={withSearch ? 260 : 160} onclose={() => (query = '')}>
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div class="body" onkeydown={onListKey}>
		{#if withSearch}
			<div class="search">
				<Search size={16} />
				<input
					bind:this={search}
					bind:value={query}
					type="text"
					placeholder={searchPlaceholder ?? t('ui.select.searchPlaceholder')}
					aria-label={t('ui.select.search')}
					aria-controls="{uid}-list"
					aria-activedescendant={filtered[active] ? optId(active) : undefined}
					autocomplete="off"
					spellcheck="false"
				/>
			</div>
		{/if}
		<div
			bind:this={list}
			id="{uid}-list"
			class="list"
			role="listbox"
			tabindex="-1"
			aria-label={label || undefined}
			aria-activedescendant={filtered[active] ? optId(active) : undefined}
		>
			{#each filtered as o, i (i)}
				{#if o.group && o.group !== filtered[i - 1]?.group}
					<div class="group" role="presentation">{o.group}</div>
				{/if}
				<div
					id={optId(i)}
					class="option"
					class:active={i === active}
					class:selected={o.value === value}
					class:indent={o.indent || !!o.group}
					class:disabled={o.disabled}
					role="option"
					tabindex="-1"
					aria-selected={o.value === value}
					aria-disabled={o.disabled}
					onpointermove={() => !o.disabled && (active = i)}
					onclick={() => choose(o)}
					onkeydown={() => {}}
				>
					{#if o.color}<span class="dot" style:background={o.color}></span>{/if}
					<span class="label" title={o.label}>{o.label}</span>
					{#if o.hint}<span class="hint">{o.hint}</span>{/if}
					<span class="tick">{#if o.value === value}<Check size={16} />{/if}</span>
				</div>
			{:else}
				<div class="empty">{t('ui.select.noResults')}</div>
			{/each}
		</div>
	</div>
</Popover>

<style>
	.body {
		display: flex;
		flex-direction: column;
		min-height: 0;
		flex: 1;
	}
	.search {
		position: relative;
		display: flex;
		align-items: center;
		padding: 0.5rem;
		border-bottom: 1px solid var(--border);
		color: var(--faint);
		flex: none;
	}
	.search :global(svg) {
		position: absolute;
		left: 1.2rem;
		pointer-events: none;
	}
	.search input {
		width: 100%;
		padding: 0.55rem 0.75rem 0.55rem 2.3rem !important;
		font-size: 0.92rem;
	}
	.list {
		overflow-y: auto;
		overscroll-behavior: contain;
		padding: 0.35rem;
		outline: none;
		flex: 1;
		min-height: 0;
	}
	.group {
		padding: 0.6rem 0.65rem 0.25rem;
		font-size: 0.7rem;
		font-weight: 650;
		text-transform: uppercase;
		letter-spacing: 0.06em;
		color: var(--faint);
	}
	.option {
		display: flex;
		align-items: center;
		gap: 0.55rem;
		padding: 0.5rem 0.65rem;
		border-radius: 9px;
		cursor: pointer;
		user-select: none;
		scroll-margin: 0.35rem;
	}
	.option.indent {
		padding-left: 1.25rem;
	}
	.option.active {
		background: var(--surface-2);
	}
	.option.selected {
		color: var(--accent-strong);
		font-weight: 600;
	}
	.option.disabled {
		opacity: 0.4;
		cursor: default;
	}
	.label {
		flex: 1;
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.hint {
		flex: none;
		white-space: nowrap;
		font-size: 0.78rem;
		color: var(--faint);
		font-weight: 450;
	}
	.tick {
		display: flex;
		width: 16px;
		flex: none;
		color: var(--accent);
	}
	.empty {
		padding: 1rem;
		text-align: center;
		color: var(--muted);
	}
	@media (max-width: 640px) {
		.option {
			padding: 0.75rem 0.8rem;
		}
		.option.indent {
			padding-left: 1.4rem;
		}
		.search input {
			font-size: 1rem;
		}
	}
</style>
