
from odoo import _, models


class StockInventoryAdjustmentName(models.TransientModel):
    _inherit = 'stock.inventory.adjustment.name'

    def action_apply(self):
        res = super().action_apply()

        context = self.env.context

        if not res and context.get("inventory_change_with_barcode"):
            return {
                "type": "ir.actions.act_multi", "actions": [
                    {'type': 'ir.actions.client', 'tag': 'stock_barcodes_main_menu'},
                    {'type': 'ir.actions.client', 'tag': 'display_notification',
                        'params': {
                            'type': 'success',
                            'message': _("The inventory adjustment has been validated"),
                        }
                    }
                ]
            }
        else:
            return res

