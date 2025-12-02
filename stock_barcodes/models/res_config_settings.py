from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    scanner_exp_date_note = fields.Boolean(
        string="Scanner note about expiration date",
        related="company_id.scanner_exp_date_note",
        readonly=False,
    )
    scanner_rem_date_note = fields.Boolean(
        string="Scanner note about removal date",
        related="company_id.scanner_rem_date_note",
        readonly=False,
    )
    scanner_bes_date_note = fields.Boolean(
        string="Scanner note about best before date",
        related="company_id.scanner_bes_date_note",
        readonly=False,
    )
