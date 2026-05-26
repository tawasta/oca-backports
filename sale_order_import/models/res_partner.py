
from odoo import fields, models


class ResPartner(models.Model):

    _inherit = "res.partner"

    is_error_partner = fields.Boolean()
    is_error_delivery = fields.Boolean()
    is_error_invoicing = fields.Boolean()
