<!--
	Truncates long single-line text in the middle, so both the start and the end
	stay readable: "Umsatzanzeige_DE85…_20261118.csv". Pure CSS, so it adapts to
	any width; the full text is always available as a tooltip and to screen readers.
-->
<script lang="ts">
	interface Props {
		text: string;
		/** Number of trailing characters that always stay visible. Defaults to the
		 *  last segment of a file name (e.g. "_20261118.csv"), at most 16 characters. */
		tail?: number;
		class?: string;
	}

	let { text, tail, class: cls = '' }: Props = $props();

	function defaultTail(s: string): number {
		const sep = Math.max(s.lastIndexOf('_'), s.lastIndexOf('-'), s.lastIndexOf(' '));
		const fromSep = sep > 0 ? s.length - sep : 0;
		return Math.min(16, Math.max(fromSep, Math.min(8, s.length)));
	}

	let cut = $derived(Math.max(0, text.length - Math.min(tail ?? defaultTail(text), text.length)));
</script>

<span class="mid-truncate {cls}" title={text}>
	<span class="head" aria-hidden="true">{text.slice(0, cut)}</span><span class="tail" aria-hidden="true">{text.slice(cut)}</span><span
		class="sr-only"
	>
		{text}
	</span>
</span>

<style>
	.mid-truncate {
		display: flex;
		min-width: 0;
		max-width: 100%;
		white-space: nowrap;
	}
	.head {
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
	}
	.tail {
		flex: none;
	}
	.sr-only {
		position: absolute;
		width: 1px;
		height: 1px;
		overflow: hidden;
		clip-path: inset(50%);
		white-space: nowrap;
	}
</style>
