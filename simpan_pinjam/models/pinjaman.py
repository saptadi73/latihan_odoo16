from odoo import models, fields, api

class Pinjaman(models.Model):
    _name = 'simpan_pinjam.pinjaman'
    _description = 'Data Pinjaman Nasabah'

    nasabah_id = fields.Many2one(
        comodel_name='simpan_pinjam.nasabah', string='Nama Nasabah', required=True
    )
    jumlah_pinjaman = fields.Float(string='Jumlah Pinjaman', required=True)
    tanggal_pinjaman = fields.Date(string='Tanggal Pinjaman', required=True)
    tenor = fields.Integer(string='Tenor (Bulan)', required=True)
    pembayaran_per_bulan = fields.Float(string='Pembayaran per Bulan', compute='_compute_pembayaran_per_bulan', store=True)
    bunga = fields.Float(string='Bunga (%)', required=True)
    status = fields.Selection(
        selection=[
            ('aktif', 'Aktif'),
            ('lunas', 'Lunas'),
            ('macet', 'Macet')
        ],
        string='Status Pinjaman',
        default='aktif',
        required=True
    )

    @api.depends('jumlah_pinjaman', 'bunga', 'tenor')
    def _compute_pembayaran_per_bulan(self):
        for record in self:
            if record.tenor > 0:
                total_pinjaman_dengan_bunga = record.jumlah_pinjaman + (record.jumlah_pinjaman * record.bunga / 100)
                pembayaran = total_pinjaman_dengan_bunga / record.tenor
                record.pembayaran_per_bulan = round(pembayaran / 100) * 100
            else:
                record.pembayaran_per_bulan = 0.0
