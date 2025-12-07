from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class ReplenishWizard(models.TransientModel):
    _name = 'replenish.wizard'
    _description = 'Manual Replenish Wizard'

    orderpoint_id = fields.Many2one('stock.warehouse.orderpoint', string='Reordering Rule', required=True)
    product_id = fields.Many2one('product.product', string='Product', readonly=True)
    company_id = fields.Many2one('res.company', string='Company', readonly=True)
    
    current_qty = fields.Float(string='Current Qty', readonly=True)
    min_qty = fields.Float(string='Min Qty', readonly=True)
    max_qty = fields.Float(string='Max Qty', readonly=True)
    
    qty_to_order = fields.Float(string='Qty to Order', required=True)
    
    dc_company_id = fields.Many2one('res.company', string='DC Company', readonly=True)
    dc_warehouse_id = fields.Many2one('stock.warehouse', string='DC Warehouse', readonly=True)
    auto_create_dc_so = fields.Boolean(string='Auto Create DC SO', readonly=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        
        if self._context.get('active_id'):
            orderpoint = self.env['stock.warehouse.orderpoint'].browse(self._context['active_id'])
            
            res.update({
                'orderpoint_id': orderpoint.id,
                'product_id': orderpoint.product_id.id,
                'company_id': orderpoint.company_id.id,
                'min_qty': orderpoint.product_min_qty,
                'max_qty': orderpoint.product_max_qty,
                'current_qty': orderpoint.qty_on_hand,
                'qty_to_order': orderpoint.product_max_qty - orderpoint.qty_on_hand,
                'dc_company_id': orderpoint.dc_company_id.id if orderpoint.dc_company_id else False,
                'dc_warehouse_id': orderpoint.dc_warehouse_id.id if orderpoint.dc_warehouse_id else False,
                'auto_create_dc_so': orderpoint.auto_create_dc_so,
            })
        
        return res

    def action_create_po(self):
        """Create manual PO dan DC SO (optional)"""
        self.ensure_one()
        
        if self.qty_to_order <= 0:
            raise UserError(_('Quantity must be greater than 0'))
        
        orderpoint = self.orderpoint_id
        
        # Create PO
        po_vals = {
            'partner_id': orderpoint.supplier_id.id if orderpoint.supplier_id else False,
            'company_id': orderpoint.company_id.id,
            'origin': f"Manual Replenish: {orderpoint.name}",
            'orderpoint_id': orderpoint.id,
            'is_from_reordering': True,
            'dc_company_id': orderpoint.dc_company_id.id if orderpoint.dc_company_id else False,
        }
        
        po = self.env['purchase.order'].sudo().with_company(orderpoint.company_id.id).create(po_vals)
        
        # Create PO line
        self.env['purchase.order.line'].sudo().with_company(orderpoint.company_id.id).create({
            'order_id': po.id,
            'product_id': orderpoint.product_id.id,
            'product_qty': self.qty_to_order,
            'product_uom': orderpoint.product_uom.id,
            'price_unit': orderpoint.product_id.standard_price,
            'date_planned': fields.Datetime.now(),
        })
        
        _logger.info("✓ Manual PO created: %s", po.name)
        
        # Auto-create DC SO if enabled
        if self.auto_create_dc_so and orderpoint.dc_company_id:
            try:
                dc_so = self._create_dc_so(po, orderpoint)
                
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
                        'notes': 'Created via Manual Replenish Wizard',
                    })
                    
                    po.sudo().write({'dc_monitor_id': monitor.id})
                    dc_so.sudo().write({'dc_monitor_id': monitor.id})
                    
                    _logger.info("✓ DC SO created: %s", dc_so.name)
                    
            except Exception as e:
                _logger.exception("Failed to create DC SO: %s", e)
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'Purchase Order',
            'res_model': 'purchase.order',
            'res_id': po.id,
            'view_mode': 'form',
            'target': 'current',
        }
    
    def _create_dc_so(self, po, orderpoint):
        """Create SO in DC company"""
        dc_company = orderpoint.dc_company_id
        retailer_partner = po.company_id.partner_id
        
        if not retailer_partner:
            _logger.warning("No partner found for retailer company %s", po.company_id.name)
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
        
        # Create SO lines
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