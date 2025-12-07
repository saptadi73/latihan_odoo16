# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


# -------------------------------------------------------------------
#  STOCK WAREHOUSE ORDERPOINT EXTENSION
# -------------------------------------------------------------------

class StockWarehouseOrderpoint(models.Model):
    _inherit = 'stock.warehouse.orderpoint'

    dc_company_id = fields.Many2one('res.company', string='DC Company', help='Distribution Center company')
    dc_warehouse_id = fields.Many2one('stock.warehouse', string='DC Warehouse', help='Warehouse at DC')
    auto_create_dc_so = fields.Boolean('Auto Create DC SO', default=True, help='Automatically create DC Sales Order')

    @api.onchange('dc_company_id')
    def _onchange_dc_company_id(self):
        if self.dc_company_id:
            wh = self.env['stock.warehouse'].search([('company_id', '=', self.dc_company_id.id)], limit=1)
            if wh:
                self.dc_warehouse_id = wh

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            if rec.dc_company_id and not rec.dc_warehouse_id:
                wh = self.env['stock.warehouse'].search([('company_id', '=', rec.dc_company_id.id)], limit=1)
                if wh:
                    rec.dc_warehouse_id = wh
        return recs

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            if rec.dc_company_id and not rec.dc_warehouse_id:
                wh = self.env['stock.warehouse'].search([('company_id', '=', rec.dc_company_id.id)], limit=1)
                if wh:
                    rec.dc_warehouse_id = wh
        return res


# -------------------------------------------------------------------
#  PURCHASE ORDER (auto-create DC SO)
# -------------------------------------------------------------------

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    dc_sales_order_id = fields.Many2one('sale.order', string='DC Sales Order', readonly=True)
    dc_company_id = fields.Many2one('res.company', string='DC Company', readonly=True)
    is_from_reordering = fields.Boolean('From Reordering', default=False)
    retail_order_id = fields.Many2one('distribution_channel.retail_order', string='Retail Order Monitor')

    @api.model_create_multi
    def create(self, vals_list):
        orders = super().create(vals_list)
        ctx_op = self.env.context.get('orderpoint_id')

        for order in orders:
            _logger.info("\n=== PO CREATE DEBUG ===")
            _logger.info("PO: %s | Origin: %s", order.name, order.origin)
            _logger.info("Context orderpoint_id: %s", ctx_op)

            is_reordering = False
            orderpoint = False

            # 1) Context detection
            if ctx_op:
                try:
                    orderpoint = self.env['stock.warehouse.orderpoint'].browse(ctx_op)
                    if orderpoint and orderpoint.exists():
                        is_reordering = True
                        _logger.info("✓ Detected from context (orderpoint_id=%s)", ctx_op)
                except Exception as e:
                    _logger.debug("Context orderpoint browse failed: %s", e)

            # 2) Origin detection
            if not is_reordering and order.origin and 'Reordering' in (order.origin or ''):
                is_reordering = True
                _logger.info("✓ Detected from origin string")

            # 3) Fallback detection scanning order lines
            if not is_reordering:
                orderpoint = order._get_related_orderpoint()
                if orderpoint:
                    is_reordering = True
                    _logger.info("✓ Detected from _get_related_orderpoint: %s", orderpoint.name)

            if not is_reordering:
                _logger.info("✗ No orderpoint detected → skipping DC SO creation")
                continue

            if not orderpoint:
                _logger.info("✗ Reordering detected but no orderpoint found → skipping")
                continue

            if not orderpoint.dc_company_id:
                _logger.info("✗ Orderpoint %s has no DC company configured → skipping", orderpoint.name)
                continue

            # mark
            order.is_from_reordering = True
            order.dc_company_id = orderpoint.dc_company_id.id

            _logger.info("Orderpoint details: name=%s, dc_company=%s, dc_wh=%s, auto_create_dc_so=%s",
                         orderpoint.name,
                         orderpoint.dc_company_id.name if orderpoint.dc_company_id else 'N/A',
                         orderpoint.dc_warehouse_id.name if orderpoint.dc_warehouse_id else 'N/A',
                         bool(orderpoint.auto_create_dc_so))

            if orderpoint.auto_create_dc_so:
                try:
                    _logger.info("→ Creating DC SO for PO %s ...", order.name)
                    dc_so = order._create_dc_sales_order(orderpoint)
                    order.dc_sales_order_id = dc_so.id
                    _logger.info("✓ DC SO created: %s (company=%s)", dc_so.name, orderpoint.dc_company_id.name)

                    # create monitoring record
                    try:
                        ro = self.env['distribution_channel.retail_order'].create_from_po(order, dc_so, orderpoint)
                        order.retail_order_id = ro.id
                        _logger.info("✓ RetailOrder monitor created: %s", ro.name)
                    except Exception as e:
                        _logger.warning("Could not create retail_order monitor: %s", e)

                    # Auto-confirm & launch procurement (in DC context)
                    try:
                        dc_so.with_company(orderpoint.dc_company_id.id).sudo().action_confirm()
                        dc_so.order_line.with_company(orderpoint.dc_company_id.id).sudo()._action_launch_stock_rule()
                        _logger.info("✓ DC SO %s auto-confirmed & procurement launched", dc_so.name)
                    except Exception as e:
                        _logger.warning("Auto-confirm or procurement launching failed for DC SO %s: %s", dc_so.name, e)

                except Exception as e:
                    _logger.exception("Error creating DC SO for PO %s: %s", order.name, e)

        return orders

    def _get_related_orderpoint(self):
        self.ensure_one()
        OP = self.env['stock.warehouse.orderpoint']
        for line in self.order_line:
            if not line.product_id:
                continue
            op = OP.search([
                ('product_id', '=', line.product_id.id),
                ('warehouse_id', '=', self.picking_type_id.warehouse_id.id),
                ('company_id', '=', self.company_id.id),
                ('dc_company_id', '!=', False),
            ], limit=1)
            if op:
                return op
        return False

    def button_confirm(self):
        res = super().button_confirm()

        for order in self:
            if not order.dc_sales_order_id:
                continue
            dc_so = order.dc_sales_order_id
            if dc_so.state == 'draft':
                try:
                    _logger.info("→ Confirming DC SO %s in company %s", dc_so.name, order.dc_company_id.name if order.dc_company_id else 'N/A')
                    dc_so.with_company(order.dc_company_id.id).sudo().action_confirm()
                    try:
                        dc_so.order_line.with_company(order.dc_company_id.id).sudo()._action_launch_stock_rule()
                        _logger.info("✓ Procurement launched for DC SO %s", dc_so.name)
                    except Exception as e:
                        _logger.warning("Procurement launching failed for DC SO %s: %s", dc_so.name, e)
                except Exception as e:
                    _logger.exception("Error confirming DC SO %s: %s", dc_so.name, e)

        return res

    def _create_dc_sales_order(self, orderpoint):
        self.ensure_one()
        if not orderpoint.dc_company_id:
            raise ValidationError(_("DC Company not configured on Orderpoint %s") % (orderpoint.name,))

        dc_company = orderpoint.dc_company_id
        retailer_partner = self.company_id.partner_id or False

        so_vals = {
            'partner_id': retailer_partner.id if retailer_partner else False,
            'company_id': dc_company.id,
            'warehouse_id': orderpoint.dc_warehouse_id.id if orderpoint.dc_warehouse_id else False,
            'origin': _("Auto from %s") % (self.name,),
            'client_order_ref': self.name,
            'note': _("Auto-created from Retailer PO: %s\nOrderpoint: %s") % (self.name, orderpoint.name),
        }

        so = self.env['sale.order'].with_company(dc_company.id).sudo().create(so_vals)

        for pl in self.order_line:
            # create sale order lines with product mapped to DC company if possible
            product_in_dc = pl.product_id.with_company(dc_company.id) if pl.product_id else False
            sol_vals = {
                'order_id': so.id,
                'product_id': product_in_dc.id if product_in_dc else (pl.product_id.id if pl.product_id else False),
                'product_uom_qty': pl.product_qty,
                'product_uom': pl.product_uom.id if pl.product_uom else False,
                'price_unit': product_in_dc.list_price if product_in_dc else (pl.product_id.list_price if pl.product_id else 0.0),
                'name': product_in_dc.display_name if product_in_dc else (pl.product_id.display_name if pl.product_id else ''),
                'company_id': dc_company.id,
            }
            self.env['sale.order.line'].with_company(dc_company.id).sudo().create(sol_vals)

        so.sudo().write({'is_auto_created': True})
        return so

    # UI action to open related DC SO (used by some views)
    def action_open_dc_so(self):
        self.ensure_one()
        if not self.dc_sales_order_id:
            return False
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'res_id': self.dc_sales_order_id.id,
            'view_mode': 'form,tree',
            'target': 'current',
            'context': {'default_company_id': self.dc_company_id.id} if self.dc_company_id else {},
        }


# -------------------------------------------------------------------
#  SALE ORDER extension (light)
# -------------------------------------------------------------------

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    retailer_po_id = fields.Many2one('purchase.order', string='Retailer PO')
    is_auto_created = fields.Boolean('Auto Created', default=False)
    dc_purchase_order_id = fields.Many2one('purchase.order', string='DC Purchase Order')
    retail_order_id = fields.Many2one('distribution_channel.retail_order', string='Retail Order Monitor')

    def action_open_retailer_po(self):
        """Open the related Retailer PO from a DC SO (if linked)"""
        self.ensure_one()
        if not self.retailer_po_id:
            return False
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order',
            'res_id': self.retailer_po_id.id,
            'view_mode': 'form,tree',
            'target': 'current',
        }


# -------------------------------------------------------------------
#  Retail Order Monitoring (full features)
# -------------------------------------------------------------------

class RetailOrder(models.Model):
    _name = 'distribution_channel.retail_order'
    _description = 'Retail Order Monitoring & Tracking'
    _order = 'create_date desc'

    # Basic reference
    name = fields.Char('Reference', required=True, default='New')

    # Companies
    retailer_company_id = fields.Many2one('res.company', string='Retailer', required=True)
    dc_company_id = fields.Many2one('res.company', string='DC', required=True)

    # Chain links
    retailer_po_id = fields.Many2one('purchase.order', string='Retailer PO')
    dc_sales_order_id = fields.Many2one('sale.order', string='DC Sales Order')
    dc_purchase_order_id = fields.Many2one('purchase.order', string='DC Purchase Order')
    retailer_sales_order_id = fields.Many2one('sale.order', string='Retailer Sales Order')

    orderpoint_id = fields.Many2one('stock.warehouse.orderpoint', string='Orderpoint')

    # Status & tracking fields (restored full)
    retailer_po_status = fields.Selection([
        ('draft', 'Draft'), ('sent', 'Sent'), ('purchase', 'Purchase'), ('done', 'Done'), ('cancel', 'Cancelled')
    ], string='Retailer PO Status', compute='_compute_retailer_po_status', store=True)

    dc_so_status = fields.Selection([
        ('draft', 'Draft'), ('sent', 'Sent'), ('sale', 'Sale'), ('done', 'Done'), ('cancel', 'Cancelled')
    ], string='DC SO Status', compute='_compute_dc_so_status', store=True)

    dc_so_delivery_status = fields.Selection([
        ('not_started', 'Not Started'), ('picking', 'Picking'), ('picked', 'Picked'),
        ('shipped', 'Shipped'), ('received', 'Received')
    ], string='DC SO Delivery', compute='_compute_dc_so_delivery_status', store=True)

    dc_po_status = fields.Selection([
        ('draft', 'Draft'), ('sent', 'Sent'), ('purchase', 'Purchase'), ('done', 'Done'), ('cancel', 'Cancelled')
    ], string='DC PO Status', compute='_compute_dc_po_status', store=True)

    retailer_so_status = fields.Selection([
        ('draft', 'Draft'), ('sent', 'Sent'), ('sale', 'Sale'), ('done', 'Done'), ('cancel', 'Cancelled')
    ], string='Retailer SO Status', compute='_compute_retailer_so_status', store=True)

    order_chain_status = fields.Selection([
        ('complete', 'Complete Chain'), ('partial', 'Partial Chain'),
        ('missing', 'Missing Links'), ('error', 'Mismatch/Error')
    ], string='Chain Status', compute='_compute_chain_status', store=True)

    missing_links = fields.Text('Missing Links', compute='_compute_chain_status', store=True)

    # Totals & amounts
    total_qty = fields.Float('Total Quantity', compute='_compute_totals', store=True)
    total_amount = fields.Float('Total Amount', compute='_compute_totals', store=True)

    retailer_po_amount = fields.Float('Retailer PO Amount', compute='_compute_amounts', store=True)
    dc_so_amount = fields.Float('DC SO Amount', compute='_compute_amounts', store=True)
    dc_po_amount = fields.Float('DC PO Amount', compute='_compute_amounts', store=True)
    retailer_so_amount = fields.Float('Retailer SO Amount', compute='_compute_amounts', store=True)

    # Dates
    retailer_po_date = fields.Datetime('Retailer PO Date', compute='_compute_dates', store=True)
    dc_so_date = fields.Datetime('DC SO Date', compute='_compute_dates', store=True)
    dc_so_delivery_date = fields.Datetime('DC SO Delivery Date', compute='_compute_delivery_dates', store=True)
    dc_po_date = fields.Datetime('DC PO Date', compute='_compute_dates', store=True)
    retailer_so_date = fields.Datetime('Retailer SO Date', compute='_compute_dates', store=True)

    notes = fields.Text('Notes')

    state = fields.Selection([
        ('draft', 'Draft'),
        ('dc_so_created', 'DC SO Created'),
        ('dc_po_created', 'DC PO Created'),
        ('complete', 'Complete'),
    ], string='Status', compute='_compute_state', store=True, readonly=True, default='draft')

    # -------------------------
    # COMPUTE METHODS
    # -------------------------

    @api.depends('retailer_po_id.state', 'dc_sales_order_id.state', 'dc_purchase_order_id.state', 'retailer_sales_order_id.state')
    def _compute_state(self):
        """Auto-compute state based on document progression"""
        for rec in self:
            if rec.retailer_sales_order_id and rec.retailer_sales_order_id.state == 'sale':
                rec.state = 'complete'
            elif rec.dc_purchase_order_id:
                rec.state = 'dc_po_created'
            elif rec.dc_sales_order_id:
                rec.state = 'dc_so_created'
            else:
                rec.state = 'draft'

    @api.depends('retailer_po_id.state')
    def _compute_retailer_po_status(self):
        for r in self:
            r.retailer_po_status = r.retailer_po_id.state if r.retailer_po_id else False

    @api.depends('dc_sales_order_id.state')
    def _compute_dc_so_status(self):
        for r in self:
            r.dc_so_status = r.dc_sales_order_id.state if r.dc_sales_order_id else False

    @api.depends('dc_sales_order_id.picking_ids.state')
    def _compute_dc_so_delivery_status(self):
        for r in self:
            if not r.dc_sales_order_id:
                r.dc_so_delivery_status = 'not_started'
            else:
                pickings = r.dc_sales_order_id.picking_ids.filtered(lambda p: p.picking_type_id.code == 'outgoing')
                if not pickings:
                    r.dc_so_delivery_status = 'not_started'
                elif all(p.state == 'done' for p in pickings):
                    r.dc_so_delivery_status = 'shipped'
                elif any(p.state == 'done' for p in pickings):
                    r.dc_so_delivery_status = 'picked'
                elif any(p.state in ('assigned', 'partially_available') for p in pickings):
                    r.dc_so_delivery_status = 'picking'
                else:
                    r.dc_so_delivery_status = 'not_started'

    @api.depends('dc_purchase_order_id.state')
    def _compute_dc_po_status(self):
        for r in self:
            r.dc_po_status = r.dc_purchase_order_id.state if r.dc_purchase_order_id else False

    @api.depends('retailer_sales_order_id.state')
    def _compute_retailer_so_status(self):
        for r in self:
            r.retailer_so_status = r.retailer_sales_order_id.state if r.retailer_sales_order_id else False

    @api.depends('retailer_po_id.order_line.product_qty', 'dc_sales_order_id.order_line.product_uom_qty')
    def _compute_totals(self):
        for r in self:
            if r.retailer_po_id:
                r.total_qty = sum(r.retailer_po_id.order_line.mapped('product_qty'))
                r.total_amount = r.retailer_po_id.amount_total
            elif r.dc_sales_order_id:
                r.total_qty = sum(r.dc_sales_order_id.order_line.mapped('product_uom_qty'))
                r.total_amount = r.dc_sales_order_id.amount_total
            else:
                r.total_qty = 0.0
                r.total_amount = 0.0

    @api.depends(
        'retailer_po_id.amount_total',
        'dc_sales_order_id.amount_total',
        'dc_purchase_order_id.amount_total',
        'retailer_sales_order_id.amount_total'
    )
    def _compute_amounts(self):
        for r in self:
            r.retailer_po_amount = r.retailer_po_id.amount_total if r.retailer_po_id else 0.0
            r.dc_so_amount = r.dc_sales_order_id.amount_total if r.dc_sales_order_id else 0.0
            r.dc_po_amount = r.dc_purchase_order_id.amount_total if r.dc_purchase_order_id else 0.0
            r.retailer_so_amount = r.retailer_sales_order_id.amount_total if r.retailer_sales_order_id else 0.0

    @api.depends('retailer_po_id.create_date', 'dc_sales_order_id.create_date',
                 'dc_purchase_order_id.create_date', 'retailer_sales_order_id.create_date')
    def _compute_dates(self):
        for r in self:
            r.retailer_po_date = r.retailer_po_id.create_date if r.retailer_po_id else False
            r.dc_so_date = r.dc_sales_order_id.create_date if r.dc_sales_order_id else False
            r.dc_po_date = r.dc_purchase_order_id.create_date if r.dc_purchase_order_id else False
            r.retailer_so_date = r.retailer_sales_order_id.create_date if r.retailer_sales_order_id else False

    @api.depends('dc_sales_order_id.picking_ids.state')
    def _compute_delivery_dates(self):
        for r in self:
            if r.dc_sales_order_id:
                done_pickings = r.dc_sales_order_id.picking_ids.filtered(lambda p: p.state == 'done')
                if done_pickings:
                    r.dc_so_delivery_date = max(done_pickings.mapped('date_done'))
                else:
                    r.dc_so_delivery_date = False
            else:
                r.dc_so_delivery_date = False

    @api.depends('retailer_po_id', 'dc_sales_order_id', 'dc_purchase_order_id', 'retailer_sales_order_id')
    def _compute_chain_status(self):
        for r in self:
            missing = []
            if not r.retailer_po_id:
                missing.append('Retailer PO')
            if not r.dc_sales_order_id:
                missing.append('DC SO')
            if not r.dc_purchase_order_id:
                missing.append('DC PO')
            if not r.retailer_sales_order_id:
                missing.append('Retailer SO')

            if not missing:
                r.order_chain_status = 'complete'
                r.missing_links = ''
            elif len(missing) == 4:
                r.order_chain_status = 'missing'
                r.missing_links = 'All links missing'
            else:
                r.order_chain_status = 'partial'
                r.missing_links = ', '.join(missing)

    # -------------------------
    # CREATE & ACTION HELPERS
    # -------------------------

    @api.model
    def create(self, vals):
        if not vals.get('name') or vals.get('name') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('distribution_channel.retail_order') or 'RO/000'
        return super().create(vals)

    @api.model
    def create_from_po(self, purchase_order, sales_order, orderpoint):
        vals = {
            'name': f'RO/{purchase_order.name}',
            'retailer_company_id': purchase_order.company_id.id,
            'dc_company_id': sales_order.company_id.id if sales_order else False,
            'retailer_po_id': purchase_order.id,
            'dc_sales_order_id': sales_order.id if sales_order else False,
            'orderpoint_id': orderpoint.id if orderpoint else False,
            'state': 'dc_so_created' if sales_order else 'draft',
            'notes': _('Auto-created from reordering rule')
        }
        return self.create(vals)

    # UI action helpers
    def action_open_retailer_po(self):
        self.ensure_one()
        if not self.retailer_po_id:
            return False
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order',
            'res_id': self.retailer_po_id.id,
            'view_mode': 'form,tree',
            'target': 'current',
        }

    def action_open_dc_so(self):
        self.ensure_one()
        if not self.dc_sales_order_id:
            return False
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'res_id': self.dc_sales_order_id.id,
            'view_mode': 'form,tree',
            'target': 'current',
        }

    def action_open_dc_po(self):
        self.ensure_one()
        if not self.dc_purchase_order_id:
            return False
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order',
            'res_id': self.dc_purchase_order_id.id,
            'view_mode': 'form,tree',
            'target': 'current',
        }

    def action_open_retailer_so(self):
        self.ensure_one()
        if not self.retailer_sales_order_id:
            return False
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'res_id': self.retailer_sales_order_id.id,
            'view_mode': 'form,tree',
            'target': 'current',
        }
