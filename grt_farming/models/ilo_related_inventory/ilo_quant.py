from odoo import models, fields, api, exceptions
import logging

_logger = logging.getLogger(__name__)

class IloQuant(models.Model):
    _name = 'ilo.quant'
    _description = 'ILO Custom Inventory Quant'

    name = fields.Char(string='Name')
    # Product Information
    product_id = fields.Many2one('product.product', string='Product', required=True)
    product_name = fields.Char(string='Product Name', compute='_compute_product_info', store=True)
    batch_code = fields.Char(string='Batch Code', compute='_compute_product_info', store=True)
    product_batch_code= fields.Char(string='Product Batch Code', related='product_id.batch_code')
    product_uom_id = fields.Many2one('uom.uom', string='Unit of Measure', default=lambda self: self.env.ref('uom.product_uom_kgm').id, required=True)
    product_image = fields.Binary(string='Product Image', compute='_compute_product_image', store=True)
    product_image_url = fields.Char(string="Product Image URL", compute="_compute_product_image_url", store=True)
 

    # Quantity and Unit
    availability_status = fields.Char(string='Availability Status', compute='_compute_availability_status', store=True)
    quantity_available = fields.Float(string='Product Available', required=True, store=True)
    quantity_sold = fields.Float(string='Product Sold', compute='_compute_quantities_sold', store=True)

    # Additional fields
    location_id = fields.Many2one('ilo.stock_location', string='Location', required=True)
    warehouse_id = fields.Many2one('ilo.warehouse', string='Warehouse', ondelete='cascade')
    ownership_line_ids = fields.One2many('ownership.line', 'quant_id', string='Ownership Line')
    employee_id = fields.Many2one(related='location_id.employee_id', comodel_name='res.partner', string='Employee')

    @api.depends('product_id')
    def _compute_product_image(self):
        for record in self:
            if record.product_id:
                record.product_image = record.product_id.image_1920
                _logger.info("Computed product image for product_id %s in ilo.quant record %s", record.product_id.id, record.id)
            else:
                record.product_image = False
                _logger.info("No product_id set for ilo.quant record %s", record.id)

    @api.depends('product_id.image_1920_url')
    def _compute_product_image_url(self):
        """Compute product_image_url from product_id's image URL."""
        for record in self:
            record.product_image_url = record.product_id.image_1920_url if record.product_id else False


    @api.model
    def backfill_product_images(self, record_ids=None):
        """Backfill product images for existing ilo.quant records."""
        # Use the provided record_ids or fetch all if None
        if record_ids:
            records = self.browse(record_ids)  # Use the specific records provided
        else:
            records = self.search([])  # Fetch all ilo.quant records

        for record in records:
            if record.product_id:
                record.product_image = record.product_id.image_1920
                _logger.info("Backfilled product image for ilo.quant ID %s with product_id %s", record.id, record.product_id.id)
            else:
                record.product_image = False
                _logger.info("No product_id set for ilo.quant record %s", record.id)



    @api.depends('quantity_available')
    def _compute_availability_status(self):
        """Compute availability status based on quantity_available."""
        for record in self:
            # Set status as "Available" if quantity_available is more than 0, else "Not Available"
            record.availability_status = "Available" if record.quantity_available > 0 else "Not Available"

    @api.depends('product_id')
    def _compute_product_info(self):
        for record in self:
            _logger.debug("Computing product info for IloQuant ID: %s", record.id)
            if record.product_id:
                record.product_name = record.product_id.name
                record.batch_code = record.product_id.batch_code or 'N/A'
                _logger.info("Product Name: %s, Batch Code: %s", record.product_name, record.batch_code)
            else:
                record.product_name = ''
                record.batch_code = ''

    @api.onchange('product_id')
    def _onchange_product_id(self):
        _logger.debug("Onchange triggered for product_id in IloQuant ID: %s", self.id)
        if self.product_id:
            self.product_name = self.product_id.name
            self.batch_code = self.product_id.batch_code or 'N/A'
            _logger.info("Changed Product Name to: %s, Batch Code to: %s", self.product_name, self.batch_code)

    @api.model
    def create(self, vals):
        _logger.debug("Creating IloQuant with vals: %s", vals)
        record = super(IloQuant, self).create(vals)
        _logger.info("Created IloQuant ID: %s", record.id)
        return record

    # Custom methods for updating quantities
    def _update_quantity_available(self, quantity_change):
        _logger.debug("Updating quantity available for IloQuant ID: %s by %s", self.id, quantity_change)
        if self.quantity_available + quantity_change < 0:
            _logger.error('Cannot update quantity available: negative quantity would result.')
            raise exceptions.UserError('The available quantity cannot be negative.')
        self.quantity_available += quantity_change
        _logger.info("New quantity available for IloQuant ID %s: %s", self.id, self.quantity_available)

    def _update_quantity_sold(self, quantity_sold):
        _logger.debug("Updating quantity sold for IloQuant ID: %s by %s", self.id, quantity_sold)
        if self.quantity_sold + quantity_sold < 0:
            _logger.error('Cannot update quantity sold: negative quantity would result.')
            raise exceptions.UserError('The sold quantity cannot be negative.')
        self.quantity_sold += quantity_sold
        _logger.info("New quantity sold for IloQuant ID %s: %s", self.id, self.quantity_sold)

    def adjust_quantity_available(self, quantity_change):
        """ Public method to adjust available quantity, checks if it can be updated """
        _logger.debug("Adjusting quantity available. Current: %s, Change: %s", self.quantity_available, quantity_change)
        self._update_quantity_available(quantity_change)
        _logger.debug("Adjusted quantity available for IloQuant ID %s: %s", self.id, self.quantity_available)

    def adjust_quantity_sold(self, quantity_sold):
        """ Public method to adjust sold quantity """
        _logger.debug("Adjusting quantity sold for IloQuant ID: %s by %s", self.id, quantity_sold)
        self._update_quantity_sold(quantity_sold)
        _logger.debug("Adjusted quantity sold for IloQuant ID %s: %s", self.id, self.quantity_sold)

    @api.model
    def update_quantities_on_stock_move(self, stock_move):
        """Update quantities based on a stock move."""
        _logger.debug("Updating quantities based on stock move for product ID: %s", stock_move.product_id.id)
        for quant in self.search([('product_id', '=', stock_move.product_id.id), ('location_id', '=', stock_move.source_location_id.id)]):
            if stock_move.movement_type == 'in':
                _logger.debug("Adjusting quantity available for IloQuant ID %s by %s (in movement)", quant.id, stock_move.quantity)
                quant.adjust_quantity_available(stock_move.quantity)
            elif stock_move.movement_type == 'out':
                _logger.debug("Adjusting quantity available for IloQuant ID %s by %s (out movement)", quant.id, -stock_move.quantity)
                quant.adjust_quantity_available(-stock_move.quantity)
