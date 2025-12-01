from odoo import models, fields, api
from odoo.exceptions import UserError

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
        for rec in self:
            pinjaman = rec.pinjaman_id if rec.pinjaman_id and not isinstance(rec.pinjaman_id, bool) else False
            if pinjaman:
                rec.pembayaran_pokok = getattr(pinjaman, 'pembayaran_pokok_pinjaman_per_bulan', 0.0) or 0.0
                rec.pembayaran_bunga = getattr(pinjaman, 'pembayaran_bunga_pinjaman_per_bulan', 0.0) or 0.0
            else:
                rec.pembayaran_pokok = 0.0
                rec.pembayaran_bunga = 0.0

    tanggal_pembayaran = fields.Date(string='Tanggal Pembayaran', required=True)
    pembayaran_pokok = fields.Float(string='Pembayaran Pokok per Bulan', required=True)
    pembayaran_bunga = fields.Float(string='Pembayaran Bunga per Bulan', required=True)
    jumlah_pembayaran = fields.Float(string='Total Pembayaran', compute='_compute_jumlah_pembayaran', store=True)

    @api.depends('pembayaran_pokok', 'pembayaran_bunga')
    def _compute_jumlah_pembayaran(self):
        for rec in self:
            rec.jumlah_pembayaran = (rec.pembayaran_pokok or 0.0) + (rec.pembayaran_bunga or 0.0)

    metode_pembayaran = fields.Selection(
        selection=[('tunai', 'Tunai'), ('transfer', 'Transfer Bank'), ('cek_giro', 'Cek/Giro')],
        string='Metode Pembayaran', required=True
    )

    # Accounting
    journal_id = fields.Many2one(
        'account.journal', string='Journal',
        domain=[('type', '=', 'general')],
        default=lambda self: self._get_default_misc_journal(),
        help='Miscellaneous Journal untuk pencatatan pembayaran'
    )
    bank_account_id = fields.Many2one(
        'account.account', string='Akun Bank',
        domain=[('account_type', 'in', ['asset_cash', 'asset_current'])],
        required=True
    )
    receivable_account_id = fields.Many2one(
        'account.account', string='Akun Piutang Anggota',
        domain=[('account_type', '=', 'asset_receivable')],
        required=True,
        help='Akun piutang untuk pembayaran pokok'
    )
    interest_income_account_id = fields.Many2one(
        'account.account', string='Akun Pendapatan Bunga',
        domain=[('account_type', 'in', ['income', 'income_other'])],
        help='Akun pendapatan untuk pembayaran bunga.'
    )

    # Dua jurnal terpisah
    move_interest_id = fields.Many2one('account.move', string='JE Bunga', readonly=True)
    move_principal_id = fields.Many2one('account.move', string='JE Pokok', readonly=True)

    # (Opsional) Backward compatibility; tidak lagi dipakai
    move_id = fields.Many2one('account.move', string='Journal Entry', readonly=True)

    # Tambahkan opsi Analytic untuk JE bunga
    analytic_account_id = fields.Many2one(
        'account.analytic.account',
        string='Analytic Account (Pendapatan Bunga)',
        help='Jika diisi, journal pendapatan bunga akan diberi analytic 100%.'
    )

    def _get_default_misc_journal(self):
        return self.env['account.journal'].search(
            [('type', '=', 'general'), ('company_id', '=', self.env.company.id)], limit=1)

    @api.model
    def create(self, vals):
        recs = super().create(vals)
        for rec in recs:
            rec._create_payment_moves_split()
        return recs

    def _create_payment_moves_split(self):
        """Buat 2 journal terpisah: bunga dan pokok."""
        self.ensure_one()
        if (self.move_interest_id or self.pembayaran_bunga == 0.0) and (self.move_principal_id or self.pembayaran_pokok == 0.0):
            return
        if self.pembayaran_pokok < 0 or self.pembayaran_bunga < 0:
            raise UserError('Pembayaran pokok/bunga tidak boleh negatif.')

        journal = self.journal_id or self._get_default_misc_journal()
        if not journal:
            raise UserError('Journal Misc tidak ditemukan.')
        if not self.bank_account_id:
            raise UserError('Akun Bank wajib diisi.')
        if self.pembayaran_pokok > 0 and not self.receivable_account_id:
            raise UserError('Akun Piutang wajib untuk pembayaran pokok.')
        if self.pembayaran_bunga > 0 and not self.interest_income_account_id:
            raise UserError('Akun Pendapatan Bunga wajib untuk pembayaran bunga.')

        partner_id = getattr(self.nasabah_id, 'partner_id', False) and self.nasabah_id.partner_id.id or False
        pinjaman = self.pinjaman_id if self.pinjaman_id and not isinstance(self.pinjaman_id, bool) else False
        pinjaman_name = getattr(pinjaman, 'name', '') or getattr(pinjaman, 'display_name', '') or ''
        nasabah_name = getattr(self.nasabah_id, 'display_name', '') or ''
        base_ref = f"Pembayaran Pinjaman {pinjaman_name} - {nasabah_name}".strip().rstrip('-').strip()

        # 1) Jurnal Bunga: DR Bank, CR Pendapatan Bunga
        if self.pembayaran_bunga > 0 and not self.move_interest_id:
            ref_bunga = f"{base_ref} - Bunga"
            # siapkan analytic_distribution jika analytic diisi
            analytic_dist = False
            if self.analytic_account_id:
                # Odoo 16: gunakan analytic_distribution (persentase 100)
                analytic_dist = {self.analytic_account_id.id: 100}

            move_bunga = self.env['account.move'].create({
                'move_type': 'entry',
                'journal_id': journal.id,
                'date': self.tanggal_pembayaran,
                'ref': ref_bunga,
                'line_ids': [
                    (0, 0, {
                        'name': ref_bunga,
                        'account_id': self.bank_account_id.id,
                        'partner_id': partner_id,
                        'debit': self.pembayaran_bunga,
                        'credit': 0.0,
                    }),
                    (0, 0, {
                        'name': ref_bunga,
                        'account_id': self.interest_income_account_id.id,
                        'partner_id': partner_id,
                        'debit': 0.0,
                        'credit': self.pembayaran_bunga,
                        # tambahkan analytic (opsional)
                        'analytic_distribution': analytic_dist if analytic_dist else False,
                    }),
                ],
            })
            move_bunga.action_post()
            self.move_interest_id = move_bunga.id
            # Isi move_id untuk kompatibilitas (pertama kali di-set)
            if not self.move_id:
                self.move_id = move_bunga.id

        # 2) Jurnal Pokok: DR Bank, CR Piutang Anggota
        if self.pembayaran_pokok > 0 and not self.move_principal_id:
            ref_pokok = f"{base_ref} - Pokok"
            move_pokok = self.env['account.move'].create({
                'move_type': 'entry',
                'journal_id': journal.id,
                'date': self.tanggal_pembayaran,
                'ref': ref_pokok,
                'line_ids': [
                    (0, 0, {
                        'name': ref_pokok,
                        'account_id': self.bank_account_id.id,
                        'partner_id': partner_id,
                        'debit': self.pembayaran_pokok,
                        'credit': 0.0,
                    }),
                    (0, 0, {
                        'name': ref_pokok,
                        'account_id': self.receivable_account_id.id,
                        'partner_id': partner_id,
                        'debit': 0.0,
                        'credit': self.pembayaran_pokok,
                    }),
                ],
            })
            move_pokok.action_post()
            self.move_principal_id = move_pokok.id
            if not self.move_id:
                self.move_id = move_pokok.id

    # Actions
    def action_open_interest_move(self):
        self.ensure_one()
        if not self.move_interest_id:
            raise UserError('Belum ada Journal Entry Bunga.')
        return {
            'type': 'ir.actions.act_window',
            'name': 'Journal Entry Bunga',
            'res_model': 'account.move',
            'view_mode': 'form',
            'target': 'current',
            'res_id': self.move_interest_id.id,
        }

    def action_open_principal_move(self):
        self.ensure_one()
        if not self.move_principal_id:
            raise UserError('Belum ada Journal Entry Pokok.')
        return {
            'type': 'ir.actions.act_window',
            'name': 'Journal Entry Pokok',
            'res_model': 'account.move',
            'view_mode': 'form',
            'target': 'current',
            'res_id': self.move_principal_id.id,
        }

    # Legacy
    def action_open_move(self):
        self.ensure_one()
        if not self.move_id:
            raise UserError('Belum ada Journal Entry.')
        return {
            'type': 'ir.actions.act_window',
            'name': 'Journal Entry',
            'res_model': 'account.move',
            'view_mode': 'form',
            'target': 'current',
            'res_id': self.move_id.id,
        }
