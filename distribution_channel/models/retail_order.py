# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class StockWarehouseOrderpoint(models.Model):
    """
    Extend Reordering Rules untuk link ke DC
    """
    _inherit = 'stock.warehouse.orderpoint'

    # Link ke DC Company
    dc_company_id = fields.Many2one(
        'res.company',
        string='DC Company',
        help='Distribution Center yang akan supply produk ini'
    )

    dc_warehouse_id = fields.Many2one(
        'stock.warehouse',
        string='DC Warehouse',
        help='DC Warehouse untuk SO'
    )

    auto_create_dc_so = fields.Boolean(
        'Auto Create DC SO',
        default=True,
        help='Otomatis buat Sales Order di DC saat PO dibuat'
    )

    @api.onchange('dc_company_id')
    def _onchange_dc_company_id(self):
        """Auto-fill DC warehouse"""
        if self.dc_company_id:
            warehouse = self.env['stock.warehouse'].search([
                ('company_id', '=', self.dc_company_id.id)
            ], limit=1)
            if warehouse:
                self.dc_warehouse_id = warehouse


class PurchaseOrder(models.Model):
    """
    Extend Purchase Order untuk auto-create Sales Order di DC
    """
    _inherit = 'purchase.order'

    # Link to DC Sales Order
    dc_sales_order_id = fields.Many2one(
        'sale.order',
        string='DC Sales Order',
        readonly=True,
        help='Sales Order yang dibuat otomatis di DC'
    )

    dc_company_id = fields.Many2one(
        'res.company',
        string='DC Company',
        help='DC Company untuk auto-create SO'
    )

    is_from_reordering = fields.Boolean(
        'From Reordering Rule',
        default=False,
        help='PO dibuat dari reordering rule'
    )

    # Link ke retail order monitoring
    retail_order_id = fields.Many2one(
        'distribution_channel.retail_order',
        string='Retail Order Monitor',
        help='Record monitoring untuk PO ini'
    )

    # Status tracking
    dc_so_delivery_status = fields.Selection([
        ('not_created', 'Not Created'),
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('picking', 'Picking'),
        ('shipped', 'Shipped'),
        ('received', 'Received'),
    ], string='DC SO Delivery Status', compute='_compute_dc_so_delivery_status', store=True)

    @api.depends('dc_sales_order_id.state', 'dc_sales_order_id.picking_ids.state')
    def _compute_dc_so_delivery_status(self):
        """Track delivery status dari DC SO"""
        for po in self:
            if not po.dc_sales_order_id:
                po.dc_so_delivery_status = 'not_created'
            else:
                so = po.dc_sales_order_id
                
                if so.state == 'draft':
                    po.dc_so_delivery_status = 'draft'
                elif so.state == 'sale':
                    # Check picking status
                    pickings = so.picking_ids
                    if not pickings:
                        po.dc_so_delivery_status = 'confirmed'
                    elif all(p.state == 'done' for p in pickings):
                        po.dc_so_delivery_status = 'shipped'
                    elif any(p.state == 'done' for p in pickings):
                        po.dc_so_delivery_status = 'picking'
                    else:
                        po.dc_so_delivery_status = 'confirmed'
                else:
                    po.dc_so_delivery_status = so.state

    @api.model_create_multi
    def create(self, vals_list):
        """Override create untuk auto-create DC SO"""
        orders = super().create(vals_list)
        
        for order in orders:
            # Check jika PO dari reordering rule
            if order.origin and 'Reordering' in order.origin:
                order.is_from_reordering = True
                
                # Cari DC company dari orderpoint
                orderpoint = order._get_related_orderpoint()
                
                if orderpoint and orderpoint.auto_create_dc_so and orderpoint.dc_company_id:
                    try:
                        # Create SO di DC
                        dc_so = order._create_dc_sales_order(orderpoint)
                        order.dc_sales_order_id = dc_so.id
                        order.dc_company_id = orderpoint.dc_company_id.id
                        
                        # Create retail order monitoring record
                        retail_order = self.env['distribution_channel.retail_order'].create_from_po(
                            order, dc_so, orderpoint
                        )
                        order.retail_order_id = retail_order.id
                        
                        _logger.info(
                            f'DC SO {dc_so.name} created for PO {order.name}'
                        )
                    except Exception as e:
                        _logger.error(f'Error creating DC SO: {str(e)}')
        
        return orders

    def _get_related_orderpoint(self):
        """Get orderpoint yang trigger PO ini"""
        self.ensure_one()
        
        if not self.order_line:
            return False
        
        # Ambil product pertama
        product = self.order_line[0].product_id
        
        # Cari orderpoint
        orderpoint = self.env['stock.warehouse.orderpoint'].search([
            ('product_id', '=', product.id),
            ('warehouse_id', '=', self.picking_type_id.warehouse_id.id),
            ('company_id', '=', self.company_id.id),
            ('dc_company_id', '!=', False),
        ], limit=1)
        
        return orderpoint

    def _create_dc_sales_order(self, orderpoint):
        """Create Sales Order di DC"""
        self.ensure_one()
        
        if not orderpoint.dc_company_id:
            raise ValidationError('DC Company not configured in reordering rule!')
        
        # Get DC partner (retailer as customer)
        dc_partner = self.company_id.partner_id
        
        # Create Sales Order di DC
        so_vals = {
            'partner_id': dc_partner.id,
            'company_id': orderpoint.dc_company_id.id,
            'warehouse_id': orderpoint.dc_warehouse_id.id if orderpoint.dc_warehouse_id else False,
            'date_order': fields.Datetime.now(),
            'origin': f'Auto from {self.name}',
            'client_order_ref': self.name,
            'note': f'Auto-created from Retailer PO: {self.name}\n'
                    f'Reordering Rule: {orderpoint.name}',
        }
        
        # Create SO dengan context DC company
        so = self.env['sale.order'].with_company(orderpoint.dc_company_id).create(so_vals)
        
        # Create SO Lines dari PO Lines
        for po_line in self.order_line:
            so_line_vals = {
                'order_id': so.id,
                'product_id': po_line.product_id.id,
                'product_uom_qty': po_line.product_qty,
                'product_uom': po_line.product_uom.id,
                'price_unit': po_line.product_id.list_price,  # Harga jual DC
                'name': po_line.product_id.display_name,
            }
            self.env['sale.order.line'].create(so_line_vals)
        
        return so

    def action_open_dc_so(self):
        """Open DC Sales Order"""
        self.ensure_one()
        if self.dc_sales_order_id:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'sale.order',
                'res_id': self.dc_sales_order_id.id,
                'view_mode': 'form',
                'target': 'current',
                'context': {'default_company_id': self.dc_company_id.id}
            }

    def button_confirm(self):
        """Override confirm untuk confirm DC SO juga"""
        res = super().button_confirm()
        
        for order in self:
            if order.dc_sales_order_id and order.dc_sales_order_id.state == 'draft':
                try:
                    order.dc_sales_order_id.action_confirm()
                    _logger.info(f'DC SO {order.dc_sales_order_id.name} confirmed')
                except Exception as e:
                    _logger.error(f'Error confirming DC SO: {str(e)}')
        
        return res


class SaleOrder(models.Model):
    """
    Extend Sales Order untuk tracking
    """
    _inherit = 'sale.order'

    retailer_po_id = fields.Many2one(
        'purchase.order',
        string='Related Retailer PO',
        help='PO di retailer yang trigger SO ini'
    )

    is_auto_created = fields.Boolean(
        'Auto Created',
        default=False,
        help='SO dibuat otomatis dari retailer PO'
    )

    # Link ke DC Purchase Order (untuk SO retailer)
    dc_purchase_order_id = fields.Many2one(
        'purchase.order',
        string='DC Purchase Order',
        help='PO dari DC untuk fulfill SO retailer ini'
    )

    # Link ke retail order monitoring
    retail_order_id = fields.Many2one(
        'distribution_channel.retail_order',
        string='Retail Order Monitor',
        help='Record monitoring untuk SO ini'
    )

    def action_open_retailer_po(self):
        """Open Retailer Purchase Order"""
        self.ensure_one()
        if self.retailer_po_id:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'purchase.order',
                'res_id': self.retailer_po_id.id,
                'view_mode': 'form',
                'target': 'current',
            }
        return False

    def action_open_dc_po(self):
        """Open DC Purchase Order"""
        self.ensure_one()
        if self.dc_purchase_order_id:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'purchase.order',
                'res_id': self.dc_purchase_order_id.id,
                'view_mode': 'form',
                'target': 'current',
            }
        return False


class RetailOrder(models.Model):
    """
    Model untuk monitoring & reporting relasi:
    Retailer PO ↔ DC SO ↔ DC PO ↔ Retailer SO
    """
    _name = 'distribution_channel.retail_order'
    _description = 'Retail Order Monitoring & Tracking'
    _order = 'create_date desc'

    name = fields.Char(
        'Reference',
        readonly=True,
        default='New'
    )

    # ============ COMPANY INFO ============
    retailer_company_id = fields.Many2one(
        'res.company',
        string='Retailer',
        required=True
    )

    dc_company_id = fields.Many2one(
        'res.company',
        string='DC',
        required=True
    )

    # ============ ORDER CHAIN ============
    # STAGE 1: Retailer PO
    retailer_po_id = fields.Many2one(
        'purchase.order',
        string='Retailer PO',
        help='PO dari retailer (Pembelian)'
    )

    # STAGE 2: DC SO (dari Retailer PO)
    dc_sales_order_id = fields.Many2one(
        'sale.order',
        string='DC Sales Order',
        help='SO di DC (Penjualan ke retailer)'
    )

    # STAGE 3: DC PO (DC beli dari supplier)
    dc_purchase_order_id = fields.Many2one(
        'purchase.order',
        string='DC Purchase Order',
        help='PO dari DC ke supplier'
    )

    # STAGE 4: Retailer SO (Penawaran ke end-customer)
    retailer_sales_order_id = fields.Many2one(
        'sale.order',
        string='Retailer Sales Order',
        help='SO di retailer (Penjualan ke customer)'
    )

    orderpoint_id = fields.Many2one(
        'stock.warehouse.orderpoint',
        string='Reordering Rule',
        help='Reordering rule yang trigger order ini'
    )

    # ============ STATUS TRACKING ============
    state = fields.Selection([
        ('draft', 'Draft'),
        ('retailer_po_created', 'Retailer PO Created'),
        ('dc_so_created', 'DC SO Created'),
        ('dc_so_confirmed', 'DC SO Confirmed'),
        ('dc_so_picked', 'DC SO Picked'),
        ('dc_so_shipped', 'DC SO Shipped'),
        ('retailer_received', 'Retailer Received'),
        ('retailer_so_created', 'Retailer SO Created'),
        ('retailer_so_confirmed', 'Retailer SO Confirmed'),
        ('retailer_so_delivered', 'Retailer SO Delivered'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ], default='draft', tracking=True)

    # Status untuk setiap tahap
    retailer_po_status = fields.Selection([
        ('draft', 'Draft'),
        ('sent', 'Sent'),
        ('purchase', 'Purchase'),
        ('done', 'Done'),
        ('cancel', 'Cancelled'),
    ], string='Retailer PO Status', compute='_compute_retailer_po_status', store=True)

    dc_so_status = fields.Selection([
        ('draft', 'Draft'),
        ('sent', 'Sent'),
        ('sale', 'Sale'),
        ('done', 'Done'),
        ('cancel', 'Cancelled'),
    ], string='DC SO Status', compute='_compute_dc_so_status', store=True)

    dc_so_delivery_status = fields.Selection([
        ('not_started', 'Not Started'),
        ('picking', 'Picking'),
        ('picked', 'Picked'),
        ('shipped', 'Shipped'),
        ('received', 'Received'),
    ], string='DC SO Delivery', compute='_compute_dc_so_delivery_status', store=True)

    dc_po_status = fields.Selection([
        ('draft', 'Draft'),
        ('sent', 'Sent'),
        ('purchase', 'Purchase'),
        ('done', 'Done'),
        ('cancel', 'Cancelled'),
    ], string='DC PO Status', compute='_compute_dc_po_status', store=True)

    retailer_so_status = fields.Selection([
        ('draft', 'Draft'),
        ('sent', 'Sent'),
        ('sale', 'Sale'),
        ('done', 'Done'),
        ('cancel', 'Cancelled'),
    ], string='Retailer SO Status', compute='_compute_retailer_so_status', store=True)

    # ============ QUANTITIES & AMOUNTS ============
    total_qty = fields.Float(
        'Total Quantity',
        compute='_compute_totals',
        store=True
    )

    total_amount = fields.Float(
        'Total Amount',
        compute='_compute_totals',
        store=True
    )

    retailer_po_amount = fields.Float(
        'Retailer PO Amount',
        compute='_compute_order_amounts',
        store=True
    )

    dc_so_amount = fields.Float(
        'DC SO Amount',
        compute='_compute_order_amounts',
        store=True
    )

    dc_po_amount = fields.Float(
        'DC PO Amount',
        compute='_compute_order_amounts',
        store=True
    )

    retailer_so_amount = fields.Float(
        'Retailer SO Amount',
        compute='_compute_order_amounts',
        store=True
    )

    # ============ DATES ============
    retailer_po_date = fields.Datetime(
        'Retailer PO Date',
        compute='_compute_dates',
        store=True
    )

    dc_so_date = fields.Datetime(
        'DC SO Date',
        compute='_compute_dates',
        store=True
    )

    dc_so_delivery_date = fields.Datetime(
        'DC SO Delivery Date',
        compute='_compute_delivery_dates',
        store=True
    )

    dc_po_date = fields.Datetime(
        'DC PO Date',
        compute='_compute_dates',
        store=True
    )

    retailer_so_date = fields.Datetime(
        'Retailer SO Date',
        compute='_compute_dates',
        store=True
    )

    # ============ HEALTH CHECK ============
    order_chain_status = fields.Selection([
        ('complete', 'Complete Chain'),
        ('partial', 'Partial Chain'),
        ('missing', 'Missing Links'),
        ('error', 'Mismatch/Error'),
    ], string='Chain Status', compute='_compute_chain_status', store=True)

    missing_links = fields.Text(
        'Missing Links',
        compute='_compute_chain_status',
        store=True
    )

    notes = fields.Text('Notes')

    # ============ COMPUTED FIELDS ============
    @api.depends('retailer_po_id.state')
    def _compute_retailer_po_status(self):
        """Track Retailer PO status"""
        for record in self:
            record.retailer_po_status = record.retailer_po_id.state if record.retailer_po_id else False

    @api.depends('dc_sales_order_id.state')
    def _compute_dc_so_status(self):
        """Track DC SO status"""
        for record in self:
            record.dc_so_status = record.dc_sales_order_id.state if record.dc_sales_order_id else False

    @api.depends('dc_sales_order_id.state', 'dc_sales_order_id.picking_ids.state')
    def _compute_dc_so_delivery_status(self):
        """Track delivery status dari DC SO"""
        for record in self:
            if not record.dc_sales_order_id:
                record.dc_so_delivery_status = 'not_started'
            else:
                so = record.dc_sales_order_id
                pickings = so.picking_ids.filtered(lambda p: p.picking_type_id.code == 'outgoing')
                
                if not pickings:
                    record.dc_so_delivery_status = 'not_started'
                elif all(p.state == 'done' for p in pickings):
                    record.dc_so_delivery_status = 'shipped'
                elif any(p.state == 'done' for p in pickings):
                    record.dc_so_delivery_status = 'picked'
                elif any(p.state in ['assigned', 'partially_available'] for p in pickings):
                    record.dc_so_delivery_status = 'picking'
                else:
                    record.dc_so_delivery_status = 'not_started'

    @api.depends('dc_purchase_order_id.state')
    def _compute_dc_po_status(self):
        """Track DC PO status"""
        for record in self:
            record.dc_po_status = record.dc_purchase_order_id.state if record.dc_purchase_order_id else False

    @api.depends('retailer_sales_order_id.state')
    def _compute_retailer_so_status(self):
        """Track Retailer SO status"""
        for record in self:
            record.retailer_so_status = record.retailer_sales_order_id.state if record.retailer_sales_order_id else False

    @api.depends('retailer_po_id.order_line.product_qty', 'dc_sales_order_id.order_line.product_uom_qty')
    def _compute_totals(self):
        """Compute totals"""
        for record in self:
            if record.retailer_po_id:
                record.total_qty = sum(record.retailer_po_id.order_line.mapped('product_qty'))
                record.total_amount = record.retailer_po_id.amount_total
            elif record.dc_sales_order_id:
                record.total_qty = sum(record.dc_sales_order_id.order_line.mapped('product_uom_qty'))
                record.total_amount = record.dc_sales_order_id.amount_total
            else:
                record.total_qty = 0.0
                record.total_amount = 0.0

    @api.depends('retailer_po_id.amount_total', 'dc_sales_order_id.amount_total', 
                 'dc_purchase_order_id.amount_total', 'retailer_sales_order_id.amount_total')
    def _compute_order_amounts(self):
        """Compute amounts untuk setiap stage"""
        for record in self:
            record.retailer_po_amount = record.retailer_po_id.amount_total if record.retailer_po_id else 0.0
            record.dc_so_amount = record.dc_sales_order_id.amount_total if record.dc_sales_order_id else 0.0
            record.dc_po_amount = record.dc_purchase_order_id.amount_total if record.dc_purchase_order_id else 0.0
            record.retailer_so_amount = record.retailer_sales_order_id.amount_total if record.retailer_sales_order_id else 0.0

    @api.depends('retailer_po_id.create_date', 'dc_sales_order_id.create_date',
                 'dc_purchase_order_id.create_date', 'retailer_sales_order_id.create_date')
    def _compute_dates(self):
        """Compute dates untuk setiap stage"""
        for record in self:
            record.retailer_po_date = record.retailer_po_id.create_date if record.retailer_po_id else False
            record.dc_so_date = record.dc_sales_order_id.create_date if record.dc_sales_order_id else False
            record.dc_po_date = record.dc_purchase_order_id.create_date if record.dc_purchase_order_id else False
            record.retailer_so_date = record.retailer_sales_order_id.create_date if record.retailer_sales_order_id else False

    @api.depends('dc_sales_order_id.picking_ids.state')
    def _compute_delivery_dates(self):
        """Compute delivery date dari DC SO"""
        for record in self:
            if record.dc_sales_order_id:
                pickings = record.dc_sales_order_id.picking_ids.filtered(lambda p: p.state == 'done')
                if pickings:
                    record.dc_so_delivery_date = max(pickings.mapped('date_done'))
                else:
                    record.dc_so_delivery_date = False
            else:
                record.dc_so_delivery_date = False

    @api.depends('retailer_po_id', 'dc_sales_order_id', 'dc_purchase_order_id', 'retailer_sales_order_id')
    def _compute_chain_status(self):
        """Check chain completeness"""
        for record in self:
            missing = []
            
            if not record.retailer_po_id:
                missing.append('Retailer PO')
            if not record.dc_sales_order_id:
                missing.append('DC SO')
            if not record.dc_purchase_order_id:
                missing.append('DC PO')
            if not record.retailer_sales_order_id:
                missing.append('Retailer SO')
            
            if not missing:
                record.order_chain_status = 'complete'
                record.missing_links = ''
            elif len(missing) == 4:
                record.order_chain_status = 'missing'
                record.missing_links = 'All orders missing!'
            else:
                record.order_chain_status = 'partial'
                record.missing_links = ', '.join(missing)

    @api.model
    def create(self, vals):
        """Generate sequence untuk name"""
        if not vals.get('name') or vals.get('name') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('distribution_channel.retail_order') or 'RO/000'
        return super().create(vals)

    @api.model
    def create_from_po(self, purchase_order, sales_order, orderpoint):
        """Create monitoring record dari PO & SO"""
        vals = {
            'name': f'RO/{purchase_order.name}',
            'retailer_company_id': purchase_order.company_id.id,
            'dc_company_id': sales_order.company_id.id if sales_order else False,
            'retailer_po_id': purchase_order.id,
            'dc_sales_order_id': sales_order.id if sales_order else False,
            'orderpoint_id': orderpoint.id if orderpoint else False,
            'state': 'dc_so_created' if sales_order else 'retailer_po_created',
            'notes': f'Auto-created from reordering rule',
        }
        return self.create(vals)

    def action_open_retailer_po(self):
        """Open Retailer PO"""
        if self.retailer_po_id:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'purchase.order',
                'res_id': self.retailer_po_id.id,
                'view_mode': 'form',
                'target': 'current',
            }

    def action_open_dc_so(self):
        """Open DC SO"""
        if self.dc_sales_order_id:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'sale.order',
                'res_id': self.dc_sales_order_id.id,
                'view_mode': 'form',
                'target': 'current',
            }

    def action_open_dc_po(self):
        """Open DC PO"""
        if self.dc_purchase_order_id:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'purchase.order',
                'res_id': self.dc_purchase_order_id.id,
                'view_mode': 'form',
                'target': 'current',
            }

    def action_open_retailer_so(self):
        """Open Retailer SO"""
        if self.retailer_sales_order_id:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'sale.order',
                'res_id': self.retailer_sales_order_id.id,
                'view_mode': 'form',
                'target': 'current',
            }

