from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError

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
    # Ubah: hilangkan domain statis agar bisa dikontrol dinamis via onchange
    equity_account_id = fields.Many2one(
        'account.account',
        string='Akun Simpanan (Equity/Liability)',
        help='Untuk Wajib/Pokok gunakan Equity; untuk Sukarela gunakan Liability.'
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

    @api.onchange('jenis_simpanan')
    def _onchange_jenis_simpanan_set_domain(self):
        """Set domain dinamis untuk equity_account_id berdasarkan jenis simpanan."""
        if self.jenis_simpanan == 'sukarela':
            domain = [('account_type', 'in', ['liability_current', 'liability_non_current', 'liability_payable'])]
            # Gunakan getattr untuk amankan akses
            acc_type = getattr(self.equity_account_id, 'account_type', None)
            if acc_type not in ['liability_current', 'liability_non_current', 'liability_payable']:
                self.equity_account_id = False
        else:
            domain = [('account_type', 'in', ['equity', 'equity_unaffected'])]
            acc_type = getattr(self.equity_account_id, 'account_type', None)
            if acc_type not in ['equity', 'equity_unaffected']:
                self.equity_account_id = False
        return {'domain': {'equity_account_id': domain}}

    @api.constrains('jenis_simpanan', 'equity_account_id')
    def _check_account_type_matches_simpanan(self):
        """Validasi tipe akun sesuai jenis simpanan."""
        for rec in self:
            if not rec.equity_account_id:
                continue
            acc_type = getattr(rec.equity_account_id, 'account_type', None)
            if rec.jenis_simpanan == 'sukarela' and acc_type not in ['liability_current', 'liability_non_current', 'liability_payable']:
                raise ValidationError('Untuk Simpanan Sukarela, pilih akun bertipe Liability (Current/Non-Current/Payable).')
            if rec.jenis_simpanan in ['wajib', 'pokok'] and acc_type not in ['equity', 'equity_unaffected']:
                raise ValidationError('Untuk Simpanan Wajib/Pokok, pilih akun bertipe Equity atau Unaffected Earnings.')

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
            raise UserError('Akun Bank dan Akun Simpanan wajib diisi.')

        # Validasi tambahan saat posting (safe getattr)
        acc_type = getattr(self.equity_account_id, 'account_type', None)
        if self.jenis_simpanan == 'sukarela' and acc_type not in ['liability_current', 'liability_non_current', 'liability_payable']:
            raise UserError('Akun Simpanan untuk Sukarela harus bertipe Liability.')
        if self.jenis_simpanan in ['wajib', 'pokok'] and acc_type not in ['equity', 'equity_unaffected']:
            raise UserError('Akun Simpanan untuk Wajib/Pokok harus bertipe Equity/Unaffected.')

        partner = getattr(self.nasabah_id, 'partner_id', None)
        partner_id = partner.id if partner else False

        # SAFE IDs untuk type checker (hindari Literal[True])
        journal_id = getattr(journal, 'id', False)
        bank_account_id = getattr(self.bank_account_id, 'id', False)
        equity_account_id = getattr(self.equity_account_id, 'id', False)
        if not journal_id or not bank_account_id or not equity_account_id:
            raise UserError('Data akun/journal tidak valid.')

        ref = f"Simpanan {dict(self._fields['jenis_simpanan'].selection).get(self.jenis_simpanan)} - {self.nasabah_id.display_name}"
        move_vals = {
            'move_type': 'entry',
            'journal_id': journal_id,
            'date': self.tanggal_simpanan,
            'ref': ref,
            'line_ids': [
                (0, 0, {
                    'name': ref,
                    'account_id': bank_account_id,
                    'partner_id': partner_id,
                    'debit': amount,
                    'credit': 0.0,
                }),
                (0, 0, {
                    'name': ref,
                    'account_id': equity_account_id,
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