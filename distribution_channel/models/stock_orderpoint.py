# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class StockWarehouseOrderpoint(models.Model):
    _inherit = 'stock.warehouse.orderpoint'

    # DC Configuration
    dc_company_id = fields.Many2one(
        'res.company',
        string='DC Company',
        help='Distribution Center company'
    )
    
    dc_warehouse_id = fields.Many2one(
        'stock.warehouse',
        string='DC Warehouse',
        help='Warehouse di DC company'
    )
    
    auto_create_dc_so = fields.Boolean(
        string='Auto Create DC SO',
        default=False,
        help='Automatically create inter-company SO when PO is created'
    )

    # Related Purchase Orders
    purchase_order_ids = fields.One2many(
        'purchase.order',
        'orderpoint_id',
        string='Related Purchase Orders',
        readonly=True,
    )
    purchase_order_count = fields.Integer(
        compute='_compute_po_count',
        string='Purchase Orders'
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
        string='Monitors'
    )

    @api.onchange('dc_company_id')
    def _onchange_dc_company_id(self):
        """Filter DC Warehouse berdasarkan DC Company"""
        if self.dc_company_id:
            return {
                'domain': {
                    'dc_warehouse_id': [('company_id', '=', self.dc_company_id.id)]
                }
            }
        else:
            self.dc_warehouse_id = False

    def _compute_po_count(self):
        for record in self:
            record.purchase_order_count = self.env['purchase.order'].search_count([
                ('orderpoint_id', '=', record.id)
            ])

    def _compute_monitor_count(self):
        for record in self:
            record.monitor_count = self.env['dc.order.monitor'].search_count([
                ('orderpoint_id', '=', record.id)
            ])

    def action_view_purchase_orders(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Purchase Orders'),
            'res_model': 'purchase.order',
            'view_mode': 'tree,form',
            'domain': [('orderpoint_id', '=', self.id)],
            'context': {'create': False},
        }

    def action_view_monitors(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('DC Order Monitors'),
            'res_model': 'dc.order.monitor',
            'view_mode': 'tree,form',
            'domain': [('orderpoint_id', '=', self.id)],
        }

    def action_open_manual_replenish(self):
        self.ensure_one()
        return {
            'name': _('Manual Replenishment'),
            'type': 'ir.actions.act_window',
            'res_model': 'replenish.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_orderpoint_id': self.id},
        }