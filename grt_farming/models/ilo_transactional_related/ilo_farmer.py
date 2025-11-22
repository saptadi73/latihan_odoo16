from odoo import models, fields, api, exceptions

class ILOFarmer(models.Model):
    _name = 'ilo.farmer'
    _description = 'ILO Farmer'

    farmer_name = fields.Many2one('res.partner', string='Farmer Name', required=True, help="Select the farmer from the list of partners.")
    farm_id = fields.Char(string='Farm ID', required=True, readonly=True, help="Unique identifier for the farm.")
    province = fields.Char(string='Province', required=True, help="Province where the farm is located.")
    crop_type = fields.Many2one('product.product', string='Crop Type', required=True, help="Link to the product as the crop type.")
    farm_size = fields.Float(string='Farm Size', default=5.0, help="Size of the farm in hectares or acres.")
    farm_location = fields.Char(string='Farm Location', help="Location of the farm.")
    production_capacity = fields.Float(string='Production Capacity', help="The maximum production capacity of the farm.")

    @api.model
    def create(self, vals):
        """
        Create method override to ensure that only partners with the 'Farmer' actor type
        can create a farm. Generates farm ID during creation.
        """
        partner = self.env['res.partner'].browse(vals.get('farmer_name'))
        if partner.ilo_associate != 'farmer':  # Validate 'ilo_associate' is farmer
            raise exceptions.ValidationError("Farm can only be created for partners with the 'Farmer' actor type.")

        # Generate farm ID upon creation
        vals['farm_id'] = self._generate_farm_id(vals.get('province'), vals.get('crop_type'))
        return super(ILOFarmer, self).create(vals)

    def write(self, vals):
        """
        Write method override to regenerate farm_id if province or crop_type changes.
        """
        if 'province' in vals or 'crop_type' in vals:
            # Fetch the updated province and crop type values
            province = vals.get('province', self.province)
            crop_type = vals.get('crop_type', self.crop_type.name)
            vals['farm_id'] = self._generate_farm_id(province, crop_type)
        return super(ILOFarmer, self).write(vals)

    def _generate_farm_id(self, province, crop_type):
        """
        Generate a unique farm ID based on province code, crop type, and a sequence number.
        """
        # Generate codes for province and crop type
        province_code = self._generate_code(province)
        crop_code = self._generate_code(crop_type)

        # Generate a sequence number for uniqueness
        sequence = self.env['ir.sequence'].next_by_code('ilofarmer.sequence')
        if not sequence:
            raise exceptions.UserError('Sequence for Farmer ID is missing. Please configure it in the settings.')

        # Combine province code, crop code, and sequence to generate a unique farm ID
        return f'{province_code}-{crop_code}-{sequence}'

    def _generate_code(self, text):
        """
        Generate a code from a given text. If the text has one word, return the first two letters.
        If the text has multiple words, return the first letter of each word.
        """
        words = text.split()
        if len(words) == 1:
            return words[0][:2].upper()
        else:
            return ''.join([word[0].upper() for word in words])

    @api.onchange('province', 'crop_type')
    def _onchange_province_crop(self):
        """
        Onchange method to regenerate farm ID whenever the province or crop type changes.
        """
        if self.province and self.crop_type:
            self.farm_id = self._generate_farm_id(self.province, self.crop_type.name)

