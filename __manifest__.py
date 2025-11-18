# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "Partner Nota de Pedido Export",
    "summary": "Exportar contactos/clientes a CSV para sistema legacy (Nota de Pedido)",
    "author": "Be OnlyOne",
    "maintainers": ["onlyone-odoo"],
    "website": "https://onlyone.odoo.com/",
    "license": "AGPL-3",
    "category": "Sales",
    "version": "17.0.1.1.1",
    "depends": [
        "contacts",
        "sale",
        "account",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/export_ndp_contacts_wizard_views.xml",
    ],
    "installable": True,
    "application": False,
}
