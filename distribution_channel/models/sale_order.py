# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    is_from_dc = fields.Boolean(
        string='From DC',
        default=False,
        readonly=True,
        help='Indicates if this SO was auto-created from a retailer PO'
    )
    retailer_company_id = fields.Many2one(
        'res.company',
        string='Retailer Company',
        readonly=True,
        help='The retailer company that created the PO'
    )
    retailer_po_id = fields.Many2one(
        'purchase.order',
        string='Retailer PO',
        readonly=True,
        help='The originating purchase order from retailer'
    )
    dc_monitor_id = fields.Many2one(
        'dc.order.monitor',
        string='DC Monitor',
        readonly=True
    )

    def action_view_retailer_po(self):
        self.ensure_one()
        if not self.retailer_po_id:
            return
        return {
            'type': 'ir.actions.act_window',
            'name': _('Retailer Purchase Order'),
            'res_model': 'purchase.order',
            'res_id': self.retailer_po_id.id,
            'view_mode': 'form',
            'target': 'current',
        }