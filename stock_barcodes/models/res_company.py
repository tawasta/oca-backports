from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    scanner_exp_date_note = fields.Boolean(
        string="Scanner note about expiration date", default=False
    )
    scanner_rem_date_note = fields.Boolean(
        string="Scanner note about removal date", default=False
    )
    scanner_bes_date_note = fields.Boolean(
        string="Scanner note about best before date", default=False
    )
