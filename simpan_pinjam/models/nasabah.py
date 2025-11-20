from odoo import models, fields,api
class Nasabah(models.Model):
    _name = 'simpan_pinjam.nasabah'
    _description = 'Data Nasabahres.partner'
    _rec_name = 'nama'

    nama = fields.Many2one(
        comodel_name='res.partner',string='Nama Nasabah',required=True
    )
    nik = fields.Text(string='nik')
    tanggal_lahir = fields.Date(string='Tanggal Lahir')
    no_anggota = fields.Char(string='No Anggota')
    usaha = fields.Text(string='Usaha')
    alamat_usaha = fields.Text(string='Alamat Usaha')