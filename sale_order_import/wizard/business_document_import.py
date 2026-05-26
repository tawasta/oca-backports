import logging
from urllib.parse import urlparse

from odoo import _, api, models
from odoo.exceptions import UserError
from odoo.osv import expression
from odoo.tools import float_compare

from odoo.addons.base_iban.models.res_partner_bank import validate_iban

logger = logging.getLogger(__name__)


class BusinessDocumentImport(models.AbstractModel):
    _inherit = "business.document.import"

    @api.model
    def _match_product_with_error(self, product_dict, chatter_msg, seller=False):
        """Retrieve product.

        Matching sequence:

        1. ID
        2. barcode
        3. packaging barcode
        4. default_code
        5. seller code

        :param product_dict: dictionary w/ product info.

            Example: {'barcode': '5449000054227', 'code': 'COCA1L'}

        :param chatter_msg: list of msgs to append to chatter (if any)
        :param seller: optional product.supplierinfo record

        PLEASE NOTE: Original _match_product -method has been modified to
        return its error message!
        """
        ppo = self.env["product.product"]
        self._strip_cleanup_dict(product_dict)
        product = self._direct_match(product_dict, ppo)
        if product:
            return product
        product = self._match_product_search(product_dict)
        if product:
            return product
        elif seller:
            # WARNING: Won't work for multi-variant products
            # because product.supplierinfo is attached to product template
            sinfo = self.env["product.supplierinfo"].search(
                self._match_company_domain()
                + [
                    ("partner_id", "=", seller.id),
                    ("product_code", "=", product_dict["code"]),
                ],
                limit=1,
            )
            if (
                sinfo
                and sinfo.product_tmpl_id.product_variant_ids
                and len(sinfo.product_tmpl_id.product_variant_ids) == 1
            ):
                return sinfo.product_tmpl_id.product_variant_ids[0]
        else:
            return False
