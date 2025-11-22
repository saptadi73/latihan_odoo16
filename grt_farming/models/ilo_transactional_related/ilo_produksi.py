from odoo import models, fields, api, exceptions
from odoo.tools import float_compare
import logging

_logger = logging.getLogger(__name__)

class ILOProduksi(models.Model):
    _name = 'ilo.production'
    _description = 'Production Management'

    production_order_id = fields.Char(string='Production Order ID', readonly=True, required=True, copy=False, default='New')
    employee_id = fields.Many2one('res.partner', string='Employee', required=True)
    asset_id = fields.Many2one('ilo.assets', string='Asset', readonly=True, help="The asset where the production occurs.")
    date_planned_start = fields.Datetime(string='Date Planned Start')
    date_planned_finished = fields.Datetime(string='Date Planned Finish')
    dashboard_id = fields.Many2one('ilo.dashboard', string='Dashboard')
    product_quantity = fields.Float(string='Product Quantity', required=True)
    product_id = fields.Many2one('product.product', string='Produced Product', required=True)
    product_uom_id = fields.Many2one('uom.uom', string='Unit of Measure', required=True)
    
    # New fields for extraction quantities
    extracted_quantity = fields.Float(string='Extracted Quantity')
    percentage_extracted_quantity = fields.Float(
        string='Percentage Extracted Quantity (%)',
        default=20.0  # Default value can be changed by user
    )
    
    # Final product quantities
    final_product_quantity = fields.Float(string='Final Product Quantity', readonly=True)
    percentage_final_product_quantity = fields.Float(
        string='Percentage Final Product Quantity (%)',
        default=2.5  # Default value can be changed by user
    )
    batch_code = fields.Char(string='Batch Code', readonly=True, copy=False)
    production_identifier = fields.Char(string='Production Identifier', readonly=True, copy=False)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('in_progress', 'In Progress'),
        ('done', 'Done'),
        ('late', 'Late')
    ], string='Status', default='draft', tracking=True, readonly=True)
    completion_percentage = fields.Float(string='Completion Percentage', compute='_compute_completion_percentage', store=True)
    growth_stage = fields.Selection([
        ('germination_early_growth', 'Germination and Early Growth'),
        ('rapid_growth', 'Rapid Growth'),
        ('flowering_preparation', 'Flowering Preparation and Initiation'),
        ('harvesting', 'Harvesting'),
        ('completed', 'Completed')
    ], string='Growth Stage', compute='_compute_growth_stage', store=True)

    
    @api.depends('date_planned_start', 'date_planned_finished', 'state')
    def _compute_completion_percentage(self):
        """Compute how much of the production time has passed as a percentage."""
        for record in self:
            if record.state == 'done':
                record.completion_percentage = 100.0
                continue

            now = fields.Datetime.now()
            
            if not record.date_planned_start or not record.date_planned_finished or now < record.date_planned_start:
                record.completion_percentage = 0.0
            elif now >= record.date_planned_finished:
                record.completion_percentage = 100.0
            else:
                total_duration = (record.date_planned_finished - record.date_planned_start).total_seconds()
                elapsed_duration = (now - record.date_planned_start).total_seconds()
                record.completion_percentage = min(100.0, (elapsed_duration / total_duration) * 100)

    @api.depends('completion_percentage')
    def _compute_growth_stage(self):
        """Compute the growth stage based on the completion percentage."""
        for record in self:
            if record.completion_percentage < 25:
                record.growth_stage = 'germination_early_growth'
            elif 25 <= record.completion_percentage < 50:
                record.growth_stage = 'rapid_growth'
            elif 50 <= record.completion_percentage < 75:
                record.growth_stage = 'flowering_preparation'
            elif 75 <= record.completion_percentage < 100:
                record.growth_stage = 'harvesting'
            else:
                record.growth_stage = 'completed'
    
    @api.onchange('product_quantity', 'extracted_quantity', 'percentage_extracted_quantity')
    def _compute_extracted_quantity(self):
        """Compute extracted quantity based on the input percentage or set the percentage based on quantity."""
        for record in self:
            if record.product_quantity:
                # If the user modifies percentage but not extracted_quantity
                if record.percentage_extracted_quantity and not record.extracted_quantity:
                    record.extracted_quantity = (record.percentage_extracted_quantity / 100.0) * record.product_quantity
                
                # If the user modifies extracted_quantity but not percentage
                elif record.extracted_quantity and not record.percentage_extracted_quantity:
                    record.percentage_extracted_quantity = (record.extracted_quantity / record.product_quantity) * 100

    @api.onchange('extracted_quantity', 'final_product_quantity', 'percentage_final_product_quantity')
    def _compute_final_product_quantity(self):
        """Compute the final product quantity based on the extracted quantity and percentage or adjust the percentage based on quantity."""
        for record in self:
            if record.extracted_quantity:
                # If the user modifies percentage but not final_product_quantity
                if record.percentage_final_product_quantity and not record.final_product_quantity:
                    record.final_product_quantity = (record.percentage_final_product_quantity / 100.0) * record.extracted_quantity
                
                # If the user modifies final_product_quantity but not percentage
                elif record.final_product_quantity and not record.percentage_final_product_quantity:
                    record.percentage_final_product_quantity = (record.final_product_quantity / record.extracted_quantity) * 100

    @api.onchange('employee_id')
    def _onchange_employee_id(self):
        """Automatically set the asset_id based on the selected employee_id."""
        if self.employee_id:
            # Search for the asset associated with the employee
            assets = self.env['ilo.assets'].search([('employee_id', '=', self.employee_id.id)], limit=1)
            if assets:
                self.asset_id = assets.id
            else:
                self.asset_id = False  # Clear the asset_id if no assets found

    @api.model
    def create(self, vals):
        """Create a new production record and set batch code and identifier."""
        product = self.env['product.product'].browse(vals['product_id'])
        
        if not product:
            raise exceptions.ValidationError("Product not found.")

        # Log product details
        _logger.info("Product UoM: %s", product.uom_id.name)

        # Search for the asset based on the employee_id
        employee = self.env['res.partner'].browse(vals['employee_id'])
        assets = self.env['ilo.assets'].search([('employee_id', '=', employee.id)], limit=1)

        if not assets:
            raise exceptions.ValidationError("No assets found for the selected employee. Please create an asset first.")

        vals['asset_id'] = assets.id  # Automatically set the asset_id
        
        # Log asset details
        asset = self.env['ilo.assets'].browse(vals['asset_id'])
        _logger.info("Asset ID: %s, Asset UoM: %s", asset.id, asset.uom_id.name)

        # Ensure UoM is set correctly
        if not product.uom_id:
            raise exceptions.ValidationError("The product has no unit of measure set.")

        if not asset.uom_id:
            raise exceptions.ValidationError("The asset has no unit of measure set.")

        vals['batch_code'] = product.batch_code
        vals['product_uom_id'] = product.uom_id.id

        if vals.get('production_order_id', 'New') == 'New':
            vals['production_order_id'] = self.env['ir.sequence'].next_by_code('ilo.production') or 'New'
        
        vals['production_identifier'] = self._generate_production_identifier(
            employee_id=vals['employee_id'],
            product_id=vals['product_id'],
            quantity=vals['product_quantity'],
            production_order_id=vals['production_order_id']
        )

        return super(ILOProduksi, self).create(vals)
    
    def write(self, vals):
        """Override the write method to prevent modifications to done records."""
        for record in self:
            if record.state == 'done':
                raise exceptions.ValidationError("This production record is marked as done and cannot be modified.")
        return super(ILOProduksi, self).write(vals)

    def action_confirm(self):
        """Confirm the production order and set the related asset to 'In Progress'."""
        asset = self.asset_id

        # Log asset's production capacity and UoM
        _logger.info("Asset UoM: %s, Production Capacity: %s", asset.uom_id.name, asset.production_capacity)
        _logger.info("Production UoM: %s, Production Quantity: %s", self.product_uom_id.name, self.product_quantity)

        # Ensure one of the extraction fields is filled
        if not self.extracted_quantity and not self.percentage_extracted_quantity:
            raise exceptions.ValidationError("Please input either extracted quantity or percentage extracted quantity.")

        # Calculate the extracted quantity based on the percentage if provided
        if self.percentage_extracted_quantity:
            self.extracted_quantity = (self.product_quantity * self.percentage_extracted_quantity) / 100
            _logger.info("Extracted Quantity calculated from percentage: %s", self.extracted_quantity)

        # Ensure one of the final product quantity fields is filled
        if not self.final_product_quantity and not self.percentage_final_product_quantity:
            raise exceptions.ValidationError("Please input either final product quantity or percentage final product quantity.")

        # Calculate the final product quantity based on the percentage if provided
        if self.percentage_final_product_quantity:
            self.final_product_quantity = (self.extracted_quantity * self.percentage_final_product_quantity) / 100
            _logger.info("Final Product Quantity calculated from percentage: %s", self.final_product_quantity)

        # Force product UoM to match asset's UoM
        if self.product_uom_id != asset.uom_id:
            _logger.info("Changing Product UoM from '%s' to '%s'", self.product_uom_id.name, asset.uom_id.name)
            self.product_uom_id = asset.uom_id  # Set product_uom_id to match asset's UoM

        # Check if the UoMs belong to the same category
        if self.product_uom_id.category_id != asset.uom_id.category_id:
            raise exceptions.ValidationError(
                "The unit of measure '%s' defined on the order line doesn't belong to the same category as the unit of measure '%s' defined on the product." %
                (self.product_uom_id.name, asset.uom_id.name)
            )

        # Convert the production quantity to the asset's UoM
        production_qty_in_asset_uom = self.product_uom_id._compute_quantity(self.product_quantity, asset.uom_id)
        _logger.info("Converted Production Quantity in Asset UoM: %s", production_qty_in_asset_uom)

        # Check if the production quantity exceeds asset capacity
        if float_compare(production_qty_in_asset_uom, asset.production_capacity, precision_rounding=asset.uom_id.rounding) > 0:
            raise exceptions.ValidationError("Production quantity exceeds the asset's production capacity.")

        # Set asset to in progress and confirm the production
        asset.set_in_progress()
        self.state = 'in_progress'


    def action_mark_done(self):
        """Change state to 'Done' and set the related asset to 'Inactive'."""
        
        # Ensure final product quantity is calculated
        if not self.final_product_quantity and self.percentage_final_product_quantity:
            self.final_product_quantity = (self.extracted_quantity * self.percentage_final_product_quantity) / 100
            _logger.info("Final Product Quantity calculated from percentage: %s", self.final_product_quantity)

        if not self.final_product_quantity:
            raise exceptions.ValidationError("Final product quantity is not available. Ensure it is either input directly or derived from the percentage.")

        # Set completion percentage to 100% directly
        self.completion_percentage = 100.0
        
        # Change the state to 'done'
        self.state = 'done'
        
        # Set the asset to inactive
        self.asset_id.set_inactive()

        # Find the stock location for the employee
        stock_location = self.env['ilo.stock_location'].search([('employee_id', '=', self.employee_id.id)], limit=1)
        if not stock_location:
            raise exceptions.UserError("No stock location found for the employee.")
        
        # Create a new ilo.quant record
        ilo_quant = self.env['ilo.quant'].create({
            'location_id': stock_location.id,
            'product_id': self.product_id.id,
            'quantity_available': self.final_product_quantity,
            'batch_code': self.batch_code,
            'product_uom_id': self.product_uom_id.id
        })
        
        return ilo_quant


    def _generate_production_identifier(self, employee_id, product_id, quantity, production_order_id):
        """Generate a unique production identifier based on employee and product details."""
        employee = self.env['res.partner'].browse(employee_id)
        ilo_association_code = employee.ilo_associate_code or 'F000'
        product = self.env['product.product'].browse(product_id)
        batch_code = product.batch_code
        production_order_sequence = str(production_order_id).zfill(3)
        return f"{ilo_association_code}-{batch_code}-{production_order_sequence}-{int(quantity)}"

    @api.constrains('date_planned_start', 'date_planned_finished')
    def _check_dates(self):
        """Ensure planned finish date is after planned start date."""
        for record in self:
            if record.date_planned_finished and record.date_planned_finished < record.date_planned_start:
                raise exceptions.ValidationError("Planned finish date must be after the planned start date.")

    @api.onchange('date_planned_start', 'date_planned_finished')
    def _update_state(self):
        """Update the state based on the planned dates."""
        current_date = fields.Datetime.now()
        if self.state == 'done':
            return
        
        # Log the current state for debugging
        _logger.debug("Current Date: %s, Planned Start: %s, Planned Finish: %s", current_date, self.date_planned_start, self.date_planned_finished)

        # Check if date_planned_finished is not None and if it's in the past
        if self.date_planned_finished and self.date_planned_finished < current_date:
            self.state = 'late'
        # Check if both dates are not None and within the range
        elif self.date_planned_start and self.date_planned_finished and self.date_planned_start <= current_date <= self.date_planned_finished:
            self.state = 'in_progress'
        else:
            self.state = 'draft'

    @api.onchange('asset_id')
    def _onchange_asset_id(self):
        """Ensure that the production UoM matches the asset's UoM when an asset is selected."""
        if self.asset_id:
            self.product_uom_id = self.asset_id.uom_id.id
            _logger.info("UoM automatically set to match Asset UoM: %s", self.asset_id.uom_id.name)
