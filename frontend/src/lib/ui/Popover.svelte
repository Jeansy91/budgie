<!--
	Floating panel for dropdowns and date pickers.
	Desktop: anchored to the trigger element (opens upwards if there is no room below).
	Mobile (narrower than 640 px): bottom sheet with a dimmed backdrop.
	The panel is attached to <body> so cards or tables cannot clip it.
-->
<script lang="ts">
	import type { Snippet } from 'svelte';
	import { onMount } from 'svelte';

	let {
		open = $bindable(false),
		anchor,
		onclose,
		matchWidth = true,
		minWidth = 0,
		label = '',
		id,
		children
	}: {
		open: boolean;
		anchor: HTMLElement | undefined;
		onclose?: () => void;
		matchWidth?: boolean;
		minWidth?: number;
		/** Heading of the bottom sheet on mobile */
		label?: string;
		id?: string;
		children: Snippet;
	} = $props();

	let panel = $state<HTMLDivElement>();
	let style = $state('');
	let above = $state(false);
	let sheet = $state(false);

	onMount(() => {
		const mq = window.matchMedia('(max-width: 640px)');
		sheet = mq.matches;
		const on = () => (sheet = mq.matches);
		mq.addEventListener('change', on);
		return () => mq.removeEventListener('change', on);
	});

	function portal(node: HTMLElement) {
		document.body.appendChild(node);
		return { destroy: () => node.remove() };
	}

	function place() {
		if (!anchor || !panel || sheet) return;
		const r = anchor.getBoundingClientRect();
		const gap = 6;
		const margin = 8;
		const width = Math.max(matchWidth ? r.width : 0, minWidth);
		const h = panel.offsetHeight;
		const below = window.innerHeight - r.bottom - gap - margin;
		const up = r.top - gap - margin;
		above = h > below && up > below;
		const maxH = Math.max(160, above ? up : below);
		let left = r.left;
		const w = Math.max(width, panel.offsetWidth);
		if (left + w > window.innerWidth - margin) left = Math.max(margin, window.innerWidth - margin - w);
		const top = above ? r.top - gap - Math.min(h, maxH) : r.bottom + gap;
		style = `top:${top}px;left:${left}px;min-width:${width}px;max-height:${maxH}px`;
	}

	function close() {
		open = false;
		onclose?.();
	}

	$effect(() => {
		if (!open) return;
		requestAnimationFrame(place);
		const onScroll = (e: Event) => {
			if (panel && e.target instanceof Node && panel.contains(e.target)) return;
			place();
		};
		const onDown = (e: PointerEvent) => {
			const t = e.target as Node;
			if (panel?.contains(t) || anchor?.contains(t)) return;
			close();
		};
		window.addEventListener('scroll', onScroll, true);
		window.addEventListener('resize', place);
		document.addEventListener('pointerdown', onDown, true);
		const ro = panel ? new ResizeObserver(place) : null;
		if (panel) ro?.observe(panel);
		return () => {
			window.removeEventListener('scroll', onScroll, true);
			window.removeEventListener('resize', place);
			document.removeEventListener('pointerdown', onDown, true);
			ro?.disconnect();
		};
	});
</script>

{#if open}
	<div use:portal class="layer" class:sheet>
		{#if sheet}
			<div class="backdrop" aria-hidden="true"></div>
		{/if}
		<div bind:this={panel} {id} class="panel" class:above style={sheet ? '' : style}>
			{#if sheet}
				<div class="grip" aria-hidden="true"></div>
				{#if label}<div class="sheet-title">{label}</div>{/if}
			{/if}
			{@render children()}
		</div>
	</div>
{/if}

<style>
	.layer {
		position: fixed;
		inset: 0;
		z-index: 1000;
		pointer-events: none;
	}
	.panel {
		pointer-events: auto;
		position: fixed;
		display: flex;
		flex-direction: column;
		background: var(--surface);
		color: var(--text);
		border: 1px solid var(--border);
		border-radius: 14px;
		box-shadow: var(--shadow-lg);
		overflow: hidden;
		/* Long option labels are truncated instead of stretching the panel */
		max-width: min(28rem, calc(100vw - 16px));
		animation: pop 0.12s ease-out;
		transform-origin: top;
		font-size: 0.92rem;
	}
	.panel.above {
		transform-origin: bottom;
	}
	@keyframes pop {
		from {
			opacity: 0;
			transform: scale(0.97) translateY(-4px);
		}
	}
	.backdrop {
		pointer-events: auto;
		position: absolute;
		inset: 0;
		background: rgb(15 23 42 / 0.4);
		animation: fade 0.15s ease-out;
	}
	.sheet .panel {
		left: 0;
		right: 0;
		bottom: 0;
		max-height: 80dvh;
		max-width: none;
		border-radius: 22px 22px 0 0;
		border-bottom: 0;
		padding-bottom: env(safe-area-inset-bottom);
		animation: slide 0.2s cubic-bezier(0.2, 0.9, 0.3, 1);
		font-size: 1rem;
	}
	.grip {
		width: 2.5rem;
		height: 0.3rem;
		border-radius: 999px;
		background: var(--surface-3);
		margin: 0.6rem auto 0.2rem;
		flex: none;
	}
	.sheet-title {
		padding: 0.35rem 1.25rem 0.5rem;
		font-weight: 650;
		flex: none;
	}
	@keyframes fade {
		from {
			opacity: 0;
		}
	}
	@keyframes slide {
		from {
			transform: translateY(100%);
		}
	}
</style>
