# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import models


class StockQuant(models.Model):
    _inherit = "stock.quant"

    def _get_inventory_move_values(
        self,
        qty,
        location_id,
        location_dest_id,
        package_id=False,
        package_dest_id=False,
    ):
        
        vals = super()._get_inventory_move_values(
            qty, location_id, location_dest_id, package_id, package_dest_id
        )
        
        move_line_vals = vals["move_line_ids"][0][2]
        # quantity before the adjustment
        move_line_vals.update(
            {
                "inventory_theoretical_qty": self.quantity,
                "inventory_real_qty": self.inventory_quantity,
            }
        )
        return vals
