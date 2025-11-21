from odoo import models, fields, api

class Simpanan(models.Model):
    _name = 'simpan_pinjam.simpanan'
    _description = 'Data Simpanan Nasabah'

    nasabah_id = fields.Many2one(
        comodel_name='simpan_pinjam.nasabah', string='Nama Nasabah', required=True
    )
    jenis_simpanan = fields.Selection(
        selection=[
            ('wajib', 'Simpanan Wajib'),
            ('pokok', 'Simpanan Pokok'),
            ('sukarela', 'Simpanan Sukarela')
        ],
        string='Jenis Simpanan',
        required=True
    )
    jumlah_simpanan = fields.Float(string='Jumlah Simpanan', required=True)
    tanggal_simpanan = fields.Date(string='Tanggal Simpanan', required=True)

    # Method untuk mendapatkan semua simpanan wajib
    @api.model
    def get_simpanan_wajib(self):
        """Mengembalikan semua record simpanan dengan jenis wajib"""
        domain = [('jenis_simpanan', '=', 'wajib')]
        return self.search(domain)

    # Method untuk mendapatkan simpanan wajib dengan filter tambahan
    @api.model
    def get_simpanan_wajib_by_date_range(self, start_date, end_date):
        """Mengembalikan simpanan wajib dalam rentang tanggal tertentu"""
        domain = [
            ('jenis_simpanan', '=', 'wajib'),
            ('tanggal_simpanan', '>=', start_date),
            ('tanggal_simpanan', '<=', end_date)
        ]
        return self.search(domain)

    # Method untuk mendapatkan total simpanan wajib per nasabah
    @api.model
    def get_total_simpanan_wajib_per_nasabah(self):
        """Mengembalikan total simpanan wajib per nasabah"""
        query = """
            SELECT nasabah_id, SUM(jumlah_simpanan) as total
            FROM simpan_pinjam_simpanan
            WHERE jenis_simpanan = 'wajib'
            GROUP BY nasabah_id
        """
        self.env.cr.execute(query)
        results = self.env.cr.dictfetchall()
        return results

    # Method dengan search_read untuk mendapatkan data dalam format dictionary
    @api.model
    def get_simpanan_wajib_read(self, fields=None):
        """Mengembalikan simpanan wajib dalam format dictionary"""
        if fields is None:
            fields = ['nasabah_id', 'jumlah_simpanan', 'tanggal_simpanan']
        
        domain = [('jenis_simpanan', '=', 'wajib')]
        return self.search_read(domain, fields)