# Copyright 2016-2017 Akretion
# @author: Alexis de Lattre <alexis.delattre@akretion.com>
# Copyright 2022 Camptocamp
# @author: Simone Orsi <simahawk@gmail.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import logging
import mimetypes
from base64 import b64decode, b64encode
import os
import shutil

from lxml import etree

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.osv.expression import AND
from odoo.tools import config, float_compare, float_is_zero

logger = logging.getLogger(__name__)


class SaleOrderImport(models.TransientModel):
    _name = "sale.order.import"
    _description = "Sale Order Import from Files"

    state = fields.Selection(
        [("import", "Import"), ("update", "Update")], default="import"
    )
    partner_id = fields.Many2one("res.partner", string="Customer")
    import_type = fields.Selection(
        [("xml", "XML"), ("pdf", "PDF")],
        required=True,
        default=None,
        help="Select a type which you want to import",
    )
    order_file = fields.Binary(
        string="Request for Quotation or Order",
        required=True,
        help="Upload a Request for Quotation or an Order file. Supported "
        "formats: XML and PDF (PDF with an embeded XML file).",
    )
    order_filename = fields.Char(string="Filename")
    doc_type = fields.Selection(
        [("rfq", "Request For Quotation"), ("order", "Sale Order")],
        string="Document Type",
        readonly=True,
    )
    price_source = fields.Selection(
        selection=[("pricelist", "Pricelist"), ("order", "Customer Order")],
        default="pricelist",
        string="Apply Prices From",
    )
    # for state = update
    commercial_partner_id = fields.Many2one(
        "res.partner", string="Commercial Entity", readonly=True
    )
    partner_shipping_id = fields.Many2one(
        "res.partner", string="Shipping Address", readonly=True
    )
    sale_id = fields.Many2one("sale.order", string="Quotation to Update")
    # Confirm order after creating Sale Order
    confirm_order = fields.Boolean(default=False)
    skip_error_lines = fields.Boolean(
        help="Ignore and push all error lines to the chatter when importing if enabled."
    )

    @api.onchange("order_file")
    def order_file_change(self):
        if not self.order_filename or not self.order_file:
            self.doc_type = False
            return

        doc_type = self._parse_file(
            self.order_filename, b64decode(self.order_file), detect_doc_type=True
        )
        if doc_type is None:
            return {"warning": self._unsupported_file_msg(self.order_filename)}
        self.doc_type = doc_type

    def _get_supported_types(self):
        # Define the supported types dictionary
        supported_types = {
            "xml": ("application/xml", "text/xml"),
            "pdf": ("application/pdf"),
        }
        return supported_types

    def _parse_file(self, filename, filecontent, detect_doc_type=False):
        assert filename, "Missing filename"
        assert filecontent, "Missing file content"
        filetype = mimetypes.guess_type(filename)
        logger.debug("Order file mimetype: %s", filetype)
        mimetype = filetype[0]
        supported_types = self._get_supported_types()
        # Check if the selected import type is supported
        if self.import_type not in supported_types:
            raise UserError(
                _("Please select a valid import type before importing!")
            )

        # Check if the detected MIME type is supported for the selected import type
        if mimetype not in supported_types[self.import_type]:
            raise UserError(
                _(
                    "This file '%(filename)s' is not recognized as a %(type)s file. "
                    "Please check the file and its extension.",
                    filename=filename,
                    type=self.import_type.upper(),
                )
            )

        if parser_method := getattr(self, f"parse_{self.import_type}_order", None):
            return parser_method(filecontent, detect_doc_type=detect_doc_type)
        else:
            logger.error(
                "%(meth)s not found %(itype)s not supported",
                meth=f"parse_{self.import_type}_order",
                itype=self.import_type,
            )
            raise UserError(
                _(
                    "This Import Type is not supported. Did you install "
                    "the module to support this type?"
                )
            )

    def _unsupported_file_msg(self, filename):
        return {
            "title": _("Unsupported file format"),
            "message": _(
                "This file '%s' is not recognised as a XML nor "
                "PDF file. Please check the file and it's "
                "extension."
            )
            % filename,
        }

    @api.model
    def _parse_xml(self, data):
        if not data:
            return None, _("No data provided")
        xml_root = None
        try:
            xml_root = etree.fromstring(data)
            error_msg = None
        except etree.XMLSyntaxError:
            error_msg = _("This XML file is not XML-compliant")
            return xml_root, error_msg
        return xml_root, error_msg

    @api.model
    def parse_xml_order(self, data, detect_doc_type=False):
        if not self.env.context.get("xml_root", False):
            xml_root, error_msg = self._parse_xml(data)
        else:
            xml_root = data
            error_msg = None
        if (xml_root is None or not len(xml_root)) and error_msg:
            raise UserError(error_msg)
        raise NotImplementedError(
            _(
                "This type of XML RFQ/order is not supported. Did you install "
                "the module to support this XML format?"
            )
        )

    @api.model
    def parse_pdf_order(self, order_file, detect_doc_type=False):
        """
        Get PDF attachments, filter on XML files and call import_order_xml
        """
        xml_files_dict = self.env["pdf.xml.tool"].pdf_get_xml_files(order_file)
        if not xml_files_dict:
            raise UserError(
                _("There are no embedded XML file in this PDF file.")
            )
        for xml_filename, xml_root in xml_files_dict.items():
            logger.info("Trying to parse XML file %s", xml_filename)
            try:
                parsed_order = self.with_context(xml_root=True).parse_xml_order(
                    xml_root, detect_doc_type=detect_doc_type
                )
                return parsed_order
            except (etree.LxmlError, UserError):
                continue
        raise UserError(
            _(
                "This type of XML RFQ/order is not supported. Did you install "
                "the module to support this XML format?"
            )
        )

    # Format of parsed_order
    # {
    # 'partner': {
    #     'vat': 'FR25499247138',
    #     'name': 'Camptocamp',
    #     'email': 'luc@camptocamp.com',
    #     },
    # 'ship_to': {
    #    'partner': partner_dict,
    #    'address': {
    #       'country_code': 'FR',
    #       'state_code': False,
    #       'zip': False,
    #       },
    # 'company': {'vat': 'FR12123456789'},  # Only used to check we are not
    #                                       # importing the order in the
    #                                       # wrong company by mistake
    # 'date': '2016-08-16',  # order date
    # 'order_ref': 'PO1242',  # Customer PO number
    # 'currency': {'iso': 'EUR', 'symbol': u'€'},
    # 'incoterm': 'EXW',
    # 'note': 'order notes of the customer',
    # 'chatter_msg': ['msg1', 'msg2']
    # 'lines': [{
    #           'product': {
    #                'code': 'EA7821',
    #                'ean13': '2100002000003',
    #                },
    #           'qty': 2.5,
    #           'uom': {'unece_code': 'C62'},
    #           'price_unit': 12.42,  # without taxes
    # 'doc_type': 'rfq' or 'order',
    #    }]

    @api.model
    def _search_existing_order_domain(
        self, parsed_order, commercial_partner, state_domain
    ):
        return AND(
            [
                state_domain,
                [
                    ("client_order_ref", "=", parsed_order["order_ref"]),
                    ("commercial_partner_id", "=", commercial_partner.id),
                ],
            ]
        )

    @api.model
    def _prepare_order(self, parsed_order, price_source):
        soo = self.env["sale.order"]
        bdio = self.env["business.document.import"]
        partner = False
        invoicing_partner = False
        shipping_partner = False

        default_ubl_partner = self.env["res.partner"].search(
            [("default_ubl_import_partner", "=", True)], limit=1
        )

        if default_ubl_partner:
            partner = default_ubl_partner
        else:
            partner = bdio._match_partner(
                parsed_order["partner"],
                parsed_order["chatter_msg"],
                partner_type="customer",
                raise_exception=False,
            )

        error_partner = False
        error_invoicing = False
        error_product = False
        error_shipping = False
        partner_error_info = False
        partner_shipping_error_info = False
        partner_invoicing_error_info = False
        product_error_info = False

        if not partner:
            error_partner = self.env['res.partner'].search([('is_error_partner', '=', True)])
            if not error_partner:
                error_partner = self.env['res.partner'].create({
                    'name': 'ERROR_CUSTOMER',
                    'is_error_partner': True,
                })
            partner = error_partner
            partner_error_info = (
                "Odoo couldn't find any {label} corresponding to the following "
                "information extracted from the business document:\n"
                "Name: {name} \n"
                "VAT number: {vat} \n"
                "Reference: {ref} \n"
                "E-mail: {email} \n"
                "Street: {street} \n"
                "Zip: {zip_code} \n"
                "Website: {website} \n"
                "State code: {state} \n"
                "Country code: {country} \n".format(
                label=parsed_order["partner"].get("type_label") or "",
                name=parsed_order["partner"].get("name") or "",
                vat=parsed_order["partner"].get("vat") or "",
                ref=parsed_order["partner"].get("ref") or "",
                email=parsed_order["partner"].get("email") or "",
                street=parsed_order["partner"].get("street") or "",
                zip_code=parsed_order["partner"].get("zip") or "",
                website=parsed_order["partner"].get("website") or "",
                state=parsed_order["partner"].get("state_code") or "",
                country=parsed_order["partner"].get("country_code") or "",
                )
            )

        currency = bdio._match_currency(
            parsed_order.get("currency"), parsed_order["chatter_msg"]
        )
        # FIXME: this should work but it's not as it breaks core price compute
        # so_vals = soo.default_get(soo._fields.keys())
        so_vals = {
            "partner_id": partner.id,
            "client_order_ref": parsed_order.get("order_ref"),
        }
        self._validate_currency(partner, currency)

        validated = self._validate_existing_orders(partner, parsed_order)
        if validated == "abort":
            return False

        so_vals = soo.play_onchanges(so_vals, ["partner_id"])
        so_vals["order_line"] = []
        if parsed_order.get("ship_to"):
            shipping_partner = bdio._match_shipping_partner(
                parsed_order["ship_to"], partner, parsed_order["chatter_msg"], raise_exception=False
            )

        parsed_shipping_partner = parsed_order.get("ship_to")

        if not shipping_partner and parsed_shipping_partner:
            country_code = parsed_shipping_partner.get('country_code', False)
            country_id = country_code and self.env['res.country'].search([("code", "=", country_code)]) or False
            if country_id:
                parsed_shipping_partner["country_id"] = country_id.id
            parsed_shipping_partner.pop('country_code', None)

            is_contact = parsed_shipping_partner.get('contact', False)
            if is_contact:
                parsed_shipping_partner["is_company"] = False
            else:
                parsed_shipping_partner["is_company"] = True
            parsed_shipping_partner.pop('contact', None)
            parsed_shipping_partner.pop('id_number', None)
            parsed_shipping_partner.pop('state_code', None)
            parsed_shipping_partner.pop('street_number', None)

            shipping_partner = self.env['res.partner'].create(parsed_shipping_partner)
            #shipping_partner = self.env['res.partner'].create(parsed_order["ship_to"])
            #error_shipping = self.env['res.partner'].search([('is_error_delivery', '=', True)])
            #if not error_shipping:
            #    error_shipping = self.env['res.partner'].create({
            #        'name': 'ERROR_SHIPPING',
            #        'is_error_delivery': True,
            #    })
            #shipping_partner = error_shipping
            #partner_shipping_error_info = (
            #    "Odoo couldn't find any {label} corresponding to the following "
            #    "information extracted from the business document:\n"
            #    "Name: {name} \n"
            #    "VAT number: {vat} \n"
            #    "Reference: {ref} \n"
            #    "E-mail: {email} \n"
            #    "Street: {street} \n"
            #    "Zip: {zip_code} \n"
            #    "Website: {website} \n"
            #    "State code: {state} \n"
            #    "Country code: {country} \n".format(
            #    label=parsed_order["ship_to"].get("type_label") or "",
            #    name=parsed_order["ship_to"].get("name") or "",
            #    vat=parsed_order["ship_to"].get("vat") or "",
            #    ref=parsed_order["ship_to"].get("ref") or "",
            #    email=parsed_order["ship_to"].get("email") or "",
            #    street=parsed_order["ship_to"].get("street") or "",
            #    zip_code=parsed_order["partner"].get("zip") or "",
            #    website=parsed_order["ship_to"].get("website") or "",
            #    state=parsed_order["ship_to"].get("state_code") or "",
            #    country=parsed_order["ship_to"].get("country_code") or "",
            #    )
            #)

        so_vals["partner_shipping_id"] = shipping_partner.id

        if parsed_order.get("delivery_detail"):
            so_vals.update(parsed_order.get("delivery_detail"))

        if parsed_order.get("invoice_to"):
            invoicing_partner = bdio._match_partner(
                parsed_order["invoice_to"], parsed_order["chatter_msg"], partner_type=""
            )
        elif parsed_order.get("invoice_to") and not invoicing_partner:
            error_invoicing = self.env['res.partner'].search([('is_error_invoicing', '=', True)])
            if not error_invoicing:
                error_invoicing = self.env['res.partner'].create({
                    'name': 'ERROR_INVOICING',
                    'is_error_invoicing': True,
                })
            invoicing_partner = error_invoicing
            partner_invoicing_error_info = (
                "Odoo couldn't find any {label} corresponding to the following "
                "information extracted from the business document:\n"
                "Name: {name} \n"
                "VAT number: {vat} \n"
                "Reference: {ref} \n"
                "E-mail: {email} \n"
                "Street: {street} \n"
                "Zip: {zip_code} \n"
                "Website: {website} \n"
                "State code: {state} \n"
                "Country code: {country} \n".format(
                label=parsed_order["invoice_to"].get("type_label") or "",
                name=parsed_order["invoice_to"].get("name") or "",
                vat=parsed_order["invoice_to"].get("vat") or "",
                ref=parsed_order["invoice_to"].get("ref") or "",
                email=parsed_order["invoice_to"].get("email") or "",
                street=parsed_order["invoice_to"].get("street") or "",
                zip_code=parsed_order["invoice_to"].get("zip") or "",
                website=parsed_order["invoice_to"].get("website") or "",
                state=parsed_order["invoice_to"].get("state_code") or "",
                country=parsed_order["invoice_to"].get("country_code") or "",
                )
            )
        else:
            invoicing_partner = partner

        so_vals["partner_invoice_id"] = invoicing_partner and invoicing_partner.id

        # Error messages of partners in case they are not found in Odoo
        so_vals["error_partner_info"] = partner_error_info
        so_vals["error_shipping_info"] = partner_shipping_error_info
        so_vals["error_invoicing_info"] = partner_invoicing_error_info
        if partner_error_info:
            so_vals["show_error_partner_info"] = True
        if partner_shipping_error_info:
            so_vals["show_error_shipping_info"] = True
        if partner_invoicing_error_info:
            so_vals["show_error_invoicing_info"] = True

        ir_config_model = self.env["ir.config_parameter"]
        if not ir_config_model.sudo().get_param(
            "sale_order_import_skip_customer_marking"
        ):
            so_vals["customer_marking"] = shipping_partner.name

        if parsed_order.get("date"):
            so_vals["date_order"] = parsed_order["date"]
        error_lines = []
        for line in parsed_order["lines"]:
            try:
                # partner=False because we don't want to use product.supplierinfo
                product = bdio._match_product_with_error(
                    line["product"], parsed_order["chatter_msg"], seller=False
                )

                if not product:
                    error_product = self.env['product.product'].search([('is_error_product', '=', True)])
                    if not error_product:
                        error_product = self.env['product.product'].create({
                            'name': 'ERROR_PRODUCT',
                            'is_error_product': True,
                        })
                    product = error_product
                    product_error_info = (
                        "Odoo couldn't find any product corresponding to the "
                        "following information extracted from the business document:\n"
                        "Barcode: {barcode}\n"
                        "Product code: {product_code}\n".format(
                        barcode=line["product"].get("barcode") or "",
                        product_code=line["product"].get("code") or "",
                        )
                    )

                uom = bdio._match_uom(
                    line.get("uom"), parsed_order["chatter_msg"], product
                )
                line_vals = self._prepare_create_order_line(
                    product, uom, so_vals, line, price_source
                )
                if product_error_info:
                    line_vals["product_error_info"] = product_error_info
                    so_vals["show_product_error_info"] = True
                so_vals["order_line"].append((0, 0, line_vals))
            except UserError as exc:
                if not self.skip_error_lines:
                    raise exc
                error_line = dict(values=line, error_msg=exc.args[0])
                error_lines.append(error_line)

        # Push to the chatter all errored lines if any
        if error_lines:
            parsed_order["error_lines"] = error_lines

        defaults = self.env.context.get("sale_order_import__default_vals", {}).get(
            "order", {}
        )
        so_vals.update(defaults)
        return so_vals

    def _validate_currency(self, partner, currency):
        if partner.property_product_pricelist.currency_id != currency:
            raise UserError(
                _(
                    "The customer '%(name)s' has a pricelist '%(pricelist)s' but the "
                    "currency of this order is '%(currency)s'.",
                    name=partner.display_name,
                    pricelist=partner.property_product_pricelist.display_name,
                    currency=currency.name,
                )
            )

    def _validate_existing_orders(self, partner, parsed_order):
        if not parsed_order.get("order_ref"):
            return
        commercial_partner = partner.commercial_partner_id
        existing_orders = self.env["sale.order"].search(
            self._search_existing_order_domain(
                parsed_order, commercial_partner, [("state", "!=", "cancel")]
            ),
            limit=1,
        )
        if existing_orders and self._context.get("ubl_import_done", False):
            msg = (_(
                    "An order of customer '%(partner)s' with reference '%(ref)s' "
                    "already exists: %(name)s (state: %(state)s)",
                    partner=partner.display_name,
                    ref=parsed_order["order_ref"],
                    name=existing_orders[0].name,
                    state=existing_orders[0].state,
                ))
            logger.info(msg)
            return "abort"
        if existing_orders:
            raise UserError(msg)

    @api.model
    def create_order(self, parsed_order, price_source, order_filename=None):
        soo = self.env["sale.order"].with_context(mail_create_nosubscribe=True)
        bdio = self.env["business.document.import"]
        so_vals = self._prepare_order(parsed_order, price_source)
        if not so_vals:
            return False
        order = soo.create(so_vals)
        bdio.post_create_or_update(parsed_order, order, doc_filename=order_filename)
        logger.info("Sale Order ID %d created", order.id)
        if self.confirm_order:
            order.action_confirm()
            logger.info("Sale Order ID %d confirmed", order.id)
        return order

    @api.model
    def create_order_ws(self, parsed_order, price_source, order_filename=None):
        """Same method as create_order() but callable via JSON-RPC
        webservice. Returns an ID to avoid this error:
        TypeError: sale.order(15,) is not JSON serializable"""
        order = self.create_order(
            parsed_order, price_source, order_filename=order_filename
        )
        return order.id

    @api.model
    def parse_order(self, order_file, order_filename, partner=False):
        parsed_order = self._parse_file(order_filename, order_file)
        logger.debug("Result of order parsing: %s", parsed_order)
        defaults = (
            ("attachments", {}),
            ("chatter_msg", []),
        )
        for key, val in defaults:
            parsed_order.setdefault(key, val)

        parsed_order["attachments"][order_filename] = b64encode(order_file)
        if (
            parsed_order.get("company")
            and not config["test_enable"]
            and not self._context.get("edi_skip_company_check")
        ):
            self.env["business.document.import"]._check_company(
                parsed_order["company"], parsed_order["chatter_msg"]
            )
        return parsed_order

    def cron_import_order_from_file(self):
        bdio = self.env["business.document.import"]

        ubl_file_path = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("order_import_ubl.path")
        )

        ubl_file_path_dest = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("order_import_ubl_destination.path")
        )

        if not ubl_file_path:
            logger.info("No directory given for UBL import")
            return

        if not os.path.exists(ubl_file_path):
            logger.info("Invalid directory given for UBL import")
            return

        import_records = self.env["sale.order.import"]

        for file_to_scan in os.scandir(ubl_file_path):
            if file_to_scan.is_file():
                with open(file_to_scan.path, "rb") as file_to_read:
                    read_file = file_to_read.read()
                    read_file = b64encode(read_file)
                    import_record = self.env["sale.order.import"].create({
                        "order_filename": file_to_scan.name,
                        "import_type": "xml",
                        "doc_type": "order",
                        "price_source": "order",
                        "confirm_order": False,
                        "state": "import",
                        "order_file": read_file,
                    })

                    import_record._context["ubl_import_done"] = True
                    import_record._context["file_to_scan_name"] = file_to_scan.name
                    import_record._context["ubl_file_path"] = ubl_file_path
                    import_record._context["ubl_file_path_dest"] = ubl_file_path_dest

                    import_record.order_file_change()
                    import_record.import_order_button()
        return

    def import_order_button(self):
        self.ensure_one()
        bdio = self.env["business.document.import"]
        order_file_decoded = b64decode(self.order_file)
        partner_shipping_error_info = False
        partner_error_info = False
        parsed_order = self.parse_order(
            order_file_decoded, self.order_filename, self.partner_id
        )
        if not parsed_order.get("lines"):
            raise UserError(_("This order doesn't have any line !"))
        partner = bdio._match_partner(
            parsed_order["partner"], [], partner_type="customer", raise_exception=False
        )

        if not partner:
            error_partner = self.env['res.partner'].search([('is_error_partner', '=', True)])
            if not error_partner:
                error_partner = self.env['res.partner'].create({
                    'name': 'ERROR_CUSTOMER',
                    'is_error_partner': True,
                })
            partner = error_partner
            partner_error_info = (
                "Odoo couldn't find any {label} corresponding to the following "
                "information extracted from the business document:\n"
                "Name: {name} \n"
                "VAT number: {vat} \n"
                "Reference: {ref} \n"
                "E-mail: {email} \n"
                "Website: {website} \n"
                "State code: {state} \n"
                "Country code: {country} \n".format(
                label=parsed_order["partner"].get("type_label") or "",
                name=parsed_order["partner"].get("name") or "",
                vat=parsed_order["partner"].get("vat") or "",
                ref=parsed_order["partner"].get("ref") or "",
                email=parsed_order["partner"].get("email") or "",
                website=parsed_order["partner"].get("website") or "",
                state=parsed_order["partner"].get("state_code") or "",
                country=parsed_order["partner"].get("country_code") or "",
                )
            )

        commercial_partner = partner.commercial_partner_id
        partner_shipping_id = False
        if parsed_order.get("ship_to"):
            partner_shipping_id = bdio._match_shipping_partner(
                parsed_order["ship_to"], partner, [], raise_exception=False
            )
            partner_shipping_id = partner_shipping_id and partner_shipping_id.id

        if not partner_shipping_id:
            error_shipping = self.env['res.partner'].search([('is_error_delivery', '=', True)])
            if not error_shipping:
                error_shipping = self.env['res.partner'].create({
                    'name': 'ERROR_SHIPPING',
                    'is_error_delivery': True,
                })
            partner_shipping_id = error_shipping
            partner_shipping_error_info = (
                "Odoo couldn't find any {label} corresponding to the following "
                "information extracted from the business document:\n"
                "Name: {name} \n"
                "VAT number: {vat} \n"
                "Reference: {ref} \n"
                "E-mail: {email} \n"
                "Website: {website} \n"
                "State code: {state} \n"
                "Country code: {country} \n".format(
                label=parsed_order["ship_to"].get("type_label") or "",
                name=parsed_order["ship_to"].get("name") or "",
                vat=parsed_order["ship_to"].get("vat") or "",
                ref=parsed_order["ship_to"].get("ref") or "",
                email=parsed_order["ship_to"].get("email") or "",
                website=parsed_order["ship_to"].get("website") or "",
                state=parsed_order["ship_to"].get("state_code") or "",
                country=parsed_order["ship_to"].get("country_code") or "",
                )
            )

        existing_quotations = self.env["sale.order"].search(
            self._search_existing_order_domain(
                parsed_order, commercial_partner, [("state", "in", ("draft", "sent"))]
            )
        )
        if existing_quotations:
            default_sale_id = False
            if len(existing_quotations) == 1:
                default_sale_id = existing_quotations[0].id
            self.write(
                {
                    "commercial_partner_id": commercial_partner.id,
                    "partner_shipping_id": partner_shipping_id,
                    "state": "update",
                    "sale_id": default_sale_id,
                    "doc_type": parsed_order.get("doc_type"),
                }
            )
            action = self.env["ir.actions.act_window"]._for_xml_id(
                "sale_order_import.sale_order_import_action"
            )
            action["res_id"] = self.id
            return action
        else:
            return self.create_order_return_action(parsed_order, self.order_filename)

    def create_order_button(self):
        self.ensure_one()
        parsed_order = self.parse_order(
            b64decode(self.order_file), self.order_filename, self.partner_id
        )
        return self.create_order_return_action(parsed_order, self.order_filename)

    def create_order_return_action(self, parsed_order, order_filename):
        self.ensure_one()
        order = self.create_order(parsed_order, self.price_source, order_filename)
        if not order:
            return False
        ctx = self._context
        if ctx.get("ubl_import_done", False):
            order.ubl_import_done = True
        file_to_scan_name, ubl_file_path, ubl_file_path_dest = (
            ctx.get("file_to_scan_name", False),
            ctx.get("ubl_file_path", False),
            ctx.get("ubl_file_path_dest", False)
        )
        if file_to_scan_name and ubl_file_path and ubl_file_path_dest:
            shutil.move(
                "{}{}".format(ubl_file_path, file_to_scan_name),
                "{}{}".format(ubl_file_path_dest, file_to_scan_name),
            )

        self._post_error_lines_message(parsed_order, order)
        order.message_post(
            body=_("Created automatically via file import (%s).")
            % self.order_filename
        )
        action = self.env["ir.actions.actions"]._for_xml_id("sale.action_quotations")
        action.update(
            {
                "view_mode": "form,list,calendar,graph",
                "views": False,
                "view_id": False,
                "res_id": order.id,
            }
        )
        return action

    # TODO: add tests
    @api.model
    def _prepare_update_order_vals(self, parsed_order, order, partner):
        bdio = self.env["business.document.import"]
        partner = bdio._match_partner(
            parsed_order["partner"],
            parsed_order["chatter_msg"],
            partner_type="customer",
        )
        vals = {"partner_id": partner.id}
        if parsed_order.get("ship_to"):
            shipping_partner = bdio._match_shipping_partner(
                parsed_order["ship_to"], partner, parsed_order["chatter_msg"]
            )
            vals["partner_shipping_id"] = shipping_partner.id
        if parsed_order.get("order_ref"):
            vals["client_order_ref"] = parsed_order["order_ref"]
        return vals

    @api.model
    def _prepare_create_order_line(
        self, product, uom, order, import_line, price_source
    ):
        """the 'order' arg can be a recordset (in case of an update of a sale order)
        or a dict (in case of the creation of a new sale order)"""
        solo = self.env["sale.order.line"]
        vals = {}
        # Ensure the company is loaded before we play onchanges.
        # Yes, `company_id` is related to `order_id.company_id`
        # but when we call `play_onchanges` it will be empty
        # w/out this precaution.
        company_id = self._prepare_order_line_get_company_id(order)
        vals.update(
            {
                "product_id": product.id,
                "product_uom_qty": import_line["qty"],
                "product_uom": uom.id,
                "company_id": company_id,
            }
        )
        assert price_source, "price_source must be defined"
        if price_source == "order":
            if "price_unit" not in import_line:
                raise UserError(
                    _(
                        "No price is defined in the file. Please double check "
                        "file or select Pricelist as the source for prices."
                    )
                )
            vals["price_unit"] = import_line["price_unit"]
        elif price_source == "pricelist":
            # product_id_change is played in the inherit of create()
            # of sale.order.line cf odoo/addons/sale/models/sale.py
            # but it is not enough: we also need to play _onchange_discount()
            # to have the right discount for pricelist
            vals["order_id"] = order
            vals = solo.play_onchanges(vals, ["product_id"])
            vals.pop("order_id")

        # Handle additional fields dynamically if available.
        # If a field is added to a record and its value is injected by a parser
        # you won't have to override `_prepare_create_order_line`
        # to let it propagate.
        for k, v in import_line.items():
            if k not in vals and k in solo._fields:
                vals[k] = v

        defaults = self.env.context.get("sale_order_import__default_vals", {}).get(
            "lines", {}
        )
        vals.update(defaults)
        return vals

    def _prepare_order_line_get_company_id(self, order):
        company_id = self.env.company.id
        if isinstance(order, models.Model):
            company_id = order.company_id.id
        elif isinstance(order, dict):
            company_id = order.get("company_id") or company_id
        return company_id

    # TODO: add tests
    @api.model
    def update_order_lines(self, parsed_order, order, price_source):
        chatter = parsed_order["chatter_msg"]
        solo = self.env["sale.order.line"]
        dpo = self.env["decimal.precision"]
        bdio = self.env["business.document.import"]
        qty_prec = dpo.precision_get("Product UoS")
        price_prec = dpo.precision_get("Product Price")
        existing_lines = []
        for oline in order.order_line:
            # compute price unit without tax
            price_unit = 0.0
            if not float_is_zero(oline.product_uom_qty, precision_digits=qty_prec):
                qty = float(oline.product_uom_qty)
                price_unit = oline.price_subtotal / qty
            existing_lines.append(
                {
                    "product": oline.product_id or False,
                    "name": oline.name,
                    "qty": oline.product_uom_qty,
                    "uom": oline.product_uom,
                    "line": oline,
                    "price_unit": price_unit,
                }
            )
        compare_res = bdio.compare_lines(
            existing_lines,
            parsed_order["lines"],
            chatter,
            qty_precision=qty_prec,
            seller=False,
        )
        # NOW, we start to write/delete/create the order lines
        for oline, cdict in compare_res["to_update"].items():
            write_vals = {}
            # TODO: add support for price_source == order
            if cdict.get("qty"):
                chatter.append(
                    _(
                        "The quantity has been updated on the order line "
                        "with product '%(product)s' from %(qty0)s to %(qty1)s %(uom)s",
                        product=oline.product_id.display_name,
                        qty0=cdict["qty"][0],
                        qty1=cdict["qty"][1],
                        uom=oline.product_uom.name,
                    )
                )
                write_vals["product_uom_qty"] = cdict["qty"][1]
                if price_source != "order":
                    new_price_unit = order.pricelist_id.with_context(
                        date=order.date_order, uom=oline.product_uom.id
                    )._price_get(
                        oline.product_id,
                        write_vals["product_uom_qty"],
                    )[order.pricelist_id.id]
                    if float_compare(
                        new_price_unit, oline.price_unit, precision_digits=price_prec
                    ):
                        chatter.append(
                            _(
                                "The unit price has been updated on the order "
                                "line with product '%(product)s' from %(old)s to "
                                "%(new)s %(currency)s",
                                product=oline.product_id.display_name,
                                old=oline.price_unit,
                                new=new_price_unit,
                                currency=order.currency_id.name,
                            )
                        )
                        write_vals["price_unit"] = new_price_unit
                write_vals.update(self._prepare_update_order_line_vals(cdict))
            if write_vals:
                oline.write(write_vals)
        if compare_res["to_remove"]:
            to_remove_label = [
                f"{line.product_uom_qty} {line.product_uom.name} "
                f"x {line.product_id.name}"
                for line in compare_res["to_remove"]
            ]
            chatter.append(
                _(
                    "%(orders)s order line(s) deleted: %(label)s",
                    orders=len(compare_res["to_remove"]),
                    label=", ".join(to_remove_label),
                )
            )
            compare_res["to_remove"].unlink()
        if compare_res["to_add"]:
            to_create_label = []
            for add in compare_res["to_add"]:
                line_vals = self._prepare_create_order_line(
                    add["product"], add["uom"], order, add["import_line"], price_source
                )
                line_vals["order_id"] = order.id
                new_line = solo.create(line_vals)
                to_create_label.append(
                    f"{new_line.product_uom_qty} {new_line.product_uom.name} "
                    f"x {new_line.name}"
                )
            chatter.append(
                _(
                    "%(orders)s new order line(s) created: %(label)s",
                    orders=len(compare_res["to_add"]),
                    label=", ".join(to_create_label),
                )
            )
        return True

    def _prepare_update_order_line_vals(self, change_dict):
        # Allows other module to update some fields on the line
        return {}

    def update_order_button(self):
        self.ensure_one()
        bdio = self.env["business.document.import"]
        order = self.sale_id
        if not order:
            raise UserError(_("You must select a quotation to update."))
        parsed_order = self.parse_order(
            b64decode(self.order_file), self.order_filename, self.partner_id
        )
        currency = bdio._match_currency(
            parsed_order.get("currency"), parsed_order["chatter_msg"]
        )
        if currency != order.currency_id:
            raise UserError(
                _(
                    "The currency of the imported order (%(old)s) is different from "
                    "the currency of the existing order (%(new)s)",
                    old=currency.name,
                    new=order.currency_id.name,
                )
            )
        vals = self._prepare_update_order_vals(
            parsed_order, order, self.commercial_partner_id
        )
        if vals:
            order.write(vals)
        self.update_order_lines(parsed_order, order, self.price_source)
        bdio.post_create_or_update(parsed_order, order)
        logger.info(
            "Quotation ID %d updated via import of file %s",
            order.id,
            self.order_filename,
        )
        order.message_post(
            body=_(
                "This quotation has been updated automatically via the import of "
                "file %s"
            )
            % self.order_filename
        )
        action = self.env["ir.actions.act_window"]._for_xml_id("sale.action_quotations")
        action.update(
            {
                "view_mode": "form,list,calendar,graph",
                "views": False,
                "view_id": False,
                "res_id": order.id,
            }
        )
        return action

    def _post_error_lines_message(self, parsed_order, order):
        order.ensure_one()
        if not self.skip_error_lines or not parsed_order.get("error_lines", False):
            return

        error_lines = parsed_order.get("error_lines")
        order.message_post_with_source(
            "sale_order_import.skip_error_lines_message",
            render_values={
                "lines": error_lines,
            },
            subtype_id=self.env.ref("mail.mt_note").id,
        )
