from odoo import fields, models


class StockLot(models.Model):

    _inherit = "stock.lot"

    expiry_message = fields.Text()
    older_quant_message = fields.Text()
