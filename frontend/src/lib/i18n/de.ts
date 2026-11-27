/**
 * German UI texts (default language). This file defines the message keys;
 * every other language must provide the same keys (see en.ts).
 *
 * Placeholders in braces are filled in by t(), e.g. {count}. Plural messages
 * use { one, other } and pick the form from the `count` parameter.
 */

export interface Plural {
	zero?: string;
	one: string;
	other: string;
}

type Widen<T> = { [K in keyof T]: T[K] extends string ? string : T[K] extends Plural ? Plural : Widen<T[K]> };

const de = {
	common: {
		month: 'Monat',
		account: 'Konto',
		category: 'Kategorie',
		close: 'Schließen',
		quoted: '„{text}“',
		cancel: 'Abbrechen',
		delete: 'Löschen',
		add: 'Hinzufügen',
		name: 'Name',
		create: 'Anlegen',
		optional: 'optional',
		save: 'Speichern',
		saving: 'Speichert …'
	},
	nav: {
		transactions: 'Buchungen',
		rules: 'Regeln',
		categories: 'Kategorien',
		overview: 'Übersicht',
		import: 'Import',
		settings: 'Einstellungen',
		logout: 'Abmelden'
	},
	auth: {
		username: 'Nutzername',
		password: 'Passwort',
		welcomeBack: 'Willkommen zurück',
		loginIntro: 'Melde dich an, um dein Haushaltsbuch zu öffnen.',
		login: 'Anmelden',
		defaultHousehold: 'Unser Haushalt',
		welcome: 'Willkommen bei Budgie',
		setupIntro:
			'Lege deinen Haushalt und das erste Konto an. Die Startkategorien werden automatisch eingerichtet. Weitere Nutzer kannst du danach in den Einstellungen anlegen.',
		householdName: 'Name des Haushalts',
		yourName: 'Dein Name',
		passwordMin: 'Passwort (mindestens 8 Zeichen)',
		setup: 'Einrichten'
	},
	overview: {
		eyebrow: 'Monatsübersicht',
		emptyTitle: 'Noch keine Buchungen.',
		emptyLink: 'Importiere deine erste ING-CSV-Datei',
		emptyRest: ', dann füllt sich die Übersicht.',
		net: 'Saldo im Monat',
		savingsRate: '{rate} der Einnahmen übrig',
		noIncomeYet: 'Noch keine Einnahmen in diesem Monat',
		income: 'Einnahmen',
		carryTitle: 'Gehalt vom Monatsende zählt für den Folgemonat. Einstellbar unter Einstellungen › Budgetmonat.',
		carry: 'davon {amount} aus dem Vormonat',
		expenses: 'Ausgaben',
		uncategorized: { one: 'hat noch keine Kategorie.', other: 'haben noch keine Kategorie.' },
		categorizeNow: 'Jetzt zuordnen',
		expensesByCategory: 'Ausgaben nach Kategorie',
		noExpenses: 'Keine Ausgaben in diesem Monat.',
		total: 'Gesamt',
		noIncome: 'Keine Einnahmen in diesem Monat.',
		transfers: 'Umbuchungen zwischen eigenen Konten: {amount} (nicht mitgezählt)',
		history: 'Verlauf der letzten 12 Monate'
	},
	transactions: {
		allAccounts: 'Alle Konten',
		allCategories: 'Alle Kategorien',
		allOfMain: 'alle',
		ruleCreated: {
			one: 'Regel für „{payee}“ angelegt, {count} weitere Buchung zugeordnet.',
			other: 'Regel für „{payee}“ angelegt, {count} weitere Buchungen zugeordnet.'
		},
		count: { one: '{count} Buchung', other: '{count} Buchungen' },
		searchPlaceholder: 'Empfänger oder Verwendungszweck suchen',
		onlyUncategorized: 'Nur ohne Kategorie',
		aiReviewTitle: 'Zuordnungen und Vorschläge der KI, die noch niemand bestätigt hat',
		aiReview: 'KI prüfen',
		learnRulesTitle: 'Beim Zuordnen eine Regel „Empfänger oder Sender enthält …“ anlegen und auf ähnliche Buchungen anwenden',
		learnRules: 'Regeln lernen',
		empty: 'Keine Buchungen für diese Filter.',
		rowLabel: '{payee}, {amount} – Details anzeigen',
		suggestionTitle: 'Vorschlag der KI mit einem Klick übernehmen: {category}',
		suggestion: 'Vorschlag:',
		accept: 'Übernehmen',
		confirmTitle: 'Passt – Zuordnung bestätigen. Die KI lernt daraus.',
		confirm: 'Zuordnung bestätigen',
		loadMore: 'Weitere laden'
	},
	detail: {
		bookingMonthNote: 'Buchungsmonat',
		nextMonthNote: 'Folgemonat',
		ruleCreatedLater: 'Regel angelegt. Sie gilt ab dem nächsten Import.',
		payer: 'Auftraggeber',
		payee: 'Empfänger',
		sourceUnknown: 'Unbekannt',
		sourceFints: 'FinTS-Abruf',
		sourceCsv: 'CSV-Import',
		closeDetails: 'Details schließen',
		transaction: 'Buchung',
		closeEsc: 'Schließen (Esc)',
		manual: 'Manuell zugeordnet',
		byRule: 'Per Regel zugeordnet',
		manageRules: 'Regeln verwalten',
		byAi: 'Von der KI zugeordnet',
		aiConfidence: 'Sicherheit der KI',
		confident: '{confidence} sicher',
		noCategory: 'Noch keine Kategorie',
		looksRight: 'Passt',
		budgetMonth: 'Budgetmonat',
		autoCountsFor: 'Automatisch: zählt für {month}.',
		budgetHint: 'Gehalt zum Monatsende kann automatisch dem Folgemonat zugerechnet werden.',
		purpose: 'Verwendungszweck',
		details: 'Details',
		bookingDate: 'Buchungstag',
		valueDate: 'Wertstellung',
		balanceAfter: 'Saldo danach',
		bookingText: 'Buchungstext',
		mandateId: 'Mandatsreferenz',
		creditorId: 'Gläubiger-ID',
		endToEnd: 'End-to-End-Referenz',
		source: 'Quelle',
		importedAt: 'Importiert am',
		csvNoSepa: 'Der CSV-Export der ING enthält keine IBAN und keine SEPA-Referenzen. Per FinTS abgerufene Buchungen zeigen sie hier an.',
		note: 'Notiz',
		notePlaceholder: 'Eigene Notiz zu dieser Buchung',
		createRule: 'Regel aus dieser Buchung erstellen',
		newRule: 'Neue Regel',
		matchesThis: 'Passt auf diese Buchung',
		notMatchesThis: 'Passt nicht auf diese Buchung',
		applyNow: 'Gleich auf passende Buchungen anwenden',
		manualNeverOverwritten: 'Manuell zugeordnete Buchungen werden nie überschrieben.'
	},
	source: {
		ai: 'KI',
		manual: 'manuell',
		rule: 'Regel',
		llm: 'KI',
		model: 'KI',
		modelTitle: 'Von der KI zugeordnet, {confidence} sicher',
		llmTitle: 'Vom lokalen Sprachmodell zugeordnet'
	},
	budgetMenu: {
		auto: 'Automatisch',
		autoHint: 'Gehalt zum Monatsende zählt für den Folgemonat',
		bookingMonth: 'Buchungsmonat',
		nextMonth: 'Folgemonat',
		countsFor: 'Zählt für {month}',
		countsForShort: 'zählt für {month}',
		set: 'Budgetmonat festlegen',
		title: 'Zählt im Monat',
		now: 'jetzt {month}'
	},
	categorySelect: {
		search: 'Kategorie suchen …',
		choose: 'Kategorie wählen',
		none: '– ohne Kategorie –'
	},
	import: {
		new: 'neu',
		duplicate: 'schon vorhanden',
		byRule: 'per Regel zugeordnet',
		autoAccount: 'Konto automatisch über die IBAN erkennen',
		eyebrow: 'Bankkonten',
		title: 'Umsätze importieren',
		intro: 'Direkt per FinTS abrufen oder eine CSV-Datei hochladen. Doppelte Buchungen werden übersprungen.',
		csvTitle: 'CSV-Datei hochladen',
		csvHint: 'Budgie erkennt CSV-Exporte von {banks} automatisch. Dateien anderer Banken ordnest du einmal den Spalten zu.',
		importing: 'Importiere …',
		drop: 'CSV-Dateien hierher ziehen',
		orClick: 'oder klicken, um Dateien auszuwählen',
		into: 'Importieren in',
		newAccount: 'Neues Konto',
		categorize: 'Zuordnen',
		accounts: 'Konten',
		noIban: 'ohne IBAN',
		confirmDeleteProfile: 'Vorlage „{name}“ löschen?',
		profiles: 'Eigene CSV-Vorlagen',
		deleteProfile: 'Vorlage {name} löschen'
	},
	bank: {
		confirmRemove: 'Zugang „{name}“ entfernen? Konten und Buchungen bleiben erhalten.',
		never: 'noch nie',
		title: 'Direkt von der Bank abrufen',
		intro: 'Per FinTS, bei fast allen deutschen Banken und Sparkassen. Die PIN gibst du bei jedem Abruf ein, gespeichert wird sie nicht.',
		notConfigured: 'FinTS ist noch nicht eingerichtet. Es fehlt in der',
		login: 'Zugang …{hint}',
		lastSync: 'zuletzt abgerufen {when}',
		sync: 'Umsätze abrufen',
		remove: 'Entfernen',
		pin: 'PIN fürs Online-Banking',
		since: 'Ab Datum',
		fetch: 'Abrufen',
		sinceHint: 'Ohne Datum holt Budgie beim ersten Mal die letzten 90 Tage, danach ab dem letzten Abruf.',
		approveInApp: 'Bitte in der Banking-App freigeben',
		waiting: 'Budgie wartet auf die Freigabe und macht dann automatisch weiter.',
		enterTan: 'TAN eingeben',
		tanImage: 'TAN-Grafik',
		send: 'Senden',
		retry: 'Noch einmal',
		cancelled: 'Abruf abgebrochen.',
		from: 'ab {date}',
		loginNumber: 'Zugangsnummer',
		loginPlaceholder: '10-stellig, wie beim Login',
		saveLogin: 'Zugang speichern',
		ingHint: 'Für die ING sind Bankleitzahl und FinTS-Server schon eingestellt. Die Zugangsnummer wird verschlüsselt gespeichert.',
		addAnother: 'Weiteren Zugang hinzufügen',
		chooseBankFirst: 'Bitte zuerst die Bank auswählen.',
		changeTanTitle: 'Beim nächsten Abruf neu auswählen',
		changeTan: 'TAN-Verfahren ändern',
		chooseMedium: 'TAN-Gerät wählen',
		chooseMechanism: 'TAN-Verfahren wählen',
		chooseMediumHint: 'Deine Bank kennt mehrere Geräte für TANs. Welches möchtest du nutzen?',
		chooseMechanismHint: 'Deine Bank bietet mehrere Verfahren an. Budgie merkt sich die Wahl für diesen Zugang.',
		tanMedium: 'TAN-Gerät',
		tanMechanism: 'TAN-Verfahren',
		appApproval: 'Freigabe in der App',
		continue: 'Weiter',
		flickerCode: 'Flickercode für chipTAN (manuell eingeben):',
		bank: 'Bank',
		loginName: 'Anmeldename',
		loginNamePlaceholder: 'wie beim Online-Banking',
		loginNameTitle: 'Zugangsnummer, Anmeldename, Legitimations-ID oder VR-NetKey',
		advanced: 'Erweitert',
		serverUrl: 'FinTS-Adresse',
		customerId: 'Kunden-ID',
		noServerUrl:
			'Für diese Bank kennt Budgie keine FinTS-Adresse. Du findest sie meist in der Hilfe deiner Bank unter „FinTS“ oder „HBCI PIN/TAN“.',
		encryptedHint: 'Der Anmeldename wird verschlüsselt gespeichert, die PIN nie.',
		bankCode: 'BLZ',
		changeBank: 'Ändern',
		searchPlaceholder: 'Bank, Ort, BLZ oder BIC',
		search: 'Bank suchen',
		noServerUrlShort: 'keine FinTS-Adresse bekannt',
		notFound: 'Keine Bank gefunden. Tipp: Die Bankleitzahl steht in deiner IBAN an Stelle 5 bis 12.'
	},
	csv: {
		notPresent: '– nicht vorhanden –',
		column: 'Spalte {n}',
		title: 'Spalten zuordnen',
		introBefore: 'Das Format von',
		introAfter: 'kennt Budgie noch nicht. Sag einmal, welche Spalte was enthält.',
		dateFormat: 'Datumsformat',
		numberFormat: 'Zahlenformat',
		needAmount: 'Bitte den Betrag zuordnen, entweder als eine Spalte mit Vorzeichen oder getrennt nach Soll und Haben.',
		saveAs: 'Als Vorlage speichern',
		saveAsPlaceholder: 'optional, z. B. Name der Bank',
		saveAsHint: 'Mit Vorlage erkennt Budgie Dateien mit denselben Spalten künftig von selbst.',
		import: 'Importieren',
		field: {
			booking_date: 'Buchungsdatum',
			value_date: 'Wertstellung',
			payee: 'Empfänger / Auftraggeber',
			purpose: 'Verwendungszweck',
			booking_text: 'Buchungstext / Art',
			amount: 'Betrag (mit Vorzeichen)',
			debit: 'Soll / Ausgang',
			credit: 'Haben / Eingang',
			balance: 'Saldo danach',
			counterparty_iban: 'IBAN Gegenkonto',
			currency: 'Währung'
		}
	},
	categories: {
		kind: {
			expense: 'Ausgabe',
			income: 'Einnahme',
			transfer: 'Umbuchung'
		},
		newName: 'Neuer Name',
		confirmDeleteMain:
			'„{name}“ mit allen Unterkategorien löschen? Zugeordnete Buchungen werden wieder unkategorisiert, passende Regeln gelöscht.',
		confirmDelete: '„{name}“ löschen? Zugeordnete Buchungen werden wieder unkategorisiert, passende Regeln gelöscht.',
		eyebrow: 'Haushalt',
		intro: 'Buchungen werden immer einer Unterkategorie zugeordnet. Die Art legt fest, ob sie als Ausgabe, Einnahme oder Umbuchung zählt.',
		kindLabel: 'Art',
		rename: 'Umbenennen',
		newSub: 'Neue Unterkategorie',
		newMain: 'Neue Hauptkategorie'
	},
	rules: {
		field: {
			payee: 'Empfänger oder Sender',
			recipient: 'Empfänger (Ausgang)',
			sender: 'Sender (Eingang)',
			purpose: 'Verwendungszweck',
			any: 'Name oder Zweck'
		},
		match: {
			contains: 'enthält',
			equals: 'ist genau',
			starts_with: 'beginnt mit',
			regex: 'passt zu Regex'
		},
		created: { one: 'Regel angelegt, {count} Buchung zugeordnet.', other: 'Regel angelegt, {count} Buchungen zugeordnet.' },
		fieldLabel: 'Feld',
		condition: 'Bedingung',
		text: 'Text',
		textPlaceholder: 'z. B. REWE',
		create: 'Regel anlegen',
		confirmDelete: 'Regel „{pattern}“ löschen? Bereits zugeordnete Buchungen behalten ihre Kategorie.',
		reapplied: { one: '{count} Buchung neu zugeordnet.', other: '{count} Buchungen neu zugeordnet.' },
		eyebrow: 'Automatisch zuordnen',
		intro: 'Regeln ordnen Buchungen beim Import zu. Höhere Priorität gewinnt, manuelle Zuordnungen bleiben unangetastet.',
		applyOpen: 'Auf offene Buchungen anwenden',
		recomputeTitle: 'Auch Zuordnungen durch Regeln neu berechnen, manuelle bleiben',
		recompute: 'Alles neu berechnen',
		if: 'Wenn',
		then: 'dann',
		priority: 'Priorität',
		prio: 'Prio',
		hits: 'Treffer',
		active: 'Aktiv',
		inactive: 'Inaktiv',
		activeLabel: 'Regel aktiv',
		empty: 'Noch keine Regeln. Lege eine an oder ordne unter „Buchungen“ zu und setze dort den Haken für Regeln.'
	},
	settings: {
		languageAuto: 'Automatisch',
		language: 'Sprache',
		languageHint: '„Automatisch“ folgt der Sprache deines Browsers (derzeit {browser}). Die Auswahl gilt für dein Konto auf allen Geräten.',
		accountSaved: 'Konto gespeichert.',
		confirmDeleteAccount: {
			one: 'Konto „{name}“ mit {count} Buchung löschen?',
			other: 'Konto „{name}“ mit allen {count} Buchungen löschen?'
		},
		accountDeleted: 'Konto gelöscht.',
		userCreated: 'Nutzer angelegt.',
		confirmDeleteUser: 'Nutzer „{name}“ löschen?',
		userDeleted: 'Nutzer gelöscht.',
		passwordChanged: 'Passwort geändert.',
		shared: 'Für alle im Haushalt sichtbar',
		visibleFor: 'Sichtbar für:',
		noAccounts: 'Konten entstehen automatisch beim ersten Import.',
		noAccountsLink: 'Zum Import',
		users: 'Nutzer im Haushalt',
		deleteUser: 'löschen',
		createUser: 'Nutzer anlegen',
		changePassword: 'Passwort ändern',
		currentPassword: 'Aktuelles Passwort',
		newPassword: 'Neues Passwort',
		change: 'Ändern'
	},
	budget: {
		saved: {
			one: 'Gespeichert. {count} Buchung zählt jetzt für den Folgemonat.',
			other: 'Gespeichert. {count} Buchungen zählen jetzt für den Folgemonat.'
		},
		intro:
			'Das Gehalt kommt zum Monatsende, gelebt wird davon im Folgemonat. Gehaltseingänge aus den letzten Tagen eines Monats zählen deshalb in Übersicht und Monatssummen für den nächsten Monat. Der Buchungstag bleibt erhalten.',
		shift: 'Gehalt dem Folgemonat zuordnen',
		shiftedCount: { one: '{count} Buchung derzeit verschoben', other: '{count} Buchungen derzeit verschoben' },
		window: 'Zeitraum zum Monatsende',
		windowHint: { one: 'Eingänge am letzten Tag eines Monats', other: 'Eingänge in den letzten {count} Tagen eines Monats' },
		fewerDays: 'Weniger Tage',
		days: { one: 'Tag', other: 'Tage' },
		moreDays: 'Mehr Tage',
		categories: 'Als Gehalt zählen diese Kategorien',
		categoriesHint: 'Buchungen in Ausgaben- und Umbuchungskategorien werden nie verschoben.',
		payers: 'Auftraggeber',
		payersHint: 'Eingänge von diesen Auftraggebern zählen immer als Gehalt (Teil des Namens genügt).',
		removePayer: '{name} entfernen',
		payerPlaceholder: 'z. B. Arbeitgeber AG',
		addPayer: 'Auftraggeber hinzufügen',
		autoDetect: 'Automatisch erkennen',
		autoDetectHint:
			'Für Buchungen ohne Kategorie: Buchungstext „Gehalt/Rente“ oder ein Auftraggeber, der auch in anderen Monaten zum Monatsende einen ähnlichen Betrag überweist.',
		perTransaction: 'Einzelne Buchungen legst du in der Buchungsliste über das Kalender-Symbol fest.'
	},
	ai: {
		trained: 'KI neu trainiert und offene Buchungen neu eingeordnet.',
		recategorizedLlm: '{assigned} zugeordnet, {suggested} Vorschläge, {queued} gehen an das Sprachmodell.',
		recategorized: '{assigned} zugeordnet, {suggested} Vorschläge.',
		title: 'KI-Kategorisierung',
		disabled: 'Ausgeschaltet',
		intro:
			'Läuft komplett auf deinem Server. Jede Zuordnung, die du änderst oder mit dem Haken bestätigst, ist ein Lernbeispiel. Ab {threshold} Sicherheit ordnet die KI selbst zu, darunter macht sie einen Vorschlag.',
		learnedFrom: 'Gelernt aus',
		ownTransactions: 'eigenen Buchungen',
		manualShare: ', davon {count} von Hand',
		accuracy: 'Trefferquote',
		accuracyHint: 'bei deinen eigenen Zuordnungen',
		accuracyLater: 'ab 20 Zuordnungen von Hand',
		toReview: 'Zu prüfen',
		toReviewHint: '{assigned} von der KI zugeordnet, {suggestions} Vorschläge',
		uncategorized: 'Ohne Kategorie',
		transactions: { one: 'Buchung', other: 'Buchungen' },
		lastTrained: 'Zuletzt trainiert {when}.',
		notTrained: 'Noch nicht trainiert. Das passiert beim ersten Import automatisch.',
		llmTitle: 'Sprachmodell für unsichere Fälle',
		llmOff: 'Aus. Optional über Ollama zuschaltbar, siehe README („docker compose --profile ai“ und BUDGIE_OLLAMA_URL).',
		llmReady: '{model} ist bereit.',
		llmRunning: 'Arbeitet gerade: {done} von {total} Buchungen eingeordnet …',
		train: 'Jetzt neu trainieren',
		recategorize: 'Offene Buchungen neu einordnen'
	},
	errors: {
		validation: {
			missing: 'Pflichtfeld fehlt: {field}',
			tooShort: '{field}: mindestens {min} Zeichen',
			tooLong: '{field}: höchstens {max} Zeichen',
			pattern: '{field}: ungültige Zeichen'
		},
		http: 'Fehler {status}'
	},
	ui: {
		date: {
			label: 'Datum',
			placeholder: 'Datum wählen',
			prevMonth: 'Vormonat',
			nextMonth: 'Nächster Monat',
			today: 'Heute',
			clear: 'Leeren'
		},
		month: {
			label: 'Monat',
			placeholder: 'Monat wählen',
			all: 'Alle Monate',
			prevYear: 'Vorjahr',
			nextYear: 'Nächstes Jahr',
			thisMonth: 'Dieser Monat'
		},
		number: {
			less: 'Weniger',
			more: 'Mehr'
		},
		password: {
			show: 'Passwort anzeigen',
			hide: 'Passwort verbergen'
		},
		select: {
			placeholder: 'Bitte wählen',
			search: 'Suchen',
			searchPlaceholder: 'Suchen …',
			noResults: 'Nichts gefunden'
		}
	}
};

export type Messages = Widen<typeof de>;
export default de;
