from odoo import models, fields, api, exceptions, _
from datetime import timedelta, datetime
import logging

_logger = logging.getLogger(__name__)


class IloProductionHarvesting(models.Model):
    _name = 'ilo.production.harvesting'
    _description = 'Produksi Ekstraksi'
    _inherit = ['portal.mixin', 'mail.thread', 'mail.activity.mixin']

    name = fields.Char(string="Nama")
    employee_id = fields.Many2one(
        'res.partner', 
        string="Petani(**)", 
        domain="[('ilo_associate', '=', 'farmers')]",
        required=True #Update
    )
    employee_ilo_associate = fields.Selection(
        selection=[
            ('farmers', 'Petani'),
            ('agent', 'Agen'),
            ('koperasi', 'Koperasi'),
            ('ugreen', 'UGreen'),
            ('green', 'Green'),
        ],
        string='Kode Asosiasi',
        related='employee_id.ilo_associate',
        store=True
    )
    produce_product = fields.Many2one('product.product', string="Produk Tanam(**)")
    planting_produce_quantity = fields.Float(string="Kuantitas dari Penanaman(**)", store=True)
    uom = fields.Many2one('uom.uom', string="Satuan Ukur", default=lambda self: self.env.ref('uom.product_uom_kgm').id)
    production_identifier = fields.Char(string="ID Produksi")
    state = fields.Selection([('draft', 'Draf'), ('in_progress', 'Sedang Proses'), ('done', 'Selesai')], string="Status", default='draft')

    # New field to link with ilo.production_monitoring
    monitoring_id = fields.Many2one('ilo.production_monitoring', string="Pemantauan Produksi")
    user_note = fields.Text(string="Catatan Pengguna", help="Catatan yang menjelaskan alasan pembaruan kuantitas.")

    # New Fields
    asset_id    = fields.Many2one('ilo.assets', string="Lahan Terpakai")
    coordinates = fields.Char(string='Koordinat Lokasi', related='asset_id.coordinates', store=True)
    address     = fields.Text(string='Alamat Lokasi Produksi', related='asset_id.address', store=True)
    area_ha     = fields.Float(string='Luas Lahan', store=True)
    area_uom    = fields.Many2one('uom.uom', string="Satuan Luas", default=9, store=True)
    # harvesting_method = fields.Selection([('manual', 'Manual'), ('machine', 'Mesin')], string="Metode Panen")
    extraction_method = fields.Selection([
        ('penyulingan_drum', 'Penyulingan Drum(Tradisional)'), 
        ('penyulingan_stainless', 'Penyulingan Stainless(Modern)'),
        ('other_methods', 'Metode Lainnya')
        ], string="Metode Ekstraksi(**)")
    date_started = fields.Datetime(string="Tanggal Mulai Produksi", default=fields.Datetime.now)
    date_harvested = fields.Datetime(string="Tanggal Akhir Produksi")
    date_created = fields.Datetime(string="Tanggal Dibuat", default=fields.Datetime.now, readonly=True)
    date_modified = fields.Datetime(string="Tanggal Terakhir Dimodifikasi", readonly=True)
    date_actual = fields.Datetime(string='Tanggal Selesai Aktual Produksi')
    date_missed = fields.Float(string="Tanggal Terlambat", compute='_compute_date_missed', store=True)
    date_missed_display = fields.Char(string="Tanggal Terlambat", compute='_compute_date_missed_display', store=False)

    product_loss = fields.Float(string="Kehilangan Produk", compute='_compute_product_loss')
    weather_conditions = fields.Selection(
        [
            ('dry', 'Musim Kemarau'),
            ('rainy', 'Musim Hujan'),
            ('transition', 'Musim Pancaroba')
        ],
        string="Kondisi Cuaca(**)"
    )
    environment_conditions = fields.Selection(
        [
            ('optimal', 'Optimal'), 
            ('humid', 'Lembab'), 
            ('dry', 'Kering'), 
            ('cold', 'Dingin')
            ], 
            string="Kondisi Lingkungan(**)")
    batch_code = fields.Char(string="Kode Batch")
    kabupaten_id = fields.Many2one('res.kabupaten', string='Kabupaten/Kota', help="Kabupaten atau Kota tempat penanaman produksi berada.")
    final_product = fields.Many2one('product.product', string="Produk Akhir")  # Update here
    actual_final_quantity=fields.Float(string='Kuantitas Akhir Aktual')
    # percentage_extracted_quantity = fields.Float(string="Persentase Kuantitas yang Diekstrak", default=20)  # Default to 20%
    # extracted_quantity = fields.Float(string="Kuantitas yang Diekstrak", compute='_compute_extracted_quantity', store=True)
    percentage_final_quantity = fields.Float(string="Persentase Kuantitas Akhir", default=0.025)  # Default to 2.5%
    final_quantity = fields.Float(string="Kuantitas Akhir Perkiraan(**)", compute='_compute_final_quantity', store=True)

    product_quality = fields.Selection(
        [
            ('excellent', 'Sangat Baik'),
            ('good', 'Baik'),
            ('average', 'Rata-rata'),
            ('poor', 'Buruk'),
            ('very_poor', 'Sangat Buruk')
        ], string="Kualitas Produk", compute='_compute_product_quality'
    )
    completion_percentage = fields.Float(string="Persentase Penyelesaian", compute='_compute_completion_percentage', store=True)
    # New Fields
    production_harvesting_image= fields.Binary(string='Ambil Foto Produksi')
    production_harvesting_image_url= fields.Char(string='URL Gambar Panen', compute='_compute_production_harvesting_image_url')

    # Add the yield_percentage field
    yield_percentage = fields.Float(string='Persentase Produksi Aktual', compute='_compute_yield_percentage', store=True)


    @api.onchange('asset_id')
    def _onchange_asset_id(self):
        if self.asset_id:
            self.kabupaten_id = self.asset_id.kabupaten_id
            
    # Migration method
    @api.model
    def migrate_weather_conditions(self):
        """Migrate data from old environment_conditions to new weather_conditions."""
        # Define the mapping of old values to new values
        mapping = {
            'optimal': 'dry',         # 'Optimal' is mapped to 'Dry Season'
            'humid': 'rainy',         # 'Humid' is mapped to 'Rainy Season'
            'dry': 'dry',             # 'Dry' remains 'Dry Season'
            'cold': 'transition',     # 'Cold' is mapped to 'Transition Season'
        }

        # Search for all records and apply the migration
        records_to_update = self.search([])
        for record in records_to_update:
            old_value = record.environment_conditions  # Access the old field
            if old_value in mapping:
                record.weather_conditions = mapping[old_value]  # Update to the new field value

        _logger.info(_("Weather conditions migration completed. Updated %s records."), len(records_to_update))

    @api.constrains('employee_id')
    def _check_employee_status(self):
        for record in self:
            if record.employee_id:
                if record.employee_id.state != 'confirm' or record.employee_id.ilo_state != 'active':
                    raise exceptions.ValidationError(
                        f"Petani {record.employee_id.name} harus memiliki status 'Confirmed' dan 'Active' untuk mencatat produksi."
                    )


    @api.depends('date_missed')
    def _compute_date_missed_display(self):
        for record in self:
            if record.date_missed:
                record.date_missed_display = f"{record.date_missed} days"
            else:
                record.date_missed_display = "0 days"


    @api.depends('date_actual', 'date_harvested')
    def _compute_date_missed(self):
        for record in self:
            if record.date_actual and record.date_harvested:
                # Extract only the date (ignoring the time) from the datetime fields
                planned_finish_date = record.date_harvested.date()  # Extract date only
                actual_finish_date = record.date_actual.date()  # Extract date only

                # Calculate the difference in days between actual finish date and planned finish date
                delta = (actual_finish_date - planned_finish_date).days

                # Set the computed value of 'date_missed' as a float (number of days)
                record.date_missed = float(delta)
            else:
                # If either date is missing, set the missed date to 0
                record.date_missed = 0.0

    @api.depends('production_harvesting_image')
    def _compute_production_harvesting_image_url(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        for record in self:
            # record.image_1920_url = f"{base_url}/web/image?model=res.partner&id={record.id}&field=image_1920"
            if record.production_harvesting_image:
                record.production_harvesting_image_url = f"{base_url}/production_harvesting/image/{record.id}"
            else:
                record.production_harvesting_image_url = False

    @api.depends('date_started', 'date_harvested', 'state')
    def _compute_completion_percentage(self):
        """Compute completion percentage based on the Production timeline."""
        for record in self:
            if record.state == 'done':
                record.completion_percentage = 1.0  # 100% as 1.0
                continue

            now = fields.Datetime.now()

            if record.date_started:
                start_date = fields.Datetime.to_datetime(record.date_started)
            else:
                start_date = False

            if record.date_harvested:
                finish_date = fields.Datetime.to_datetime(record.date_harvested)
            else:
                finish_date = False

            if not start_date or not finish_date or now < start_date:
                record.completion_percentage = 0.0  # 0%
            elif now >= finish_date:
                record.completion_percentage = 1.0  # 100% as 1.0
            else:
                total_duration = (finish_date - start_date).days
                elapsed_duration = (now - start_date).days
                # Now completion_percentage is a fraction from 0 to 1
                record.completion_percentage = min(1.0, elapsed_duration / total_duration)


    @api.depends('actual_final_quantity', 'planting_produce_quantity')
    def _compute_yield_percentage(self):
        for record in self:
            if record.planting_produce_quantity > 0:
                # Calculate yield percentage
                record.yield_percentage = record.actual_final_quantity / record.planting_produce_quantity
            else:
                record.yield_percentage = 0  # Avoid division by zero

    @api.depends('actual_final_quantity', 'planting_produce_quantity', 'yield_percentage')
    def _compute_product_quality(self):
        for record in self:
            if record.planting_produce_quantity > 0:
                # Determine product quality based on the yield_percentage field
                if record.yield_percentage > 0.03:
                    record.product_quality = 'excellent'
                elif 0.025 < record.yield_percentage <= 0.03:
                    record.product_quality = 'good'
                elif 0.02 <= record.yield_percentage <= 0.025:
                    record.product_quality = 'average'
                elif 0.015 <= record.yield_percentage < 0.02:
                    record.product_quality = 'poor'
                else:
                    record.product_quality = 'very_poor'
            else:
                record.product_quality = 'very_poor'  # Default if planting_produce_quantity is zero to avoid division error

    @api.depends('actual_final_quantity', 'final_quantity')
    def _compute_product_loss(self):
        for record in self:
            if record.final_quantity and record.actual_final_quantity > record.final_quantity:
                # No loss if actual is greater than expected
                record.product_loss = 0
            else:
                # Calculate the loss as the difference when final_quantity is greater
                record.product_loss = max(0, record.final_quantity - record.actual_final_quantity) if record.final_quantity else 0

    # @api.depends('planting_produce_quantity', 'percentage_extracted_quantity')
    # def _compute_extracted_quantity(self):
    #     """Compute extracted quantity based on the input percentage."""
    #     for record in self:
    #         if record.state != 'done':  # Prevent modifications if done
    #             if record.planting_produce_quantity:
    #                 record.extracted_quantity = (record.percentage_extracted_quantity / 100.0) * record.planting_produce_quantity
    #             else:
    #                 record.extracted_quantity = 0  # Reset if no planting_produce_quantity

    @api.depends('planting_produce_quantity', 'percentage_final_quantity')
    def _compute_final_quantity(self):
        """Compute the final product quantity based on planting produce quantity and percentage."""
        for record in self:
            record.final_quantity = (
                record.percentage_final_quantity * record.planting_produce_quantity
                if record.planting_produce_quantity else 0
            )


    
    @api.onchange('final_quantity', 'planting_produce_quantity', 'percentage_final_quantity')
    def _onchange_final_values(self):
        """Adjust percentage, planting quantity, or final quantity dynamically based on changes."""
        for record in self:
            if record.final_quantity and record.percentage_final_quantity:
                # Calculate planting_produce_quantity when final_quantity is entered
                record.planting_produce_quantity = (
                    record.final_quantity / record.percentage_final_quantity
                    if record.percentage_final_quantity
                    else 0
                )
            elif record.planting_produce_quantity and record.final_quantity:
                # Calculate percentage_final_quantity if planting_produce_quantity and final_quantity exist
                record.percentage_final_quantity = (
                    (record.final_quantity / record.planting_produce_quantity)
                    if record.planting_produce_quantity
                    else 0
                )
            elif record.planting_produce_quantity and record.percentage_final_quantity:
                # Calculate final_quantity if planting_produce_quantity and percentage_final_quantity exist
                record.final_quantity = (
                    record.percentage_final_quantity * record.planting_produce_quantity
                    if record.planting_produce_quantity
                    else 0
                )


    @api.onchange('employee_id')
    def _onchange_employee_id(self):
        if self.employee_id:
            # Search for assets linked to the selected employee
            assets = self.env['ilo.assets'].search(
                [('employee_id', '=', self.employee_id.id)],
                order='create_date desc'
            )
            if assets:
                # Automatically select the latest asset
                self.asset_id = assets[0].id
            else:
                # Clear the asset_id field if no assets are found
                self.asset_id = False

            # Return a domain to restrict selectable assets
            return {
                'domain': {'asset_id': [('id', 'in', assets.ids)]}
            }
        else:
            # Clear the asset_id field and return an empty domain if no employee is selected
            self.asset_id = False
            return {
                'domain': {'asset_id': []}
            }



    @api.model
    def create(self, vals):
        """Create a new production record and set batch code and identifier."""
        _logger.debug("Creating production with vals: %s", vals)
        vals['date_created'] = fields.Datetime.now()

        # Get planting_produce_quantity
        planting_produce_quantity = vals.get('planting_produce_quantity', 0)
        _logger.debug("Planting produce quantity set to: %s", planting_produce_quantity)

        # Final product validation
        final_product_id = vals.get('final_product')
        if not final_product_id:
            raise exceptions.ValidationError(_("Final product ID is missing."))

        # Fetch the final product
        final_product = self.env['product.product'].browse(final_product_id)
        if not final_product.exists():
            raise exceptions.ValidationError(_("Final product not found."))

        # Get produce product
        produce_product_id = vals.get('produce_product')
        if not produce_product_id:
            raise exceptions.ValidationError(_("Produce product ID is missing."))

        produce_product = self.env['product.product'].browse(produce_product_id)
        if not produce_product.exists():
            raise exceptions.ValidationError(_("Produce product not found."))

        # Check employee assets
        employee_id = vals.get('employee_id')
        if not employee_id:
            raise exceptions.ValidationError(_("Employee ID is missing."))

        employee = self.env['res.partner'].browse(employee_id)
        assets = self.env['ilo.assets'].search([('employee_id', '=', employee.id)], limit=1)

        if not assets:
            raise exceptions.ValidationError(_("No assets found for the selected employee. Please create an asset first."))

        vals['asset_id'] = assets.id  # Automatically set the asset_id
        vals['batch_code'] = final_product.batch_code  # Set batch code

        # Generate production identifier
        production_identifier = self._generate_production_identifier(employee_id, final_product_id, planting_produce_quantity)
        vals['production_identifier'] = production_identifier
        vals['name'] = production_identifier  # Directly set the name as production identifier

        # Set default percentages if not provided
        # vals.setdefault('percentage_extracted_quantity', 20)  # Default to 20%
        vals.setdefault('percentage_final_quantity', 2.5)  # Default to 2.5%

        # Call the superclass create method
        record = super(IloProductionHarvesting, self).create(vals)

        # Manually compute extracted and final quantities
        # record._compute_extracted_quantity()
        record._compute_final_quantity()

        return record

    def write(self, vals):
        """Override the write method to enforce rules."""
        # Automatically update the last modified date
        vals['date_modified'] = fields.Datetime.now()

        # Call the original write method to apply the changes
        return super().write(vals)



    def action_confirm(self):
        """Confirm the harvesting process and set asset to 'In Progress'."""
        asset = self.asset_id

        # # Ensure extracted quantity is provided
        # if not self.extracted_quantity and not self.percentage_extracted_quantity:
        #     raise exceptions.ValidationError(_("Please input either extracted quantity or percentage extracted quantity."))

        # # Calculate extracted quantity if percentage is provided
        # if self.percentage_extracted_quantity:
        #     self.extracted_quantity = (self.planting_produce_quantity * self.percentage_extracted_quantity) / 100

        # Ensure final quantity is provided
        if not self.final_quantity and not self.percentage_final_quantity:
            raise exceptions.ValidationError(_("Please input either final product quantity or percentage final product quantity."))

        # Calculate final quantity if percentage is provided
        if self.percentage_final_quantity:
            self.final_quantity = (self.planting_produce_quantity * self.percentage_final_quantity) / 100

        # Set asset status to 'In Progress' and update production state
        asset.set_in_progress(process_type='harvesting')
        self.state = 'in_progress'

        # Locate the stock location associated with the employee
        stock_location = self.env['ilo.stock_location'].search([('employee_id', '=', self.employee_id.id)], limit=1)
        if not stock_location:
            raise exceptions.ValidationError(_("No stock location found for the employee."))

        _logger.debug("Stock location found: %s (ID: %s)", stock_location.name, stock_location.id)

        try:
            # Get the quant for the produced product in the employee's stock location
            produce_quant = self.env['ilo.quant'].search([('product_id', '=', self.produce_product.id), ('location_id', '=', stock_location.id)], limit=1)

            # Ensure there is enough stock available
            if not produce_quant:
                raise exceptions.UserError(_("No quant found for product %s in location %s." % (self.produce_product.name, stock_location.name)))

            if produce_quant.quantity_available < self.planting_produce_quantity:
                raise exceptions.UserError(_("Insufficient stock for produce product in the location. Available: %s, Trying to deduct: %s" % 
                                            (produce_quant.quantity_available, self.planting_produce_quantity)))

            # Adjust the quantity in ilo.quant
            produce_quant.adjust_quantity_available(-self.planting_produce_quantity)

            _logger.info("Harvesting confirmed. Deducted quantity: %s from produce product: %s", self.planting_produce_quantity, self.produce_product.name)

        except exceptions.ValidationError as e:
            _logger.error("Validation error occurred during harvesting confirmation: %s", e)
            raise
        except Exception as e:
            _logger.error("An error occurred while confirming the harvesting process: %s", e)
            raise


    def action_mark_done(self):
        """Mark the harvesting process as done and update asset to 'Inactive' if no other active harvestings exist."""
        _logger.info("Starting to mark harvesting as done for production ID: %s", self.id)

        # Calculate final quantity based directly on planting produce quantity and percentage_final_quantity
        if not self.final_quantity and self.percentage_final_quantity:
            self.final_quantity = self.planting_produce_quantity * self.percentage_final_quantity
            _logger.debug("Estimated Final quantity calculated as: %s", self.final_quantity)

        # Validate actual final quantity
        if not self.actual_final_quantity:
            raise exceptions.ValidationError(_("Actual Final Quantity must be entered before completing the harvesting."))

        _logger.info("Actual Final quantity is: %s", self.actual_final_quantity)
        
        # Mark production as done
        self.date_actual = fields.Datetime.now()
        self.state = 'done'

        # Check if this is the last active harvesting for the asset
        other_active_harvestings = self.env['ilo.production.harvesting'].search([
            ('asset_id', '=', self.asset_id.id),
            ('id', '!=', self.id),
            ('state', '=', 'in_progress')
        ])
        if not other_active_harvestings:
            # No other active harvestings; set the asset to inactive for harvesting
            self.asset_id.set_inactive(process_type='harvesting')

        _logger.info("Harvesting marked as done and asset harvesting status updated if applicable.")

        # Get the stock location associated with the employee
        stock_location = self.env['ilo.stock_location'].search([('employee_id', '=', self.employee_id.id)], limit=1)
        if not stock_location:
            raise exceptions.ValidationError(_("No stock location found for the employee."))

        _logger.debug("Stock location found: %s (ID: %s)", stock_location.name, stock_location.id)

        try:
            # Get or create the quant for the final product in the employee's stock location
            final_quant = self.env['ilo.quant'].search([('product_id', '=', self.final_product.id), ('location_id', '=', stock_location.id)], limit=1)

            if not final_quant:
                # If no quant exists, create a new one
                final_quant = self.env['ilo.quant'].create({
                    'product_id': self.final_product.id,
                    'quantity_available': 0,
                    'location_id': stock_location.id,
                    'product_uom_id': self.final_product.uom_id.id,
                })

            # Adjust the quantity for the final product
            final_quant.adjust_quantity_available(self.actual_final_quantity)

            _logger.info("Actual Final product quantity updated. Added quantity: %s for final product: %s", self.actual_final_quantity, self.final_product.name)

        except exceptions.ValidationError as e:
            _logger.error("Validation error occurred during final product quantity adjustment: %s", e)
            raise
        except Exception as e:
            _logger.error("An error occurred while marking the harvesting process as done: %s", e)
            raise


    def _generate_production_identifier(self, employee_id, final_product_id, quantity):
        """Generate a unique production identifier based on employee and final product details."""
        employee = self.env['res.partner'].browse(employee_id)
        ilo_association_code = employee.ilo_associate_code or 'F000'

        final_product = self.env['product.product'].browse(final_product_id)
        batch_code = final_product.batch_code

        # Search for existing productions to determine the next sequence number
        existing_productions = self.search([
            ('employee_id', '=', employee_id),
            ('final_product', '=', final_product_id)
        ])
        sequence_number = len(existing_productions) + 1  # Increment based on existing records

        # Ensure the sequence number is three digits, padded with zeros if necessary
        sequence_number_str = str(sequence_number).zfill(3)

        # Format the production identifier as specified
        return f"HASIL-{ilo_association_code}-{batch_code}-{int(quantity)}-{sequence_number_str}"

