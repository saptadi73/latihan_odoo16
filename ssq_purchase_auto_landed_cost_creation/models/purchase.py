from odoo import models, fields, api, _
from odoo.exceptions import UserError


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    landed_cost_lines = fields.One2many("purchase.landed.cost.line", "purchase_id", "Landed Costs")
    landed_costs_ids = fields.Many2many("stock.landed.cost")

    def action_view_landed_costs(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("stock_landed_costs.action_stock_landed_cost")
        domain = [("id", "in", self.landed_costs_ids.ids)]
        context = dict(self.env.context, default_purchase_id=self.id)
        views = [
            (self.env.ref("ssq_purchase_auto_landed_cost_creation.view_stock_landed_cost_tree").id, "tree"),
            (False, "form"),
            (False, "kanban"),
        ]
        return dict(action, domain=domain, context=context, views=views)


class PurchaseLandedCost(models.Model):
    _name = "purchase.landed.cost.line"

    name = fields.Char("Description")
    product_id = fields.Many2one("product.product", "Product", domain=[("landed_cost_ok", "=", True)], required=True)
    account_id = fields.Many2one("account.account", "Account")
    split_method = fields.Selection(
        [
            ("equal", "Equal"),
            ("by_quantity", "By Quantity"),
            ("by_current_cost_price", "By Current Cost"),
            ("by_weight", "By Weight"),
            ("by_volume", "By Volume"),
        ],
        "Split Method",
        default="equal",
        required=True,
    )
    price_unit = fields.Float("Cost")
    purchase_id = fields.Many2one("purchase.order")
    is_landed_cost_created = fields.Boolean(default=False)

    def unlink(self):
        for record in self:
            if record.is_landed_cost_created:
                raise UserError(_("You cannot delete a posted landed cost entry !!!"))
        return super(PurchaseLandedCost, self).unlink()

    @api.onchange("product_id")
    def onchange_product_id(self):
        self.name = self.product_id.name
        self.account_id = (
            self.product_id.property_account_expense_id.id
            or self.product_id.categ_id.property_account_expense_categ_id.id
        )
