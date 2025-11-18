# wizards/export_ndp_contacts_wizard.py
from odoo import api, fields, models
import csv
import io
import base64


class ExportNdpContactsWizard(models.TransientModel):
    _name = "export.ndp.contacts.wizard"
    _description = "Wizard to export contacts to legacy CSV format"

    partner_ids = fields.Many2many(
        "res.partner",
        string="Clientes a Exportar",
        required=True,
        domain=[("customer_rank", ">", 0)],
    )
    datas = fields.Binary("Archivo CSV", attachment=True)

    def _format_cuit(self, vat):
        """Formatea CUIT con guiones tipo 20-12345678-9"""
        vat = (vat or "").replace("-", "").replace(" ", "")
        if len(vat) == 11 and vat.isdigit():
            return f"{vat[:2]}-{vat[2:10]}-{vat[10:]}"
        return vat

    def generate_csv(self):
        output = io.StringIO()
        writer = csv.writer(output, delimiter="|", quoting=csv.QUOTE_MINIMAL)

        for partner in self.partner_ids:
            # Contactos secundarios
            compra_contact = (
                partner.child_ids.filtered(
                    lambda c: c.function and "compra" in c.function.lower()
                )[:1]
                or partner
            )
            pago_contact = (
                partner.child_ids.filtered(
                    lambda c: c.type == "invoice"
                    or (c.function and "pago" in c.function.lower())
                )[:1]
                or partner
            )

            # Saldo abierto
            open_moves = self.env["account.move"].search(
                [
                    ("partner_id", "=", partner.id),
                    ("move_type", "in", ("out_invoice", "out_refund")),
                    ("state", "=", "posted"),
                    ("payment_state", "not in", ("paid", "reversed")),
                ]
            )
            balance = sum(open_moves.mapped("amount_residual_signed"))

            # Días de deuda máximo
            overdue_days = 0
            for move in open_moves.filtered(
                lambda m: m.invoice_date_due
                and m.invoice_date_due < fields.Date.context_today(self)
            ):
                days = (fields.Date.context_today(self) - move.invoice_date_due).days
                if days > overdue_days:
                    overdue_days = days

            # Split apellido / nombre vendedor (formato típico argentino: APELLIDO, NOMBRE)
            apellido_vend = ""
            nombre_vend = ""
            if partner.user_id and partner.user_id.name:
                if ", " in partner.user_id.name:
                    parts = partner.user_id.name.split(", ", 1)
                    apellido_vend = parts[0]
                    nombre_vend = parts[1] if len(parts) > 1 else ""
                else:
                    parts = partner.user_id.name.split()
                    apellido_vend = (
                        " ".join(parts[:-1])
                        if len(parts) > 1
                        else (parts[0] if parts else "")
                    )
                    nombre_vend = parts[-1] if len(parts) > 1 else ""

            # Tags ordenados por ID para zona y categoría (coincide con los números de los ejemplos)
            tags_sorted = partner.category_id.sorted(key="id")
            zona = str(tags_sorted[0].id) if tags_sorted else "1"
            categoria = str(tags_sorted[1].id) if len(tags_sorted) > 1 else "1"

            row = [
                partner.ref or str(partner.id),  # 1 NRO DE CLIENTE
                partner.name or "",  # 2 RAZÓN SOCIAL
                partner.commercial_company_name or "",  # 3 NOMBRE FANTASÍA
                self._format_cuit(partner.vat),  # 4 CUIT
                partner.street or "",  # 5 DOMICILIO
                partner.street2 or "",  # 6 DOMICILIO CORRESPONDENCIA
                compra_contact.name or "",  # 7 CONTACTO COMPRA
                pago_contact.email or "",  # 8 CORREO CONTACTO PAGO
                partner.city or "",  # 9 LOCALIDAD
                partner.state_id.name or "",  # 10 PROVINCIA
                partner.zip or "",  # 11 CÓDIGO POSTAL
                str(partner.property_product_pricelist.id or 1),  # 12 LISTA PRECIOS
                str(partner.user_id.id or ""),  # 13 CÓDIGO VENDEDOR
                apellido_vend,  # 14 APELLIDO VENDEDOR
                nombre_vend,  # 15 NOMBRE VENDEDOR
                zona,  # 16 ZONA
                categoria,  # 17 CATEGORÍA CLIENTE
                "1",  # 18 COND VENTA (fijo 1)
                str(partner.property_delivery_carrier_id.id or 1),  # 19 TRANSPORTE
                str(partner.property_payment_term_id.id or 1),  # 20 TIPO PAGO
                pago_contact.name or "",  # 21 CONTACTO PAGO
                compra_contact.email or "",  # 22 CORREO COMPRA 1
                "",  # 23 CORREO COMPRA 2 (no tenemos)
                f"{partner.credit_limit:.2f}".rstrip("0").rstrip(".")
                if partner.credit_limit
                else "0",  # 24 CRÉDITO
                compra_contact.phone or "",  # 25 TEL COMPRA
                pago_contact.phone or "",  # 26 TEL PAGO
                compra_contact.mobile or "",  # 27 CEL COMPRA
                pago_contact.mobile or "",  # 28 CEL PAGO
                partner.user_id.name or "",  # 29 REPRESENTANTE (vendedor)
                str(overdue_days) if overdue_days > 0 else "",  # 30 DÍAS DEUDA
                f"{balance:.2f}".rstrip("0").rstrip(".")
                if balance
                else "0",  # 31 SALDO
                "",  # 32 CHEQUE PROPIO
                "",  # 33 CHEQUE TERCEROS
            ]

            writer.writerow(row)

        data = output.getvalue().encode("utf-8-sig")
        self.datas = base64.b64encode(data)

        return {
            "type": "ir.actions.act_url",
            "url": f"/web/content/?model={self._name}&id={self.id}&field=datas&download=true&filename=clilis2.csv",
            "target": "self",
        }
