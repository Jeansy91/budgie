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
	let newName = $state('');
	let newIban = $state('');
	let error = $state('');
	let notice = $state('');
	let saving = $state(false);

	api<TransferSettings>('/transfers/settings')
		.then((settings) => (s = settings))
		.catch((e) => (error = e.message));

	const addIban = (e?: Event) => {
		e?.preventDefault();
		const name = newName.trim();
		const value = newIban.replace(/\s+/g, '').toUpperCase();
		if (!s || !name || !value) return;
		if (!s.extra_accounts.some((a) => a.iban === value)) s.extra_accounts = [...s.extra_accounts, { name, iban: value }];
		newName = '';
		newIban = '';
	};

	async function save() {
		if (!s) return;
		saving = true;
		try {
			s = await api<TransferSettings>('/transfers/settings', {
				method: 'PUT',
				body: { auto_detect: s.auto_detect, extra_accounts: s.extra_accounts }
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
				{#if s.extra_accounts.length}
					<ul class="accounts">
						{#each s.extra_accounts as a (a.iban)}
							<li>
								<span>{a.name}</span>
								<span class="muted small">{formatIban(a.iban)}</span>
								<button
									type="button"
									class="remove"
									aria-label={t('transfers.removeAccount', { name: a.name })}
									onclick={() => s && (s.extra_accounts = s.extra_accounts.filter((x) => x.iban !== a.iban))}
								>
									<X size={14} />
								</button>
							</li>
						{/each}
					</ul>
				{/if}
				<form class="add" onsubmit={addIban}>
					<input
						bind:value={newName}
						maxlength="100"
						placeholder={t('transfers.namePlaceholder')}
						aria-label={t('transfers.accountName')}
					/>
					<input bind:value={newIban} placeholder={t('transfers.extraPlaceholder')} aria-label={t('transfers.ibanLabel')} />
					<button type="submit" class="secondary" disabled={!newName.trim() || !newIban.trim()}>
						<Plus size={15} />
						{t('transfers.addIban')}
					</button>
				</form>
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
	.accounts li .remove {
		margin-left: auto;
		display: grid;
		place-items: center;
		width: 1.6rem;
		height: 1.6rem;
		padding: 0;
		border-radius: 999px;
		background: transparent;
		color: var(--muted);
		box-shadow: none;
	}
	.accounts li .remove:hover {
		background: var(--surface-3);
		filter: none;
	}
	.add {
		display: flex;
		flex-wrap: wrap;
		gap: 0.45rem;
	}
	.add input {
		flex: 1 1 12rem;
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
</style>
