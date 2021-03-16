# Copyright 2019 Ecosoft Co., Ltd. (http://ecosoft.co.th)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class StockCardView(models.TransientModel):
    _name = "stock.card.msa.view"
    _description = "Stock Card View - MSA"
    _order = "date"

    date = fields.Datetime()
    product_id = fields.Many2one(comodel_name="product.product")
    product_qty = fields.Float()
    product_uom_qty = fields.Float()
    product_uom = fields.Many2one(comodel_name="uom.uom")
    reference = fields.Char()
    location_id = fields.Many2one(comodel_name="stock.location")
    location_dest_id = fields.Many2one(comodel_name="stock.location")
    is_initial = fields.Boolean()
    product_in = fields.Float()
    product_out = fields.Float()

    date_alt = fields.Datetime()
    price_unit = fields.Float()
    price_unit_value = fields.Float()
    origin = fields.Char()
    origin_alt = fields.Char()
    reference_alt = fields.Char()
    #product_in_cost = fields.Float()
    #product_out_cost = fields.Float()
    #product_in_value = fields.Float()
    #product_out_value = fields.Float()


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
                move.product_uom,
                move.reference,
                move.product_qty,
                move.location_id, 
                move.location_dest_id,

                move.origin,
                move.price_unit,
                move.price_unit*move.product_qty AS price_unit_value, 

                CASE WHEN spt.code = 'incoming' 
                    THEN move.product_qty END AS product_in,
                CASE WHEN spt.code = 'outgoing'
                    THEN move.product_qty END AS product_out,
                CASE WHEN move.date < %s THEN True else False end as is_initial

            FROM stock_move move

            LEFT JOIN (SELECT id, code FROM stock_picking_type) AS spt ON move.picking_type_id=spt.id
            
            WHERE spt.code IN ('incoming', 'outgoing')
                and move.state = 'done' and move.product_id in %s
                and CAST(move.date AS date) <= %s
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
        product_input_qty = sum(product_line.mapped("product_in"))
        product_output_qty = sum(product_line.mapped("product_out"))
        return product_input_qty - product_output_qty

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
