# Copyright 2022 Camptocamp SA (https://www.camptocamp.com).
# @author Iván Todorovich <ivan.todorovich@camptocamp.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class MailTemplate(models.Model):
    _inherit = "mail.template"

    force_email_layout_id = fields.Many2one(
        comodel_name="ir.ui.view",
        string="Force Layout",
        domain=[("type", "=", "qweb"), ("mode", "=", "primary")],
        context={"default_type": "qweb"},
        help="Force a mail layout for this template.",
    )

    email_layout_xmlid = fields.Char(
        compute="_compute_email_layout_id", store=True, readonly=False
    )

    def _compute_email_layout_id(self):
        for template in self:
            if template.force_email_layout_id:
                template.email_layout_xmlid = template.force_email_layout_id.xml_id
