from odoo import models, fields, api, exceptions
import base64
import logging
import json

_logger = logging.getLogger(__name__)

class ILOAssets(models.Model):
    _name = 'ilo.assets'
    _description = 'Manajemen Lahan untuk Petani'
    _inherit = ['portal.mixin', 'mail.thread', 'mail.activity.mixin']

    #Status
    status = fields.Selection(
        [('draft', 'Draft'), ('confirm', 'Confirm')],
        string='Status',
        default='draft',
        required=True,
        tracking=True,
        help="Status Lahan. 'Draft' menunggu konfirmasi sebelum dapat dibuat; 'Confirm' telah dikonfirmasi."
    )
    # Produk & Karyawan
    product_id = fields.Many2one('product.product', string='Produk', required=True, help="Pilih produk yang terkait dengan aset ini.", ondelete='restrict')
    name = fields.Char(string='Kode Lahan', readonly=True, help="Nama aset akan diatur sebagai ID farm, mewakili kode unik untuk aset ini.", tracking=True)
    employee_id = fields.Many2one('res.partner', string="Nama Petani", domain="[('ilo_associate', '=', 'farmers')]", required=True)
    employee_ilo_associate = fields.Selection([('farmers', 'Petani'), ('agent', 'Agen'), ('koperasi', 'Koperasi'), ('ugreen', 'UGreen'), ('green', 'Green')], 
                                              string='Kode Asosiasi', related='employee_id.ilo_associate', store=True)
    employee_ilo_associate_code = fields.Char(string='Kode Petani', related='employee_id.ilo_associate_code')

    # Lokasi & Alamat
    coordinates = fields.Char(string='Koordinat (Lat,Long)(**)')
    address = fields.Text(string='Alamat(**)', help="Alamat lengkap lokasi aset.")
    state_id = fields.Many2one('res.country.state', string='Provinsi(**)', help="Pilih provinsi tempat aset berada.", tracking=True)
    kabupaten_id = fields.Many2one('res.kabupaten', string='Kabupaten/Kota(**)', help="Pilih kabupaten/kota tempat aset berada.")
    
    # Status & Luas
    ownership_status = fields.Selection([('rent', 'Sewa'), ('self_owned', 'Miliki Sendiri'), ('other', 'Lainnya')], string='Status Kepemilikan')
    area_ha = fields.Float(string='Luas Aset(**)')
    area_uom = fields.Many2one('uom.uom', string='Satuan Ukur Luas', default=9, help="Default Set Luas Lahan adalah meter persegi.")
    average_yield_per_m2 = fields.Float(string='Rata-rata Hasil (kg/m²)', default=0.003, store=True, help="Hasil rata-rata per meter persegi, bisa spesifik untuk jenis tanaman")
    
    # Status Penanaman & Panen
    planting_status = fields.Selection([('proses', 'Proses'), ('belum aktif', 'Tidak Aktif')], string='Status Penanaman', default='belum aktif', tracking=True)
    harvesting_status = fields.Selection([('proses', 'Proses'), ('belum aktif', 'Tidak Aktif')], string='Status Panen', default='belum aktif', tracking=True)

    # Kapasitas & Produksi
    production_capacity = fields.Float(string='Kapasitas Produksi Perkiraan (kg)', compute='_compute_production_capacity', store=True,
                                      help='Dihitung sebagai: Luas × Faktor Konversi × Hasil Rata-rata per m². Pastikan "Luas" dan "Hasil Rata-rata per m²" diisi untuk menghitung kapasitas.')
    uom_id = fields.Many2one('uom.uom', string='Satuan Ukur', default=lambda self: self.env.ref('uom.product_uom_kgm').id)
    area_conversion_factor = fields.Float(string="Faktor Konversi", default=10000, store=True, help='Konversi ke m²')

    # ID Farm & Shapefile
    farm_id = fields.Char(string='ID Farm', readonly=True, store=True, help="Identifikasi unik untuk farm.")
    shp_file = fields.Binary(string='Shapefile (.GeoJSON)', help="Unggah file .shp untuk aset ini.")
    shp_filename = fields.Char(string='Nama GeoJSON', compute='_compute_shp_filename', store=True, help="Nama file .shp yang diunggah.")
    shp_file_url = fields.Char(string='GeoJSON URL', compute='_compute_asset_shp_url', store=True)

    # Gambar Aset
    asset_image = fields.Binary(string='Gambar Lahan')
    asset_image_url = fields.Char(string='URL Gambar Lahan', compute='_compute_asset_image_url')

    #Misc
    dashboard_id=fields.Many2one('ilo.dashboard', string='Dashboard')
    
    @api.depends('asset_image')
    def _compute_asset_image_url(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        for record in self:
            # record.image_1920_url = f"{base_url}/web/image?model=res.partner&id={record.id}&field=image_1920"
            if record.asset_image:
                record.asset_image_url = f"{base_url}/ilo_asset/image/{record.id}"
            else:
                record.asset_image_url = False    


    @api.depends('shp_file', 'shp_filename')
    def _compute_asset_shp_url(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        for record in self:
            if record.shp_file and record.shp_filename:
                # Include the filename in the URL
                sanitized_filename = record.shp_filename.replace(" ", "_")  # Replace spaces with underscores for URL safety
                record.shp_file_url = f"{base_url}/ilo_asset/geojson/{record.id}/{sanitized_filename}"
            else:
                record.shp_file_url = False


    @api.depends('employee_id', 'farm_id')
    def _compute_shp_filename(self):
        for asset in self:
            if asset.employee_id and asset.farm_id:
                # Employee and farm details combined for filename
                employee_name = asset.employee_id.name.replace(" ", "")
                asset.shp_filename = f"{employee_name}-Asset-{asset.farm_id}.json"
            else:
                asset.shp_filename = 'default_filename.json'  # Fallback in case fields are missing


    @api.depends('area_ha', 'average_yield_per_m2', 'area_conversion_factor')
    def _compute_production_capacity(self):
        for asset in self:
            if asset.area_ha and asset.average_yield_per_m2 and asset.area_conversion_factor:
                asset.production_capacity = asset.area_ha * asset.area_conversion_factor * asset.average_yield_per_m2
            else:
                asset.production_capacity = 0.0

    @api.model
    def create(self, vals):
        _logger.info("Starting ILOAssets creation with values: %s", vals)

        if not vals.get('product_id'):
            raise exceptions.ValidationError("Product must be selected.")

        product = self.env['product.product'].browse(vals['product_id'])

        if vals.get('employee_id'):
            employee = self.env['res.partner'].browse(vals['employee_id'])
            if not employee.exists():
                raise exceptions.ValidationError("The selected employee does not exist. Create it from Keanggotaan. ILO Farming Perspective->Keanggotaan->New")

        state = self.env['res.country.state'].browse(vals.get('state_id'))
        kabupaten = self.env['res.kabupaten'].browse(vals.get('kabupaten_id'))  # Reference to res.kabupaten

        if not product.name:
            raise exceptions.ValidationError("Product name cannot be empty.")
        if state and not state.name:
            raise exceptions.ValidationError("State name cannot be empty.")
        if kabupaten and not kabupaten.name:
            raise exceptions.ValidationError("Kabupaten name cannot be empty.")  # Validation for Kabupaten

        # File validation: Check if the shp_file is a valid JSON (either GeoJSON or general JSON)
        if vals.get('shp_file'):
            shp_file = base64.b64decode(vals['shp_file'])
            try:
                # Try to parse the file content to JSON to ensure it's a valid JSON
                json_data = json.loads(shp_file)
            except (ValueError, TypeError):
                raise exceptions.ValidationError("The uploaded file is not a valid JSON or GeoJSON file.")

        return super(ILOAssets, self).create(vals)


    def write(self, vals):
        for record in self:
            # Check if certain fields are being updated and reset the status to 'draft'
            fields_to_check = ['product_id', 'employee_id', 'coordinates', 'address', 'state_id', 'kabupaten_id', 'area_ha', 
                            'average_yield_per_m2', 'production_capacity', 'shp_file', 'asset_image', 'ownership_status']

            # If any of the listed fields are present in the update, reset the status to 'draft'
            if any(field in vals for field in fields_to_check):
                vals['status'] = 'draft'

            # File validation: Check if the shp_file is a valid JSON (either GeoJSON or general JSON)
            if 'shp_file' in vals:
                shp_file = base64.b64decode(vals['shp_file'])
                try:
                    # Try to parse the file content to JSON to ensure it's a valid JSON
                    json_data = json.loads(shp_file)
                except (ValueError, TypeError):
                    raise exceptions.ValidationError("The uploaded file is not a valid JSON or GeoJSON file.")

            # Ensure shapefile filename is recomputed properly
            if 'shp_file' in vals or 'employee_id' in vals or 'farm_id' in vals:
                # Manually compute shp_filename
                employee_name = record.employee_id.name.replace(" ", "") if record.employee_id else "default"
                farm_id = record.farm_id or "unknown"
                vals['shp_filename'] = f"{employee_name}-Asset-{farm_id}.json"

        # Call the parent write method to handle all standard operations
        result = super(ILOAssets, self).write(vals)
        return result


    def _generate_farm_id(self, product, state, kabupaten, employee, area_ha):
        province = state.name or 'UNKNOWN'
        kabupaten_name = kabupaten.name or 'UNKNOWN'  # Kabupaten name included in the farm ID
        ilo_associate_code = employee.ilo_associate_code or 'F000'

        # Use the passed area_ha instead of self.area_ha
        area_str = f'{int(area_ha):04d}' if area_ha else '0000'

        name_code = self._generate_code(product.name)
        province_code = self._generate_code(province)
        kabupaten_code = self._generate_code(kabupaten_name)  # Generate code for Kabupaten

        # Replace capacity_str with area_str
        farm_id = f'{name_code}-{province_code}-{kabupaten_code}-{ilo_associate_code}-{area_str}'

        return farm_id

    def _generate_code(self, text):
        words = text.split()
        if len(words) == 1:
            code = words[0][:3].upper()
        else:
            code = ''.join([word[0].upper() for word in words])
        return code

    def set_inactive(self, process_type='planting'):
        if process_type == 'planting':
            self.planting_status = 'belum aktif'
        elif process_type == 'harvesting':
            self.harvesting_status = 'belum aktif'

    def set_in_progress(self, process_type='planting'):
        if process_type == 'planting':
            self.planting_status = 'proses'
        elif process_type == 'harvesting':
            self.harvesting_status = 'proses'


    def action_confirm(self):
        for record in self:
            if record.status == 'draft':
                # Ensure farm_id is generated during confirmation
                product = record.product_id
                state = record.state_id
                kabupaten = record.kabupaten_id
                employee = record.employee_id
                area_ha = record.area_ha

                if not product or not product.name:
                    raise exceptions.ValidationError("Product name is required to generate Farm ID.")
                if not state or not state.name:
                    raise exceptions.ValidationError("State name is required to generate Farm ID.")
                if not kabupaten or not kabupaten.name:
                    raise exceptions.ValidationError("Kabupaten name is required to generate Farm ID.")
                if not employee or not employee.ilo_associate_code:
                    raise exceptions.ValidationError("Associate code is required to generate Farm ID.")

                record.farm_id = self._generate_farm_id(product, state, kabupaten, employee, area_ha)
                record.name = record.farm_id  # Update the name with the farm_id

                # Generate shp_filename based on employee and farm_id
                employee_name = employee.name.replace(" ", "") if employee else "UNKNOWN"
                record.shp_filename = f"{employee_name}-Lahan-{record.farm_id}.json"

                # Update the status to 'confirm'
                record.status = 'confirm'
            else:
                raise exceptions.UserError("Asset is already confirmed and cannot be reverted to draft.")
