from odoo import models, fields, api
from odoo.exceptions import UserError

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
    # Tambahan konfigurasi dan link jurnal
    journal_id = fields.Many2one(
        'account.journal',
        string='Journal',
        domain=[('type', '=', 'general')],
        help='Miscellaneous Journal untuk pencatatan simpanan'
    )
    bank_account_id = fields.Many2one(
        'account.account',
        string='Akun Bank',
        domain=[('account_type', 'in', ['asset_cash', 'asset_current'])],
        help='Akun kas/bank untuk debit saat simpanan dibuat'
    )
    equity_account_id = fields.Many2one(
        'account.account',
        string='Akun Equity Simpanan',
        domain=[('account_type', 'in', ['equity', 'equity_unaffected'])],
        help='Akun ekuitas simpanan anggota untuk kredit'
    )
    move_id = fields.Many2one('account.move', string='Journal Entry', readonly=True)

    def action_open_move(self):
        self.ensure_one()
        if not self.move_id:
            raise UserError('Tidak ada Journal Entry untuk record ini.')
        return {
            'type': 'ir.actions.act_window',
            'name': 'Journal Entry',
            'res_model': 'account.move',
            'view_mode': 'form',
            'target': 'current',
            'res_id': self.move_id.id,
        }

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

    # Helper: ambil default miscellaneous journal jika tidak diisi
    def _get_default_misc_journal(self):
        company = self.env.company
        return self.env['account.journal'].search([('type', '=', 'general'), ('company_id', '=', company.id)], limit=1)

    # Buat journal entry otomatis saat create
    @api.model
    def create(self, vals):
        records = super().create(vals)
        for rec in records:
            rec._create_journal_for_simpanan()
        return records

    def _create_journal_for_simpanan(self):
        """Membuat account.move (Miscellaneous) + account.move.line untuk simpanan"""
        self.ensure_one()
        amount = self.jumlah_simpanan
        if amount <= 0:
            raise UserError('Jumlah simpanan harus lebih besar dari 0.')

        journal = self.journal_id or self._get_default_misc_journal()
        if not journal:
            raise UserError('Journal Miscellaneous tidak ditemukan. Isi field Journal di simpanan.')

        if not self.bank_account_id or not self.equity_account_id:
            raise UserError('Akun Bank dan Akun Equity Simpanan wajib diisi.')

        # Optional partner jika model nasabah terhubung ke res.partner
        partner_id = getattr(self.nasabah_id, 'partner_id', False) and self.nasabah_id.partner_id.id or False

        ref = f"Simpanan {dict(self._fields['jenis_simpanan'].selection).get(self.jenis_simpanan)} - {self.nasabah_id.display_name}"
        move_vals = {
            'move_type': 'entry',
            'journal_id': journal.id,
            'date': self.tanggal_simpanan,
            'ref': ref,
            'line_ids': [
                (0, 0, {
                    'name': ref,
                    'account_id': self.bank_account_id.id,
                    'partner_id': partner_id,
                    'debit': amount,
                    'credit': 0.0,
                }),
                (0, 0, {
                    'name': ref,
                    'account_id': self.equity_account_id.id,
                    'partner_id': partner_id,
                    'debit': 0.0,
                    'credit': amount,
                }),
            ],
        }
        move = self.env['account.move'].create(move_vals)
        move.action_post()
        self.move_id = move.id

    # Jika Anda butuh method untuk pembatalan simpanan + reverse journal, tambahkan sesuai kebutuhan.