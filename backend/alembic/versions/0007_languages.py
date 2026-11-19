"""Languages: per-user UI language and keys for the default categories

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-18 22:30:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0007'
down_revision: Union[str, Sequence[str], None] = '0006'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Frozen copy of the default category names and keys (app/seed.py) at the time
# of this migration: main key, main name, {sub key: sub name}
DEFAULTS = [
    ("housing", "Wohnen", {"rent": "Miete/Kredit", "service_charges": "Nebenkosten", "electricity": "Strom",
                           "heating": "Gas/Heizung", "internet_phone": "Internet/Telefon",
                           "broadcasting_fee": "Rundfunkbeitrag", "maintenance": "Instandhaltung"}),
    ("groceries", "Lebensmittel", {"supermarket": "Supermarkt", "bakery_butcher": "Bäcker/Metzger",
                                   "drinks": "Getränke", "drugstore": "Drogerie"}),
    ("household", "Haushalt", {"furnishing": "Einrichtung", "appliances": "Geräte", "cleaning": "Reinigung",
                               "garden": "Garten"}),
    ("shopping", "Shopping", {"clothing": "Kleidung", "electronics": "Elektronik", "online": "Online-Handel",
                              "gifts": "Geschenke"}),
    ("mobility", "Kfz und Mobilität", {"fuel": "Tanken/Laden", "repairs": "Werkstatt/Wartung",
                                       "car_insurance": "Kfz-Versicherung", "vehicle_tax": "Kfz-Steuer",
                                       "public_transport": "ÖPNV/Bahn", "parking": "Parken/Maut"}),
    ("insurance", "Versicherungen", {"liability": "Haftpflicht", "contents": "Hausrat", "life": "Leben/BU",
                                     "legal": "Rechtsschutz", "other": "Sonstige"}),
    ("health", "Gesundheit", {"pharmacy": "Apotheke", "doctor": "Arzt/Zuzahlung", "optician": "Optiker",
                              "fitness": "Sport/Fitness"}),
    ("leisure", "Freizeit", {"restaurants": "Restaurant/Lieferdienst", "outings": "Ausflüge/Events",
                             "hobbies": "Hobbys", "travel": "Urlaub/Reisen"}),
    ("subscriptions", "Abos und Medien", {"streaming": "Streaming", "software": "Software/Apps",
                                          "magazines": "Zeitschriften", "memberships": "Mitgliedschaften"}),
    ("family", "Kinder und Haustiere", {"childcare": "Betreuung/Schule", "children": "Kinderbedarf",
                                        "pets": "Tierbedarf/Tierarzt"}),
    ("finance", "Finanzen", {"savings": "Sparen/Depot", "loan_repayment": "Kredittilgung",
                             "bank_fees": "Bankgebühren", "taxes": "Steuern", "donations": "Spenden"}),
    ("income", "Einnahmen", {"salary": "Gehalt", "child_benefit": "Kindergeld", "refunds": "Erstattungen",
                             "interest": "Zinsen/Dividenden", "other": "Sonstige Einnahmen"}),
    ("transfers", "Umbuchungen", {"own_accounts": "Transfers zwischen eigenen Konten"}),
    ("misc", "Sonstiges", {"cash": "Bargeld", "uncategorized": "Unkategorisiert"}),
]


def upgrade() -> None:
    op.add_column('users', sa.Column('language', sa.String(length=5), nullable=True))
    op.add_column('categories', sa.Column('default_key', sa.String(length=50), nullable=True))

    # Existing households: categories that still carry their default name get
    # their key, so they are shown translated. Renamed ones stay as they are.
    conn = op.get_bind()
    for main_key, main_name, subs in DEFAULTS:
        conn.execute(
            sa.text("UPDATE categories SET default_key = :key WHERE parent_id IS NULL AND name = :name"),
            {"key": main_key, "name": main_name},
        )
        for sub_key, sub_name in subs.items():
            conn.execute(
                sa.text(
                    "UPDATE categories c SET default_key = :key FROM categories p "
                    "WHERE c.parent_id = p.id AND p.default_key = :main AND c.name = :name"
                ),
                {"key": f"{main_key}.{sub_key}", "main": main_key, "name": sub_name},
            )


def downgrade() -> None:
    op.drop_column('categories', 'default_key')
    op.drop_column('users', 'language')
