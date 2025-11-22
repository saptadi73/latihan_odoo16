from odoo import models, fields, api, exceptions, _
import base64
import logging


_logger = logging.getLogger(__name__)
# class ILOSaleOrder(models.Model):
#     _inherit = 'sale.order'
    
    # dashboard_id = fields.Many2one('ilo.dashboard', string='Dashboard', ondelete='cascade')
    # farm_location = fields.Char(string='Farm Location', help="Location of the farm where the products are sold.")
    # production_capacity = fields.Float(string='Production Capacity', help="The maximum production capacity of the farm.")

class ILOEmployee(models.Model):
    _inherit = 'res.partner'

    # ILO Associate Selection Field
    nik_id= fields.Char(String='NIK')
    ilo_associate = fields.Selection([
        ('farmers', 'Petani'),
        ('agent', 'Agent'),
        ('koperasi', 'Koperasi'),
        ('ugreen', 'UGreen'),
        ('green', 'Green')
    ], string='Asosiasi Ugreen(**)', required=True)

    # ILO Associate Code (auto-generated field)
    ilo_associate_code = fields.Char(string='Kode Asosiasi', readonly=True)

    # Additional fields
    family_members = fields.Integer(string='Anggota Keluarga')
    organization_status = fields.Selection([
        ('member', 'Member'),
        ('not_member', 'Bukan Member'),
        ('employee', 'Pegawai dalam Organisasi')  # New status added
    ], string='Status Keorganisasian(**)')

    organization_name = fields.Char(string='Nama Organisasi', compute='_compute_organization_name', store=True)
    
    employment_contract = fields.Binary(string='Kontrak Pekerjaan')
    contract_file_name = fields.Char(string='Contract File Name', store=True, default=lambda self: self._default_contract_file_name())
    contract_url = fields.Char(string='URL Contract', compute='_compute_contract_url', store=True)
    
    asset_ids = fields.One2many(
        'ilo.assets',  # Target model
        'employee_id',  # Field on ilo.assets that links back to res.partner
        string='Lahan Yang Dimiliki'
    )
    # Field to sum the total area of all assets linked to this employee (in hectares)
    total_area_ha = fields.Float(string='Total Area Lahan', compute='_compute_total_area_ha')
    description=fields.Text(string='Informative Description')
    production_id=fields.One2many('ilo.production_planting','employee_id', string='Production ID')
    # New field to sum the total quantity of planting for the employee
    
    #Production Planting Sum
    total_planting_quantity = fields.Float(
        string='Estimatasi Keseluruhan Jumlah Produksi Tanam', 
        compute='_compute_total_planting_quantity', 
        store=True
    )
    in_progress_planting_quantity = fields.Float(
        string='Jumlah Tanam yang Sedang Dalam Proses', 
        compute='_compute_total_planting_quantity', 
        store=True
    )
    in_progress_percentage_quantity = fields.Float(
        string='Persentase Estimasi Jumlah Produksi Tanam Yang Dikerjakann (%)', 
        compute='_compute_total_planting_quantity', 
        store=True
    )
    total_actual_quantity = fields.Float(
        string='Total Jumlah Tanam Aktual',
        compute='_compute_total_planting_quantity',
        store=True
    )
    total_product_loss = fields.Float(
        string='Total Produksi Loss Tanam',
        compute='_compute_total_planting_quantity',
        store=True
    )
    percentage_product_loss = fields.Float(
        string='Persentase Produksi Loss Tanam(%)',
        compute='_compute_total_planting_quantity',
        store=True
    )

    #Oil Production Sum
    oil_production_id=fields.One2many('ilo.production.harvesting', 'employee_id', string='Harvesting ID')
    total_oil_quantity = fields.Float(
        string='Estimasi Jumlah Minyak', 
        compute='_compute_total_oil_quantity', 
        store=True
    )
    in_progress_oil_quantity = fields.Float(
        string='Jumlah Minyak yang Sedang Dalam Proses', 
        compute='_compute_total_oil_quantity', 
        store=True
    )
    in_progress_oil_percentage_quantity = fields.Float(
        string='Estimasi Minyak Yang Sedang Diproduksi',
        compute='_compute_total_oil_quantity', 
        store=True
    )
    total_actual_oil_quantity = fields.Float(
        string='Jumlah Aktual Minyak',
        compute='_compute_total_oil_quantity',
        store=True
    )
    total_oil_quantity_loss = fields.Float(
        string='Jumlah Produksi Loss Minyak',
        compute='_compute_total_oil_quantity',
        store=True
    )
    total_oil_loss_percentage = fields.Float(
        string='Persentase Produksi Loss Minyak (%)',
        compute='_compute_total_oil_quantity',
        store=True
    )

    #Transaction Details
    ownership_line_id = fields.One2many('ownership.line', 'source_actor', string='Ownership Line')
    total_transaction_quantity = fields.Float(
        string='Total Barang Terjual',
        compute='_compute_transaction',
        store=True
        )
    total_transaction_value = fields.Float(
        string='Total Harga Barang Terjual',
        compute='_compute_transaction',
        store=True
    )
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirm', 'Confirmed')
    ], string='Confirmation Status', default='draft')

    ilo_state = fields.Selection([
        ('active', 'Active'),
        ('inactive', 'Inactive'),
    ],
    string='Active/Inactive',
    default='active'
    )

    # @api.constrains('nik_id', 'is_company')
    # def _check_nik_id(self):
    #     for record in self:
    #         # Skip constraint if it's a company
    #         if record.is_company:
    #             continue

    #         if not record.nik_id or not record.nik_id.isdigit() or len(record.nik_id) != 16:
    #             raise exceptions.ValidationError(_("NIK harus 16 karakter dan harus angka."))
                
    @api.depends('employment_contract', 'contract_file_name')
    def _compute_contract_url(self):
        """Compute the URL for the employment contract."""
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        for record in self:
            if record.employment_contract and record.contract_file_name:
                # Sanitize the filename for URL safety
                sanitized_filename = record.contract_file_name.replace(" ", "_")
                record.contract_url = f"{base_url}/partner/contract/{record.id}/{sanitized_filename}"
            else:
                record.contract_url = False

    @api.depends('ownership_line_id.quantity', 'ownership_line_id.value')
    def _compute_transaction(self):
        for partner in self:
            partner.total_transaction_quantity = sum(line.quantity for line in partner.ownership_line_id)
            partner.total_transaction_value = sum(line.value for line in partner.ownership_line_id)


    @api.depends('oil_production_id.final_quantity', 'oil_production_id.actual_final_quantity', 'oil_production_id.state')
    def _compute_total_oil_quantity(self):
        for employee in self:
            total_quantity = sum(employee.oil_production_id.mapped('final_quantity'))
            total_actual_quantity = sum(employee.oil_production_id.mapped('actual_final_quantity'))
            total_loss = total_quantity - total_actual_quantity if total_quantity > total_actual_quantity else 0
            in_progress_quantity = sum(
                rec.final_quantity for rec in employee.oil_production_id if rec.state == 'in_progress'
            )
            in_progress_percentage = (in_progress_quantity / total_quantity) if total_quantity else 0
            loss_percentage = (total_loss / total_quantity) if total_quantity else 0

            # Assign computed values
            employee.total_oil_quantity = total_quantity
            employee.total_actual_oil_quantity = total_actual_quantity
            employee.total_oil_quantity_loss = total_loss
            employee.in_progress_oil_quantity = in_progress_quantity
            employee.in_progress_oil_percentage_quantity = in_progress_percentage
            employee.total_oil_loss_percentage = loss_percentage

    @api.depends('production_id.quantity', 'production_id.actual_quantity', 'production_id.quantity_loss', 'production_id.state')
    def _compute_total_planting_quantity(self):
        for employee in self:
            total_quantity = sum(employee.production_id.mapped('quantity'))
            total_actual_quantity = sum(employee.production_id.mapped('actual_quantity'))
            total_product_loss = sum(employee.production_id.mapped('quantity_loss'))
            in_progress_quantity = sum(
                rec.quantity for rec in employee.production_id if rec.state == 'in_progress'
            )
            percentage_product_loss = (total_product_loss / total_quantity) if total_quantity else 0
            in_progress_percentage_quantity = (in_progress_quantity / total_quantity) if total_quantity else 0

            # Assign computed values
            employee.total_planting_quantity = total_quantity
            employee.total_actual_quantity = total_actual_quantity
            employee.total_product_loss = total_product_loss
            employee.in_progress_planting_quantity = in_progress_quantity
            employee.percentage_product_loss = percentage_product_loss
            employee.in_progress_percentage_quantity = in_progress_percentage_quantity

                
    @api.depends('asset_ids.area_ha')
    def _compute_total_area_ha(self):
        for record in self:
            total_area = sum(asset.area_ha for asset in record.asset_ids)
            record.total_area_ha = total_area

    @api.depends('parent_id')
    def _compute_organization_name(self):
        """Automatically fill organization_name from the parent company's name (if parent_id is set)."""
        for partner in self:
            if partner.parent_id:
                partner.organization_name = partner.parent_id.name
            else:
                partner.organization_name = False

    def _default_contract_file_name(self):
        """Generate default contract file name using partner's name and associate code."""
        name = (self.name or "Unnamed").replace(" ", "_")
        ilo_code = (self.ilo_associate_code or "NoCode").replace(" ", "_")
        return f"{name}_-_{ilo_code}.pdf"

    
    @api.onchange('name', 'ilo_associate_code')
    def _onchange_contract_file_name(self):
        """Update the contract file name based on name or associate code changes."""
        for record in self:
            name = (record.name or "Unnamed").replace(" ", "_")
            ilo_code = (record.ilo_associate_code or "NoCode").replace(" ", "_")
            record.contract_file_name = f"{name}_-_{ilo_code}.pdf"
    
    @api.model
    def create(self, vals):
        # Set default company if missing
        if not vals.get('company_id'):
            vals['company_id'] = self.env.user.company_id.id

        # Set a default associate code if 'ilo_associate' exists
        if 'ilo_associate' in vals and not vals.get('ilo_associate_code'):
            vals['ilo_associate_code'] = '000'  # Placeholder to ensure validation passes

        # Create the new partner record
        new_partner = super(ILOEmployee, self).create(vals)

        # Log creation for debugging purposes
        _logger.info(f"Created ILO Employee: {new_partner.name}")

        return new_partner


    def write(self, vals):
        """Ensure contract_file_name is updated when a new attachment is added."""
        for record in self:
            # Check if employment_contract is being modified (file uploaded)
            if 'employment_contract' in vals:
                name = (record.name or '').replace(" ", "_")
                ilo_code = (record.ilo_associate_code or '').replace(" ", "_")
                # Generate the contract file name
                vals['contract_file_name'] = f"{name}_-_{ilo_code}.pdf"
        return super(ILOEmployee, self).write(vals)


    def _ensure_location_warehouse(self, new_partner, vals):
        """
        Ensure stock location and warehouse generation or assignment.
        """
        location_name = f"{new_partner.name}'s Stock"
        _logger.info(f"Checking for stock location: {location_name}")
        location = self._create_stock_location(location_name, new_partner)

        if new_partner.parent_id:
            # Inherit parent's warehouse if parent exists
            _logger.info(f"Inheriting warehouse from parent for: {new_partner.name}")
            parent_warehouse = self.env['ilo.stock_location'].search([('employee_id', '=', new_partner.parent_id.id)], limit=1).warehouse_id
            location.warehouse_id = parent_warehouse
        else:
            # Otherwise, create a new warehouse
            _logger.info(f"Creating a new warehouse for: {new_partner.name}")
            warehouse = self._create_warehouse(f"{new_partner.name}'s Warehouse", new_partner)
            location.warehouse_id = warehouse


    def _create_stock_location(self, name, partner):
        """
        Create or retrieve a stock location.
        """
        # Ensure required fields are present
        if not partner.street:
            raise exceptions.ValidationError(_("Street address is required to create a stock location."))
        if not partner.city:
            raise exceptions.ValidationError(_("City is required to create a stock location."))
        if not partner.state_id:
            raise exceptions.ValidationError(_("State/Region is required to create a stock location."))
        if not partner.country_id:
            raise exceptions.ValidationError(_("Country is required to create a stock location."))

        _logger.info(f"Searching for stock location: {name}")
        location = self.env['ilo.stock_location'].search([('name', '=', name)], limit=1)

        if not location:
            _logger.info(f"Creating new stock location: {name}")
            return self.env['ilo.stock_location'].create({
                'name': name,
                'location_code': name[:3].upper(),
                'address': partner.street,
                'city': partner.city,
                'region': partner.state_id.name,
                'kabupaten_id': partner.kabupaten_id.id if partner.kabupaten_id else False,
                'kecamatan': partner.kecamatan,
                'kelurahan': partner.kelurahan,
                'country': partner.country_id.name,
                'employee_id': partner.id,
            })
        else:
            _logger.info(f"Found existing stock location: {location.name}")
        return location



    def _create_warehouse(self, name, partner):
        """
        Create or retrieve a warehouse for the partner.
        """
        # Ensure required fields are present
        if not partner.street:
            raise exceptions.ValidationError(_("Street address is required to create a warehouse."))
        if not partner.city:
            raise exceptions.ValidationError(_("City is required to create a warehouse."))
        if not partner.state_id:
            raise exceptions.ValidationError(_("State/Region is required to create a warehouse."))
        if not partner.country_id:
            raise exceptions.ValidationError(_("Country is required to create a warehouse."))

        _logger.info(f"Searching for warehouse: {name}")
        warehouse = self.env['ilo.warehouse'].search([('warehouse_name', '=', name)], limit=1)
        company_id = partner.company_id.id if partner.company_id else self.env.user.company_id.id

        if not warehouse:
            _logger.info(f"Creating new warehouse: {name}")
            return self.env['ilo.warehouse'].create({
                'warehouse_name': name,
                'warehouse_code': name[:3].upper(),
                'street': partner.street,
                'city': partner.city,
                'state_id': partner.state_id.id,
                'kabupaten_id': partner.kabupaten_id.id if partner.kabupaten_id else False,
                'kecamatan': partner.kecamatan,
                'kelurahan': partner.kelurahan,
                'country_id': partner.country_id.id,
                'actor_id': partner.id,
                'company_id': company_id
            })
        else:
            _logger.info(f"Found existing warehouse: {warehouse.warehouse_name}")
        return warehouse



    def _generate_ilo_associate_code(self, associate):
        """Generate a unique code for the ILO associate based on the type."""
        code_map = {
            'farmers': ('FA', 'ilo.employee.farmers.sequence'),
            'agent': ('AG', 'ilo.employee.agent.sequence'),
            'koperasi': ('KO', 'ilo.employee.koperasi.sequence'),
            'ugreen': ('UG', 'ilo.employee.ugreen.sequence'),
            'green': ('GR', 'ilo.employee.green.sequence')
        }
        prefix, sequence_code = code_map.get(associate, ('', ''))
        sequence = self.env['ir.sequence'].next_by_code(sequence_code) or '000'
        _logger.info(f"Generated ILO associate code: {prefix}{sequence} for associate type: {associate}")
        return f"{prefix}{sequence}"


    def action_confirm(self):
        """
        Action method to confirm the partner and change the state to 'confirm'.
        """
        for record in self:
            if record.state == 'confirm':
                raise exceptions.ValidationError(_("The record is already confirmed."))

            _logger.info(f"Confirming ILO Employee: {record.name}")

            # Generate organization_name from parent_id if missing
            if not record.organization_name and record.parent_id:
                record.organization_name = record.parent_id.name

            # Create a parent organization if missing but organization_name exists
            if not record.parent_id and record.organization_name:
                parent_org_vals = {'name': record.organization_name, 'is_company': True}
                if record.company_id:
                    parent_org_vals['company_id'] = record.company_id.id
                parent_org = self.env['res.partner'].create(parent_org_vals)
                record.parent_id = parent_org.id

            # Inherit company_id from parent_id if missing
            if not record.company_id and record.parent_id:
                record.company_id = record.parent_id.company_id.id

            # Generate the ILO Associate Code if it's missing or contains a placeholder
            if not record.ilo_associate_code or record.ilo_associate_code in ['000', 'PLACEHOLDER']:
                if not record.ilo_associate:  # Ensure 'associate_type' exists
                    raise exceptions.ValidationError(_("Associate type is required to generate the ILO Associate Code."))
                record.ilo_associate_code = self._generate_ilo_associate_code(record.ilo_associate)

            # Ensure contract file name is set
            if not record.contract_file_name:
                name = record.name.replace(" ", "_")
                ilo_code = record.ilo_associate_code.replace(" ", "_")
                record.contract_file_name = f"{name}_-_{ilo_code}.pdf"

            # Perform additional tasks like stock location and warehouse creation
            _logger.info(f"Creating stock location and warehouse for: {record.name}")
            self._ensure_location_warehouse(record, {
                'name': record.name,
                'ilo_associate_code': record.ilo_associate_code,
            })

            # Update the state to 'confirm'
            record.state = 'confirm'
            _logger.info(f"ILO Employee {record.name} confirmed with state: {record.state}")



class ProductProduct(models.Model):
    _inherit = 'product.product'

    batch_code = fields.Char(string='Batch Code', readonly=True)
    image_1920_url = fields.Char(string='Image URL', compute='_compute_image_1920_url')

    @api.depends('image_1920')
    def _compute_image_1920_url(self):
        """Compute the URL for image_1920 based on product ID."""
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        for record in self:
            if record.image_1920:
                record.image_1920_url = f"{base_url}/product/image/{record.id}"
            else:
                record.image_1920_url = False

    @api.model
    def create(self, vals):
        # Log the incoming values
        _logger.debug("Creating product with vals: %s", vals)

        # Retrieve the name directly from vals or from the related product template
        product_name = vals.get('name')
        if not product_name:
            product_tmpl_id = vals.get('product_tmpl_id')
            if product_tmpl_id:
                product_template = self.env['product.template'].browse(product_tmpl_id)
                product_name = product_template.name

        # Validate and generate the batch_code
        if 'batch_code' not in vals or vals['batch_code'] == '/':
            if product_name:
                vals['batch_code'] = self._generate_batch_code(product_name)
            else:
                raise exceptions.ValidationError("Product name must be provided to generate a batch code.")

        return super(ProductProduct, self).create(vals)

    def _generate_batch_code(self, product_name):
        """Generate batch code based on product name."""
        return self._generate_code(product_name)

    def _generate_code(self, text):
        """Generate code by taking first letters of words or first two letters."""
        words = text.split()
        if len(words) == 1:
            return words[0][:2].upper()
        else:
            return ''.join([word[0].upper() for word in words])
