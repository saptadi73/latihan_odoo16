from odoo import models, fields

class ResKabupaten(models.Model):
    _name = 'res.kabupaten'
    _description = 'Kabupaten/Kota'

    name = fields.Char(string='Nama Kabupaten', required=True)
    # code = fields.Char(string='Kode Kabupaten', required=True)
    state_id = fields.Many2one('res.country.state', string='Provinsi', required=True)

