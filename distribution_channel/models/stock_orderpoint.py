# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class StockWarehouseOrderpoint(models.Model):
    _inherit = 'stock.warehouse.orderpoint'

    # DC Configuration
    dc_company_id = fields.Many2one(
        'res.company',
        string='DC Company',
        help='Distribution Center that will fulfill this order'
    )
    
    dc_warehouse_id = fields.Many2one(
        'stock.warehouse',
        string='DC Warehouse',
        domain="[('company_id', '=', dc_company_id)]",
        help='DC warehouse for SO creation'
    )
    
    auto_create_dc_so = fields.Boolean(
        string='Auto Create DC SO',
        default=True,
        help='Auto-create Sales Order in DC when PO is created'
    )

    # Related Purchase Orders
    purchase_order_ids = fields.One2many(
        'purchase.order',
        'orderpoint_id',
        string='Related Purchase Orders',
        readonly=True,
    )
    purchase_order_count = fields.Integer(
        compute='_compute_purchase_order_count',
        string='PO Count'
    )

    # Monitor records
    monitor_ids = fields.One2many(
        'dc.order.monitor',
        'orderpoint_id',
        string='Order Monitors',
        readonly=True,
    )
    monitor_count = fields.Integer(
        compute='_compute_monitor_count',
        string='Monitor Count'
    )

    qty_on_hand = fields.Float(
        string='On Hand',
        compute='_compute_qty_on_hand',
        store=False,
        help='Current on-hand quantity of the product for this orderpoint'
    )

    @api.depends('purchase_order_ids')
    def _compute_purchase_order_count(self):
        for rec in self:
            rec.purchase_order_count = len(rec.purchase_order_ids)

    @api.depends('monitor_ids')
    def _compute_monitor_count(self):
        for rec in self:
            rec.monitor_count = len(rec.monitor_ids)

    @api.depends('product_id', 'warehouse_id')
    def _compute_qty_on_hand(self):
        Quant = self.env['stock.quant']
        for rec in self:
            if rec.product_id and rec.warehouse_id:
                quants = Quant.read_group(
                    domain=[
                        ('product_id', '=', rec.product_id.id),
                        ('location_id', 'child_of', rec.warehouse_id.view_location_id.id),
                        ('company_id', '=', rec.company_id.id),
                    ],
                    fields=['quantity:sum'],
                    groupby=[]
                )
                rec.qty_on_hand = quants[0]['quantity'] if quants else 0.0
            else:
                rec.qty_on_hand = 0.0

    @api.constrains('dc_company_id', 'company_id')
    def _check_dc_company(self):
        for rec in self:
            if rec.dc_company_id and rec.dc_company_id == rec.company_id:
                raise ValidationError(_("DC Company must be different from Retailer Company!"))

    @api.onchange('dc_company_id')
    def _onchange_dc_company_id(self):
        if self.dc_company_id:
            if self.dc_company_id.dc_warehouse_id:
                self.dc_warehouse_id = self.dc_company_id.dc_warehouse_id
            else:
                wh = self.env['stock.warehouse'].search([('company_id', '=', self.dc_company_id.id)], limit=1)
                self.dc_warehouse_id = wh

    def action_open_manual_replenish(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Manual Replenish'),
            'res_model': 'replenish.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_orderpoint_id': self.id},
        }

    def action_view_purchase_orders(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Purchase Orders'),
            'res_model': 'purchase.order',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', self.purchase_order_ids.ids)],
            'context': {'create': False},
        }

    def action_view_monitors(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Order Monitors'),
            'res_model': 'dc.order.monitor',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', self.monitor_ids.ids)],
            'context': {'create': False},
        }