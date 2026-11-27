<script lang="ts">
	import { api } from './api';
	import { Switch } from './ui';
	import { iban as formatIban } from './format';
	import type { TransferSettings } from './types';
	import { t } from './i18n/index.svelte';
	import ArrowLeftRight from '@lucide/svelte/icons/arrow-left-right';
	import Plus from '@lucide/svelte/icons/plus';
	import Check from '@lucide/svelte/icons/check';
	import X from '@lucide/svelte/icons/x';

	/** Household settings for transfers between own accounts. */
	let s = $state<TransferSettings | null>(null);
	let newIban = $state('');
	let error = $state('');
	let notice = $state('');
	let saving = $state(false);

	api<TransferSettings>('/transfers/settings')
		.then((settings) => (s = settings))
		.catch((e) => (error = e.message));

	const addIban = (e?: Event) => {
		e?.preventDefault();
		const value = newIban.replace(/\s+/g, '').toUpperCase();
		if (!s || !value) return;
		if (!s.extra_ibans.includes(value)) s.extra_ibans = [...s.extra_ibans, value];
		newIban = '';
	};

	async function save() {
		if (!s) return;
		saving = true;
		try {
			s = await api<TransferSettings>('/transfers/settings', {
				method: 'PUT',
				body: { auto_detect: s.auto_detect, extra_ibans: s.extra_ibans }
			});
			error = '';
			notice = t('transfers.saved', { count: s.changed });
		} catch (e) {
			error = (e as Error).message;
			notice = '';
		} finally {
			saving = false;
		}
	}
</script>

<section class="card">
	<div class="title">
		<span class="ic"><ArrowLeftRight size={18} /></span>
		<div>
			<h2>{t('transfers.title')}</h2>
			<p class="muted small">{t('transfers.intro')}</p>
		</div>
	</div>

	{#if error}<div class="error">{error}</div>{/if}

	{#if s}
		<div class="opt">
			<div>
				<Switch bind:checked={s.auto_detect}><strong>{t('transfers.autoDetect')}</strong></Switch>
				<span class="muted small">{t('transfers.autoDetectHint')}</span>
				<span class="muted small">{t('transfers.detectedCount', { count: s.detected_count })}</span>
			</div>
		</div>

		<div class="body" class:off={!s.auto_detect}>
			<div class="opt col">
				<strong>{t('transfers.ownAccounts')}</strong>
				{#if s.account_ibans.length}
					<ul class="accounts">
						{#each s.account_ibans as a (a.iban)}
							<li><span>{a.name}</span> <span class="muted small">{formatIban(a.iban)}</span></li>
						{/each}
					</ul>
				{:else}
					<span class="muted small">{t('transfers.noOwnAccounts')}</span>
				{/if}
			</div>

			<div class="opt col">
				<div class="head">
					<strong>{t('transfers.extra')}</strong>
					<span class="muted small">{t('transfers.extraHint')}</span>
				</div>
				<div class="chips">
					{#each s.extra_ibans as i (i)}
						<span class="chip tag">
							{formatIban(i)}<button
								type="button"
								aria-label={t('transfers.removeIban', { iban: formatIban(i) })}
								onclick={() => s && (s.extra_ibans = s.extra_ibans.filter((x) => x !== i))}
							>
								<X size={13} />
							</button>
						</span>
					{/each}
					<form class="add" onsubmit={addIban}>
						<input bind:value={newIban} placeholder={t('transfers.extraPlaceholder')} aria-label={t('transfers.addIban')} />
						<button type="submit" class="secondary" disabled={!newIban.trim()}><Plus size={15} /> {t('common.add')}</button>
					</form>
				</div>
			</div>
		</div>

		<div class="row foot">
			<button onclick={save} disabled={saving}>{saving ? t('common.saving') : t('common.save')}</button>
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
		gap: 0.3rem;
		max-width: 40rem;
	}
	.opt.col {
		flex-direction: column;
		align-items: stretch;
	}
	.head {
		display: grid;
		gap: 0.15rem;
	}
	.body {
		transition: opacity 0.2s;
	}
	.body.off {
		opacity: 0.45;
		pointer-events: none;
	}
	.accounts {
		list-style: none;
		margin: 0;
		padding: 0;
		display: grid;
		gap: 0.3rem;
	}
	.accounts li {
		display: flex;
		flex-wrap: wrap;
		gap: 0.2rem 0.75rem;
		align-items: baseline;
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
		padding: 0.4rem 0.35rem 0.4rem 0.85rem;
		border-radius: 999px;
		background: var(--accent-soft);
		color: var(--accent-strong);
		font-size: 0.85rem;
		font-weight: 550;
		font-variant-numeric: tabular-nums;
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
		.add {
			flex-basis: 100%;
		}
	}
</style>
