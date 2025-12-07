from odoo import models, fields, api
import logging


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    dc_sales_order_id = fields.Many2one(
        'sale.order',
        string='DC Sales Order',
        readonly=True,
        help='Related Sales Order in DC company'
    )
    
    dc_company_id = fields.Many2one(
        'res.company',
        string='DC Company',
        readonly=True
    )
    
    is_from_reordering = fields.Boolean(
        string='From Reordering',
        default=False,
        readonly=True,
        help='Auto-created from reordering rules'
    )
    
    orderpoint_id = fields.Many2one(
        'stock.warehouse.orderpoint',
        string='Reordering Rule',
        readonly=True,
        help='Source orderpoint that triggered this PO'
    )
    
    dc_monitor_id = fields.Many2one(
        'dc.order.monitor',
        string='Monitor',
        readonly=True
    )
    
    def action_view_dc_so(self):
        """Button to view related DC SO"""
        self.ensure_one()
        if not self.dc_sales_order_id:
            return
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'DC Sales Order',
            'res_model': 'sale.order',
            'res_id': self.dc_sales_order_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
    
    @api.model
    def _cron_create_dc_sales_orders(self):
        """
        CRON JOB: Auto-create DC SO from new retailer PO
        Run every 5 minutes
        """
        _logger = logging.getLogger(__name__)
        _logger.info("=" * 80)
        _logger.info("CRON START: Auto-create DC SO")
        
        from datetime import timedelta
        threshold = fields.Datetime.now() - timedelta(minutes=5)
        
        # Find PO: draft, from reordering, no DC SO yet
        pos = self.sudo().search([
            ('create_date', '>=', threshold),
            ('state', 'in', ('draft', 'sent')),
            ('orderpoint_id', '!=', False),
            ('dc_sales_order_id', '=', False),
            ('dc_company_id', '!=', False),
        ])
        
        _logger.info("Found %s PO candidates", len(pos))
        processed = 0
        
        for po in pos:
            try:
                orderpoint = po.orderpoint_id
                
                if not orderpoint.auto_create_dc_so:
                    _logger.info("PO %s: auto_create_dc_so disabled", po.name)
                    continue
                
                if not orderpoint.dc_company_id:
                    _logger.warning("PO %s: no DC company configured", po.name)
                    continue
                
                _logger.info("→ Creating DC SO for PO %s", po.name)
                
                # Create DC SO
                dc_so = self._create_dc_so_from_po(po, orderpoint)
                
                if dc_so:
                    po.sudo().write({'dc_sales_order_id': dc_so.id})
                    
                    # Create monitor
                    monitor = self.env['dc.order.monitor'].sudo().create({
                        'retailer_company_id': po.company_id.id,
                        'dc_company_id': orderpoint.dc_company_id.id,
                        'retailer_po_id': po.id,
                        'dc_sales_order_id': dc_so.id,
                        'orderpoint_id': orderpoint.id,
                        'state': 'dc_so_created',
                        'notes': 'Auto-created via CRON',
                    })
                    
                    po.sudo().write({'dc_monitor_id': monitor.id})
                    dc_so.sudo().write({'dc_monitor_id': monitor.id})
                    
                    _logger.info("✓ DC SO %s created", dc_so.name)
                    processed += 1
                    
            except Exception as e:
                _logger.exception("Error processing PO %s: %s", po.name, e)
        
        _logger.info("CRON END: %s DC SO created", processed)
        _logger.info("=" * 80)
    
    @api.model
    def _create_dc_so_from_po(self, po, orderpoint):
        """Helper: Create SO in DC company"""
        dc_company = orderpoint.dc_company_id
        retailer_partner = po.company_id.partner_id
        
        if not retailer_partner:
            return False
        
        so_vals = {
            'partner_id': retailer_partner.id,
            'company_id': dc_company.id,
            'warehouse_id': orderpoint.dc_warehouse_id.id if orderpoint.dc_warehouse_id else False,
            'origin': f"Auto from {po.name}",
            'client_order_ref': po.name,
            'is_auto_created': True,
            'retailer_po_id': po.id,
        }
        
        so = self.env['sale.order'].sudo().with_company(dc_company.id).create(so_vals)
        
        for po_line in po.order_line:
            if not po_line.product_id:
                continue
            
            product = po_line.product_id.sudo().with_company(dc_company.id)
            
            self.env['sale.order.line'].sudo().with_company(dc_company.id).create({
                'order_id': so.id,
                'product_id': product.id,
                'product_uom_qty': po_line.product_qty,
                'product_uom': po_line.product_uom.id,
                'price_unit': product.list_price or 0,
            })
        
        return so