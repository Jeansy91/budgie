<script lang="ts">
	import { api } from './api';
	import type { BudgetSettings, Category } from './types';
	import CalendarArrowDown from '@lucide/svelte/icons/calendar-arrow-down';
	import Minus from '@lucide/svelte/icons/minus';
	import Plus from '@lucide/svelte/icons/plus';
	import Check from '@lucide/svelte/icons/check';
	import X from '@lucide/svelte/icons/x';

	/** Household settings for "assign salary to the following month". */
	let s = $state<BudgetSettings | null>(null);
	let categories = $state<Category[]>([]);
	let payee = $state('');
	let error = $state('');
	let notice = $state('');
	let saving = $state(false);

	// Income categories (main and subcategories) to choose from
	let incomeCategories = $derived(categories.filter((c) => c.kind === 'income'));

	Promise.all([api<BudgetSettings>('/budget-month/settings'), api<Category[]>('/categories')])
		.then(([settings, tree]) => {
			s = settings;
			categories = tree;
		})
		.catch((e) => (error = e.message));

	const toggleCategory = (id: number) => {
		if (!s) return;
		s.salary_category_ids = s.salary_category_ids.includes(id)
			? s.salary_category_ids.filter((x) => x !== id)
			: [...s.salary_category_ids, id];
	};
	const addPayee = (e?: Event) => {
		e?.preventDefault();
		const p = payee.trim();
		if (!s || !p) return;
		if (!s.salary_payees.some((x) => x.toLowerCase() === p.toLowerCase())) s.salary_payees = [...s.salary_payees, p];
		payee = '';
	};
	const setDays = (d: number) => s && (s.salary_shift_days = Math.min(15, Math.max(1, d)));

	async function save() {
		if (!s) return;
		saving = true;
		try {
			const { shifted_count, ...body } = s;
			s = await api<BudgetSettings>('/budget-month/settings', { method: 'PUT', body });
			error = '';
			notice = `Gespeichert. ${s.shifted_count} ${s.shifted_count === 1 ? 'Buchung zählt' : 'Buchungen zählen'} jetzt für den Folgemonat.`;
		} catch (e) {
			error = (e as Error).message;
			notice = '';
		} finally {
			saving = false;
		}
	}
</script>

{#snippet toggle(on: boolean, label: string, flip: () => void)}
	<button type="button" class="switch" class:on role="switch" aria-checked={on} aria-label={label} onclick={flip}>
		<span class="knob"></span>
	</button>
{/snippet}

<section class="card bm-settings">
	<div class="title">
		<span class="ic"><CalendarArrowDown size={18} /></span>
		<div>
			<h2>Budgetmonat</h2>
			<p class="muted small">
				Das Gehalt kommt zum Monatsende, gelebt wird davon im Folgemonat. Gehaltseingänge aus den letzten Tagen eines Monats
				zählen deshalb in Übersicht und Monatssummen für den nächsten Monat. Der Buchungstag bleibt erhalten.
			</p>
		</div>
	</div>

	{#if error}<div class="error">{error}</div>{/if}

	{#if s}
		<div class="opt">
			<div>
				<strong>Gehalt dem Folgemonat zuordnen</strong>
				<span class="muted small">{s.shifted_count} {s.shifted_count === 1 ? 'Buchung' : 'Buchungen'} derzeit verschoben</span>
			</div>
			{@render toggle(s.salary_shift_enabled, 'Gehalt dem Folgemonat zuordnen', () => s && (s.salary_shift_enabled = !s.salary_shift_enabled))}
		</div>

		<div class="body" class:off={!s.salary_shift_enabled}>
			<div class="opt">
				<div>
					<strong>Zeitraum zum Monatsende</strong>
					<span class="muted small">Eingänge in den letzten {s.salary_shift_days} Tagen eines Monats</span>
				</div>
				<div class="stepper">
					<button type="button" aria-label="Weniger Tage" onclick={() => setDays(s!.salary_shift_days - 1)} disabled={s.salary_shift_days <= 1}><Minus size={15} /></button>
					<span class="val"><strong>{s.salary_shift_days}</strong> Tage</span>
					<button type="button" aria-label="Mehr Tage" onclick={() => setDays(s!.salary_shift_days + 1)} disabled={s.salary_shift_days >= 15}><Plus size={15} /></button>
				</div>
			</div>

			<div class="opt col">
				<div>
					<strong>Als Gehalt zählen diese Kategorien</strong>
					<span class="muted small">Buchungen in Ausgaben- und Umbuchungskategorien werden nie verschoben.</span>
				</div>
				<div class="chips">
					{#each incomeCategories as main (main.id)}
						{#each main.children as sub (sub.id)}
							{@const on = s.salary_category_ids.includes(sub.id)}
							<button type="button" class="chip" class:on aria-pressed={on} onclick={() => toggleCategory(sub.id)}>
								{#if on}<Check size={14} />{/if}{sub.name}
							</button>
						{/each}
					{/each}
				</div>
			</div>

			<div class="opt col">
				<div>
					<strong>Auftraggeber</strong>
					<span class="muted small">Eingänge von diesen Auftraggebern zählen immer als Gehalt (Teil des Namens genügt).</span>
				</div>
				<div class="chips">
					{#each s.salary_payees as p (p)}
						<span class="chip on tag"
							>{p}<button type="button" aria-label={`${p} entfernen`} onclick={() => s && (s.salary_payees = s.salary_payees.filter((x) => x !== p))}
								><X size={13} /></button
							></span
						>
					{/each}
					<form class="add" onsubmit={addPayee}>
						<input bind:value={payee} placeholder="z. B. Arbeitgeber AG" aria-label="Auftraggeber hinzufügen" />
						<button type="submit" class="secondary" disabled={!payee.trim()}><Plus size={15} /> Hinzufügen</button>
					</form>
				</div>
			</div>

			<div class="opt">
				<div>
					<strong>Automatisch erkennen</strong>
					<span class="muted small"
						>Für Buchungen ohne Kategorie: Buchungstext „Gehalt/Rente“ oder ein Auftraggeber, der auch in anderen Monaten zum
						Monatsende einen ähnlichen Betrag überweist.</span
					>
				</div>
				{@render toggle(s.salary_auto_detect, 'Automatisch erkennen', () => s && (s.salary_auto_detect = !s.salary_auto_detect))}
			</div>
		</div>

		<p class="muted small">Einzelne Buchungen legst du in der Buchungsliste über das Kalender-Symbol fest.</p>
		<div class="row foot">
			<button onclick={save} disabled={saving}>{saving ? 'Speichert …' : 'Speichern'}</button>
			{#if notice}<span class="saved small"><Check size={15} /> {notice}</span>{/if}
		</div>
	{/if}
</section>

<style>
	.title {
		display: flex;
		gap: 0.85rem;
		align-items: flex-start;
		margin-bottom: 0.5rem;
	}
	.title h2 {
		margin: 0 0 0.2rem;
	}
	.title p {
		margin: 0;
		max-width: 46rem;
	}
	.ic {
		display: grid;
		place-items: center;
		width: 2.4rem;
		height: 2.4rem;
		flex: none;
		border-radius: 12px;
		background: var(--accent-soft);
		color: var(--accent-strong);
	}
	.opt {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 1rem;
		padding: 0.9rem 0;
		border-top: 1px solid var(--border);
	}
	.opt > div:first-child {
		display: grid;
		gap: 0.15rem;
		max-width: 40rem;
	}
	.opt.col {
		flex-direction: column;
		align-items: stretch;
	}
	.body {
		transition: opacity 0.2s;
	}
	.body.off {
		opacity: 0.45;
		pointer-events: none;
	}
	.switch {
		position: relative;
		width: 2.9rem;
		height: 1.65rem;
		flex: none;
		padding: 0;
		border-radius: 999px;
		background: var(--surface-3);
		box-shadow: inset 0 0 0 1px var(--border);
	}
	.switch:hover {
		filter: none;
	}
	.switch.on {
		background: var(--gradient);
		box-shadow: none;
	}
	.knob {
		position: absolute;
		top: 0.2rem;
		left: 0.2rem;
		width: 1.25rem;
		height: 1.25rem;
		border-radius: 999px;
		background: #fff;
		box-shadow: 0 1px 3px rgb(15 23 42 / 0.25);
		transition: transform 0.18s ease;
	}
	.switch.on .knob {
		transform: translateX(1.25rem);
	}
	.stepper {
		display: inline-flex;
		align-items: center;
		gap: 0.25rem;
		padding: 0.2rem;
		border-radius: 999px;
		background: var(--surface-2);
		flex: none;
	}
	.stepper button {
		display: grid;
		place-items: center;
		width: 2rem;
		height: 2rem;
		padding: 0;
		border-radius: 999px;
		background: var(--surface);
		color: var(--text);
		box-shadow: var(--shadow);
	}
	.val {
		min-width: 4.6rem;
		text-align: center;
		font-size: 0.9rem;
		color: var(--muted);
	}
	.val strong {
		color: var(--text);
		font-variant-numeric: tabular-nums;
	}
	.chips {
		display: flex;
		flex-wrap: wrap;
		gap: 0.45rem;
		align-items: center;
	}
	.chip {
		display: inline-flex;
		align-items: center;
		gap: 0.3rem;
		padding: 0.4rem 0.85rem;
		border-radius: 999px;
		background: var(--surface-2);
		color: var(--muted);
		box-shadow: none;
		font-size: 0.85rem;
		font-weight: 550;
	}
	.chip:hover {
		filter: none;
		box-shadow: none;
		background: var(--surface-3);
	}
	.chip.on {
		background: var(--accent-soft);
		color: var(--accent-strong);
	}
	.tag {
		padding-right: 0.35rem;
	}
	.tag button {
		display: grid;
		place-items: center;
		width: 1.35rem;
		height: 1.35rem;
		padding: 0;
		border-radius: 999px;
		background: transparent;
		color: inherit;
		box-shadow: none;
	}
	.tag button:hover {
		background: color-mix(in srgb, var(--accent) 20%, transparent);
		filter: none;
	}
	.add {
		display: flex;
		gap: 0.45rem;
		flex: 1 1 18rem;
		min-width: 0;
		max-width: 100%;
	}
	.add input {
		flex: 1 1 0;
		width: 100%;
		min-width: 0;
		border-radius: 999px;
		padding-top: 0.45rem;
		padding-bottom: 0.45rem;
	}
	.add button {
		display: inline-flex;
		align-items: center;
		gap: 0.3rem;
		border-radius: 999px;
		padding: 0.45rem 0.9rem;
		white-space: nowrap;
		flex: none;
	}
	.foot {
		align-items: center;
		margin-top: 0.25rem;
	}
	.saved {
		display: inline-flex;
		align-items: center;
		gap: 0.3rem;
		color: var(--accent-strong);
	}
	@media (max-width: 640px) {
		.opt {
			align-items: flex-start;
		}
		.add {
			flex-basis: 100%;
		}
	}
</style>
