# -*- coding: utf-8 -*-
from odoo import models, fields, api
from datetime import datetime, timedelta


class PosSalesReport(models.Model):
    """
    Model untuk reporting penjualan PoS per retailer
    """
    _name = 'distribution_channel.pos_sales_report'
    _description = 'PoS Sales Report per Retailer'
    _auto = False
    _order = 'date_order desc'

    # ============ IDENTIFIERS ============
    name = fields.Char('Reference', readonly=True)
    
    retailer_company_id = fields.Many2one(
        'res.company',
        string='Retailer',
        readonly=True
    )

    pos_order_id = fields.Many2one(
        'pos.order',
        string='PoS Order',
        readonly=True
    )

    # ============ ORDER INFO ============
    sale_order_id = fields.Many2one(
        'sale.order',
        string='Sale Order',
        readonly=True
    )

    partner_id = fields.Many2one(
        'res.partner',
        string='Customer',
        readonly=True
    )

    # ============ PRODUCT INFO ============
    product_id = fields.Many2one(
        'product.product',
        string='Product',
        readonly=True
    )

    product_category_id = fields.Many2one(
        'product.category',
        string='Product Category',
        readonly=True
    )

    # ============ QUANTITIES & AMOUNTS ============
    quantity = fields.Float(
        'Quantity',
        readonly=True
    )

    unit_price = fields.Float(
        'Unit Price',
        readonly=True
    )

    price_subtotal = fields.Float(
        'Subtotal',
        readonly=True
    )

    price_total = fields.Float(
        'Total',
        readonly=True
    )

    tax_amount = fields.Float(
        'Tax Amount',
        readonly=True
    )

    discount_amount = fields.Float(
        'Discount Amount',
        readonly=True
    )

    # ============ DATES ============
    date_order = fields.Datetime(
        'Order Date',
        readonly=True
    )

    date_day = fields.Date(
        'Day',
        compute='_compute_date_fields',
        store=True,
        readonly=True
    )

    date_month = fields.Char(
        'Month',
        compute='_compute_date_fields',
        store=True,
        readonly=True
    )

    date_year = fields.Char(
        'Year',
        compute='_compute_date_fields',
        store=True,
        readonly=True
    )

    # ============ PAYMENT INFO ============
    payment_method = fields.Char(
        'Payment Method',
        readonly=True
    )

    # ============ STATUS ============
    order_state = fields.Selection([
        ('draft', 'Draft'),
        ('sale', 'Sale'),
        ('done', 'Done'),
        ('cancel', 'Cancelled'),
    ], 'Order State', readonly=True)

    pos_state = fields.Selection([
        ('draft', 'Draft'),
        ('paid', 'Paid'),
        ('posted', 'Posted'),
        ('invoiced', 'Invoiced'),
    ], 'PoS State', readonly=True)

    @api.depends('date_order')
    def _compute_date_fields(self):
        """Extract date components"""
        for record in self:
            if record.date_order:
                date_obj = record.date_order
                record.date_day = date_obj.date()
                record.date_month = date_obj.strftime('%B %Y')
                record.date_year = date_obj.strftime('%Y')
            else:
                record.date_day = False
                record.date_month = False
                record.date_year = False

    def init(self):
        """Create report view from PoS order lines"""
        self.env.cr.execute("""
            DROP VIEW IF EXISTS distribution_channel_pos_sales_report
        """)
        
        self.env.cr.execute("""
            CREATE VIEW distribution_channel_pos_sales_report AS (
                SELECT
                    row_number() OVER (ORDER BY pol.id) as id,
                    CONCAT('POS/', po.name, '/', pol.id) as name,
                    po.company_id as retailer_company_id,
                    po.id as pos_order_id,
                    NULL::integer as sale_order_id,
                    po.partner_id as partner_id,
                    pol.product_id as product_id,
                    pt.categ_id as product_category_id,
                    pol.qty as quantity,
                    pol.price_unit as unit_price,
                    (pol.qty * pol.price_unit) - pol.discount as price_subtotal,
                    pol.price_subtotal_incl as price_total,
                    (pol.price_subtotal_incl - ((pol.qty * pol.price_unit) - pol.discount)) as tax_amount,
                    pol.discount as discount_amount,
                    po.date_order as date_order,
                    'done' as order_state,
                    po.state as pos_state,
                    COALESCE(pm.name::varchar, 'Unknown') as payment_method
                FROM pos_order_line pol
                JOIN pos_order po ON pol.order_id = po.id
                JOIN product_product pp ON pol.product_id = pp.id
                JOIN product_template pt ON pp.product_tmpl_id = pt.id
                LEFT JOIN pos_payment pp2 ON po.id = pp2.pos_order_id
                LEFT JOIN pos_payment_method pm ON pp2.payment_method_id = pm.id
                WHERE po.company_id IS NOT NULL
            )
        """)


class PosSalesReportDaily(models.Model):
    """
    Model untuk daily summary PoS sales per retailer
    """
    _name = 'distribution_channel.pos_sales_report_daily'
    _description = 'Daily PoS Sales Report'
    _auto = False
    _order = 'date_day desc'

    # ============ IDENTIFIERS ============
    name = fields.Char('Reference', readonly=True)

    retailer_company_id = fields.Many2one(
        'res.company',
        string='Retailer',
        readonly=True
    )

    # ============ DATE ============
    date_day = fields.Date(
        'Date',
        readonly=True
    )

    # ============ SUMMARY ============
    total_orders = fields.Integer(
        'Total Orders',
        readonly=True
    )

    total_items = fields.Float(
        'Total Items Sold',
        readonly=True
    )

    total_subtotal = fields.Float(
        'Subtotal',
        readonly=True
    )

    total_tax = fields.Float(
        'Total Tax',
        readonly=True
    )

    total_discount = fields.Float(
        'Total Discount',
        readonly=True
    )

    total_revenue = fields.Float(
        'Total Revenue',
        readonly=True
    )

    average_ticket = fields.Float(
        'Average Ticket Value',
        readonly=True
    )

    # ============ CATEGORIES ============
    top_category_id = fields.Many2one(
        'product.category',
        string='Top Category',
        readonly=True
    )

    top_category_sales = fields.Float(
        'Top Category Sales',
        readonly=True
    )

    def init(self):
        """Create daily summary view"""
        self.env.cr.execute("""
            DROP VIEW IF EXISTS distribution_channel_pos_sales_report_daily
        """)
        
        self.env.cr.execute("""
            CREATE VIEW distribution_channel_pos_sales_report_daily AS (
                SELECT
                    row_number() OVER (ORDER BY DATE(po.date_order), po.company_id) as id,
                    CONCAT('DAILY/', po.company_id, '/', DATE(po.date_order)) as name,
                    po.company_id as retailer_company_id,
                    DATE(po.date_order) as date_day,
                    COUNT(DISTINCT po.id) as total_orders,
                    SUM(pol.qty) as total_items,
                    SUM((pol.qty * pol.price_unit) - pol.discount) as total_subtotal,
                    SUM(pol.price_subtotal_incl - ((pol.qty * pol.price_unit) - pol.discount)) as total_tax,
                    SUM(pol.discount) as total_discount,
                    SUM(pol.price_subtotal_incl) as total_revenue,
                    SUM(pol.price_subtotal_incl) / COUNT(DISTINCT po.id) as average_ticket,
                    pt.categ_id as top_category_id,
                    SUM(pol.price_subtotal_incl) as top_category_sales
                FROM pos_order_line pol
                JOIN pos_order po ON pol.order_id = po.id
                JOIN product_product pp ON pol.product_id = pp.id
                JOIN product_template pt ON pp.product_tmpl_id = pt.id
                WHERE po.state IN ('paid', 'posted', 'invoiced')
                GROUP BY DATE(po.date_order), po.company_id, pt.categ_id
            )
        """)


class PosSalesReportCategory(models.Model):
    """
    Model untuk sales by category per retailer
    """
    _name = 'distribution_channel.pos_sales_report_category'
    _description = 'PoS Sales by Category'
    _auto = False

    name = fields.Char('Category', readonly=True)

    retailer_company_id = fields.Many2one(
        'res.company',
        string='Retailer',
        readonly=True
    )

    product_category_id = fields.Many2one(
        'product.category',
        string='Product Category',
        readonly=True
    )

    total_quantity = fields.Float(
        'Total Quantity',
        readonly=True
    )

    total_sales = fields.Float(
        'Total Sales',
        readonly=True
    )

    percentage = fields.Float(
        'Percentage of Total',
        readonly=True
    )

    date_from = fields.Date('From', readonly=True)
    date_to = fields.Date('To', readonly=True)

    def init(self):
        """Create category summary view"""
        self.env.cr.execute("""
            DROP VIEW IF EXISTS distribution_channel_pos_sales_report_category
        """)
        
        self.env.cr.execute("""
            CREATE VIEW distribution_channel_pos_sales_report_category AS (
                SELECT
                    row_number() OVER (ORDER BY po.company_id, pt.categ_id) as id,
                    pt.name as name,
                    po.company_id as retailer_company_id,
                    pt.id as product_category_id,
                    SUM(pol.qty) as total_quantity,
                    SUM(pol.price_subtotal_incl) as total_sales,
                    (SUM(pol.price_subtotal_incl) / 
                     (SELECT SUM(pol2.price_subtotal_incl) 
                      FROM pos_order_line pol2 
                      JOIN pos_order po2 ON pol2.order_id = po2.id 
                      WHERE po2.company_id = po.company_id 
                      AND po2.state IN ('paid', 'posted', 'invoiced')) * 100) as percentage,
                    DATE(MIN(po.date_order)) as date_from,
                    DATE(MAX(po.date_order)) as date_to
                FROM pos_order_line pol
                JOIN pos_order po ON pol.order_id = po.id
                JOIN product_product pp ON pol.product_id = pp.id
                JOIN product_template pt ON pp.product_tmpl_id = pt.id
                WHERE po.state IN ('paid', 'posted', 'invoiced')
                GROUP BY po.company_id, pt.id, pt.name
            )
        """)


class PosSalesReportProduct(models.Model):
    """
    Model untuk top selling products per retailer
    """
    _name = 'distribution_channel.pos_sales_report_product'
    _description = 'PoS Top Selling Products'
    _auto = False
    _order = 'total_sales desc'

    name = fields.Char('Product', readonly=True)

    retailer_company_id = fields.Many2one(
        'res.company',
        string='Retailer',
        readonly=True
    )

    product_id = fields.Many2one(
        'product.product',
        string='Product',
        readonly=True
    )

    total_quantity = fields.Float(
        'Quantity Sold',
        readonly=True
    )

    total_sales = fields.Float(
        'Total Sales',
        readonly=True
    )

    average_price = fields.Float(
        'Average Price',
        readonly=True
    )

    def init(self):
        """Create top products view"""
        self.env.cr.execute("""
            DROP VIEW IF EXISTS distribution_channel_pos_sales_report_product
        """)
        
        self.env.cr.execute("""
            CREATE VIEW distribution_channel_pos_sales_report_product AS (
                SELECT
                    row_number() OVER (ORDER BY po.company_id, SUM(pol.price_subtotal_incl) DESC) as id,
                    pt.name as name,
                    po.company_id as retailer_company_id,
                    pol.product_id as product_id,
                    SUM(pol.qty) as total_quantity,
                    SUM(pol.price_subtotal_incl) as total_sales,
                    AVG(pol.price_unit) as average_price
                FROM pos_order_line pol
                JOIN pos_order po ON pol.order_id = po.id
                JOIN product_product pp ON pol.product_id = pp.id
                JOIN product_template pt ON pp.product_tmpl_id = pt.id
                WHERE po.state IN ('paid', 'posted', 'invoiced')
                GROUP BY po.company_id, pol.product_id, pt.name
            )
        """)