# © 2016-2017 Akretion (Alexis de Lattre <alexis.delattre@akretion.com>)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models, _


class SaleOrder(models.Model):
    _inherit = "sale.order"

    ubl_import_done = fields.Boolean(default=False, copy=False)
    has_error_info = fields.Boolean(copy=False)
    show_errors_are_fixed_button = fields.Boolean(copy=False)
    error_partner_info = fields.Text(copy=False)
    error_invoicing_info = fields.Text(copy=False)
    error_shipping_info = fields.Text(copy=False)
    show_error_partner_info = fields.Boolean(copy=False)
    show_error_invoicing_info = fields.Boolean(copy=False)
    show_error_shipping_info = fields.Boolean(copy=False)
    show_product_error_info = fields.Boolean(copy=False)

    @api.depends_context("sale_order_show_amount")
    def _compute_display_name(self):
        if not self.env.context.get("sale_order_show_amount"):
            return super()._compute_display_name()
        for order in self:
            # TODO: find a python method to easily display a float + currency
            # symbol (before or after) depending on lang of context and currency
            order.display_name = order.name + _(
                " Amount w/o tax: %(amount)s %(currency)s",
                amount=order.amount_untaxed,
                currency=order.currency_id.name,
            )

    def errors_are_fixed(self):
        self.show_error_partner_info = False
        self.show_error_invoicing_info = False
        self.show_error_shipping_info = False
        self.show_product_error_info = False
        self.has_error_info = True
        self.show_errors_are_fixed_button = False

    def show_error_info(self):
        self.show_error_partner_info = self.error_partner_info and True or False
        self.show_error_invoicing_info = self.error_invoicing_info and True or False
        self.show_error_shipping_info = self.error_shipping_info and True or False

        has_error_product = False
        for line in self.order_line:
            if line.product_id and line.product_id.is_error_product:
                has_error_product = True
        self.show_product_error_info = has_error_product

        self.has_error_info = False
        self.show_errors_are_fixed_button = True
