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
        vat = (vat or "").replace("-", "").replace(" ", "")
        if len(vat) == 11 and vat.isdigit():
            return f"{vat[:2]}-{vat[2:10]}-{vat[10:]}"
        return vat

    def _safe_property_id(self, prop):
        return prop.id if prop else 1

    def generate_csv(self):
        output = io.StringIO()
        writer = csv.writer(output, delimiter="|", quoting=csv.QUOTE_MINIMAL)

        for partner in self.partner_ids:
            # Contactos secundarios
            compra_contact = partner.child_ids.filtered(lambda c: c.function and "compra" in c.function.lower())[:1] or partner
            pago_contact = partner.child_ids.filtered(lambda c: c.type == "invoice" or (c.function and "pago" in c.function.lower()))[:1] or partner

            # Saldo abierto
            open_moves = self.env["account.move"].search([
                ("partner_id", "=", partner.id),
                ("move_type", "in", ("out_invoice", "out_refund")),
                ("state", "=", "posted"),
                ("payment_state", "not in", ("paid", "reversed")),
            ])
            balance = sum(open_moves.mapped("amount_residual_signed"))

            # Días de deuda máximo
            overdue_days = 0
            today = fields.Date.context_today(self)
            for move in open_moves.filtered(lambda m: m.invoice_date_due and m.invoice_date_due < today):
                days = (today - move.invoice_date_due).days
                if days > overdue_days:
                    overdue_days = days

            # Split apellido / nombre vendedor
            apellido_vend = ""
            nombre_vend = ""
            if partner.user_id and partner.user_id.name and (
                ", " in partner.user_id.name
                and (parts := partner.user_id.name.split(", ", 1)) or (parts := [partner.user_id.name])
            )
            if partner.user_id and partner.user_id.name:
                if ", " in partner.user_id.name:
                    parts = partner.user_id.name.split(", ", 1)
                    apellido_vend = parts[0]
                    nombre_vend = parts[1] if len(parts) > 1 else ""
                else:
                    parts = partner.user_id.name.split()
                    apellido_vend = " ".join(parts[:-1]) if len(parts) > 1 else parts[0]
                    nombre_vend = parts[-1] if len(parts) > 1 else ""

            # Tags para zona y categoría
            tags_sorted = partner.category_id.sorted("id")
            zona = str(tags_sorted[0].id if tags_sorted else 1)
            categoria = str(tags_sorted[1].id if len(tags_sorted) > 1 else (tags_sorted[0].id if tags_sorted else 1))

            # Crédito y saldo sin .00 si es entero
            def fmt_amount(amount):
                if not amount:
                    return "0"
                s = f"{amount:.2f}"
                return s.rstrip("0").rstrip(".") if "." in s else s

            row = [
                partner.ref or str(partner.id),                                      # 1
                partner.name or "",                                                   # 2
                partner.commercial_company_name or "",                               # 3
                self._format_cuit(partner.vat),                                       # 4
                partner.street or "",                                                 # 5
                partner.street2 or "",                                                # 6
                compra_contact.name or "",                                            # 7
                pago_contact.email or "",                                             # 8
                partner.city or "",                                                   # 9
                partner.state_id.name or "",                                          # 10
                partner.zip or "",                                                    # 11
                str(self._safe_property_id(partner.property_product_pricelist)),      # 12
                str(partner.user_id.id or ""),                                        # 13
                apellido_vend,                                                        # 14
                nombre_vend,                                                          # 15
                zona,                                                                 # 16
                categoria,                                                            # 17
                "1",                                                                  # 18
                str(self._safe_property_id(partner.property_delivery_carrier_id)),    # 19
                str(self._safe_property_id(partner.property_payment_term_id)),       # 20
                pago_contact.name or "",                                              # 21
                compra_contact.email or "",                                           # 22
                "",                                                                  # 23
                fmt_amount(partner.credit_limit),                                     # 24
                compra_contact.phone or "",                                           # 25
                pago_contact.phone or "",                                             # 26
                compra_contact.mobile or "",                                          # 27
                pago_contact.mobile or "",                                            # 28
                partner.user_id.name or "",                                           # 29
                str(overdue_days) if overdue_days > 0 else "",                          # 30
                fmt_amount(balance),                                                  # 31
                "",                                                                  # 32
                "",                                                                  # 33
            ]

            writer.writerow(row)

        data = output.getvalue().encode("utf-8-sig")
        self.datas = base64.b64encode(data)

        return {
            "type": "ir.actions.act_url",
            "url": f"/web/content/?model={self._name}&id={self.id}&field=datas&download=true&filename=clilis2.csv",
            "target": "self",
        }