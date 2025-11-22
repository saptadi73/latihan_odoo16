from odoo import models, fields, api
import qrcode
from io import BytesIO
import base64

class ILOQRCode(models.Model):
    _name = 'qr.code'
    _description = 'QR Code Management'

    # Name of the QR code record
    name = fields.Char(string='Name', required=True)

    # Data to encode in the QR code
    data = fields.Text(string='Data', required=True)

    # Field to store the QR code image
    qr_code = fields.Binary(string='QR Code Image', attachment=True)

    # Field to store the image filename
    qr_code_filename = fields.Char(string='QR Code Filename')

    @api.model
    def create(self, vals):
        """Override create method to generate QR code and set a dynamic filename."""
        if vals.get('data'):
            # Generate the QR code image
            vals['qr_code'] = self._generate_qr_code(vals['data'])
            
            # Set a dynamic filename based on the record's name or other context
            name_part = vals.get('name', 'qr_code').replace(' ', '_')  # Replace spaces for filename compatibility
            timestamp = fields.Datetime.now().strftime('%Y%m%d_%H%M%S')  # Add a timestamp
            vals['qr_code_filename'] = f"{name_part}_{timestamp}.png"
        
        return super(ILOQRCode, self).create(vals)

    def write(self, vals):
        """Override write method to regenerate QR code if data is updated."""
        if vals.get('data'):
            vals['qr_code'] = self._generate_qr_code(vals['data'])
            vals['qr_code_filename'] = 'qrcode.png'
        return super(ILOQRCode, self).write(vals)

    def _generate_qr_code(self, data):
        qr = qrcode.QRCode(version=1, box_size=10, border=4)
        qr.add_data(data)
        qr.make(fit=True)

        img = qr.make_image(fill='black', back_color='white')

        img_io = BytesIO()
        img.save(img_io, 'PNG')
        img_io.seek(0)

        qr_code_image = base64.b64encode(img_io.getvalue()).decode('utf-8')  # Added decode
        return qr_code_image


    @api.depends('data')
    def _compute_qr_code(self):
        """Compute QR code for existing records based on the data."""
        for record in self:
            if record.data:
                record.qr_code = self._generate_qr_code(record.data)
                record.qr_code_filename = 'qrcode.png'
