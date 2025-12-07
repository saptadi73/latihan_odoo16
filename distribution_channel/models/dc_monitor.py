# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class DcOrderMonitor(models.Model):
    _name = 'dc.order.monitor'
    _description = 'DC Order Chain Monitor'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char(string='Monitor Reference', required=True, copy=False, readonly=True, default='New')
    
    # Companies
    retailer_company_id = fields.Many2one('res.company', string='Retailer', required=True, readonly=True)
    dc_company_id = fields.Many2one('res.company', string='DC', required=True, readonly=True)
    
    # Orders
    retailer_po_id = fields.Many2one('purchase.order', string='Retailer PO', readonly=True)
    dc_sales_order_id = fields.Many2one('sale.order', string='DC SO', readonly=True)
    
    # Orderpoint
    orderpoint_id = fields.Many2one('stock.warehouse.orderpoint', string='Reordering Rule', readonly=True)
    
    # Totals
    total_qty = fields.Float(string='Total Qty', compute='_compute_totals', store=True)
    total_amount = fields.Float(string='Total Amount', compute='_compute_totals', store=True)
    
    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('dc_so_created', 'DC SO Created'),
        ('dc_so_confirmed', 'DC SO Confirmed'),
        ('completed', 'Completed'),
    ], default='draft', string='Status', readonly=True)
    
    notes = fields.Text(string='Notes')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('dc.order.monitor') or _('New')
        return super().create(vals_list)
    
    @api.depends('retailer_po_id.order_line.product_qty', 'retailer_po_id.amount_total')
    def _compute_totals(self):
        for rec in self:
            if rec.retailer_po_id:
                rec.total_qty = sum(rec.retailer_po_id.order_line.mapped('product_qty'))
                rec.total_amount = rec.retailer_po_id.amount_total
            else:
                rec.total_qty = 0
                rec.total_amount = 0
    
    def action_view_retailer_po(self):
        """Open retailer PO"""
        self.ensure_one()
        if not self.retailer_po_id:
            return
        return {
            'type': 'ir.actions.act_window',
            'name': 'Retailer PO',
            'res_model': 'purchase.order',
            'res_id': self.retailer_po_id.id,
            'view_mode': 'form',
        }
    
    def action_view_dc_so(self):
        """Open DC SO"""
        self.ensure_one()
        if not self.dc_sales_order_id:
            return
        return {
            'type': 'ir.actions.act_window',
            'name': 'DC Sales Order',
            'res_model': 'sale.order',
            'res_id': self.dc_sales_order_id.id,
            'view_mode': 'form',
        }