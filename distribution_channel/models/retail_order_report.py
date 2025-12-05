from odoo import models, fields, api


class RetailOrderReport(models.Model):
    """
    Report Model untuk analytics & reporting
    """
    _name = 'distribution_channel.retail_order.report'
    _description = 'Retail Order Report'
    _auto = False
    _order = 'create_date desc'

    name = fields.Char('Reference', readonly=True)
    retailer_company_id = fields.Many2one('res.company', 'Retailer', readonly=True)
    dc_company_id = fields.Many2one('res.company', 'DC', readonly=True)
    
    retailer_po_id = fields.Many2one('purchase.order', 'Retailer PO', readonly=True)
    dc_so_id = fields.Many2one('sale.order', 'DC SO', readonly=True)
    dc_po_id = fields.Many2one('purchase.order', 'DC PO', readonly=True)
    retailer_so_id = fields.Many2one('sale.order', 'Retailer SO', readonly=True)
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('complete', 'Complete Chain'),
        ('partial', 'Partial Chain'),
    ], 'Chain Status', readonly=True)
    
    total_qty = fields.Float('Total Qty', readonly=True)
    total_amount = fields.Float('Total Amount', readonly=True)
    
    order_chain_status = fields.Selection([
        ('complete', 'Complete'),
        ('partial', 'Partial'),
        ('missing', 'Missing'),
    ], 'Status', readonly=True)
    
    missing_links = fields.Text('Missing Links', readonly=True)
    create_date = fields.Datetime('Created', readonly=True)
    write_date = fields.Datetime('Updated', readonly=True)

    def init(self):
        """Create report view"""
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW distribution_channel_retail_order_report AS
            SELECT
                ro.id,
                ro.name,
                ro.retailer_company_id,
                ro.dc_company_id,
                ro.retailer_po_id,
                ro.dc_sales_order_id as dc_so_id,
                ro.dc_purchase_order_id as dc_po_id,
                ro.retailer_sales_order_id as retailer_so_id,
                ro.state,
                ro.total_qty,
                ro.total_amount,
                ro.order_chain_status,
                ro.missing_links,
                ro.create_date,
                ro.write_date
            FROM distribution_channel_retail_order ro
        """)