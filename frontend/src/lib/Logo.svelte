<script lang="ts">
	let { size = 32 }: { size?: number } = $props();
	const uid = $props.id();
	const gid = `budgie-g-${uid}`;
</script>

<svg width={size} height={size} viewBox="0 0 48 48" aria-hidden="true">
	<defs>
		<linearGradient id={gid} x1="0" y1="0" x2="1" y2="1">
			<stop offset="0" stop-color="#10b981" />
			<stop offset="0.6" stop-color="#14b8a6" />
			<stop offset="1" stop-color="#0ea5e9" />
		</linearGradient>
	</defs>
	<rect width="48" height="48" rx="14" fill="url(#{gid})" />
	<path d="M13 35c3-8 9-13 17-13l5 3-3 6c-4 4-11 6-19 4z" fill="#fff" opacity="0.95" />
	<circle cx="30" cy="17" r="6.5" fill="#facc15" />
	<circle cx="32" cy="16" r="1.4" fill="#0f172a" />
	<path d="M36 17.5l3.5 1.5-3.5 1.5z" fill="#f97316" />
	<path d="M13 35l-4 5 7-3z" fill="#fff" opacity="0.8" />
	<path d="M20 29c3 1 7 1 10-1" stroke="#14b8a6" stroke-width="1.6" fill="none" stroke-linecap="round" />
</svg>
