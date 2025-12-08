from odoo import models, fields, api
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)  # add logger


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
    
    @api.model
    def create(self, vals):
        # Tangkap orderpoint_id dari context (dikirim dari stock_rule)
        if 'orderpoint_id' not in vals and self.env.context.get('orderpoint_id'):
            vals['orderpoint_id'] = self.env.context.get('orderpoint_id')
        
        # Mark as from reordering jika ada orderpoint
        if vals.get('orderpoint_id'):
            vals['is_from_reordering'] = True
        
        po = super().create(vals)
        _logger.info("PO %s created | is_from_reordering=%s | orderpoint_id=%s",
                    po.name, vals.get('is_from_reordering'), vals.get('orderpoint_id'))
        
        return po

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
        """Cron: Auto-create DC SO from PO - DIRECT APPROACH"""
        self = self.sudo().with_context(active_test=False)
        
        # Cari PO yang:
        # 1. Belum punya DC SO
        # 2. State = purchase (confirmed)
        # 3. Ada product yang punya reordering rule dengan DC
        pos = self.search([
            ('dc_sales_order_id', '=', False),
            ('state', '=', 'purchase'),  # hanya confirmed PO
        ])
        
        _logger.info("CRON: Scanning %d PO for DC SO creation", len(pos))
        
        ok = fail = 0
        for po in pos:
            # Cari orderpoint dari product di PO
            products = po.order_line.product_id
            warehouse = po.picking_type_id.warehouse_id if po.picking_type_id else None
            
            if not warehouse:
                _logger.warning("PO %s: no warehouse found", po.name)
                continue
            
            # Cari orderpoint punya DC config
            orderpoint = self.env['stock.warehouse.orderpoint'].sudo().search([
                ('product_id', 'in', products.ids),
                ('warehouse_id', '=', warehouse.id),
                ('auto_create_dc_so', '=', True),
                ('dc_company_id', '!=', False),
                ('dc_warehouse_id', '!=', False),
            ], limit=1)
            
            if not orderpoint:
                _logger.info("Skip PO %s: no suitable orderpoint found", po.name)
                continue
            
            try:
                so = po._create_dc_so_from_po(po, orderpoint)
                if so:
                    po.write({
                        'dc_sales_order_id': so.id,
                        'dc_company_id': orderpoint.dc_company_id.id,
                        'orderpoint_id': orderpoint.id,  # set sekarang
                    })
                    _logger.info("✓ Created DC SO %s for PO %s", so.name, po.name)
                    ok += 1
            except Exception as e:
                fail += 1
                _logger.exception("✗ Failed PO %s: %s", po.name, str(e))
        
        _logger.info("CRON DONE: %d success, %d failed", ok, fail)
    
    @api.model
    def _create_dc_so_from_po(self, po, orderpoint):
        """Helper: Create SO in DC company"""
        dc_company = orderpoint.dc_company_id
        retailer_partner = po.company_id.partner_id
        
        if not retailer_partner:
            _logger.warning("PO %s: retailer partner not found", po.name)
            return False
        
        SO = self.env['sale.order'].sudo().with_company(dc_company.id)
        
        so_vals = {
            'partner_id': retailer_partner.id,
            'company_id': dc_company.id,
            'warehouse_id': orderpoint.dc_warehouse_id.id if orderpoint.dc_warehouse_id else False,
            'origin': f"Auto from {po.name}",
            'client_order_ref': po.name,
        }
        
        so = SO.create(so_vals)
        
        # Copy lines
        for po_line in po.order_line:
            if not po_line.product_id:
                continue
            
            self.env['sale.order.line'].sudo().with_company(dc_company.id).create({
                'order_id': so.id,
                'product_id': po_line.product_id.id,
                'product_uom_qty': po_line.product_qty,
                'product_uom': po_line.product_uom.id,
                'price_unit': po_line.price_unit or 0,
            })
        
        # Auto-confirm DC SO
        so.action_confirm()
        _logger.info("DC SO %s auto-confirmed", so.name)
        
        # AUTO: Create monitor
        monitor = self.env['dc.order.monitor'].sudo().create({
            'retailer_company_id': po.company_id.id,
            'dc_company_id': dc_company.id,
            'retailer_po_id': po.id,
            'dc_sales_order_id': so.id,
            'orderpoint_id': orderpoint.id,
            'state': 'dc_so_created',
            'notes': f"Auto-created from PO {po.name}",
        })
        
        _logger.info("✓ Monitor %s created for SO %s", monitor.name, so.name)
        
        return so

    def action_create_dc_monitor(self):
        """Create DC Monitor dari PO ini"""
        self.ensure_one()
        
        if not self.orderpoint_id:
            raise UserError("Reordering Rule belum diset pada PO ini")

        dc_so = self.dc_sales_order_id
        if not dc_so:
            # fallback: cari SO yang dibuat dari PO ini
            dc_so = self.env['sale.order'].sudo().search([
                ('origin', '=', f"Auto from {self.name}")
            ], limit=1)

        vals = {
            'retailer_company_id': self.company_id.id,
            'dc_company_id': self.orderpoint_id.dc_company_id.id if self.orderpoint_id.dc_company_id else False,
            'retailer_po_id': self.id,
            'orderpoint_id': self.orderpoint_id.id,
            'notes': f"Created from PO {self.name}",
        }
        if dc_so:
            vals['dc_sales_order_id'] = dc_so.id

        monitor = self.env['dc.order.monitor'].sudo().create(vals)
        return {
            'type': 'ir.actions.act_window',
            'name': 'DC Order Monitor',
            'res_model': 'dc.order.monitor',
            'res_id': monitor.id,
            'view_mode': 'form',
            'target': 'current',
        }