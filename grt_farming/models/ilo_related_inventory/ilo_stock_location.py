from odoo import models, fields, api, exceptions, _
import logging

_logger = logging.getLogger(__name__)

class ILOStockLocation(models.Model):
    _name = 'ilo.stock_location'
    _description = 'ILO Custom Stock Location'

    is_virtual = fields.Boolean(string='Is Virtual', default=False)
    name = fields.Char(string='Location Name', required=True)

    location_code = fields.Char(string='Location Code')
    address = fields.Char(string='Address')
    city = fields.Char(string='City')
    region = fields.Char(string='Region')
    country = fields.Char(string='Country')
    kabupaten_id = fields.Many2one('res.kabupaten', string='Kabupaten/Kota')
    kecamatan = fields.Char(string='Kecamatan')
    kelurahan = fields.Char(string='Kelurahan')
    employee_id = fields.Many2one('res.partner', string='Employee')
    employee_ilo_associate = fields.Char(
        string='ILO Associate', compute='_compute_employee_info', store=True
    )
    employee_ilo_associate_code = fields.Char(
        string='ILO Associate Code', compute='_compute_employee_info', store=True
    )
    employee_image = fields.Binary(string='Employee Image', compute='_compute_employee_image', store=True)
    employee_image_url = fields.Char(string='Image URL', compute='_compute_employee_image_url')

    # New warehouse relation field, mandatory with cascade deletion
    warehouse_id = fields.Many2one(
        'ilo.warehouse',
        string='Warehouse',
        ondelete='cascade',
        help="The warehouse this location belongs to."
    )
    # product_id = fields.Many2many('product.product', 
    #                               string='Product Contain of', 
    #                               compute='_compute_product_ids', 
    #                               store=True)
    # product_uom_id = fields.Many2one('uom.uom', string='Unit of Measure', default=lambda self: self.env.ref('uom.product_uom_kgm').id)
    quantity_available = fields.Float(string='Available Quantity', compute='_compute_quantities', store=True)
    quantity_sold = fields.Float(string='Sold Quantity', compute='_compute_quantities', store=True)

    # product_in = fields.Many2many('product.product', 'ilo_stock_location_product_in_rel', 'location_id', 'product_id', string='Products In')
    # product_out = fields.Many2many('product.product', 'ilo_stock_location_product_out_rel', 'location_id', 'product_id', string='Products Out')
    stock_move_ids = fields.One2many('ilo.stock_move', 'location_id', string="Stock Moves Out")
    stock_move_dest_ids = fields.One2many('ilo.stock_move', 'location_dest_id', string="Stock Moves In")
    # movement_date = fields.Datetime(string='Last Movement Date')
    # source_location = fields.Many2one('ilo.stock_location', string='Source Location')
    # destination_location = fields.Many2one('ilo.stock_location', string='Destination Location')
    stock_quant_ids = fields.One2many('ilo.quant', 'location_id', string='Stock Quants')


    @api.depends('employee_id')
    def _compute_employee_image(self):
        for record in self:
            if record.employee_id and record.employee_id.image_1920:
                record.employee_image = record.employee_id.image_1920
                _logger.info("Computed Employee photo image for employee_id %s in ilo.stock_location record %s", record.employee_id.id, record.id)
            else:
                record.employee_image = False
                _logger.info("No employee_image set for ilo.stock_location record %s", record.id)

    @api.depends('employee_id')
    def _compute_employee_image_url(self):
        for record in self:
            if record.employee_id and record.employee_id.image_1920_url:
                record.employee_image_url = record.employee_id.image_1920_url
            else:
                record.employee_image_url = False

    @api.model
    def backfill_employee_images(self, record_ids=None):
        """Backfill employee images for existing ilo.stock_location records."""
        # Use the provided record_ids or fetch all if None
        if record_ids:
            records = self.browse(record_ids)  # Use the specific records provided
        else:
            records = self.search([])  # Fetch all ilo.stock_location records

        for record in records:
            if record.employee_id:
                # Set the employee_image based on the related employee
                record.employee_image = record.employee_id.image_1920
                _logger.info("Backfilled employee image for ilo.stock_location ID %s with employee_id %s", record.id, record.employee_id.id)
            else:
                record.employee_image = False
                _logger.info("No employee_id set for ilo.stock_location record %s", record.id)




    @api.depends('employee_id.ilo_associate', 'employee_id.ilo_associate_code')
    def _compute_employee_info(self):
        for record in self:
            # Check if employee_id exists, then retrieve related fields
            if record.employee_id:
                # Fetch the display label of ilo_associate selection field
                ilo_associate = record.employee_id.ilo_associate
                record.employee_ilo_associate = dict(record.employee_id._fields['ilo_associate'].selection).get(ilo_associate)
                # Fetch the associate code directly
                record.employee_ilo_associate_code = record.employee_id.ilo_associate_code
            else:
                # Reset fields if no employee_id is linked
                record.employee_ilo_associate = ''
                record.employee_ilo_associate_code = ''


    # @api.depends('stock_quant_ids.product_id')
    # def _compute_product_ids(self):
    #     for location in self:
    #         # Collect all unique product_ids from the related ilo.quant records
    #         product_ids = location.stock_quant_ids.mapped('product_id').ids
    #         location.product_id = [(6, 0, product_ids)]

    @api.depends('stock_quant_ids.quantity_available', 'stock_quant_ids.quantity_sold')
    def _compute_quantities(self):
        for location in self:
            # Sum quantity_available and quantity_sold from ilo.quant records for this location
            location.quantity_available = sum(location.stock_quant_ids.mapped('quantity_available'))
            location.quantity_sold = sum(location.stock_quant_ids.mapped('quantity_sold'))



    def deactivate_location(self):
        """Deactivate the stock location."""
        self.active = False

    @api.model
    def get_warehouse_by_name(self, warehouse_name):
        """Fetch warehouse record by name."""
        warehouse = self.env['ilo.warehouse'].search([('warehouse_name', '=', warehouse_name)], limit=1)
        if not warehouse:
            raise exceptions.ValidationError(f"No warehouse found with the name '{warehouse_name}'.")
        return warehouse