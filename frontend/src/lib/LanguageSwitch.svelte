<!--
	Compact language switch for the login and setup pages. Before login the
	choice is only remembered in this browser; signed-in users pick their
	language in the settings.
-->
<script lang="ts">
	import { RadioGroup } from './ui';
	import { LOCALES, getLocale, setLocale, t, type Locale } from './i18n/index.svelte';

	let value = $state<Locale>(getLocale());
	const options = LOCALES.map((l) => ({ value: l.code, label: l.code.toUpperCase() }));
</script>

<div class="lang" title={t('settings.language')}>
	<RadioGroup {options} bind:value label={t('settings.language')} onchange={setLocale} />
</div>

<style>
	.lang {
		display: flex;
		justify-content: flex-end;
		margin: -0.75rem -0.5rem 0.25rem 0;
		font-size: 0.8rem;
	}
</style>
