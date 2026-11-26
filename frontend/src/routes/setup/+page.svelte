<script lang="ts">
	import { PasswordInput } from '#lib/ui/index.ts';
	import { goto, invalidateAll } from '$app/navigation';
	import { api } from '#lib/api.ts';
	import Logo from '#lib/Logo.svelte';
	import LanguageSwitch from '#lib/LanguageSwitch.svelte';
	import { t } from '#lib/i18n/index.svelte.ts';

	let household_name = $state(t('auth.defaultHousehold'));
	let display_name = $state('');
	let username = $state('');
	let password = $state('');
	let error = $state('');
	let busy = $state(false);

	async function submit(e: SubmitEvent) {
		e.preventDefault();
		busy = true;
		error = '';
		try {
			await api('/auth/setup', { method: 'POST', body: { household_name, display_name, username, password } });
			await invalidateAll();
			await goto('/import');
		} catch (err) {
			error = (err as Error).message;
		} finally {
			busy = false;
		}
	}
</script>

<div class="auth-wrap">
	<div class="auth card">
		<LanguageSwitch />
		<div class="logo"><Logo size={52} /></div>
		<h1>{t('auth.welcome')}</h1>
		<p class="muted">
			{t('auth.setupIntro')}
		</p>
		{#if error}<div class="error">{error}</div>{/if}
		<form onsubmit={submit}>
			<label>{t('auth.householdName')} <input bind:value={household_name} required /></label>
			<label>{t('auth.yourName')} <input bind:value={display_name} required /></label>
			<label>{t('auth.username')} <input bind:value={username} autocomplete="username" required pattern="[A-Za-z0-9._\-]+" /></label>
			<label>
				{t('auth.passwordMin')}
				<PasswordInput bind:value={password} autocomplete="new-password" minlength={8} required />
			</label>
			<button disabled={busy}>{t('auth.setup')}</button>
		</form>
	</div>
</div>

<style>
	.auth-wrap {
		min-height: 100vh;
		display: grid;
		place-items: center;
		padding: 1.5rem;
		background:
			radial-gradient(circle at 15% 10%, rgb(16 185 129 / 0.25), transparent 45%),
			radial-gradient(circle at 85% 90%, rgb(14 165 233 / 0.22), transparent 45%), var(--bg);
	}
	.auth {
		width: 100%;
		max-width: 420px;
		padding: 2.25rem 2rem;
		box-shadow: var(--shadow-lg);
		text-align: center;
	}
	.logo {
		display: flex;
		justify-content: center;
		margin-bottom: 1rem;
	}
	h1 {
		margin-bottom: 0.4rem;
	}
	p {
		margin: 0 0 1.5rem;
	}
	form {
		display: grid;
		gap: 0.9rem;
		text-align: left;
	}
	form button {
		margin-top: 0.5rem;
		padding: 0.8rem;
	}
</style>
