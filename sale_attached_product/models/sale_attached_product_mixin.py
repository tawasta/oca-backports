# Copyright 2022 Tecnativa - David Vidal
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, models


class SaleAttachedProductMixin(models.AbstractModel):
    _name = "sale.attached.product.mixin"
    _description = "Mixin class for sale attached product features"

    @api.model
    def _get_auto_refresh_attached_product_triggers(self) -> set:
        """Returns set of fields which trigger the recomputation.
        The method is overriden in the proper modules to set the proper triggers though
        """
        return set()

    def _get_recs_data(self) -> list:
        """Allows to optimize the comparison before and after the write for the
        minimum possible set of fields"""
        triggers = self._get_auto_refresh_attached_product_triggers()
        recs_data = []
        for rec in self:
            data = {}
            for dotted_field_name in triggers:
                # One value per record on the path, e.g. one unit per order line.
                # mapped() of a relational field would return a deduplicated union
                path, _sep, field_name = dotted_field_name.rpartition(".")
                records = rec.mapped(path) if path else rec
                relational = records._fields[field_name].relational
                data[dotted_field_name] = [
                    record[field_name].ids if relational else record[field_name]
                    for record in records
                ]
            recs_data.append({rec: data})
        return recs_data

    def _check_skip_attached_product_refresh(self):
        """Checks whether refresh should be skipped

        Hook method to be overridden if necessary
        :return: True if auto-refresh should be skipped
        """
        ctx = self.env.context
        return ctx.get("skip_auto_refresh_attached_product")
