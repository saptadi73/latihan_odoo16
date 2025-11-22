from odoo import models, fields, api, exceptions
from datetime import timedelta, datetime
import logging

# Define the logger
_logger = logging.getLogger(__name__)

class IloProductionPlanting(models.Model):
    _name = 'ilo.production_planting'
    _description = 'Penanaman Produksi'
    _inherit = ['portal.mixin', 'mail.thread', 'mail.activity.mixin']

    # Informasi Umum
    name = fields.Char(string="Nama")
    production_identifier = fields.Char(string="ID Produksi")
    state = fields.Selection([('draft', 'Draft'), ('in_progress', 'Sedang Berlangsung'), 
                              ('done', 'Selesai'), ('canceled', 'Dibatalkan')], string="Status", default='draft')
    user_note = fields.Text(string="Catatan Pengguna")
    
    # Tanggal
    date_created = fields.Datetime(string="Tanggal Dibuat", default=fields.Datetime.now, readonly=True)
    date_modified = fields.Datetime(string="Tanggal Terakhir Diubah", readonly=True)
    date_actual = fields.Datetime(string="Tanggal Selesai Aktual")
    date_missed = fields.Float(string="Tanggal Terlewat", compute='_compute_date_missed', store=True)
    date_missed_display = fields.Char(string="Tanggal Terlambat", compute='_compute_date_missed_display', store=False)
    date_planned_start = fields.Date(string="Tanggal Mulai yang Direncanakan", default=fields.Date.today)
    date_planned_finish = fields.Date(string="Tanggal Selesai yang Direncanakan", 
                                      default=lambda self: fields.Date.today() + timedelta(days=120))
    
    # Kuantitas & Pengukuran
    plant = fields.Float(string='Batang ditanam')
    average_weight = fields.Float(string='Rata-rata Berat per Tanam(Kg)', default=3.0)    
    quantity = fields.Float(string="Estimasi Berat Basah(**)")
    drying_percentage = fields.Float(string="Persentase Pengeringan (%)", default=0.2)
    dry_quantity = fields.Float(string="Estimasi Berat Kering (Kg)", compute="_compute_quantities")
    actual_quantity = fields.Float(string='Kuantitas Aktual Kering(**)')
    actual_estimate_dry_quantity = fields.Float(string="Produk Loss Kering (kg)", compute='_compute_actual_estimate_dry_quantity', store=True)
    quantity_loss = fields.Float(string='Estimasi Jumlah Penyusutan', compute='_compute_loss_quantity')
    actual_drying_percentage = fields.Float(string="Persentase Pengeringan Aktual (%)", compute="_compute_actual_drying_percentage")
    completion_percentage = fields.Float(string="Persentase Penyelesaian", compute='_compute_completion_percentage', store=True)
    uom = fields.Many2one('uom.uom', string="Satuan Ukur", default=lambda self: self.env.ref('uom.product_uom_kgm').id)

    # Area & Lokasi
    area = fields.Float(
        string="Luas", 
        store=True)
    area_uom = fields.Many2one('uom.uom', string='Satuan Ukur Luas', default=9)
    kabupaten_id = fields.Many2one('res.kabupaten', string='Kabupaten/Kota')
    coordinates = fields.Char(string='Koordinat Lokasi', related='asset_id.coordinates', store=True)
    address = fields.Text(string='Alamat Lokasi Produksi', related='asset_id.address', store=True)
    weather_conditions = fields.Selection([('dry', 'Musim Kemarau'), ('rainy', 'Musim Hujan'), 
                                           ('transition', 'Musim Pancaroba')], string="Kondisi Cuaca")

    # Produk & Manajemen Aset
    produce_product = fields.Many2one('product.product', string="Produk yang Dihasilkan")
    asset_id = fields.Many2one('ilo.assets', string="Lahan Dipakai")
    production_planting_image = fields.Binary(string='Ambil Foto Produksi')
    production_planting_image_url = fields.Char(string='URL Gambar Penanaman', compute='_compute_production_planting_image_url')

    # Informasi Karyawan
    employee_id = fields.Many2one('res.partner', string="Nama Petani", domain="[('ilo_associate', '=', 'farmers')]", required=True)
    employee_ilo_associate = fields.Selection([('farmers', 'Petani'), ('agent', 'Agen'), ('koperasi', 'Koperasi'),
                                               ('ugreen', 'UGreen'), ('green', 'Green')], string='Kode Asosiasi', 
                                               related='employee_id.ilo_associate', store=True)

    # Pemantauan
    monitoring_id = fields.Many2one('ilo.production_monitoring', string="Pemantauan Produksi")


    @api.depends('plant', 'average_weight', 'drying_percentage')
    def _compute_quantities(self):
        for record in self:
            # Compute wet quantity
            record.quantity = record.plant * record.average_weight if record.plant and record.average_weight else 0
            # Compute dry quantity based on drying percentage
            record.dry_quantity = record.quantity * record.drying_percentage  if record.quantity and record.drying_percentage else 0

    @api.onchange('asset_id')
    def _onchange_asset_id(self):
        if self.asset_id:
            self.kabupaten_id = self.asset_id.kabupaten_id  # Existing logic
            self.area = self.asset_id.area_ha  # Sync area with the asset's area_ha
            self.area_uom = self.asset_id.area_uom  # Sync area_uom with the asset's area_uom


    @api.depends('date_missed')
    def _compute_date_missed_display(self):
        for record in self:
            if record.date_missed:
                record.date_missed_display = f"{record.date_missed} days"
            else:
                record.date_missed_display = "0 days"
                
    @api.constrains('employee_id')
    def _check_employee_status(self):
        for record in self:
            if record.employee_id:
                if record.employee_id.state != 'confirm' or record.employee_id.ilo_state != 'active':
                    raise exceptions.ValidationError(
                        f"Petani {record.employee_id.name} harus memiliki status 'Confirmed' dan 'Active' untuk mencatat produksi."
                    )


    @api.depends('quantity', 'actual_quantity')
    def _compute_loss_quantity(self):
        for record in self:
            # Check if actual quantity is less than planned quantity
            if record.actual_quantity < record.quantity:
                record.quantity_loss = record.quantity - record.actual_quantity  # Loss if actual is less
            else:
                record.quantity_loss = 0.0  # No loss if actual is equal or more than planned

    @api.depends('quantity', 'actual_quantity')
    def _compute_actual_drying_percentage(self):
        for record in self:
            # Compute actual drying percentage
            if record.quantity and record.actual_quantity:
                record.actual_drying_percentage = record.actual_quantity / record.quantity
            else:
                record.actual_drying_percentage = 0.0

    @api.depends('dry_quantity', 'actual_quantity')
    def _compute_actual_estimate_dry_quantity(self):
        for record in self:
            if record.actual_quantity > record.dry_quantity:
                record.actual_estimate_dry_quantity = 0
            else:
                record.actual_estimate_dry_quantity = record.dry_quantity - record.actual_quantity

    @api.depends('date_actual', 'date_planned_finish')
    def _compute_date_missed(self):
        for record in self:
            if record.date_actual and record.date_planned_finish:
                # Directly use the date part (without converting to datetime)
                planned_finish_date = record.date_planned_finish  # 'fields.Date' already gives us a date object
                actual_finish_date = record.date_actual.date()  # Convert datetime to date (ignoring time)

                # Calculate difference in days between actual finish date and planned finish date
                delta = (actual_finish_date - planned_finish_date).days

                # Set the computed value of 'date_missed'
                record.date_missed = delta
            else:
                record.date_missed = 0.0  # Set 0 if either date is missing

    @api.model
    def migrate_weather_conditions(self):
        # Define the mapping of old values to new values
        mapping = {
            'sunny': 'dry',
            'rainy': 'rainy',
            'cloudy': 'rainy',
            'stormy': 'rainy',
        }

        # Search for records with old values and update them
        records_to_update = self.search([])
        for record in records_to_update:
            if record.weather_conditions in mapping:
                record.weather_conditions = mapping[record.weather_conditions]

    @api.depends('production_planting_image')
    def _compute_production_planting_image_url(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        for record in self:
            # record.image_1920_url = f"{base_url}/web/image?model=res.partner&id={record.id}&field=image_1920"
            if record.production_planting_image:
                record.production_planting_image_url = f"{base_url}/production_planting/image/{record.id}"
            else:
                record.production_planting_image_url = False

    @api.depends('date_planned_start', 'date_planned_finish', 'state')
    def _compute_completion_percentage(self):
        """Compute completion percentage based on the planting timeline."""
        for record in self:
            if record.state == 'done':
                record.completion_percentage = 1.0  # Now as a fraction (1.0 instead of 100.0)
                continue

            now = fields.Datetime.now()

            if record.date_planned_start:
                start_date = fields.Datetime.to_datetime(record.date_planned_start)
            else:
                start_date = False

            if record.date_planned_finish:
                finish_date = fields.Datetime.to_datetime(record.date_planned_finish)
            else:
                finish_date = False

            if not start_date or not finish_date or now < start_date:
                record.completion_percentage = 0.0
            elif now >= finish_date:
                record.completion_percentage = 1.0  # Fractional completion (1.0 instead of 100%)
            else:
                total_duration = (finish_date - start_date).days
                elapsed_duration = (now - start_date).days
                record.completion_percentage = min(1.0, elapsed_duration / total_duration)  # Fractional percentage


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

    @api.onchange('produce_product')
    def _onchange_produce_product(self):
        """Ensure the correct UOM is set based on the product."""
        if self.produce_product:
            if not self.produce_product.uom_id:
                default_uom = self.env.ref('uom.product_uom_kgm')
                self.uom = default_uom
            else:
                self.uom = self.produce_product.uom_id

    @api.model
    def create(self, vals):
        """Override the create method to validate UOM, auto-generate the production identifier, and populate asset_id."""
        vals['date_created'] = fields.Datetime.now()
        if 'produce_product' in vals:
            product = self.env['product.product'].browse(vals['produce_product'])
            if not vals.get('uom'):
                vals['uom'] = product.uom_id.id if product.uom_id else self.env.ref('uom.product_uom_kgm').id

        if 'employee_id' in vals and not vals.get('asset_id'):
            asset = self.env['ilo.assets'].search([('employee_id', '=', vals['employee_id'])], limit=1)
            if asset:
                vals['asset_id'] = asset.id

        vals['production_identifier'] = self._generate_production_identifier(
            employee_id=vals['employee_id'],
            product_id=vals['produce_product'],
            quantity=vals['quantity']
        )

        return super(IloProductionPlanting, self).create(vals)
    
    def write(self, vals):
        """Override the write method to update the last modified date."""
        vals['date_modified'] = fields.Datetime.now()  # Update modification date
        return super(IloProductionPlanting, self).write(vals)

    

    def _generate_production_identifier(self, employee_id, product_id, quantity):
        """Generate a unique identifier for the planting production."""
        employee = self.env['res.partner'].browse(employee_id)
        product = self.env['product.product'].browse(product_id)
        existing_productions = self.search([
            ('employee_id', '=', employee_id),
            ('produce_product', '=', product_id)
        ])
        sequence_number = len(existing_productions) + 1
        sequence_number_str = str(sequence_number).zfill(3)
        identifier = f"PLANT-{employee.ilo_associate_code}-{product.batch_code}-{int(quantity)}-{sequence_number_str}"
        return identifier

    @api.constrains('date_planned_start', 'date_planned_finish')
    def _check_dates(self):
        """Ensure that the planned finish date is after the start date."""
        for record in self:
            if record.date_planned_finish and record.date_planned_finish < record.date_planned_start:
                raise exceptions.ValidationError("Planned finish date must be after the start date.")

    # Enhanced Methods with Stock Move Logic
    def action_confirm(self):
        """Confirm the planting order."""
        if not self.asset_id:
            raise exceptions.ValidationError("Please assign an asset to proceed.")

        # Mark the asset as 'in progress' for the planting process
        self.asset_id.set_in_progress(process_type='planting')
        self.state = 'in_progress'

    def action_done(self):
        """Mark the planting as complete and update stock levels using actual_quantity."""
        if self.state != 'in_progress':
            raise exceptions.UserError("The state must be 'In Progress' to mark as 'Done'.")

        # Ensure actual_quantity is filled
        if self.actual_quantity is None:
            raise exceptions.ValidationError("Actual Quantity must be entered before completing the production.")
        
        # Ensure actual_quantity is greater than zero
        if self.actual_quantity <= 0:
            raise exceptions.ValidationError("Actual Quantity must be greater than zero before completing the production.")

        # Update state
        self.state = 'done'

        # Set the actual finish date to the current datetime
        self.date_actual = fields.Datetime.now()

        # Locate the stock location for the employee
        location = self.env['ilo.stock_location'].search([('employee_id', '=', self.employee_id.id)], limit=1)
        if not location:
            raise exceptions.UserError('No stock location found for this employee.')

        # Update ilo.quant for the produced product
        try:
            quant = self.env['ilo.quant'].search([
                ('product_id', '=', self.produce_product.id),
                ('location_id', '=', location.id),
                ('product_uom_id', '=', self.uom.id),
            ], limit=1)

            if not quant:
                quant = self.env['ilo.quant'].create({
                    'product_id': self.produce_product.id,
                    'product_uom_id': self.uom.id,
                    'quantity_available': 0.0,  # Start from zero
                    'location_id': location.id,
                })

            # Adjust the quantity using actual_quantity
            quant.adjust_quantity_available(self.actual_quantity)
            _logger.info(f"Produced {self.actual_quantity} units of {self.produce_product.name} into {location.name}.")

            location._compute_quantities()

        except exceptions.ValidationError as e:
            _logger.error("Validation error occurred: %s", e)
            raise
        except Exception as e:
            _logger.error("An error occurred while marking planting as done: %s", e)
            raise

        # Check if this is the last active planting for the asset
        other_active_plantings = self.env['ilo.production_planting'].search([
            ('asset_id', '=', self.asset_id.id),
            ('id', '!=', self.id),
            ('state', '=', 'in_progress')
        ])
        if not other_active_plantings:
            # No other active plantings; set the asset to inactive
            self.asset_id.set_inactive(process_type='planting')


    def action_cancel(self):
        """Cancel the planting and associated stock move if it exists."""
        self.state = 'canceled'
        if self.stock_move_id and self.stock_move_id.state != 'done':
            self.stock_move_id.action_cancel()
