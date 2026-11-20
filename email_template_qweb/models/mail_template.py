# Copyright 2016-2024 Therp BV <http://therp.nl>
# Copyright 2024 ForgeFlow S.L. (https://www.forgeflow.com)
# License LGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo import fields, models


class MailTemplate(models.Model):
    _inherit = "mail.template"

    body_type = fields.Selection(
        [("qweb", "QWeb"), ("qweb_view", "QWeb View")],
        "Body templating engine",
        default="qweb",
        required=True,
    )
    body_view_id = fields.Many2one("ir.ui.view", domain=[("type", "=", "qweb")])
    body_view_arch = fields.Text(related="body_view_id.arch")

    def _render_template(
        self,
        template_src,
        model,
        res_ids,
        engine="inline_template",
        add_context=None,
        options=None,
    ):
        """Render the view of the template instead of its body.

        Only ``body_html`` is rendered with the ``qweb`` engine on a template, so
        that is the one swapped for the ``qweb_view`` engine of core. Core then
        takes care of the language of the template, of the evaluation context and
        of the post processing of the result (absolute links), like for a body.
        """
        if (
            engine == "qweb"
            and len(self) == 1
            and self.body_type == "qweb_view"
            and self.body_view_id
        ):
            return super()._render_template(
                self.body_view_id,
                model,
                res_ids,
                engine="qweb_view",
                add_context={**(add_context or {}), "email_template": self},
                options=options,
            )
        return super()._render_template(
            template_src,
            model,
            res_ids,
            engine=engine,
            add_context=add_context,
            options=options,
        )
