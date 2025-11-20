from odoo import models, fields, api

class PencairanPinjaman(models.Model):
    _name = 'simpan_pinjam.pencairan_pinjaman'
    _description = 'Data Pencairan Pinjaman Nasabah'

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
            self.jumlah_pencairan = self.pinjaman_id.jumlah_pinjaman
        else:
            self.jumlah_pencairan = 0.0

    tanggal_pencairan = fields.Date(string='Tanggal Pencairan', required=True)
    jumlah_pencairan = fields.Float(string='Jumlah Pencairan', required=True)
    biaya_administrasi = fields.Float(string='Biaya Administrasi', required=False)
    biaya_provisi = fields.Float(string='Biaya Provisi', required=False)
    total_pencairan = fields.Float(string='Total Pencairan', compute='_compute_total_pencairan', store=True)
    metode_pencairan = fields.Selection(
        selection=[
            ('tunai', 'Tunai'),
            ('transfer', 'Transfer Bank'),
            ('cek_giro', 'Cek/Giro')
        ],
        string='Metode Pencairan',
        required=True
    )

    @api.depends('jumlah_pencairan', 'biaya_administrasi', 'biaya_provisi')
    def _compute_total_pencairan(self):
        for record in self:
            total = record.jumlah_pencairan - (record.biaya_administrasi + record.biaya_provisi)
            record.total_pencairan = total
