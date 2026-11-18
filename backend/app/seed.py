"""Default category scheme (see docs/ARCHITECTURE.md)."""

from sqlalchemy.orm import Session

from .models import Category, CategoryKind

DEFAULT_CATEGORIES: list[tuple[str, CategoryKind, list[str]]] = [
    ("Wohnen", CategoryKind.expense,
     ["Miete/Kredit", "Nebenkosten", "Strom", "Gas/Heizung", "Internet/Telefon", "Rundfunkbeitrag", "Instandhaltung"]),
    ("Lebensmittel", CategoryKind.expense, ["Supermarkt", "Bäcker/Metzger", "Getränke", "Drogerie"]),
    ("Haushalt", CategoryKind.expense, ["Einrichtung", "Geräte", "Reinigung", "Garten"]),
    ("Shopping", CategoryKind.expense, ["Kleidung", "Elektronik", "Online-Handel", "Geschenke"]),
    ("Kfz und Mobilität", CategoryKind.expense,
     ["Tanken/Laden", "Werkstatt/Wartung", "Kfz-Versicherung", "Kfz-Steuer", "ÖPNV/Bahn", "Parken/Maut"]),
    ("Versicherungen", CategoryKind.expense, ["Haftpflicht", "Hausrat", "Leben/BU", "Rechtsschutz", "Sonstige"]),
    ("Gesundheit", CategoryKind.expense, ["Apotheke", "Arzt/Zuzahlung", "Optiker", "Sport/Fitness"]),
    ("Freizeit", CategoryKind.expense, ["Restaurant/Lieferdienst", "Ausflüge/Events", "Hobbys", "Urlaub/Reisen"]),
    ("Abos und Medien", CategoryKind.expense, ["Streaming", "Software/Apps", "Zeitschriften", "Mitgliedschaften"]),
    ("Kinder und Haustiere", CategoryKind.expense, ["Betreuung/Schule", "Kinderbedarf", "Tierbedarf/Tierarzt"]),
    ("Finanzen", CategoryKind.expense, ["Sparen/Depot", "Kredittilgung", "Bankgebühren", "Steuern", "Spenden"]),
    ("Einnahmen", CategoryKind.income,
     ["Gehalt", "Kindergeld", "Erstattungen", "Zinsen/Dividenden", "Sonstige Einnahmen"]),
    ("Umbuchungen", CategoryKind.transfer, ["Transfers zwischen eigenen Konten"]),
    ("Sonstiges", CategoryKind.expense, ["Bargeld", "Unkategorisiert"]),
]


def seed_categories(db: Session, household_id: int) -> None:
    for i, (name, kind, subs) in enumerate(DEFAULT_CATEGORIES):
        main = Category(household_id=household_id, name=name, kind=kind, sort_order=i)
        main.children = [
            Category(household_id=household_id, name=sub, kind=kind, sort_order=j) for j, sub in enumerate(subs)
        ]
        db.add(main)
