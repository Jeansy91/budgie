export type Kind = 'expense' | 'income' | 'transfer';

export interface Me {
	id: number;
	username: string;
	display_name: string;
	is_admin: boolean;
	household_name: string;
}

export interface User {
	id: number;
	username: string;
	display_name: string;
	is_admin: boolean;
}

export interface Account {
	id: number;
	name: string;
	iban: string | null;
	bank: string;
	currency: string;
	shared: boolean;
	member_ids: number[];
	balance: string | null;
	transaction_count: number;
	bank_connection_id: number | null;
}

export interface Category {
	id: number;
	name: string;
	parent_id: number | null;
	kind: Kind;
	sort_order: number;
	children: Category[];
}

export interface Rule {
	id: number;
	category_id: number;
	field: 'payee' | 'purpose' | 'any';
	match_type: 'contains' | 'equals' | 'starts_with' | 'regex';
	pattern: string;
	priority: number;
	active: boolean;
	match_count: number;
}

export interface Transaction {
	id: number;
	account_id: number;
	booking_date: string;
	value_date: string | null;
	amount: string;
	currency: string;
	payee: string;
	booking_text: string;
	purpose: string;
	note: string;
	category_id: number | null;
	category_source: 'manual' | 'rule' | 'model' | 'llm' | null;
	rule_id: number | null;
	/** Date that decides which month the transaction counts towards (end-of-month salary → 1st of next month) */
	budget_date: string;
	/** Manual override: null = automatic */
	budget_shift: 'next' | 'same' | null;
	category_confidence: number | null;
	suggested_category_id: number | null;
	suggestion_confidence: number | null;
}

export interface AiStatus {
	enabled: boolean;
	auto_threshold: number;
	model: {
		trained_at: string;
		samples: number;
		corrections: number;
		classes: number;
		accuracy: number | null;
	} | null;
	llm: {
		configured: boolean;
		reachable: boolean;
		model_available: boolean;
		model: string;
		error: string | null;
		running: boolean;
		done: number;
		total: number;
		failed: number;
	};
	ai_categorized: number;
	suggestions: number;
	uncategorized: number;
}

export interface BudgetSettings {
	salary_shift_enabled: boolean;
	salary_shift_days: number;
	salary_category_ids: number[];
	salary_payees: string[];
	salary_auto_detect: boolean;
	shifted_count: number;
}

export interface CategorySum {
	category_id: number | null;
	name: string;
	amount: string;
	count: number;
	children: CategorySum[];
}

export interface Overview {
	month: string;
	income: string;
	expenses: string;
	net: string;
	transfers: string;
	income_from_previous_month: string;
	uncategorized_count: number;
	expense_categories: CategorySum[];
	income_categories: CategorySum[];
	history: { month: string; income: string; expenses: string }[];
}

export interface ImportResult {
	id: number;
	account_id: number;
	filename: string | null;
	rows_total: number;
	rows_imported: number;
	rows_duplicate: number;
	rows_categorized: number;
	account_created: boolean;
}

export interface FintsStatus {
	enabled: boolean;
	missing: string[];
}

export interface BankConnection {
	id: number;
	name: string;
	bank_code: string;
	server_url: string;
	login_hint: string;
	tan_mechanism_name: string | null;
	last_sync_at: string | null;
	last_error: string | null;
	accounts: { id: number; name: string; iban: string | null }[];
}

export interface SyncResult {
	iban: string;
	account_id: number | null;
	account_name: string | null;
	account_created: boolean;
	since: string | null;
	rows_total: number;
	rows_imported: number;
	rows_duplicate: number;
	rows_categorized: number;
	skipped: string | null;
}

export interface SyncJob {
	id: string;
	connection_id: number;
	state: 'running' | 'need_tan' | 'done' | 'error' | 'cancelled';
	message: string;
	decoupled: boolean;
	challenge: string | null;
	challenge_image: string | null;
	error: string | null;
	results: SyncResult[];
}
