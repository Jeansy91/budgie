<script lang="ts">
	import { api } from '$lib/api';
	import { Checkbox, PasswordInput, Switch } from '$lib/ui';
	import type { Account, AiStatus, User } from '$lib/types';
	import { onDestroy } from 'svelte';
	import Wand from '@lucide/svelte/icons/wand-sparkles';
	import { initials } from '$lib/colors';
	import BudgetMonthSettings from '$lib/BudgetMonthSettings.svelte';

	let { data } = $props();
	let users = $state<User[]>([]);
	let accounts = $state<Account[]>([]);
	let error = $state('');
	let notice = $state('');
	let newUser = $state({ username: '', display_name: '', password: '', is_admin: false });
	let pw = $state({ current_password: '', new_password: '' });

	async function run(fn: () => Promise<unknown>, ok = '') {
		try {
			await fn();
			error = '';
			notice = ok;
		} catch (e) {
			error = (e as Error).message;
			notice = '';
		}
		[users, accounts] = await Promise.all([api<User[]>('/users'), api<Account[]>('/accounts')]);
	}
	run(async () => {});

	// --- AI categorization ---
	let ai = $state<AiStatus | null>(null);
	let aiBusy = $state(false);
	let poll: ReturnType<typeof setTimeout> | undefined;
	const pct = (v: number) => `${Math.round(v * 100)} %`;
	const when = (iso: string) =>
		new Intl.DateTimeFormat('de-DE', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(iso));

	async function loadAi() {
		clearTimeout(poll);
		try {
			ai = await api<AiStatus>('/ai/status');
		} catch (e) {
			error = (e as Error).message;
		}
		// Keep polling progress while the language model works in the background
		if (ai?.llm.running) poll = setTimeout(loadAi, 4000);
	}
	loadAi();
	onDestroy(() => clearTimeout(poll));

	async function aiAction(path: string, ok: (r: any) => string) {
		aiBusy = true;
		try {
			const r = await api(path, { method: 'POST', body: path.endsWith('recategorize') ? { use_llm: true } : undefined });
			notice = ok(r);
			error = '';
		} catch (e) {
			error = (e as Error).message;
			notice = '';
		}
		aiBusy = false;
		await loadAi();
	}
	const train = () => aiAction('/ai/train', () => 'KI neu trainiert und offene Buchungen neu eingeordnet.');
	const recategorize = () =>
		aiAction('/ai/recategorize', (r: { assigned: number; suggested: number; llm_queued: number }) =>
			`${r.assigned} Buchungen zugeordnet, ${r.suggested} Vorschläge` +
			(r.llm_queued ? `, ${r.llm_queued} gehen an das Sprachmodell.` : '.')
		);

	const saveAccount = (a: Account) =>
		run(() => api(`/accounts/${a.id}`, { method: 'PATCH', body: { name: a.name, shared: a.shared, member_ids: a.member_ids } }), 'Konto gespeichert.');
	const deleteAccount = (a: Account) => {
		if (confirm(`Konto „${a.name}“ mit allen ${a.transaction_count} Buchungen löschen?`))
			run(() => api(`/accounts/${a.id}`, { method: 'DELETE' }), 'Konto gelöscht.');
	};
	const toggleMember = (a: Account, id: number) => {
		a.member_ids = a.member_ids.includes(id) ? a.member_ids.filter((m) => m !== id) : [...a.member_ids, id];
	};
	const addUser = (e: SubmitEvent) => {
		e.preventDefault();
		run(async () => {
			await api('/users', { method: 'POST', body: newUser });
			newUser = { username: '', display_name: '', password: '', is_admin: false };
		}, 'Nutzer angelegt.');
	};
	const deleteUser = (u: User) => {
		if (confirm(`Nutzer „${u.display_name}“ löschen?`)) run(() => api(`/users/${u.id}`, { method: 'DELETE' }), 'Nutzer gelöscht.');
	};
	const changePassword = (e: SubmitEvent) => {
		e.preventDefault();
		run(async () => {
			await api('/auth/password', { method: 'POST', body: pw });
			pw = { current_password: '', new_password: '' };
		}, 'Passwort geändert.');
	};
</script>

<div class="page-head">
	<div>
		<span class="eyebrow">{data.me?.household_name}</span>
		<h1>Einstellungen</h1>
	</div>
</div>
{#if error}<div class="error">{error}</div>{/if}
{#if notice}<div class="ok">{notice}</div>{/if}

<section class="card">
	<h2>Konten</h2>
	{#each accounts as a (a.id)}
		<div class="account">
			<div class="row">
				<label>Name <input bind:value={a.name} /></label>
				<span class="small muted">{a.iban ?? 'ohne IBAN'} · {a.transaction_count} Buchungen</span>
			</div>
			<Switch bind:checked={a.shared}>Für alle im Haushalt sichtbar</Switch>
			{#if !a.shared}
				<div class="row small">
					Sichtbar für:
					{#each users as u (u.id)}
						<Checkbox checked={a.member_ids.includes(u.id)} onchange={() => toggleMember(a, u.id)} disabled={u.id === data.me?.id}>
							{u.display_name}
						</Checkbox>
					{/each}
				</div>
			{/if}
			<div class="row">
				<button class="secondary" onclick={() => saveAccount(a)}>Speichern</button>
				<button class="danger" onclick={() => deleteAccount(a)}>Löschen</button>
			</div>
		</div>
	{:else}
		<p class="muted">Konten entstehen automatisch beim ersten <a href="/import">CSV-Import</a>.</p>
	{/each}
</section>

<BudgetMonthSettings />

<section class="card">
	<h2><Wand size={20} /> KI-Kategorisierung</h2>
	{#if ai}
		{#if !ai.enabled}
			<p class="muted">Ausgeschaltet (BUDGIE_AI_ENABLED=false).</p>
		{:else}
			<p class="muted small">
				Läuft komplett auf deinem Server. Jede Zuordnung, die du änderst oder mit dem Haken bestätigst, ist ein
				Lernbeispiel. Ab {pct(ai.auto_threshold)} Sicherheit ordnet die KI selbst zu, darunter macht sie einen Vorschlag.
			</p>
			<div class="stats">
				<div>
					<span class="label">Gelernt aus</span>
					<strong>{ai.model ? ai.model.samples : 0}</strong>
					<span class="small muted">eigenen Buchungen{#if ai.model}, davon {ai.model.corrections} von Hand{/if}</span>
				</div>
				<div>
					<span class="label">Trefferquote</span>
					<strong>{ai.model?.accuracy != null ? pct(ai.model.accuracy) : '–'}</strong>
					<span class="small muted">{ai.model?.accuracy != null ? 'bei deinen eigenen Zuordnungen' : 'ab 20 Zuordnungen von Hand'}</span>
				</div>
				<a class="stat-link" href="/transactions?ai_review=1">
					<span class="label">Zu prüfen</span>
					<strong>{ai.ai_categorized + ai.suggestions}</strong>
					<span class="small muted">{ai.ai_categorized} von der KI zugeordnet, {ai.suggestions} Vorschläge</span>
				</a>
				<a class="stat-link" href="/transactions?uncategorized=1">
					<span class="label">Ohne Kategorie</span>
					<strong>{ai.uncategorized}</strong>
					<span class="small muted">Buchungen</span>
				</a>
			</div>
			<p class="small muted">
				{#if ai.model}Zuletzt trainiert {when(ai.model.trained_at)}.{:else}Noch nicht trainiert. Das passiert beim ersten Import automatisch.{/if}
			</p>

			<div class="llm">
				<span class="dot" class:on={ai.llm.configured && ai.llm.model_available} class:off={ai.llm.configured && !ai.llm.model_available}></span>
				<div>
					<strong>Sprachmodell für unsichere Fälle</strong>
					{#if !ai.llm.configured}
						<div class="small muted">
							Aus. Optional über Ollama zuschaltbar, siehe README („docker compose --profile ai“ und BUDGIE_OLLAMA_URL).
						</div>
					{:else if ai.llm.error}
						<div class="small warn">{ai.llm.error}</div>
					{:else}
						<div class="small muted">{ai.llm.model} ist bereit.</div>
					{/if}
					{#if ai.llm.running}
						<div class="small">Arbeitet gerade: {ai.llm.done} von {ai.llm.total} Buchungen eingeordnet …</div>
					{/if}
				</div>
			</div>

			<div class="row">
				<button class="secondary" onclick={train} disabled={aiBusy}>Jetzt neu trainieren</button>
				<button class="secondary" onclick={recategorize} disabled={aiBusy}>Offene Buchungen neu einordnen</button>
			</div>
		{/if}
	{/if}
</section>

<section class="card">
	<h2>Nutzer im Haushalt</h2>
	<table>
		<tbody>
			{#each users as u (u.id)}
				<tr>
					<td>
						<span class="user"><span class="av">{initials(u.display_name)}</span> <span><strong>{u.display_name}</strong> <span class="muted small">@{u.username}</span></span>
						{#if u.is_admin}<span class="badge accent">Admin</span>{/if}</span>
					</td>
					<td class="amount">
						{#if data.me?.is_admin && u.id !== data.me.id}<button class="link small" onclick={() => deleteUser(u)}>löschen</button>{/if}
					</td>
				</tr>
			{/each}
		</tbody>
	</table>
	{#if data.me?.is_admin}
		<form class="row" style="margin-top: 1rem" onsubmit={addUser}>
			<label>Name <input bind:value={newUser.display_name} required /></label>
			<label>Nutzername <input bind:value={newUser.username} required pattern="[A-Za-z0-9._\-]+" /></label>
			<label>Passwort <PasswordInput bind:value={newUser.password} minlength={8} required autocomplete="new-password" /></label>
			<Checkbox bind:checked={newUser.is_admin} class="admin">Admin</Checkbox>
			<button>Nutzer anlegen</button>
		</form>
	{/if}
</section>

<section class="card">
	<h2>Passwort ändern</h2>
	<form class="row" onsubmit={changePassword}>
		<label>Aktuelles Passwort <PasswordInput bind:value={pw.current_password} required autocomplete="current-password" /></label>
		<label>Neues Passwort <PasswordInput bind:value={pw.new_password} minlength={8} required autocomplete="new-password" /></label>
		<button>Ändern</button>
	</form>
</section>

<style>
	.user {
		display: flex;
		align-items: center;
		gap: 0.7rem;
	}
	.av {
		display: grid;
		place-items: center;
		width: 2.2rem;
		height: 2.2rem;
		border-radius: 999px;
		background: var(--gradient);
		color: #fff;
		font-weight: 700;
		font-size: 0.78rem;
	}
	.account {
		display: grid;
		gap: 0.6rem;
		padding: 0.75rem 0;
		border-bottom: 1px solid var(--border);
	}
	.account:last-child {
		border-bottom: 0;
	}
	h2 {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}
	.stats {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
		gap: 0.75rem;
		margin: 1rem 0 0.5rem;
	}
	.stats > * {
		display: grid;
		align-content: start;
		gap: 0.15rem;
		padding: 0.85rem 1rem;
		border-radius: var(--radius-sm);
		background: var(--surface-2);
		color: inherit;
		text-decoration: none;
	}
	.stats strong {
		font-size: 1.5rem;
	}
	.stat-link:hover {
		background: var(--surface-3);
	}
	.label {
		font-size: 0.75rem;
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.04em;
		color: var(--muted);
	}
	.llm {
		display: flex;
		gap: 0.75rem;
		align-items: flex-start;
		margin: 1rem 0;
		padding: 0.85rem 1rem;
		border: 1px solid var(--border);
		border-radius: var(--radius-sm);
	}
	.llm .dot {
		flex: none;
		width: 0.7rem;
		height: 0.7rem;
		margin-top: 0.35rem;
		border-radius: 999px;
		background: var(--faint);
	}
	.llm .dot.on {
		background: var(--accent);
	}
	.llm .dot.off {
		background: var(--warn);
	}
	.warn {
		color: var(--warn);
	}
	.account > :global(.switch) {
		justify-self: start;
	}
	form :global(.admin) {
		height: 2.6rem;
	}
</style>
