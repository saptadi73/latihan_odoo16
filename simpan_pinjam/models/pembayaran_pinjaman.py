from odoo import models, fields, api

class PembayaranPinjaman(models.Model):
    _name = 'simpan_pinjam.pembayaran_pinjaman'
    _description = 'Data Pembayaran Pinjaman Nasabah'

    nasabah_id = fields.Many2one(
        comodel_name='simpan_pinjam.nasabah', string='Nama Nasabah', required=True
    )
    pinjaman_id = fields.Many2one(
        comodel_name='simpan_pinjam.pinjaman', string='Pinjaman', required=True,
        domain="[('nasabah_id', '=', nasabah_id)]"
    )

    @api.onchange('nasabah_id')
    def _onchange_nasabah_id(self):
        self.pinjaman_id = False

    @api.onchange('pinjaman_id')
    def _onchange_pinjaman_id(self):
        if self.pinjaman_id:
            self.jumlah_pembayaran = self.pinjaman_id.pembayaran_per_bulan
        else:
            self.jumlah_pembayaran = 0.0

    tanggal_pembayaran = fields.Date(string='Tanggal Pembayaran', required=True)
    jumlah_pembayaran = fields.Float(string='Jumlah Pembayaran', required=True)
    metode_pembayaran = fields.Selection(
        selection=[
            ('tunai', 'Tunai'),
            ('transfer', 'Transfer Bank'),
            ('cek_giro', 'Cek/Giro')
        ],
        string='Metode Pembayaran',
        required=True
    )
