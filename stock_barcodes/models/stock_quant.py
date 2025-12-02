# Copyright 2023 Tecnativa - Sergio Teruel
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from odoo import api, fields, models

MODEL_UPDATE_INVENTORY = ["wiz.stock.barcodes.read.inventory"]


class StockQuant(models.Model):
    _name = "stock.quant"
    _inherit = ["stock.quant", "barcodes.barcode_events_mixin"]

    remove_quantity = fields.Integer(default=0)
    expiry_message = fields.Text(related="lot_id.expiry_message")
    older_quant_message = fields.Text(related="lot_id.older_quant_message")
    add_move_quantities = fields.Boolean(default=False)

    def action_barcode_inventory_quant_unlink(self):
        self.with_context(inventory_mode=True).action_clear_inventory_quantity()
        context = dict(self.env.context)
        params = context.get("params", {})
        res_model = params.get("model", False)
        res_id = params.get("id", False)
        if res_id and res_model in MODEL_UPDATE_INVENTORY:
            wiz_id = self.env[params["model"]].browse(params["id"])
            wiz_id._compute_count_inventory_quants()
            wiz_id.send_bus_done(
                "stock_barcodes_form_update",
                "count_apply_inventory",
                {"count": wiz_id.count_inventory_quants},
            )

    def _get_fields_to_edit(self):
        return [
            "location_id",
            "product_id",
            "product_uom_id",
            "lot_id",
            "package_id",
        ]

    def action_barcode_inventory_quant_edit(self):
        wiz_barcode_id = self.env.context.get("wiz_barcode_id", False)
        wiz_barcode = self.env["wiz.stock.barcodes.read.inventory"].browse(
            wiz_barcode_id
        )
        for quant in self:
            # Try to assign fields with the same name between quant and the scan wizard
            for fname in self._get_fields_to_edit():
                wiz_barcode[fname] = quant[fname]
            wiz_barcode.product_qty = quant.inventory_quantity

        wiz_barcode.manual_entry = True
        self.send_bus_done(
            "stock_barcodes_scan",
            "stock_barcodes_edit_manual",
            {
                "manual_entry": True,
            },
        )

    def enable_current_operations(self):
        self.send_bus_done(
            "stock_barcodes_kanban_update",
            "enable_operations",
            {
                "id": self.id,
            },
        )

    def append_quantity_0(self):
        str_qty = int(self.inventory_quantity // 1)
        decimal = self.inventory_quantity % 1
        append_qty = float("".join([str(num) for num in ([str_qty] + [0])]))
        append_qty += decimal
        self.write({"inventory_quantity": append_qty})
        self.enable_current_operations()

    def append_quantity_1(self):
        str_qty = int(self.inventory_quantity // 1)
        decimal = self.inventory_quantity % 1
        append_qty = float("".join([str(num) for num in ([str_qty] + [1])]))
        append_qty += decimal
        self.write({"inventory_quantity": append_qty})
        self.enable_current_operations()

    def append_quantity_2(self):
        str_qty = int(self.inventory_quantity // 1)
        decimal = self.inventory_quantity % 1
        append_qty = float("".join([str(num) for num in ([str_qty] + [2])]))
        append_qty += decimal
        self.write({"inventory_quantity": append_qty})
        self.enable_current_operations()

    def append_quantity_3(self):
        str_qty = int(self.inventory_quantity // 1)
        decimal = self.inventory_quantity % 1
        append_qty = float("".join([str(num) for num in ([str_qty] + [3])]))
        append_qty += decimal
        self.write({"inventory_quantity": append_qty})
        self.enable_current_operations()

    def append_quantity_4(self):
        str_qty = int(self.inventory_quantity // 1)
        decimal = self.inventory_quantity % 1
        append_qty = float("".join([str(num) for num in ([str_qty] + [4])]))
        append_qty += decimal
        self.write({"inventory_quantity": append_qty})
        self.enable_current_operations()

    def append_quantity_5(self):
        str_qty = int(self.inventory_quantity // 1)
        decimal = self.inventory_quantity % 1
        append_qty = float("".join([str(num) for num in ([str_qty] + [5])]))
        append_qty += decimal
        self.write({"inventory_quantity": append_qty})
        self.enable_current_operations()

    def append_quantity_6(self):
        str_qty = int(self.inventory_quantity // 1)
        decimal = self.inventory_quantity % 1
        append_qty = float("".join([str(num) for num in ([str_qty] + [6])]))
        append_qty += decimal
        self.write({"inventory_quantity": append_qty})
        self.enable_current_operations()

    def append_quantity_7(self):
        str_qty = int(self.inventory_quantity // 1)
        decimal = self.inventory_quantity % 1
        append_qty = float("".join([str(num) for num in ([str_qty] + [7])]))
        append_qty += decimal
        self.write({"inventory_quantity": append_qty})
        self.enable_current_operations()

    def append_quantity_8(self):
        str_qty = int(self.inventory_quantity // 1)
        decimal = self.inventory_quantity % 1
        append_qty = float("".join([str(num) for num in ([str_qty] + [8])]))
        append_qty += decimal
        self.write({"inventory_quantity": append_qty})
        self.enable_current_operations()

    def append_quantity_9(self):
        str_qty = int(self.inventory_quantity // 1)
        decimal = self.inventory_quantity % 1
        append_qty = float("".join([str(num) for num in ([str_qty] + [9])]))
        append_qty += decimal
        self.write({"inventory_quantity": append_qty})
        self.enable_current_operations()

    def null_quantity(self):
        self.write({"inventory_quantity": 0})
        self.enable_current_operations()

    def operation_quantities_decrease(self):
        self.write({"remove_quantity": self.remove_quantity - 1})
        self.write({"inventory_quantity": self.remove_quantity})
        self.enable_current_operations()

    def operation_quantities_rest(self):
        self.write({"inventory_quantity": self.inventory_quantity - 1})
        self.enable_current_operations()

    def operation_quantities(self):
        self.write({"inventory_quantity": self.inventory_quantity + 1})
        self.enable_current_operations()

    def action_apply_inventory(self):
        res = super().action_apply_inventory()
        self.send_bus_done(
            "stock_barcodes_scan",
            "actions_barcode",
            {"apply_inventory": True},
        )

        for quant in self:
            quant.remove_quantity = quant.quantity
            quant.add_move_quantities = False
        return res

    @api.onchange("inventory_quantity_auto_apply")
    def onchange_auto_apply_quantity(self):
        self.remove_quantity = self.inventory_quantity_auto_apply

    @api.model
    def _get_forbidden_fields_write(self):
        res = super()._get_forbidden_fields_write()
        if self.env.context.get("allow_edit_owner"):
            res.remove("owner_id")
        return res
