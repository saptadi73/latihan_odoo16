from odoo import models, fields,api

class Simpanan(models.Model):
    _name = 'simpan_pinjam.simpanan'
    _description = 'Data Simpanan Nasabah'

    nasabah_id = fields.Many2one(
        comodel_name='simpan_pinjam.nasabah',string='Nama Nasabah',required=True
    )
    jenis_simpanan = fields.Selection(
        selection=[
            ('wajib','Simpanan Wajib'),
            ('pokok','Simpanan Pokok'),
            ('sukarela','Simpanan Sukarela')
        ],
        string='Jenis Simpanan',
        required=True
    )
    jumlah_simpanan = fields.Float(string='Jumlah Simpanan',required=True)
    tanggal_simpanan = fields.Date(string='Tanggal Simpanan',required=True)