from odoo import models, fields

class ResPartner(models.Model):
    _inherit = 'res.partner'

    kabupaten_id = fields.Many2one('res.kabupaten', string='Kabupaten/Kota')
    kecamatan = fields.Char(string='Kecamatan')
    kelurahan = fields.Char(string='Kelurahan')

    education_level_id = fields.Many2one('education.level', string="Education Level", help="Select the education level of the partner.")
