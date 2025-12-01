from odoo import models, fields, api
from odoo.exceptions import UserError

class PencairanPinjaman(models.Model):
    _name = 'simpan_pinjam.pencairan_pinjaman'
    _description = 'Data Pencairan Pinjaman Nasabah'

    nasabah_id = fields.Many2one('simpan_pinjam.nasabah', string='Nama Nasabah', required=True)
    pinjaman_id = fields.Many2one(
        'simpan_pinjam.pinjaman', string='Pinjaman', required=True,
        domain="[('nasabah_id', '=', nasabah_id)]"
    )

    tanggal_pencairan = fields.Date(string='Tanggal Pencairan', required=True)
    jumlah_pencairan = fields.Float(string='Jumlah Pencairan', required=True)
    biaya_administrasi = fields.Float(string='Biaya Administrasi')
    biaya_provisi = fields.Float(string='Biaya Provisi')
    total_pencairan = fields.Float(string='Total Pencairan', compute='_compute_total_pencairan', store=True)
    metode_pencairan = fields.Selection(
        [('tunai', 'Tunai'), ('transfer', 'Transfer Bank'), ('cek_giro', 'Cek/Giro')],
        string='Metode Pencairan', required=True
    )

    # Akunting
    journal_id = fields.Many2one(
        'account.journal', string='Journal',
        domain=[('type', '=', 'general')],
        default=lambda self: self._get_default_misc_journal()
    )
    bank_account_id = fields.Many2one(
        'account.account', string='Akun Bank',
        domain=[('account_type', 'in', ['asset_cash', 'asset_current'])],
        required=True
    )
    receivable_account_id = fields.Many2one(
        'account.account', string='Akun Piutang Anggota',
        domain=[('account_type', '=', 'asset_receivable')],
        required=True
    )
    admin_fee_account_id = fields.Many2one(
        'account.account', string='Akun Pendapatan Administrasi',
        domain=[('account_type', 'in', ['income', 'income_other'])]
    )
    provisi_fee_account_id = fields.Many2one(
        'account.account', string='Akun Pendapatan Provisi',
        domain=[('account_type', 'in', ['income', 'income_other'])]
    )
    admin_fee_analytic_id = fields.Many2one(
        'account.analytic.account',
        string='Analytic (Pendapatan Administrasi)',
        help='Opsional: isi untuk memberi analytic 100% pada pendapatan administrasi.'
    )
    provisi_fee_analytic_id = fields.Many2one(
        'account.analytic.account',
        string='Analytic (Pendapatan Provisi)',
        help='Opsional: isi untuk memberi analytic 100% pada pendapatan provisi.'
    )
    move_id = fields.Many2one('account.move', string='Journal Entry', readonly=True)

    @api.depends('jumlah_pencairan', 'biaya_administrasi', 'biaya_provisi')
    def _compute_total_pencairan(self):
        for r in self:
            r.total_pencairan = r.jumlah_pencairan - (r.biaya_administrasi + r.biaya_provisi)

    @api.onchange('nasabah_id')
    def _onchange_nasabah_id(self):
        self.pinjaman_id = False

    @api.onchange('pinjaman_id')
    def _onchange_pinjaman_id(self):
        for rec in self:
            pinjaman = rec.pinjaman_id
            # Jika pinjaman adalah boolean (korup data), abaikan
            if not pinjaman or isinstance(pinjaman, bool):
                rec.jumlah_pencairan = 0.0
            else:
                rec.jumlah_pencairan = getattr(pinjaman, 'jumlah_pinjaman', 0.0) or 0.0

    def _get_default_misc_journal(self):
        return self.env['account.journal'].search(
            [('type', '=', 'general'), ('company_id', '=', self.env.company.id)], limit=1)

    @api.model
    def create(self, vals):
        recs = super().create(vals)
        for rec in recs:
            rec._create_disbursement_move()
        return recs

    def _create_disbursement_move(self):
        self.ensure_one()
        if self.move_id:
            return
        if self.jumlah_pencairan <= 0:
            raise UserError('Jumlah pencairan harus > 0.')

        # Sanitasi pinjaman_id (menghindari boolean True)
        pinjaman = self.pinjaman_id if self.pinjaman_id and not isinstance(self.pinjaman_id, bool) else False

        total_pencairan = self.jumlah_pencairan - (self.biaya_administrasi + self.biaya_provisi)

        journal = self.journal_id or self._get_default_misc_journal()
        if not journal:
            raise UserError('Journal misc tidak ditemukan.')
        if not self.bank_account_id or not self.receivable_account_id:
            raise UserError('Akun bank dan piutang wajib diisi.')

        if self.biaya_administrasi > 0 and not self.admin_fee_account_id:
            raise UserError('Biaya administrasi > 0. Isi Akun Pendapatan Administrasi.')
        if self.biaya_provisi > 0 and not self.provisi_fee_account_id:
            raise UserError('Biaya provisi > 0. Isi Akun Pendapatan Provisi.')

        partner_id = getattr(self.nasabah_id, 'partner_id', False) and self.nasabah_id.partner_id.id or False

        pinjaman_name = ''
        if pinjaman:
            pinjaman_name = getattr(pinjaman, 'name', False) or getattr(pinjaman, 'display_name', '') or ''
        nasabah_name = getattr(self.nasabah_id, 'display_name', '') or ''
        ref = f"Pencairan Pinjaman {pinjaman_name} - {nasabah_name}".strip().rstrip('-').strip()

        lines = []
        lines.append((0, 0, {
            'name': ref,
            'account_id': self.receivable_account_id.id,
            'partner_id': partner_id,
            'debit': self.jumlah_pencairan,
            'credit': 0.0,
        }))
        lines.append((0, 0, {
            'name': ref,
            'account_id': self.bank_account_id.id,
            'partner_id': partner_id,
            'debit': 0.0,
            'credit': total_pencairan,
        }))

        # Biaya Administrasi
        if self.biaya_administrasi > 0:
            admin_analytic = False
            if self.admin_fee_analytic_id:
                admin_analytic = {self.admin_fee_analytic_id.id: 100}  # 100% ke analytic
            lines.append((0, 0, {
                'name': ref + ' - Adm',
                'account_id': self.admin_fee_account_id.id,
                'partner_id': partner_id,
                'debit': 0.0,
                'credit': self.biaya_administrasi,
                # Tambahkan analytic (opsional)
                'analytic_distribution': admin_analytic if admin_analytic else False,
            }))

        # Biaya Provisi
        if self.biaya_provisi > 0:
            provisi_analytic = False
            if self.provisi_fee_analytic_id:
                provisi_analytic = {self.provisi_fee_analytic_id.id: 100}  # 100% ke analytic
            lines.append((0, 0, {
                'name': ref + ' - Provisi',
                'account_id': self.provisi_fee_account_id.id,
                'partner_id': partner_id,
                'debit': 0.0,
                'credit': self.biaya_provisi,
                # Tambahkan analytic (opsional)
                'analytic_distribution': provisi_analytic if provisi_analytic else False,
            }))

        total_debit = sum(l[2]['debit'] for l in lines)
        total_credit = sum(l[2]['credit'] for l in lines)
        if round(total_debit - total_credit, 2) != 0.0:
            raise UserError(f'Journal tidak seimbang (Debit={total_debit}, Credit={total_credit}).')

        move = self.env['account.move'].create({
            'move_type': 'entry',
            'journal_id': journal.id,
            'date': self.tanggal_pencairan,
            'ref': ref,
            'line_ids': lines,
        })
        move.action_post()
        self.move_id = move.id

    def action_open_move(self):
        self.ensure_one()
        if not self.move_id:
            raise UserError('Belum ada journal entry.')
        return {
            'type': 'ir.actions.act_window',
            'name': 'Journal Entry',
            'res_model': 'account.move',
            'view_mode': 'form',
            'target': 'current',
            'res_id': self.move_id.id,
        }
