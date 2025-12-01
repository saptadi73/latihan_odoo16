# -*- coding: utf-8 -*-
from odoo import models, api, fields
from odoo.exceptions import UserError  # ← TAMBAHKAN INI
import logging

_logger = logging.getLogger(__name__)

class Consolidation(models.Model):
    _name = 'account.consolidation'
    _description = 'Multi-Company Consolidation with Intercompany Elimination'

    name = fields.Char(string='Consolidation Name', required=True)
    date_from = fields.Date(string='Date From')
    date_to = fields.Date(string='Date To')
    company_ids = fields.Many2many('res.company', string='Companies to Consolidate')
    elimination_account_ids = fields.Many2many(
        'account.account', 
        string='Intercompany Elimination Accounts',
        help='Accounts that represent intercompany transactions (e.g., Intercompany Payables/Receivables)'
    )
    state = fields.Selection([
        ('draft', 'Draft'),
        ('done', 'Consolidated')
    ], default='draft', string='Status')
    result_json = fields.Text(string='Consolidation Result (JSON)', readonly=True, copy=False)

    @api.model
    def get_consolidated_balance_sheet(self, date_from=False, date_to=False, company_ids=False, elimination_account_ids=False, analytic_account_ids=False):
        """
        Konsolidasi Balance Sheet Multi-Company dengan Eliminasi Intercompany.
        
        Args:
            date_from: tanggal awal periode
            date_to: tanggal akhir periode
            company_ids: list of company IDs untuk dikonsolidasi
            elimination_account_ids: list of account IDs untuk eliminasi intercompany
            analytic_account_ids: optional filter analytic accounts
        
        Returns:
            dict dengan struktur:
            - per_company: data per company sebelum eliminasi
            - elimination: detail eliminasi intercompany
            - consolidated: hasil akhir setelah eliminasi
        """
        _logger.info("=== CONSOLIDATION: Multi-Company Balance Sheet ===")
        
        if not company_ids:
            company_ids = self.env['res.company'].search([]).ids
        
        companies = self.env['res.company'].browse(company_ids)
        aml = self.env['account.move.line']
        
        # Normalisasi analytic filter
        analytic_domain = []
        if analytic_account_ids:
            if isinstance(analytic_account_ids, int):
                analytic_account_ids = [analytic_account_ids]
            elif isinstance(analytic_account_ids, (list, tuple)):
                analytic_account_ids = [int(aid) for aid in analytic_account_ids if aid is not None]
            
            if analytic_account_ids:
                aal = self.env['account.analytic.line'].search([
                    ('account_id', 'in', analytic_account_ids),
                ])
                move_line_ids = list(set(aal.mapped('move_line_id').ids))
                if move_line_ids:
                    analytic_domain = [('id', 'in', move_line_ids)]

        # Normalisasi elimination accounts
        elimination_accounts = []
        if elimination_account_ids:
            if isinstance(elimination_account_ids, int):
                elimination_accounts = [elimination_account_ids]
            elif isinstance(elimination_account_ids, (list, tuple)):
                elimination_accounts = [int(aid) for aid in elimination_account_ids if aid is not None]

        # Helper function untuk build balance per company
        def get_company_balance(company):
            """Ambil balance per company untuk semua account types."""
            account_types = {
                'assets': ['asset_receivable', 'asset_cash', 'asset_current', 'asset_non_current', 'asset_prepayments', 'asset_fixed'],
                'liabilities': ['liability_payable', 'liability_credit_card', 'liability_current', 'liability_non_current'],
                'equity': ['equity', 'equity_unaffected'],
                'income': ['income', 'income_other'],
                'expense': ['expense', 'expense_depreciation', 'expense_direct_cost']
            }
            
            result = {
                'company_id': company.id,
                'company_name': company.name,
                'currency': company.currency_id.name,
                'sections': {}
            }
            
            for section_name, types in account_types.items():
                accounts = self.env['account.account'].search([
                    ('account_type', 'in', types),
                    ('company_id', '=', company.id)
                ])
                
                section_data = {
                    'accounts': [],
                    'total_balance': 0.0,
                    'total_debit': 0.0,
                    'total_credit': 0.0
                }
                
                for account in accounts:
                    # Domain untuk period
                    domain = [
                        ('account_id', '=', account.id),
                        ('move_id.state', '=', 'posted'),
                        ('company_id', '=', company.id)
                    ] + analytic_domain
                    
                    if date_from:
                        domain.append(('date', '>=', date_from))
                    if date_to:
                        domain.append(('date', '<=', date_to))
                    
                    lines = aml.search(domain)
                    
                    if lines:
                        debit = sum(lines.mapped('debit'))
                        credit = sum(lines.mapped('credit'))
                        balance = sum(lines.mapped('balance'))
                        
                        # Tandai jika account ini adalah intercompany elimination
                        is_elimination = account.id in elimination_accounts
                        
                        section_data['accounts'].append({
                            'account_id': account.id,
                            'account_code': account.code,
                            'account_name': account.name,
                            'account_type': account.account_type,
                            'debit': debit,
                            'credit': credit,
                            'balance': balance,
                            'is_elimination_account': is_elimination
                        })
                        
                        section_data['total_debit'] += debit
                        section_data['total_credit'] += credit
                        section_data['total_balance'] += balance
                
                result['sections'][section_name] = section_data
            
            return result

        # Ambil data per company
        per_company_data = []
        for company in companies:
            company_data = get_company_balance(company)
            per_company_data.append(company_data)

        # Hitung eliminasi intercompany
        elimination_details = {
            'total_eliminated': 0.0,
            'by_account': [],
            'by_section': {}
        }
        
        for account_id in elimination_accounts:
            account = self.env['account.account'].browse(account_id)
            if not account.exists():
                continue
            
            # Sum balance dari account ini di semua companies
            total_balance = 0.0
            company_balances = []
            
            for company in companies:
                domain = [
                    ('account_id', '=', account_id),
                    ('move_id.state', '=', 'posted'),
                    ('company_id', '=', company.id)
                ] + analytic_domain
                
                if date_from:
                    domain.append(('date', '>=', date_from))
                if date_to:
                    domain.append(('date', '<=', date_to))
                
                lines = aml.search(domain)
                balance = sum(lines.mapped('balance'))
                
                if balance != 0:
                    company_balances.append({
                        'company_id': company.id,
                        'company_name': company.name,
                        'balance': balance
                    })
                    total_balance += balance
            
            # Asumsi: eliminasi penuh jika total balance mendekati 0 (transaksi antar perusahaan saling menghapus)
            # Atau eliminasi sebagian jika ada ketidakseimbangan
            elimination_amount = total_balance  # Jumlah yang perlu dieliminasi
            
            elimination_details['by_account'].append({
                'account_id': account_id,
                'account_code': account.code,
                'account_name': account.name,
                'company_balances': company_balances,
                'total_balance': total_balance,
                'elimination_amount': elimination_amount,
                'fully_eliminated': abs(elimination_amount) < 0.01
            })
            
            elimination_details['total_eliminated'] += abs(elimination_amount)
            
            # Group by section
            section = account.account_type
            if section not in elimination_details['by_section']:
                elimination_details['by_section'][section] = 0.0
            elimination_details['by_section'][section] += elimination_amount

        # Konsolidasi: agregasi semua company dan kurangi eliminasi
        consolidated = {
            'assets': {'total_balance': 0.0, 'accounts': {}},
            'liabilities': {'total_balance': 0.0, 'accounts': {}},
            'equity': {'total_balance': 0.0, 'accounts': {}},
            'income': {'total_debit': 0.0, 'total_credit': 0.0, 'net': 0.0},
            'expense': {'total_debit': 0.0, 'total_credit': 0.0, 'net': 0.0}
        }
        
        for company_data in per_company_data:
            for section_name, section_data in company_data['sections'].items():
                if section_name in ['assets', 'liabilities', 'equity']:
                    for acc in section_data['accounts']:
                        acc_id = acc['account_id']
                        if acc_id not in consolidated[section_name]['accounts']:
                            consolidated[section_name]['accounts'][acc_id] = {
                                'account_code': acc['account_code'],
                                'account_name': acc['account_name'],
                                'balance': 0.0,
                                'is_elimination_account': acc['is_elimination_account']
                            }
                        
                        # Tambahkan balance, kecuali jika account ini dieliminasi
                        if acc['is_elimination_account']:
                            # Eliminasi: tidak tambahkan ke consolidated
                            pass
                        else:
                            consolidated[section_name]['accounts'][acc_id]['balance'] += acc['balance']
                
                elif section_name in ['income', 'expense']:
                    consolidated[section_name]['total_debit'] += section_data['total_debit']
                    consolidated[section_name]['total_credit'] += section_data['total_credit']
        
        # Hitung totals
        for section_name in ['assets', 'liabilities', 'equity']:
            consolidated[section_name]['total_balance'] = sum(
                acc['balance'] for acc in consolidated[section_name]['accounts'].values()
            )
        
        consolidated['income']['net'] = consolidated['income']['total_credit'] - consolidated['income']['total_debit']
        consolidated['expense']['net'] = consolidated['expense']['total_credit'] - consolidated['expense']['total_debit']
        
        net_profit = consolidated['income']['net'] + consolidated['expense']['net']
        
        # Summary
        total_assets = consolidated['assets']['total_balance']
        total_liabilities = consolidated['liabilities']['total_balance']
        total_equity = consolidated['equity']['total_balance']
        total_liabilities_equity_pl = total_liabilities + total_equity + net_profit
        
        return {
            'status': 'success',
            'consolidation_info': {
                'date_from': date_from,
                'date_to': date_to,
                'companies': [{'id': c.id, 'name': c.name} for c in companies],
                'total_companies': len(companies),
                'elimination_accounts_count': len(elimination_accounts),
            },
            'per_company': per_company_data,
            'elimination': elimination_details,
            'consolidated': {
                'assets': {
                    'accounts': list(consolidated['assets']['accounts'].values()),
                    'total_balance': consolidated['assets']['total_balance']
                },
                'liabilities': {
                    'accounts': list(consolidated['liabilities']['accounts'].values()),
                    'total_balance': consolidated['liabilities']['total_balance']
                },
                'equity': {
                    'accounts': list(consolidated['equity']['accounts'].values()),
                    'total_balance': consolidated['equity']['total_balance']
                },
                'income': consolidated['income'],
                'expense': consolidated['expense'],
                'net_profit': net_profit,

                # ========== Tambahan: daftar eliminasi dan nilainya ==========
                'eliminations': {
                    # Total nilai eliminasi agregat
                    'total_eliminated': elimination_details['total_eliminated'],
                    # Ringkasan total eliminasi per section (assets/liabilities/equity dll sesuai account_type)
                    'by_section': elimination_details['by_section'],
                    # Daftar per akun yang dieliminasi: company balances dan jumlah eliminasi
                    'by_account': elimination_details['by_account'],
                }
            },
            'summary': {
                'total_assets': total_assets,
                'total_liabilities': total_liabilities,
                'total_equity': total_equity,
                'net_profit': net_profit,
                'total_liabilities_equity_pl': total_liabilities_equity_pl,
                'balanced': abs(total_assets - total_liabilities_equity_pl) < 0.01,
                'difference': total_assets - total_liabilities_equity_pl,
                'total_eliminated': elimination_details['total_eliminated'],
            }
        }

    @api.model
    def get_consolidated_balance_sheet_grouped(self, date_from=False, date_to=False, company_ids=False, elimination_account_ids=False, analytic_account_ids=False):
        """
        Balance Sheet Consolidation (multi-company) grouped by account.group dengan summary per group
        dan eliminasi intercompany.
        """
        _logger.info("=== CONSOLIDATION GROUPED: Balance Sheet by Group ===")

        # Companies
        if not company_ids:
            company_ids = self.env['res.company'].search([]).ids
        companies = self.env['res.company'].browse(company_ids)
        aml = self.env['account.move.line']

        # Analytic filter -> move_line ids
        analytic_domain = []
        normalized_analytic = []
        if analytic_account_ids:
            if isinstance(analytic_account_ids, int):
                normalized_analytic = [analytic_account_ids]
            elif isinstance(analytic_account_ids, (list, tuple)):
                normalized_analytic = [int(aid) for aid in analytic_account_ids if aid is not None]
            if normalized_analytic:
                aal = self.env['account.analytic.line'].search([('account_id', 'in', normalized_analytic)])
                ml_ids = list(set(aal.mapped('move_line_id').ids))
                if ml_ids:
                    analytic_domain = [('id', 'in', ml_ids)]

        # Elimination account ids
        elimination_accounts = []
        if elimination_account_ids:
            if isinstance(elimination_account_ids, int):
                elimination_accounts = [elimination_account_ids]
            elif isinstance(elimination_account_ids, (list, tuple)):
                elimination_accounts = [int(aid) for aid in elimination_account_ids if aid is not None]

        # Account type buckets (balance sheet only)
        bs_types = {
            'assets': ['asset_receivable', 'asset_cash', 'asset_current', 'asset_non_current', 'asset_prepayments', 'asset_fixed'],
            'liabilities': ['liability_payable', 'liability_credit_card', 'liability_current', 'liability_non_current'],
            'equity': ['equity', 'equity_unaffected'],
        }

        # Collect per-company grouped data (opening/period/ending) by account.group
        def collect_company_groups(company):
            res = {'company_id': company.id, 'company_name': company.name, 'groups': {'assets': {}, 'liabilities': {}, 'equity': {}}}
            for section, types in bs_types.items():
                accounts = self.env['account.account'].search([('account_type', 'in', types), ('company_id', '=', company.id)])
                groups = res['groups'][section]

                for account in accounts:
                    ag = account.group_id
                    gid = ag.id if ag else 0
                    gname = ag.name if ag else 'Unassigned'
                    gcode = ag.code_prefix_start if ag and ag.code_prefix_start else ''

                    if gid not in groups:
                        groups[gid] = {
                            'group_id': gid, 'group_name': gname, 'group_code': gcode,
                            'opening_debit': 0.0, 'opening_credit': 0.0, 'opening_balance': 0.0,
                            'period_debit': 0.0, 'period_credit': 0.0, 'period_balance': 0.0,
                            'ending_debit': 0.0, 'ending_credit': 0.0, 'ending_balance': 0.0,
                            'accounts': []
                        }

                    # Opening (before date_from)
                    o_deb = o_cred = o_bal = 0.0
                    o_lines = []
                    if date_from:
                        dom_o = [
                            ('account_id', '=', account.id),
                            ('move_id.state', '=', 'posted'),
                            ('company_id', '=', company.id),
                            ('date', '<', date_from),
                        ] + analytic_domain
                        o_lines = aml.search(dom_o)
                        o_deb = sum(o_lines.mapped('debit'))
                        o_cred = sum(o_lines.mapped('credit'))
                        o_bal = sum(o_lines.mapped('balance'))

                    # Period (date_from..date_to)
                    dom_p = [
                        ('account_id', '=', account.id),
                        ('move_id.state', '=', 'posted'),
                        ('company_id', '=', company.id),
                    ] + analytic_domain
                    if date_from:
                        dom_p.append(('date', '>=', date_from))
                    if date_to:
                        dom_p.append(('date', '<=', date_to))
                    p_lines = aml.search(dom_p)
                    p_deb = sum(p_lines.mapped('debit'))
                    p_cred = sum(p_lines.mapped('credit'))
                    p_bal = sum(p_lines.mapped('balance'))

                    e_deb = o_deb + p_deb
                    e_cred = o_cred + p_cred
                    e_bal = o_bal + p_bal

                    is_elim = account.id in elimination_accounts

                    # Append account row
                    grp = groups[gid]
                    grp['accounts'].append({
                        'account_id': account.id,
                        'account_code': account.code,
                        'account_name': account.name,
                        'is_elimination_account': is_elim,
                        'opening_debit': o_deb, 'opening_credit': o_cred, 'opening_balance': o_bal,
                        'period_debit': p_deb, 'period_credit': p_cred, 'period_balance': p_bal,
                        'ending_debit': e_deb, 'ending_credit': e_cred, 'ending_balance': e_bal,
                    })
                    # Accumulate group summary
                    grp['opening_debit'] += o_deb
                    grp['opening_credit'] += o_cred
                    grp['opening_balance'] += o_bal
                    grp['period_debit'] += p_deb
                    grp['period_credit'] += p_cred
                    grp['period_balance'] += p_bal
                    grp['ending_debit'] += e_deb
                    grp['ending_credit'] += e_cred
                    grp['ending_balance'] += e_bal

            return res

        per_company = [collect_company_groups(c) for c in companies]

        # Build consolidated groups (sum across companies, then eliminate intercompany accounts)
        def merge_groups(section):
            merged = {}
            # Sum all companies
            for comp in per_company:
                for gid, grp in comp['groups'][section].items():
                    if gid not in merged:
                        merged[gid] = {
                            'group_id': gid, 'group_name': grp['group_name'], 'group_code': grp['group_code'],
                            'opening_debit': 0.0, 'opening_credit': 0.0, 'opening_balance': 0.0,
                            'period_debit': 0.0, 'period_credit': 0.0, 'period_balance': 0.0,
                            'ending_debit': 0.0, 'ending_credit': 0.0, 'ending_balance': 0.0,
                            'accounts': {}
                        }
                    m = merged[gid]
                    # Merge account rows
                    for acc in grp['accounts']:
                        aid = acc['account_id']
                        if aid not in m['accounts']:
                            m['accounts'][aid] = {
                                'account_id': aid,
                                'account_code': acc['account_code'],
                                'account_name': acc['account_name'],
                                'is_elimination_account': acc['is_elimination_account'],
                                'opening_debit': 0.0, 'opening_credit': 0.0, 'opening_balance': 0.0,
                                'period_debit': 0.0, 'period_credit': 0.0, 'period_balance': 0.0,
                                'ending_debit': 0.0, 'ending_credit': 0.0, 'ending_balance': 0.0,
                            }
                        a = m['accounts'][aid]
                        # Sum before elimination
                        a['opening_debit'] += acc['opening_debit']; a['opening_credit'] += acc['opening_credit']; a['opening_balance'] += acc['opening_balance']
                        a['period_debit'] += acc['period_debit']; a['period_credit'] += acc['period_credit']; a['period_balance'] += acc['period_balance']
                        a['ending_debit'] += acc['ending_debit']; a['ending_credit'] += acc['ending_credit']; a['ending_balance'] += acc['ending_balance']

            # Apply elimination: zero out elimination accounts balances in consolidated totals
            total_elim = {'opening': 0.0, 'period': 0.0, 'ending': 0.0}
            for gid, g in merged.items():
                for aid, a in list(g['accounts'].items()):
                    if a['is_elimination_account']:
                        total_elim['opening'] += a['opening_balance']
                        total_elim['period'] += a['period_balance']
                        total_elim['ending'] += a['ending_balance']
                        # Remove from consolidated by zeroing or deleting
                        # Option 1: keep row with zero balances
                        a['opening_debit'] = a['opening_credit'] = a['opening_balance'] = 0.0
                        a['period_debit'] = a['period_credit'] = a['period_balance'] = 0.0
                        a['ending_debit'] = a['ending_credit'] = a['ending_balance'] = 0.0

                # Recompute group totals from accounts (post-elimination)
                g['opening_debit'] = sum(x['opening_debit'] for x in g['accounts'].values())
                g['opening_credit'] = sum(x['opening_credit'] for x in g['accounts'].values())
                g['opening_balance'] = sum(x['opening_balance'] for x in g['accounts'].values())
                g['period_debit'] = sum(x['period_debit'] for x in g['accounts'].values())
                g['period_credit'] = sum(x['period_credit'] for x in g['accounts'].values())
                g['period_balance'] = sum(x['period_balance'] for x in g['accounts'].values())
                g['ending_debit'] = sum(x['ending_debit'] for x in g['accounts'].values())
                g['ending_credit'] = sum(x['ending_credit'] for x in g['accounts'].values())
                g['ending_balance'] = sum(x['ending_balance'] for x in g['accounts'].values())

            # Sort groups
            out = [dict(g, accounts=list(g['accounts'].values())) for g in merged.values()]
            out.sort(key=lambda x: (x['group_code'], x['group_name']))
            return out, total_elim

        assets_groups, assets_elim = merge_groups('assets')
        liabilities_groups, liabilities_elim = merge_groups('liabilities')
        equity_groups, equity_elim = merge_groups('equity')

        def summarize(groups):
            return {
                'opening_balance': sum(g['opening_balance'] for g in groups),
                'period_balance': sum(g['period_balance'] for g in groups),
                'ending_balance': sum(g['ending_balance'] for g in groups),
            }

        assets_sum = summarize(assets_groups)
        liabilities_sum = summarize(liabilities_groups)
        equity_sum = summarize(equity_groups)

        # Consolidated balance check
        balanced = abs(assets_sum['ending_balance'] - (liabilities_sum['ending_balance'] + equity_sum['ending_balance'])) < 0.01

        return {
            'status': 'success',
            'consolidation_info': {
                'date_from': date_from,
                'date_to': date_to,
                'companies': [{'id': c.id, 'name': c.name} for c in companies],
                'elimination_accounts_count': len(elimination_accounts),
                'analytic_filter_ids': normalized_analytic,
                'eliminations_summary': {
                    'assets': assets_elim,
                    'liabilities': liabilities_elim,
                    'equity': equity_elim,
                }
            },
            'assets': {'groups': assets_groups, 'summary': assets_sum},
            'liabilities': {'groups': liabilities_groups, 'summary': liabilities_sum},
            'equity': {'groups': equity_groups, 'summary': equity_sum},
            'summary': {
                'assets_ending': assets_sum['ending_balance'],
                'liabilities_ending': liabilities_sum['ending_balance'],
                'equity_ending': equity_sum['ending_balance'],
                'balanced': balanced,
                'difference': assets_sum['ending_balance'] - (liabilities_sum['ending_balance'] + equity_sum['ending_balance'])
            }
        }

    def action_consolidate(self):
        """
        Button action: proses konsolidasi berdasarkan data yang sudah diinput di form.
        Panggil method get_consolidated_balance_sheet_grouped dengan parameter dari record ini.
        """
        self.ensure_one()
        
        if not self.company_ids:
            raise UserError("Please select at least one company to consolidate.")
        
        result = self.get_consolidated_balance_sheet_grouped(
            date_from=self.date_from,
            date_to=self.date_to,
            company_ids=self.company_ids.ids,
            elimination_account_ids=self.elimination_account_ids.ids,
        )
        
        # Simpan hasil ke JSON field
        import json
        self.result_json = json.dumps(result, indent=2, default=str)
        self.state = 'done'
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Consolidation Completed',
                'message': f"Successfully consolidated {len(self.company_ids)} companies",
                'type': 'success',
            }
        }

    def action_reset_to_draft(self):
        """Reset ke draft untuk edit ulang."""
        self.state = 'draft'

    @api.model
    def get_consolidation_by_id(self, consolidation_id):
        """
        API wrapper: ambil record consolidation dan proses konsolidasi.
        Digunakan oleh controller untuk frontend/API call.
        """
        record = self.browse(consolidation_id)
        if not record.exists():
            return {'status': 'error', 'message': 'Consolidation record not found'}
        
        return self.get_consolidated_balance_sheet_grouped(
            date_from=record.date_from,
            date_to=record.date_to,
            company_ids=record.company_ids.ids,
            elimination_account_ids=record.elimination_account_ids.ids,
            analytic_account_ids=False
        )