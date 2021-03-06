# Copyright 2019 Ecosoft Co., Ltd. (http://ecosoft.co.th)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class StockCardView(models.TransientModel):
    _name = "stock.card.msa.view"
    _description = "Stock Card View - MSA"
    _order = "date"

    is_initial = fields.Boolean()

    date = fields.Datetime()
    product_id = fields.Many2one(comodel_name="product.product")
    product_qty = fields.Float()
    reference = fields.Char()
    location_id = fields.Many2one(comodel_name="stock.location")
    location_dest_id = fields.Many2one(comodel_name="stock.location")
    origin = fields.Char()

    price_unit = fields.Float()
    price_unit_value = fields.Float()
    picking_code = fields.Char()
    am_name = fields.Char()
    am_si_number = fields.Char()

    product_int = fields.Float()
    product_int_cost = fields.Float()
    product_int_value = fields.Float()

    product_in = fields.Float()
    product_in_cost = fields.Float()
    product_in_value = fields.Float()

    product_out = fields.Float()
    product_out_cost = fields.Float()
    product_out_value = fields.Float()


class StockCardReport(models.TransientModel):
    _name = "report.stock.card.msa.report"
    _description = "Stock Card Report MSA"

    # Filters fields, used for data computation
    date_from = fields.Date()
    date_to = fields.Date()
    product_ids = fields.Many2many(comodel_name="product.product")
    location_id = fields.Many2one(comodel_name="stock.location")

    # Data fields, used to browse report data
    results = fields.Many2many(
        comodel_name="stock.card.msa.view",
        compute="_compute_results",
        help="Use compute fields, so there is nothing store in database",
    )

    def _compute_results(self):
        self.ensure_one()
        date_from = self.date_from or "0001-01-01"
        self.date_to = self.date_to or fields.Date.context_today(self)
        self._cr.execute(
            """
            SELECT 

                move.date,
                move.product_id, 
                move.product_qty, 
                move.reference,
                move.location_id, 
                move.location_dest_id,
                move.origin,

                sml.unit_cost AS price_unit,
                sml.value AS price_unit_value, 
                spt.code AS picking_code,
                
                am.name AS am_name,
                am.x_ref_sales_invoice AS am_si_number,

                CASE WHEN spt.code IS null
                    THEN move.product_qty END AS product_int,
                CASE WHEN spt.code IS null
                    THEN sml.unit_cost END AS product_int_cost,
                CASE WHEN spt.code IS null
                    THEN sml.value END AS product_int_value,

                CASE WHEN spt.code = 'incoming'
                    THEN move.product_qty END AS product_in,
                CASE WHEN spt.code = 'incoming'
                    THEN sml.unit_cost END AS product_in_cost,
                CASE WHEN spt.code = 'incoming' 
                    THEN sml.value END AS product_in_value,

                CASE WHEN spt.code = 'outgoing'
                    THEN move.product_qty END AS product_out,
                CASE WHEN spt.code = 'outgoing' 
                    THEN aml.purchase_price END AS product_out_cost,
                CASE WHEN spt.code = 'outgoing' 
                    THEN move.product_qty*aml.purchase_price END AS product_out_value,
                CASE WHEN move.date < %s THEN True ELSE False END AS is_initial

            FROM stock_move move

            LEFT JOIN (SELECT id, code FROM stock_picking_type) AS spt ON move.picking_type_id=spt.id
            LEFT JOIN (SELECT id, price_unit FROM purchase_order_line) AS pol ON move.purchase_line_id=pol.id
            LEFT JOIN (SELECT id, name, invoice_origin, x_ref_sales_invoice, invoice_date FROM account_move) AS am ON am.invoice_origin=move.origin
            LEFT JOIN (SELECT id, move_id, product_id, purchase_price FROM account_move_line WHERE product_id IS NOT null) AS aml ON aml.move_id=am.id AND aml.product_id=move.product_id
            LEFT JOIN (SELECT unit_cost, value, stock_move_id FROM stock_valuation_layer) AS sml ON sml.stock_move_id=move.id

            WHERE move.state = 'done' and move.product_id in %s
                AND CAST(move.date AS date) <= %s
            ORDER BY move.date, move.reference
        """,
            (
                date_from,
                tuple(self.product_ids.ids),
                self.date_to,
            ),
        )
        stock_card_results = self._cr.dictfetchall()
        ReportLine = self.env["stock.card.msa.view"]
        self.results = [ReportLine.new(line).id for line in stock_card_results]

    def _get_initial(self, product_line):
        product_int_qty = sum(product_line.mapped("product_int"))
        product_input_qty = sum(product_line.mapped("product_in"))
        product_output_qty = sum(product_line.mapped("product_out"))
        return product_int_qty + product_input_qty - product_output_qty
    
    def _get_initial_cost(self, initial_value, initial):
        if initial == 0:
            initial_cost = 0
        else:
            initial_cost = initial_value / initial
        return initial_cost

    def _get_initial_value(self, product_line):
        product_int_value = sum(product_line.mapped("product_int_value"))
        product_input_value = sum(product_line.mapped("product_in_value"))
        product_output_value = sum(product_line.mapped("product_out_value"))
        return product_int_value + product_input_value - product_output_value

    

    def print_report(self, report_type="qweb"):
        self.ensure_one()
        action = (
            report_type == "xlsx"
            and self.env.ref("stock_card_report_msa.action_stock_card_report_msa_xlsx")
            or self.env.ref("stock_card_report_msa.action_stock_card_report_msa_pdf")
        )
        return action.report_action(self, config=False)

    def _get_html(self):
        result = {}
        rcontext = {}
        report = self.browse(self._context.get("active_id"))
        if report:
            rcontext["o"] = report
            result["html"] = self.env.ref(
                "stock_card_report_msa.report_stock_card_report_msa_html"
            ).render(rcontext)
        return result

    @api.model
    def get_html(self, given_context=None):
        return self.with_context(given_context)._get_html()
