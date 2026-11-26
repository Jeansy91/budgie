"""Default category scheme (see docs/ARCHITECTURE.md).

Every default category has a stable key (e.g. "groceries.supermarket"). The
database stores the German name; the API shows the name in the language of
the request as long as the category keeps its key. Renaming a category
removes the key, so names chosen by the user are never translated.
"""

from sqlalchemy.orm import Session

from .models import Category, CategoryKind

# (key, German name, English name)
Name = tuple[str, str, str]

DEFAULT_CATEGORIES: list[tuple[Name, CategoryKind, list[Name]]] = [
    (
        ("housing", "Wohnen", "Housing"),
        CategoryKind.expense,
        [
            ("rent", "Miete/Kredit", "Rent/Mortgage"),
            ("service_charges", "Nebenkosten", "Service charges"),
            ("electricity", "Strom", "Electricity"),
            ("heating", "Gas/Heizung", "Gas/Heating"),
            ("internet_phone", "Internet/Telefon", "Internet/Phone"),
            ("broadcasting_fee", "Rundfunkbeitrag", "Broadcasting fee"),
            ("maintenance", "Instandhaltung", "Maintenance"),
        ],
    ),
    (
        ("groceries", "Lebensmittel", "Groceries"),
        CategoryKind.expense,
        [
            ("supermarket", "Supermarkt", "Supermarket"),
            ("bakery_butcher", "Bäcker/Metzger", "Bakery/Butcher"),
            ("drinks", "Getränke", "Drinks"),
            ("drugstore", "Drogerie", "Drugstore"),
        ],
    ),
    (
        ("household", "Haushalt", "Household"),
        CategoryKind.expense,
        [
            ("furnishing", "Einrichtung", "Furnishing"),
            ("appliances", "Geräte", "Appliances"),
            ("cleaning", "Reinigung", "Cleaning"),
            ("garden", "Garten", "Garden"),
        ],
    ),
    (
        ("shopping", "Shopping", "Shopping"),
        CategoryKind.expense,
        [
            ("clothing", "Kleidung", "Clothing"),
            ("electronics", "Elektronik", "Electronics"),
            ("online", "Online-Handel", "Online shopping"),
            ("gifts", "Geschenke", "Gifts"),
        ],
    ),
    (
        ("mobility", "Kfz und Mobilität", "Car and transport"),
        CategoryKind.expense,
        [
            ("fuel", "Tanken/Laden", "Fuel/Charging"),
            ("repairs", "Werkstatt/Wartung", "Repairs/Servicing"),
            ("car_insurance", "Kfz-Versicherung", "Car insurance"),
            ("vehicle_tax", "Kfz-Steuer", "Vehicle tax"),
            ("public_transport", "ÖPNV/Bahn", "Public transport/Rail"),
            ("parking", "Parken/Maut", "Parking/Tolls"),
        ],
    ),
    (
        ("insurance", "Versicherungen", "Insurance"),
        CategoryKind.expense,
        [
            ("liability", "Haftpflicht", "Liability"),
            ("contents", "Hausrat", "Home contents"),
            ("life", "Leben/BU", "Life/Disability"),
            ("legal", "Rechtsschutz", "Legal expenses"),
            ("other", "Sonstige", "Other"),
        ],
    ),
    (
        ("health", "Gesundheit", "Health"),
        CategoryKind.expense,
        [
            ("pharmacy", "Apotheke", "Pharmacy"),
            ("doctor", "Arzt/Zuzahlung", "Doctor/Co-payments"),
            ("optician", "Optiker", "Optician"),
            ("fitness", "Sport/Fitness", "Sports/Fitness"),
        ],
    ),
    (
        ("leisure", "Freizeit", "Leisure"),
        CategoryKind.expense,
        [
            ("restaurants", "Restaurant/Lieferdienst", "Restaurants/Delivery"),
            ("outings", "Ausflüge/Events", "Outings/Events"),
            ("hobbies", "Hobbys", "Hobbies"),
            ("travel", "Urlaub/Reisen", "Holidays/Travel"),
        ],
    ),
    (
        ("subscriptions", "Abos und Medien", "Subscriptions and media"),
        CategoryKind.expense,
        [
            ("streaming", "Streaming", "Streaming"),
            ("software", "Software/Apps", "Software/Apps"),
            ("magazines", "Zeitschriften", "Magazines"),
            ("memberships", "Mitgliedschaften", "Memberships"),
        ],
    ),
    (
        ("family", "Kinder und Haustiere", "Children and pets"),
        CategoryKind.expense,
        [
            ("childcare", "Betreuung/Schule", "Childcare/School"),
            ("children", "Kinderbedarf", "Children's supplies"),
            ("pets", "Tierbedarf/Tierarzt", "Pet supplies/Vet"),
        ],
    ),
    (
        ("finance", "Finanzen", "Finance"),
        CategoryKind.expense,
        [
            ("savings", "Sparen/Depot", "Savings/Investments"),
            ("loan_repayment", "Kredittilgung", "Loan repayment"),
            ("bank_fees", "Bankgebühren", "Bank fees"),
            ("taxes", "Steuern", "Taxes"),
            ("donations", "Spenden", "Donations"),
        ],
    ),
    (
        ("income", "Einnahmen", "Income"),
        CategoryKind.income,
        [
            ("salary", "Gehalt", "Salary"),
            ("child_benefit", "Kindergeld", "Child benefit"),
            ("refunds", "Erstattungen", "Refunds"),
            ("interest", "Zinsen/Dividenden", "Interest/Dividends"),
            ("other", "Sonstige Einnahmen", "Other income"),
        ],
    ),
    (
        ("transfers", "Umbuchungen", "Transfers"),
        CategoryKind.transfer,
        [
            ("own_accounts", "Transfers zwischen eigenen Konten", "Transfers between own accounts"),
        ],
    ),
    (
        ("misc", "Sonstiges", "Miscellaneous"),
        CategoryKind.expense,
        [
            ("cash", "Bargeld", "Cash"),
            ("uncategorized", "Unkategorisiert", "Uncategorized"),
        ],
    ),
]

# Category key → name per language, e.g. "groceries.supermarket" → {"de": "Supermarkt", "en": "Supermarket"}
DEFAULT_NAMES: dict[str, dict[str, str]] = {}
for (_key, _de, _en), _kind, _subs in DEFAULT_CATEGORIES:
    DEFAULT_NAMES[_key] = {"de": _de, "en": _en}
    for _sub_key, _sub_de, _sub_en in _subs:
        DEFAULT_NAMES[f"{_key}.{_sub_key}"] = {"de": _sub_de, "en": _sub_en}


def seed_categories(db: Session, household_id: int) -> None:
    for i, ((key, name, _en), kind, subs) in enumerate(DEFAULT_CATEGORIES):
        main = Category(household_id=household_id, name=name, kind=kind, sort_order=i, default_key=key)
        main.children = [
            Category(
                household_id=household_id,
                name=sub_name,
                kind=kind,
                sort_order=j,
                default_key=f"{key}.{sub_key}",
            )
            for j, (sub_key, sub_name, _sub_en) in enumerate(subs)
        ]
        db.add(main)
