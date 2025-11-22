from odoo import models, fields, api, exceptions, _
import qrcode
from io import BytesIO
import base64
import logging

_logger = logging.getLogger(__name__)

class OwnershipCode(models.Model):
    _name = 'ownership.code'
    _description = 'Kode Kepemilikan'
    _inherit = ['portal.mixin', 'mail.thread', 'mail.activity.mixin']


    # General Information
    name = fields.Char(string='Kode Penjualan', readonly=True)
    specific_codes = fields.Char(string='Kode Penjualan Spesifik', readonly=True)
    reference_code = fields.Char(string='Kode Referensi', compute='_compute_reference_code', store=True)
    production_code = fields.Many2many('ilo.production.harvesting', string='Kode Produksi', compute='_compute_production_code', store=True)
    general_ownership_code = fields.Char(string='Kode Penjualan Umum', readonly=True)  # or just 'Kode Umum'

    # Actors and Associate Codes
    source_actor_ids = fields.Many2many('res.partner', string='Penjual', compute='_compute_source_actors', store=True)
    source_actor_ids_associate_code = fields.Char(string="Asosiasi Penjual", compute='_compute_source_actor_associate_code', store=True)
    destination_actor = fields.Many2one('res.partner', string='Pembeli', required=True)
    destination_actor_associate_code = fields.Char(string='Asosiasi Pembeli', compute='_compute_destination_actor_associate_code', store=True, readonly=True)

    # Product and Transaction Details
    product_id = fields.Many2one('product.product', string='Produk', compute='_compute_product', store=True)
    product_image = fields.Binary(string="Gambar Produk", compute="_compute_product_image", store=True)
    product_image_url = fields.Char(string="URL Gambar Produk", compute="_compute_product_image_url", store=True)

    product_uom_id = fields.Many2one('uom.uom', string='Satuan Ukur', compute='_compute_product_uom', store=True)
    history = fields.Text(string='Sejarah')
    ilo_reference_ids = fields.One2many(
        'ilo.reference.link',
        'ownership_code_id',
        string='Pelacak Pergerakan Produk',
        readonly=True,
    )
    linked_references_count = fields.Integer(compute='_compute_linked_references_count', string='Jumlah Referensi Terkait')


    price = fields.Float(string='Harga')
    quantity = fields.Float(string='Kuantitas')
    total_requested_quantity = fields.Float(string='Total Kuantitas', compute='_compute_total_requested_quantity', store=True)

    total_value = fields.Float(string='Total Subtotal', compute='_compute_total_value', store=True)
    currency_id = fields.Many2one(
        'res.currency', string='Currency', required=True, default=lambda self: self.env.company.currency_id
    )
    total_price = fields.Monetary(
        string='Total Harga', compute='_compute_total_price', store=True, currency_field='currency_id'
    )
    transaction_number = fields.Char(string='Nomor Transaksi', readonly=True)

    # Dates
    date_order = fields.Datetime(string='Tanggal Pemesanan', default=fields.Datetime.now, required=True)
    date_confirm = fields.Datetime(string='Tanggal Konfirmasi')
    date_done = fields.Datetime(string='Tanggal Selesai')
    date_receive = fields.Datetime(string='Tanggal Penerimaan')

    # Status and Location
    state = fields.Selection([
        ('draft', 'Draf'),
        ('confirmed', 'Dikonfirmasi'),
        ('done', 'Selesai'),
        ('cancelled', 'Dibatalkan'),
        ('received', 'Diterima')
    ], string='Status', default='draft', readonly=True, tracking=True)
    kabupaten_id = fields.Many2one('res.kabupaten', string='Kabupaten/Kota', help="Kabupaten atau Kota tempat lokasi penanaman produksi.")

    # Ownership Lines and Reference Types
    ownership_line_ids = fields.One2many('ownership.line', 'ownership_code_id', string='Kode Penjualan Petani')
    specific_ownership_line_ids = fields.Many2many('ownership.line', string='Kode Penjualan Petani')

    ownership_reference_type = fields.Selection([
        ('specific', 'Dari Petani'),
        ('general', 'Bukan dari Petani'),
    ], string='Jenis Referensi Kepemilikan', default='specific')
    
    general_ownership_code_ids = fields.Many2many(
        'ownership.code',  # Same model
        'ownership_code_general_rel',  # Explicit table name for Many2many relation
        'ownership_code_id',  # Column for the current model in the relation table
        'general_code_id',  # Column for the related model in the relation table
        store=True,  # Store the computed value in the database
        readonly=False,  # Allow the field to be manually edited
        string='Kode Penjualan Lain'
    )


    # QR Code Details
    qr_code_id = fields.Many2one('qr.code', string="QR Code")
    qr_code_image = fields.Binary("Gambar QR Code", attachment=True)

    #ProductTransaction
    product_transaction_image_ownership_code = fields.Binary(string="Gambar Produk Jual")
    product_transaction_image_ownership_code_url = fields.Char(string="URL Foto Penjualan", compute='_compute_ownership_code_image_url')


    @api.depends('product_transaction_image_ownership_code')
    def _compute_ownership_code_image_url(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        for record in self:
            # record.image_1920_url = f"{base_url}/web/image?model=res.partner&id={record.id}&field=image_1920"
            if record.product_transaction_image_ownership_code:
                record.product_transaction_image_ownership_code_url = f"{base_url}/ownership_code/image/{record.id}"
            else:
                record.product_transaction_image_ownership_code_url = False

    # @api.depends('ownership_line_ids.source_actor')  # Trigger on changes to source_actor in ownership lines
    # def _compute_general_ownership_code_ids(self):
    #     for record in self:
    #         # Get the current source_actors from the ownership.line records
    #         current_source_actors = record.ownership_line_ids.mapped('source_actor.id')

    #         # Find previous ownership codes where destination_actor matches the current source actors
    #         previous_ownership_codes = self.env['ownership.code'].search([
    #             ('destination_actor', 'in', current_source_actors)
    #         ])

    #         # Gather unique ownership code IDs from these records
    #         unique_codes = previous_ownership_codes.ids

    #         # Assign these unique ownership codes to general_ownership_code_ids
    #         record.general_ownership_code_ids = [(6, 0, unique_codes)]


    @api.depends('product_id')
    def _compute_product_image(self):
        """Compute product_image from product_id's image."""
        for record in self:
            record.product_image = record.product_id.image_1920 if record.product_id else False

    @api.depends('product_id.image_1920_url')
    def _compute_product_image_url(self):
        """Compute product_image_url from product_id's image URL."""
        for record in self:
            record.product_image_url = record.product_id.image_1920_url if record.product_id else False

    @api.model
    def backfill_product_images(self, record_ids=None):
        """Backfill product images for existing ownership.code records."""
        # Use the provided record_ids or fetch all if None
        if record_ids:
            records = self.browse(record_ids)  # Use the specific records provided
        else:
            records = self.search([])  # Fetch all ownership.code records

        for record in records:
            if record.product_id:
                record.product_image = record.product_id.image_1920
                _logger.info("Backfilled product image for ownership.code ID %s with product_id %s", record.id, record.product_id.id)
            else:
                record.product_image = False
                _logger.info("No product_id set for ownership.code record %s", record.id)

    @api.depends('ilo_reference_ids')
    def _compute_linked_references_count(self):
        for record in self:
            record.linked_references_count = len(record.ilo_reference_ids)
    
    def action_view_linked_references(self):
        """ Action to view linked references """
        return {
            'type': 'ir.actions.act_window',
            'name': 'Linked References',
            'res_model': 'ilo.reference',
            'domain': [('id', 'in', self.ilo_reference_ids.ids)],
            'view_mode': 'tree,form',
            'target': 'current',  # Use 'current' to open in the same window
        }


    def _compute_single_field_if_same(self, field_name):
        """Helper to compute field if all ownership lines share the same value."""
        for record in self:
            values = record.ownership_line_ids.mapped(field_name)
            record[field_name] = values[0] if len(set(values.ids)) == 1 else False

    @api.depends('ownership_line_ids.product_id')
    def _compute_product(self):
        self._compute_single_field_if_same('product_id')

    @api.depends('ownership_line_ids.product_uom_id')
    def _compute_product_uom(self):
        self._compute_single_field_if_same('product_uom_id')

    @api.depends('ownership_line_ids.value')
    def _compute_total_value(self):
        """Compute the total value from ownership lines."""
        for record in self:
            record.total_value = sum(record.ownership_line_ids.mapped('value'))

    @api.depends('ownership_line_ids.price')
    def _compute_total_price(self):
        """Compute the total price from ownership lines."""
        for record in self:
            record.total_price = sum(record.ownership_line_ids.mapped('price'))


    @api.depends('ownership_line_ids.source_actor')
    def _compute_source_actors(self):
        """Compute method to gather unique source actors from related ownership lines"""
        for record in self:
            source_actors = record.ownership_line_ids.mapped('source_actor')
            record.source_actor_ids = [(6, 0, source_actors.ids)]  # Assign M2M field

    @api.depends('ownership_line_ids.source_actor_associate_code')
    def _compute_source_actor_associate_code(self):
        """Compute associate codes from source actors in ownership lines"""
        for record in self:
            associate_codes = record.ownership_line_ids.mapped('source_actor_associate_code')
            record.source_actor_ids_associate_code = ', '.join(associate_codes) if associate_codes else ''

    @api.depends('specific_ownership_line_ids.production_harvesting_id')
    def _compute_production_code(self):
        """Compute the production code and set it as a Many2many link to ilo.production.harvesting."""
        for record in self:
            if record.ownership_reference_type == 'specific':
                if not record.specific_ownership_line_ids:
                    record._auto_populate_specific_ownership_lines()

                # Gather production identifiers from specific_ownership_line_ids
                production_identifiers = record.specific_ownership_line_ids.mapped('production_harvesting_id.production_identifier')
                
                # Fetch ilo.production.harvesting records that match these identifiers
                harvesting_records = self.env['ilo.production.harvesting'].search([
                    ('production_identifier', 'in', production_identifiers)
                ])
                
                # Assign them to the production_code Many2many field
                record.production_code = [(6, 0, harvesting_records.ids)]
            else:
                record.production_code = [(5, 0, 0)]  # Clear the field if not 'specific'   
                
    @api.depends('destination_actor')
    def _compute_destination_actor_associate_code(self):
        for record in self:
            record.destination_actor_associate_code = record.destination_actor.ilo_associate if record.destination_actor else ''

    @api.onchange('ownership_reference_type')
    def _onchange_ownership_reference_type(self):
        """Ensure only the relevant field is visible based on the selection."""
        if self.ownership_reference_type == 'specific':
            self.general_ownership_code_ids = False  # Clear the general ownership codes if 'specific' is selected
        else:
            self.specific_ownership_line_ids = False  # Clear the specific ownership lines if 'general' is selected

    @api.depends('specific_ownership_line_ids', 'general_ownership_code_ids', 'ownership_reference_type')
    def _compute_reference_code(self):
        """Compute reference based on the chosen ownership reference type."""
        for record in self:
            # Trigger the general ownership lines population based on the ownership reference type
            if record.ownership_reference_type == 'general':
                record._auto_populate_general_ownership_lines()  # Call to populate general ownership lines

            if record.ownership_reference_type == 'specific':
                # If specific_ownership_line_ids is empty, auto-populate it from ownership.line
                if not record.specific_ownership_line_ids:
                    record._auto_populate_specific_ownership_lines()

                # Gather actual data from specific_ownership_line_ids
                specific_codes = [line.specific_code for line in record.specific_ownership_line_ids]
                record.reference_code = ', '.join(specific_codes) if specific_codes else 'No specific codes found'
            else:
                # Gather actual data from general_ownership_code_ids
                general_codes = [code.name for code in record.general_ownership_code_ids]
                record.reference_code = ', '.join(general_codes) if general_codes else 'No general codes found'



    def _auto_populate_general_ownership_lines(self):
        """Gather all reference_codes from ownership.line records related to this ownership.code."""
        all_reference_codes = set()  # Use a set to avoid duplicates

        # Fetch ownership line records related to this ownership.code
        ownership_lines = self.env['ownership.line'].search([('ownership_code_id', '=', self.id)])
        
        # Iterate through each ownership line and collect reference_codes
        for line in ownership_lines:
            if line.reference_code:  # Check if reference_code exists
                # Assuming reference_code is a Many2many field, we can extend our set
                all_reference_codes.update(line.reference_code.ids)  # Collecting IDs to avoid duplicates

        # If you want to set the general ownership codes from the collected reference codes
        if all_reference_codes:
            self.general_ownership_code_ids = [(6, 0, list(all_reference_codes))]  # Set the fetched codes
        else:
            self.general_ownership_code_ids = [(5, 0, 0)]  # Clear the field if no reference codes found

    def _auto_populate_specific_ownership_lines(self):
        """Auto-populate specific_ownership_line_ids if the user has not input them."""
        # Fetch ownership lines related to this ownership.code
        ownership_lines = self.env['ownership.line'].search([('ownership_code_id', '=', self.id)])
        if ownership_lines:
            self.specific_ownership_line_ids = [(6, 0, ownership_lines.ids)]  # Set the fetched lines

    @api.depends('quantity', 'ownership_line_ids.quantity')  # Trigger when either quantity or ownership line quantities change
    def _compute_total_requested_quantity(self):
        for record in self:
            # Start with the quantity of the ownership code
            total_quantity = record.quantity
            
            # Add the quantities from ownership lines
            total_quantity += sum(line.quantity for line in record.ownership_line_ids)
            
            # Set the computed total_requested_quantity
            record.total_requested_quantity = total_quantity
    
    
    @api.model
    def create(self, vals):
        """Create the ownership code record but defer computations to the confirm step."""
        
        # Clear irrelevant fields based on ownership_reference_type
        if vals.get('ownership_reference_type') == 'specific':
            vals['general_ownership_code_ids'] = [(5, 0, 0)]  # Clear general codes
        else:
            vals['specific_ownership_line_ids'] = [(5, 0, 0)]  # Clear specific codes

        # Create the ownership code record
        record = super(OwnershipCode, self).create(vals)
        return record

    
    def write(self, vals):
        """Override the write method to enforce state-based restrictions on field modifications,
        while allowing 'product_image' to be updated in all states.
        """
        for record in self:
            # Define allowed fields that bypass state restrictions
            allowed_fields = {'product_image'}

            # Allow changes to 'product_image' field in any state
            if set(vals.keys()).issubset(allowed_fields):
                return super(OwnershipCode, self).write(vals)

            # Restrict modifications if the record is in the 'received' state (except for 'product_image')
            if record.state == 'received':
                raise exceptions.UserError("This record is read-only as it is already in the 'received' state.")

            # For 'confirmed', 'done', or 'cancelled' states, allow only specific modifications
            if record.state in ['confirmed', 'done', 'cancelled']:
                # Allow state transitions to 'done' or 'received' only
                if 'state' in vals and vals['state'] in ['done', 'received']:
                    return super(OwnershipCode, self).write(vals)

                # If the update isn't allowed, raise an error
                raise exceptions.UserError(
                    _("This order cannot be modified because it is in '%s' state.") % record.state
                )

        # For records not in restricted states, proceed with the usual write
        return super(OwnershipCode, self).write(vals)



    def _generate_general_ownership_code(self):
        """Generate a general ownership code."""
        
        # Use the transaction number set during the record creation
        batch_codes = {line.batch_code or 'NA' for line in self.ownership_line_ids}
        destination_actor_code = self.destination_actor.ilo_associate_code or 'NA'
        
        # Construct the general ownership code using the pre-assigned transaction number
        general_ownership_code = f"{'-'.join(batch_codes)}-{destination_actor_code}-{int(self.total_requested_quantity)}-{self.transaction_number}"
        
        # Store specific ownership codes for reference
        self.specific_codes = "\n".join(batch_codes)
        self.general_ownership_code = general_ownership_code
        return general_ownership_code

    def get_unique_transaction_number(self, record_id):
        """Generate a unique transaction number using the record id."""
        
        # Format the transaction number using the record ID
        transaction_number = str(record_id).zfill(3)  # Ensure the transaction number is at least 3 digits
        
        _logger.info("Generated new transaction number for OwnershipCode: %s", transaction_number)
        return transaction_number

    def _generate_and_link_qr_code(self):
        """
        Generate and link a QR code based on the general ownership code.
        This will include details like product, actors, reference codes, and quantities.
        """
        if self.name:
            # Gather source actors and their associate codes
            source_actors = self.source_actor_ids.mapped(lambda p: f"{p.name} (Code: {p.ilo_associate})")
            source_actors_info = ', '.join(source_actors) if source_actors else 'N/A'

            # Gather destination actor and its associate code
            destination_actor_info = f"{self.destination_actor.name} (Code: {self.destination_actor.ilo_associate})" if self.destination_actor else 'N/A'

            # Collect relevant data for the QR code
            qr_data = f"""
                Ownership: {self.name},
                Product: {self.product_id.name if self.product_id else 'N/A'},
                Quantity: {self.total_requested_quantity},
                Gather From: {self.reference_code if self.reference_code else 'N/A'},
                Penjual (Source Actors): {source_actors_info},
                Pembeli (Destination Actor): {destination_actor_info},
                Location: {self.kabupaten_id.name if self.kabupaten_id else 'N/A'},
                Date of Order: {self.date_order.strftime('%Y-%m-%d %H:%M:%S') if self.date_order else 'N/A'}
            """
            
            # Create the QR code
            qr_code = self.env['qr.code'].create({
                'name': self.name,
                'data': qr_data
            })

            # Link the QR code to the ownership code record
            self.qr_code_id = qr_code.id
            self.qr_code_image = qr_code.qr_code

    def action_confirm(self):
        self.ensure_one()
        if self.state != 'draft':
            raise exceptions.UserError("Only draft orders can be confirmed.")

        # Generate transaction number
        transaction_number = self.get_unique_transaction_number(self.id)
        self.write({'transaction_number': transaction_number})

        # Compute additional fields and populate ilo.reference
        self._compute_total_requested_quantity()
        self.name = self._generate_general_ownership_code()  # Generate general code name
        self._generate_and_link_qr_code()  # Generate and link QR code

        # Trigger reference creation for the current ownership code
        self.env['ilo.reference'].create_reference_from_ownership(self)

        # Update reference_three for any pending references
        self.env['ilo.reference'].update_reference_on_new_ownership(self)

        # Optionally, update ilo.product.history based on the created ownership code
        # histories = self.env['ilo.product.history'].search([
        #     '|', 
        #     ('production_code', '=', self.production_code),
        #     ('then_then', '=', self.id)
        # ])
        # for history in histories:
        #     history._compute_production_code()
        #     # history._compute_goes_to()  # Uncomment if needed
        #     # history._compute_then_then()  # Uncomment if needed
        #     # history._compute_after_that()  # Uncomment if needed

        # Create stock moves for the ownership lines before confirming
        for line in self.ownership_line_ids:
            line._create_stock_move()

        # Update the record's state and log history
        self.write({
            'state': 'confirmed',
            'date_confirm': fields.Datetime.now(),
            'history': (self.history or '') + f"\nConfirmed: {self.name} on {fields.Datetime.now()}."
        })

    def action_done(self):
        self.ensure_one()
        if self.state != 'confirmed':
            raise exceptions.UserError("Only confirmed orders can be marked as done.")
        
        # Mark stock moves as done for each line
        for line in self.ownership_line_ids:
            line._confirm_stock_move()

        self.write({
            'state': 'done',
            'date_done': fields.Datetime.now(),
            'history': (self.history or '') + f"\nDone: {self.name} on {fields.Datetime.now()}."
        })

    def action_cancel(self):
        self.ensure_one()
        if self.state == 'done':
            raise exceptions.UserError("You cannot cancel an order that is already done.")
        
        # Cancel stock moves for each line
        for line in self.ownership_line_ids:
            line._cancel_stock_move()

        self.write({
            'state': 'cancelled',
            'history': (self.history or '') + f"\nCancelled: {self.name} on {fields.Datetime.now()}."
        })

    def action_receive(self):
        self.ensure_one()
        if self.state != 'done':
            raise exceptions.UserError("Only done orders can be received.")
        
        # Ensure stock moves have been received for each line
        for line in self.ownership_line_ids:
            line._update_stock_location()

        self.write({
            'state': 'received',
            'date_receive': fields.Datetime.now(),
            'history': (self.history or '') + f"\nReceived: {self.name} on {fields.Datetime.now()}."
        })

    def action_view_qr_code(self):
        self.ensure_one()
        return {
            'name': 'View Ownership Code',
            'type': 'ir.actions.act_window',
            'res_model': 'ownership.code',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
            'context': {'no_create': True}
        }


class OwnershipLine(models.Model):
    _name = 'ownership.line'
    _description = 'Baris Kepemilikan'
    _inherit = ['portal.mixin', 'mail.thread', 'mail.activity.mixin']


    # Basic Information
    name = fields.Char(string='Kode Keseluruhan')
    specific_code = fields.Char(string='Kode Penjualan Spesifik', readonly=True)

    # Actor Information
    source_actor = fields.Many2one('res.partner', string='Penjual', required=True)
    source_actor_ilo_associate_code = fields.Char(
        string="Kode Penjual",
        compute="_compute_source_actor_ilo_associate_code",
        store=True
    )
    source_location_id = fields.Many2one('ilo.stock_location', string='Lokasi')
    destination_actor = fields.Many2one('res.partner', string='Pembeli', compute='_compute_destination_actor', store=True)
    destination_actor_ilo_associate_code = fields.Char(
        string="Kode Pembeli",
        compute="_compute_destination_actor_ilo_associate_code",
        store=True
    )    
    destination_location_id = fields.Many2one('ilo.stock_location', string='Lokasi')
    source_actor_associate_code = fields.Char(string="Asosiasi Penjual", compute="_compute_source_actor_associate_code", store=True)
    destination_actor_associate_code = fields.Char(string="Asosiasi Pembeli", compute="_compute_destination_actor_associate_code", store=True)

    # Transaction Details
    kabupaten_id = fields.Many2one(
        'res.kabupaten',
        string='Kabupaten/Kota Tujuan',
        compute="_compute_kabupaten_id",
        help="Kabupaten atau Kota tempat lokasi penanaman produksi.",
    )

    date_order = fields.Datetime(string='Tanggal Pemesanan', related='ownership_code_id.date_order', store=True)
    product_id = fields.Many2one('product.product', string='Produk', required=True)
    product_image = fields.Binary(string="Gambar Produk", compute="_compute_product_image", store=True)
    product_uom_id = fields.Many2one('uom.uom', string='Satuan', default=lambda self: self.env.ref('uom.product_uom_kgm').id, required=True)
    product_image_url = fields.Char(string="URL Gambar Produk", compute="_compute_product_image_url", store=True)

    state = fields.Selection(
        related='ownership_code_id.state', 
        string='Status', 
        readonly=True, 
        store=True
    )
        
    quantity = fields.Float(string='Jumlah', required=True)
    currency_id = fields.Many2one(
        'res.currency', string='Currency', required=True, default=lambda self: self.env.company.currency_id
    )
    price = fields.Monetary(
        string='Harga', required=True, currency_field='currency_id'
    )
    value = fields.Float(string='Subtotal', compute='_compute_value', store=True)
    subtotal = fields.Float(string='Subtotal', compute='_compute_subtotal', store=True)
    quant_id = fields.Many2one('ilo.quant',string='ILO Quant', ondelete='cascade')


    # Related Information
    batch_code = fields.Char(string='Kode Barang', related='product_id.batch_code', readonly=True)
    ownership_code_id = fields.Many2one('ownership.code', string='Kode Kepemilikan', ondelete='cascade')
    transaction_number = fields.Char(string='Nomor Transaksi', readonly=True)

    # QR Code Information
    qr_code_id = fields.Many2one('qr.code', string="Rekor QR Code")
    qr_code_image = fields.Binary("Gambar QR Code", attachment=True)

    # Stock Movement Link
    stock_move_id = fields.Many2one('ilo.stock_move', string='Pergerakan Stok', help="Pergerakan stok terkait untuk baris kepemilikan ini")
    
    # Monitoring
    transaction_monitoring_id = fields.Many2one('ilo.transaction_monitoring', string="Pemantauan Transaksi")

    # Production Harvesting Information
    production_harvesting_id = fields.Many2one(
        'ilo.production.harvesting',
        string='Identifikasi Produksi Panen',
        domain="[('employee_id', '=', source_actor), ('state', '=', 'done')]",
        help="Pilih rekaman produksi panen terkait dengan aktor sumber (pegawai).",
        compute='_compute_production_harvesting_id',
        store=True
    )

    # Production Code Reference
    production_code = fields.Char(
        string='Kode Produksi',
        related='production_harvesting_id.production_identifier',
        store=True
    )

    reference_code = fields.Many2many(
        'ownership.code',
        string="Kode Referensi",
        domain="[('destination_actor', '=', source_actor), ('state', '=', 'received')]",
        help="Pilih rekaman ownership.code di mana source_actor adalah destination_actor dalam ownership.code dan statusnya adalah 'received'."
    )

    #ProductTransaction
    product_transaction_image_ownership_line = fields.Binary(string="Gambar Produk Jual")
    product_transaction_image_ownership_line_url = fields.Char(string="URL Foto Penjualan", compute='_compute_ownership_line_image_url')

    @api.depends('product_transaction_image_ownership_line')
    def _compute_ownership_line_image_url(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        for record in self:
            # record.image_1920_url = f"{base_url}/web/image?model=res.partner&id={record.id}&field=image_1920"
            if record.product_transaction_image_ownership_line:
                record.product_transaction_image_ownership_line_url = f"{base_url}/ownership_line/image/{record.id}"
            else:
                record.product_transaction_image_ownership_line_url = False

    @api.depends('product_id')
    def _compute_product_image(self):
        """Compute product_image based on the product_id's image."""
        for record in self:
            record.product_image = record.product_id.image_1920 if record.product_id else False

    @api.depends('product_id.image_1920_url')
    def _compute_product_image_url(self):
        """Compute product_image_url from product_id's image URL."""
        for record in self:
            record.product_image_url = record.product_id.image_1920_url if record.product_id else False


    @api.model
    def backfill_product_images(self, record_ids=None):
        """Backfill product images for existing ownership.line records."""
        # Use the provided record_ids or fetch all if None
        if record_ids:
            records = self.browse(record_ids)  # Use the specific records provided
        else:
            records = self.search([])  # Fetch all ownership.line records

        for record in records:
            if record.product_id:
                record.product_image = record.product_id.image_1920
                _logger.info("Backfilled product image for ownership.line ID %s with product_id %s", record.id, record.product_id.id)
            else:
                record.product_image = False
                _logger.info("No product_id set for ownership.line record %s", record.id)

    @api.depends('ownership_code_id.kabupaten_id')
    def _compute_kabupaten_id(self):
        for record in self:
            if record.ownership_code_id:
                record.kabupaten_id = record.ownership_code_id.kabupaten_id
            else:
                record.kabupaten_id = False

    @api.onchange('ownership_code_id')
    def _onchange_ownership_code_id(self):
        if self.ownership_code_id:
            self.date_order = self.ownership_code_id.date_order
        else:
            self.date_order = False     # Clear date_order if ownership_code_id is not set

    @api.depends('source_actor', 'production_harvesting_id')
    def _compute_production_harvesting_id(self):
        """Compute the production_harvesting_id based on the associate type of source_actor."""
        for line in self:
            if line.source_actor.ilo_associate == 'farmers':  # 'Petani' in your terminology
                # Check if a specific harvesting record is selected
                if line.production_harvesting_id:
                    # If a specific harvesting is selected, use it
                    continue
                else:
                    # Search for the latest production harvesting related to the source_actor
                    latest_harvesting = self.env['ilo.production.harvesting'].search(
                        [('employee_id', '=', line.source_actor.id)],
                        order="create_date desc", 
                        limit=1
                    )
                    line.production_harvesting_id = latest_harvesting.id if latest_harvesting else False
            else:
                line.production_harvesting_id = False  # Clear the field if not Petani

            # Update the related ownership_code with the production code
            if line.ownership_code_id:
                line.ownership_code_id._compute_production_code()
            
            # Set a default message if production_code is empty
            if not line.production_code:
                line.production_code = 'No production code here; not farmer-related. Check the reference code for details.'
            

    

    @api.depends('quantity', 'price')
    def _compute_value(self):
        for line in self:
            line.value = line.quantity * line.price

    @api.depends('value')
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = line.value

    @api.constrains('quantity')
    def _check_quantity(self):
        for line in self:
            if line.quantity <= 0:
                raise exceptions.ValidationError("Quantity must be greater than zero.")
    
    @api.depends('ownership_code_id.destination_actor')
    def _compute_destination_actor(self):
        for line in self:
            if line.ownership_code_id:
                line.destination_actor = line.ownership_code_id.destination_actor

    @api.onchange('source_actor', 'destination_actor')
    def _onchange_specific_code(self):
        for line in self:

            # Automatically update specific_code and name field
            line.generate_specific_ownership_code()  # Update specific_code
            line.name = line.specific_code  # Set name from specific_code

    @api.depends('destination_actor')
    def _compute_destination_actor_associate_code(self):
        for record in self:
            record.destination_actor_associate_code = record.destination_actor.ilo_associate if record.destination_actor else ''

    @api.depends('source_actor')
    def _compute_source_actor_associate_code(self):
        for record in self:
            record.source_actor_associate_code = record.source_actor.ilo_associate if record.destination_actor else ''

    @api.depends('source_actor')
    def _compute_source_actor_ilo_associate_code(self):
        for record in self:
            record.source_actor_ilo_associate_code = (
                record.source_actor.ilo_associate_code if record.source_actor else ''
            )

    @api.depends('destination_actor')
    def _compute_destination_actor_ilo_associate_code(self):
        for record in self:
            record.destination_actor_ilo_associate_code = (
                record.destination_actor.ilo_associate_code if record.destination_actor else ''
            )


    @api.onchange('source_actor')
    def _onchange_source_actor(self):
        """Automatically set the source location based on the selected source actor."""
        if self.source_actor:
            location = self.env['ilo.stock_location'].search([
                ('employee_id', '=', self.source_actor.id)
            ], limit=1)
            _logger.info(f"Source location for actor {self.source_actor.name}: {location}")
            self.source_location_id = location if location else False

    @api.onchange('destination_actor')
    def _onchange_destination_actor(self):
        """Automatically set the destination location based on the selected destination actor."""
        if self.destination_actor:
            location = self.env['ilo.stock_location'].search([
                ('employee_id', '=', self.destination_actor.id)
            ], limit=1)
            _logger.info(f"Destination location for actor {self.destination_actor.name}: {location}")
            self.destination_location_id = location if location else False


    @api.model
    def create(self, vals):
        """Override the create method to also create a product history and update related ownership code."""
        
        # Generate a unique transaction number
        vals['transaction_number'] = self.get_unique_transaction_number()

        # Create the ownership line record
        ownership_line = super(OwnershipLine, self).create(vals)

        # Automatically set destination_actor from ownership_code if present
        ownership_code = self.env['ownership.code'].browse(vals.get('ownership_code_id'))
        if ownership_code:
            ownership_line.destination_actor = ownership_code.destination_actor.id

        # Generate specific ownership code and QR code after record is created
        ownership_line.generate_specific_ownership_code()
        ownership_line.name = ownership_line.specific_code
        ownership_line._generate_qr_code()

        # Update the related ownership_code with the production code
        if ownership_code:
            ownership_code._compute_production_code()
        ownership_line._update_quant_quantity_sold()


        return ownership_line

    def write(self, vals):
        """Override the write method to enforce state-based restrictions on field modifications
        when the parent ownership code is in confirmed, done, or cancelled states, except for marking
        the line as done or received, and allowing 'product_image' updates at any time.
        """
        # Define allowed fields that can bypass restrictions
        allowed_fields = {'product_image'}

        for line in self:
            # Allow changes to 'product_image' field regardless of state
            if set(vals.keys()).issubset(allowed_fields):
                continue  # Skip checks and allow update for product_image only

            # Check the state of the related ownership code
            if line.ownership_code_id and line.ownership_code_id.state in ['confirmed', 'done', 'cancelled']:
                # Allow changes only if marking as done or if it's a receive operation
                if vals.get('state') in ['done', 'received']:
                    continue  # Allow state transition without raising an error
                
                # If modifications are not allowed, raise an error
                raise exceptions.UserError(
                    _("This line cannot be modified because the related ownership code is in a '%s' state.") % line.ownership_code_id.state
                )

        # Proceed with the usual write for unrestricted records or permitted fields
        return super(OwnershipLine, self).write(vals)
    
    def generate_specific_ownership_code(self):
        for line in self:
            source_actor_code = line.source_actor.ilo_associate_code or 'NA'
            product_batch_code = line.batch_code or 'NA'
            destination_actor_code = line.destination_actor.ilo_associate_code or 'NA'
            
            # Convert quantity to int to avoid decimal points
            transaction_number = line.transaction_number or '000'
            quantity = int(line.quantity) if line.quantity else 0  # Ensure quantity is an integer

            specific_code = f"{source_actor_code}-{product_batch_code}-{destination_actor_code}-{quantity}-{transaction_number}"
            line.specific_code = specific_code  # Set specific_code directly

    def get_unique_transaction_number(self):
        last_line = self.search([], order='transaction_number desc', limit=1)
        new_number = int(last_line.transaction_number) + 1 if last_line else 1
        return f"{new_number:03d}"


    def _update_quant_quantity_sold(self):
        """Update quantity_sold in ilo.quant based on ownership line's quantity and source_location_id."""
        for record in self:
            quant = self.env['ilo.quant'].search([
                ('product_id', '=', record.product_id.id),
                ('location_id', '=', record.source_location_id.id)
            ], limit=1)

            if quant:
                quant.adjust_quantity_sold(record.quantity)
            
    @api.model
    def _create_stock_move(self):
        """Create a stock move when confirming the ownership line."""
        if not self.source_location_id:
            raise exceptions.UserError(_('Source location not set for product %s', self.product_id.name))
        if not self.destination_location_id:
            raise exceptions.UserError(_('Destination location not set for product %s', self.product_id.name))

        # Create the stock move using ilo.stock_move
        stock_move = self.env['ilo.stock_move'].create_move(
            product_id=self.product_id.id,
            location_id=self.source_location_id.id,
            location_dest_id=self.destination_location_id.id,
            quantity=self.quantity,
            product_uom_id=self.product_uom_id.id
        )

        # Confirm and assign the stock move
        stock_move.action_confirm()
        
        # Store the created stock move ID
        self.write({'stock_move_id': stock_move.id})

    def _confirm_stock_move(self):
        """Confirm the stock move associated with the ownership line."""
        if self.stock_move_id and self.stock_move_id.state == 'draft':
            self.stock_move_id.action_confirm()

    def _cancel_stock_move(self):
        """Cancel the stock move associated with the ownership line."""
        if self.stock_move_id and self.stock_move_id.state != 'cancel':
            self.stock_move_id.action_cancel()

    def _update_stock_location(self):
        """Update stock locations after confirming the stock move."""
        if not self.stock_move_id:
            raise exceptions.UserError(_('No stock move associated with this line.'))

        self.stock_move_id.action_done()
        
        # Update quantity_sold in ilo.quant after confirming stock move
        self.quant_id.adjust_quantity_sold(self.quantity)

    def _generate_qr_code(self):
        for record in self:
            if record.specific_code:
                # Prepare QR code data to include additional fields
                qr_code_data = f"""
                    Transaction Code: {record.specific_code}
                    Seller: {record.source_actor.name or 'N/A'}
                    Seller Code: {record.source_actor_associate_code or 'N/A'}
                    Buyer: {record.destination_actor.name or 'N/A'}
                    Buyer Code: {record.destination_actor_associate_code or 'N/A'}
                    Date of Order: {record.date_order or 'N/A'}
                    Product: {record.product_id.display_name or 'N/A'}
                    Quantity: {record.quantity or 0} {record.product_uom_id.name or ''}
                    Production Code: {record.production_code or 'N/A'}
                    Price: {record.price or 0}
                    Value: {record.value or 0}
                """
                # Set up values for the QR code record creation
                qr_code_vals = {
                    'name': f"QR for {record.specific_code}",
                    'data': qr_code_data,
                }
                # Create the QR code in the 'qr.code' model
                qr_code_record = self.env['qr.code'].create(qr_code_vals)
                
                # Link the newly created QR code to the current record
                record.qr_code_id = qr_code_record.id
                record.qr_code_image = qr_code_record.qr_code  # Store the generated image from qr.code

    def action_view_qr_code(self):
        """Open QR Code image in a new window."""
        if self.qr_code_image:
            return {
                'type': 'ir.actions.act_url',
                'url': f'/web/content/{self._name}/{self.id}/qr_code_image',
                'target': 'new',
            }
        else:
            raise exceptions.UserError("QR Code image not generated yet.")


