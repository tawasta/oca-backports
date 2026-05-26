
from odoo import fields, models


class ResPartner(models.Model):

    _inherit = "res.partner"

    is_error_partner = fields.Boolean(copy=False, store=True)
    is_error_delivery = fields.Boolean(copy=False, store=True)
    is_error_invoicing = fields.Boolean(copy=False, store=True)
    default_ubl_import_partner = fields.Boolean(copy=False, store=True)
