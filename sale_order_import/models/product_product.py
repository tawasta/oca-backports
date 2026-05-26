

from odoo import fields, models


class ProductProduct(models.Model):

    _inherit = "product.product"

    is_error_product = fields.Boolean()
