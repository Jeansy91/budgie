<script lang="ts">
	import { PasswordInput } from '$lib/ui';
	import { goto, invalidateAll } from '$app/navigation';
	import { api } from '$lib/api';
	import Logo from '$lib/Logo.svelte';

	let household_name = $state('Unser Haushalt');
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
	<div class="logo"><Logo size={52} /></div>
	<h1>Willkommen bei Budgie</h1>
	<p class="muted">
		Lege deinen Haushalt und das erste Konto an. Die Startkategorien werden automatisch eingerichtet. Weitere
		Nutzer kannst du danach in den Einstellungen anlegen.
	</p>
	{#if error}<div class="error">{error}</div>{/if}
	<form onsubmit={submit}>
		<label>Name des Haushalts <input bind:value={household_name} required /></label>
		<label>Dein Name <input bind:value={display_name} required /></label>
		<label>Nutzername <input bind:value={username} autocomplete="username" required pattern="[A-Za-z0-9._\-]+" /></label>
		<label
			>Passwort (mindestens 8 Zeichen)
			<PasswordInput bind:value={password} autocomplete="new-password" minlength={8} required /></label
		>
		<button disabled={busy}>Einrichten</button>
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
			radial-gradient(circle at 85% 90%, rgb(14 165 233 / 0.22), transparent 45%),
			var(--bg);
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
