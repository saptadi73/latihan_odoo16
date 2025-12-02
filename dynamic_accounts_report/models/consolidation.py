# -*- coding: utf-8 -*-
from odoo import models, api, fields
from odoo.exceptions import UserError
import logging
import json  # ← TAMBAHKAN INI

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

    @api.model
    def get_balance_sheet_per_company(self, date_from=False, date_to=False, company_ids=False, analytic_account_ids=False):
        """
        1. Ambil balance sheet per company menggunakan financial_report_combined (basis konsolidasi).
           Multi-company selalu mengikuti daftar company di record account.consolidation jika dipanggil dari record.
        2. Lakukan eliminasi sesuai elimination_account_ids di record (intercompany).
        3. Keluarkan hasil agregasi: before & after elimination (konsolidasi).
        """
        self.ensure_one()

        # Sumber company: dari argumen (panggilan luar) atau dari record
        companies = self.env['res.company'].browse(company_ids) if company_ids else self.company_ids
        if not companies:
            return {'status': 'error', 'message': 'No companies to consolidate'}

        # Tanggal default jika kosong
        date_from = date_from or self.date_from
        date_to = date_to or self.date_to

        # Analytic filter normalisasi
        normalized_analytic = []
        if analytic_account_ids:
            if isinstance(analytic_account_ids, int):
                normalized_analytic = [analytic_account_ids]
            elif isinstance(analytic_account_ids, (list, tuple)):
                normalized_analytic = [int(a) for a in analytic_account_ids if a]

        per_company = []
        for company in companies:
            try:
                # Penting: set context per company agar hitungan tidak 0
                bs_report = self.env['account.balance.sheet.report'].with_context(
                    allowed_company_ids=[company.id],
                    force_company=company.id,
                )
                if normalized_analytic:
                    data = bs_report.financial_report_combined_analytic(
                        date_from=date_from,
                        date_to=date_to,
                        company_id=company.id,
                        analytic_account_ids=normalized_analytic
                    )
                else:
                    data = bs_report.financial_report_combined(
                        date_from=date_from,
                        date_to=date_to,
                        company_id=company.id
                    )

                if data.get('status') != 'success':
                    per_company.append({
                        'company': {'id': company.id, 'name': company.name},
                        'status': 'error',
                        'error': data.get('message', 'Report failed')
                    })
                    continue

                per_company.append({
                    'company': {
                        'id': company.id,
                        'name': company.name,
                        'currency': company.currency_id.name,
                        'currency_symbol': company.currency_id.symbol,
                    },
                    'status': 'success',
                    'report': data,
                    'summary': data.get('summary', {}),
                })
            except Exception as e:
                per_company.append({
                    'company': {'id': company.id, 'name': company.name},
                    'status': 'error',
                    'error': str(e)
                })

        ok_companies = [c for c in per_company if c.get('status') == 'success']
        if not ok_companies:
            return {'status': 'error', 'message': 'No successful company reports', 'per_company': per_company}

        # Agregasi sebelum eliminasi
        agg_before = {
            'opening': {'assets': 0.0, 'liabilities': 0.0, 'equity': 0.0, 'net_profit': 0.0},
            'period': {'assets': 0.0, 'liabilities': 0.0, 'equity': 0.0, 'income_net': 0.0, 'expense_net': 0.0, 'net_profit': 0.0},
            'ending': {'assets': 0.0, 'liabilities': 0.0, 'equity': 0.0, 'liabilities_equity_plus_pl': 0.0, 'balanced': False, 'difference': 0.0}
        }
        for comp in ok_companies:
            s = comp['summary'] or {}
            opening = s.get('opening', {})
            period = s.get('period', {})
            ending = s.get('ending', {})
            agg_before['opening']['assets'] += opening.get('assets', 0.0)
            agg_before['opening']['liabilities'] += opening.get('liabilities', 0.0)
            agg_before['opening']['equity'] += opening.get('equity', 0.0)
            agg_before['opening']['net_profit'] += opening.get('net_profit', 0.0)
            agg_before['period']['assets'] += period.get('assets', 0.0)
            agg_before['period']['liabilities'] += period.get('liabilities', 0.0)
            agg_before['period']['equity'] += period.get('equity', 0.0)
            agg_before['period']['income_net'] += period.get('income_net', 0.0)
            agg_before['period']['expense_net'] += period.get('expense_net', 0.0)
            agg_before['period']['net_profit'] += period.get('net_profit', 0.0)
            agg_before['ending']['assets'] += ending.get('assets', 0.0)
            agg_before['ending']['liabilities'] += ending.get('liabilities', 0.0)
            agg_before['ending']['equity'] += ending.get('equity', 0.0)
            agg_before['ending']['liabilities_equity_plus_pl'] += ending.get('liabilities_equity_plus_pl', 0.0)

        agg_before['ending']['balanced'] = abs(
            agg_before['ending']['assets'] - agg_before['ending']['liabilities_equity_plus_pl']
        ) < 0.01
        agg_before['ending']['difference'] = agg_before['ending']['assets'] - agg_before['ending']['liabilities_equity_plus_pl']

        # Eliminasi intercompany
        elimination_accounts = self.elimination_account_ids.ids
        eliminations = {'accounts': [], 'totals': {'opening': 0.0, 'period': 0.0, 'ending': 0.0}}
        if elimination_accounts:
            for acc in self.elimination_account_ids:
                company_rows, opening_sum, period_sum, ending_sum = [], 0.0, 0.0, 0.0
                for comp in companies:
                    # Penting: context per company saat baca AML
                    aml = self.env['account.move.line'].with_context(
                        allowed_company_ids=[comp.id],
                        force_company=comp.id,
                    )
                    o_bal = 0.0
                    if date_from:
                        o_lines = aml.search([
                            ('account_id', '=', acc.id),
                            ('company_id', '=', comp.id),
                            ('move_id.state', '=', 'posted'),
                            ('date', '<', date_from),
                        ])
                        o_bal = sum(o_lines.mapped('balance'))

                    dom_p = [
                        ('account_id', '=', acc.id),
                        ('company_id', '=', comp.id),
                        ('move_id.state', '=', 'posted'),
                    ]
                    if date_from:
                        dom_p.append(('date', '>=', date_from))
                    if date_to:
                        dom_p.append(('date', '<=', date_to))
                    p_lines = aml.search(dom_p)
                    p_bal = sum(p_lines.mapped('balance'))

                    e_bal = o_bal + p_bal
                    if abs(e_bal) > 0.00001 or abs(o_bal) > 0.00001 or abs(p_bal) > 0.00001:
                        company_rows.append({
                            'company_id': comp.id, 'company_name': comp.name,
                            'opening_balance': o_bal, 'period_balance': p_bal, 'ending_balance': e_bal
                        })
                        opening_sum += o_bal; period_sum += p_bal; ending_sum += e_bal

                eliminations['accounts'].append({
                    'account_id': acc.id, 'code': acc.code, 'name': acc.name,
                    'company_balances': company_rows,
                    'opening_total': opening_sum, 'period_total': period_sum, 'ending_total': ending_sum,
                    'fully_eliminated': abs(ending_sum) < 0.01
                })
                eliminations['totals']['opening'] += opening_sum
                eliminations['totals']['period'] += period_sum
                eliminations['totals']['ending'] += ending_sum

        # Konsolidasi setelah eliminasi (kurangi akun eliminasi dari agregat)
        agg_after = {
            'opening': dict(agg_before['opening']),
            'period': dict(agg_before['period']),
            'ending': dict(agg_before['ending']),
        }
        if elimination_accounts and eliminations['accounts']:
            elim_ending = eliminations['totals']['ending']
            agg_after['ending']['assets'] -= elim_ending
            agg_after['ending']['liabilities_equity_plus_pl'] -= elim_ending
            agg_after['ending']['balanced'] = abs(
                agg_after['ending']['assets'] - agg_after['ending']['liabilities_equity_plus_pl']
            ) < 0.01
            agg_after['ending']['difference'] = (
                agg_after['ending']['assets'] - agg_after['ending']['liabilities_equity_plus_pl']
            )

        summary = {
            'before': {
                'assets': agg_before['ending']['assets'],
                'liabilities_equity_plus_pl': agg_before['ending']['liabilities_equity_plus_pl'],
                'balanced': agg_before['ending']['balanced'],
                'difference': agg_before['ending']['difference'],
            },
            'elimination_totals': eliminations['totals'],
            'after': {
                'assets': agg_after['ending']['assets'],
                'liabilities_equity_plus_pl': agg_after['ending']['liabilities_equity_plus_pl'],
                'balanced': agg_after['ending']['balanced'],
                'difference': agg_after['ending']['difference'],
            }
        }

        return {
            'status': 'success',
            'date_from': date_from,
            'date_to': date_to,
            'total_companies': len(companies),
            'successful_companies': len(ok_companies),
            'failed_companies': len(per_company) - len(ok_companies),
            'per_company': per_company,
            'consolidated_before': agg_before,
            'eliminations': eliminations,
            'consolidated_after': agg_after,
            'summary': summary,
        }

    def action_consolidate(self):
        """
        PERBAIKAN: Gunakan get_balance_sheet_per_company sebagai basis konsolidasi.
        Button action untuk proses konsolidasi dengan eliminasi intercompany.
        """
        self.ensure_one()
        
        if not self.company_ids:
            raise UserError('Please select at least one company to consolidate.')
        
        _logger.info(f"=== CONSOLIDATION PROCESS START ===")
        _logger.info(f"Consolidation ID: {self.id}")
        _logger.info(f"Name: {self.name}")
        _logger.info(f"Companies: {self.company_ids.mapped('name')}")
        _logger.info(f"Date Range: {self.date_from} to {self.date_to}")
        _logger.info(f"Elimination Accounts: {len(self.elimination_account_ids)}")
        
        try:
            # STEP 1: Get balance sheet per company (basis konsolidasi)
            per_company_data = self.get_balance_sheet_per_company(
                date_from=self.date_from,
                date_to=self.date_to,
                company_ids=self.company_ids.ids,
                analytic_account_ids=False  # TODO: add field analytic filter di form jika diperlukan
            )
            
            if per_company_data.get('status') != 'success':
                raise UserError(f"Failed to get balance sheet per company: {per_company_data.get('message', 'Unknown error')}")
            
            _logger.info(f"✓ Step 1: Retrieved balance sheet for {per_company_data['successful_companies']} companies")
            
            # STEP 2: Perform elimination (jika ada elimination accounts)
            elimination_summary = {
                'total_eliminated': 0.0,
                'by_account': [],
                'assets': {'opening': 0.0, 'period': 0.0, 'ending': 0.0},
                'liabilities': {'opening': 0.0, 'period': 0.0, 'ending': 0.0},
                'equity': {'opening': 0.0, 'period': 0.0, 'ending': 0.0},
            }
            
            if self.elimination_account_ids:
                _logger.info(f"✓ Step 2: Processing eliminations for {len(self.elimination_account_ids)} accounts")
                
                # TODO: Implement elimination logic
                # Untuk saat ini, simpan struktur kosong
                # Logic eliminasi akan mengurangi saldo intercompany dari grand_totals
                pass
            else:
                _logger.info("⚠ Step 2: No elimination accounts defined, skipping elimination")
            
            # STEP 3: Calculate consolidated totals (after elimination)
            grand_totals = per_company_data['grand_totals']
            
            # Apply elimination adjustments (TODO: implement actual elimination)
            consolidated_totals = {
                'opening': {
                    'assets': grand_totals['opening']['assets'] - elimination_summary['assets']['opening'],
                    'liabilities': grand_totals['opening']['liabilities'] - elimination_summary['liabilities']['opening'],
                    'equity': grand_totals['opening']['equity'] - elimination_summary['equity']['opening'],
                },
                'period': {
                    'assets': grand_totals['period']['assets'] - elimination_summary['assets']['period'],
                    'liabilities': grand_totals['period']['liabilities'] - elimination_summary['liabilities']['period'],
                    'equity': grand_totals['period']['equity'] - elimination_summary['equity']['period'],
                    'income_net': grand_totals['period']['income_net'],
                    'expense_net': grand_totals['period']['expense_net'],
                    'net_profit': grand_totals['period']['net_profit'],
                },
                'ending': {
                    'assets': grand_totals['ending']['assets'] - elimination_summary['assets']['ending'],
                    'liabilities': grand_totals['ending']['liabilities'] - elimination_summary['liabilities']['ending'],
                    'equity': grand_totals['ending']['equity'] - elimination_summary['equity']['ending'],
                },
            }
            
            # Recalculate L+E+P/L after elimination
            consolidated_totals['ending']['liabilities_equity_plus_pl'] = (
                consolidated_totals['ending']['liabilities'] +
                consolidated_totals['ending']['equity'] +
                consolidated_totals['period']['net_profit']
            )
            
            consolidated_totals['ending']['balanced'] = abs(
                consolidated_totals['ending']['assets'] -
                consolidated_totals['ending']['liabilities_equity_plus_pl']
            ) < 0.01
            
            consolidated_totals['ending']['difference'] = (
                consolidated_totals['ending']['assets'] -
                consolidated_totals['ending']['liabilities_equity_plus_pl']
            )
            
            _logger.info(f"=== CONSOLIDATED TOTALS (After Elimination) ===")
            _logger.info(f"  Assets: {consolidated_totals['ending']['assets']:,.2f}")
            _logger.info(f"  Liabilities: {consolidated_totals['ending']['liabilities']:,.2f}")
            _logger.info(f"  Equity: {consolidated_totals['ending']['equity']:,.2f}")
            _logger.info(f"  L+E+P/L: {consolidated_totals['ending']['liabilities_equity_plus_pl']:,.2f}")
            _logger.info(f"  Balanced: {consolidated_totals['ending']['balanced']}")
            _logger.info(f"  Difference: {consolidated_totals['ending']['difference']:,.2f}")
            
            # STEP 4: Build final result JSON
            result_json = {
                'status': 'success',
                'consolidation_info': {
                    'consolidation_id': self.id,
                    'name': self.name,
                    'date_from': str(self.date_from) if self.date_from else False,
                    'date_to': str(self.date_to) if self.date_to else False,
                    'companies': [{'id': c.id, 'name': c.name} for c in self.company_ids],
                    'total_companies': len(self.company_ids),
                    'elimination_accounts_count': len(self.elimination_account_ids),
                    'elimination_accounts': [{'id': a.id, 'code': a.code, 'name': a.name} for a in self.elimination_account_ids],
                },
                'per_company': per_company_data['companies'],
                'before_elimination': grand_totals,
                'elimination_summary': elimination_summary,
                'after_elimination': consolidated_totals,
                'summary': consolidated_totals,  # Alias untuk backward compatibility
            }
            
            # STEP 5: Save result to database
            self.write({
                'result_json': json.dumps(result_json, default=str),
                'state': 'done'
            })
            
            _logger.info(f"✓ Consolidation completed successfully")
            _logger.info(f"=== CONSOLIDATION PROCESS END ===")
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Success',
                    'message': f'Successfully consolidated {len(self.company_ids)} companies',
                    'type': 'success',
                    'sticky': False,
                }
            }
            
        except Exception as e:
            _logger.error(f"✗ Consolidation failed: {str(e)}", exc_info=True)
            self.write({'state': 'draft'})
            raise UserError(f'Consolidation failed: {str(e)}')

    def action_reset_to_draft(self):
        """
        Reset consolidation to draft state.
        Clear result_json and allow re-processing.
        """
        self.ensure_one()
        
        _logger.info(f"Resetting consolidation {self.id} ({self.name}) to draft")
        
        self.write({
            'state': 'draft',
            'result_json': False,
        })
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Reset',
                'message': 'Consolidation has been reset to draft. You can now re-process.',
                'type': 'info',
                'sticky': False,
            }
        }

    @api.model
    def get_consolidation_by_id(self, consolidation_id):
        """
        Ambil data konsolidasi berdasarkan ID.
        
        Returns:
            dict: {
                'status': 'success',
                'consolidation': {
                    'id': int,
                    'name': str,
                    'date_from': date,
                    'date_to': date,
                    'company_ids': [int],
                    'elimination_account_ids': [int],
                    'state': 'draft'|'done',
                    'result_json': str,  # JSON string hasil konsolidasi
                }
            }
        """
        _logger.info(f"=== GET CONSOLIDATION BY ID: {consolidation_id} ===")
        
        consolidation = self.browse(consolidation_id)
        if not consolidation.exists():
            return {'status': 'error', 'message': 'Consolidation not found'}
        
        return {
            'status': 'success',
            'consolidation': {
                'id': consolidation.id,
                'name': consolidation.name,
                'date_from': consolidation.date_from,
                'date_to': consolidation.date_to,
                'company_ids': consolidation.company_ids.ids,
                'elimination_account_ids': consolidation.elimination_account_ids.ids,
                'state': consolidation.state,
                'result_json': consolidation.result_json,
            }
        }

    @api.model
    def preview_single_company_with_elimination(self, company_id=False, date_from=False, date_to=False):
        """
        Tampilkan 1 balance sheet per company (format financial_report_combined),
        lalu tampilkan hasil setelah eliminasi (mengurangi saldo akun yang ada di elimination_account_ids).
        Output berisi groups dan akun (opening/period/ending) sebelum & sesudah eliminasi.
        """
        self.ensure_one()
        # Tentukan company
        company = self.env['res.company'].browse(company_id) if company_id else (self.company_ids[:1])
        if not company:
            return {'status': 'error', 'message': 'Company is required'}
        company = company[0]

        # Tanggal
        date_from = date_from or self.date_from
        date_to = date_to or self.date_to

        # Ambil report asli (format sama dgn financial_report_combined)
        bs_report = self.env['account.balance.sheet.report'] \
            .with_company(company) \
            .with_context(company_id=company.id, company_ids=[company.id],
                          allowed_company_ids=[company.id], force_company=company.id) \
            .sudo()

        data = bs_report.financial_report_combined(
            date_from=date_from,
            date_to=date_to,
            company_id=company.id
        )
        if data.get('status') != 'success':
            return {'status': 'error', 'message': data.get('message', 'Failed to build report')}

        # Siapkan lookup untuk eliminasi
        elim_ids = set(self.elimination_account_ids.ids)
        # Util untuk clone dict akun/group agar bisa membuat versi "after"
        def clone_account_row(row):
            return {
                'account_id': row.get('account_id'),
                'account_code': row.get('account_code'),
                'account_name': row.get('account_name'),
                'opening_debit': row.get('opening_debit', 0.0),
                'opening_credit': row.get('opening_credit', 0.0),
                'opening_balance': row.get('opening_balance', 0.0),
                'period_debit': row.get('period_debit', 0.0),
                'period_credit': row.get('period_credit', 0.0),
                'period_balance': row.get('period_balance', 0.0),
                'ending_debit': row.get('ending_debit', 0.0),
                'ending_credit': row.get('ending_credit', 0.0),
                'ending_balance': row.get('ending_balance', 0.0),
            }

        def clone_group_row(grp):
            return {
                'group_id': grp.get('group_id'),
                'group_code': grp.get('group_code'),
                'group_name': grp.get('group_name'),
                'opening_debit': grp.get('opening_debit', 0.0),
                'opening_credit': grp.get('opening_credit', 0.0),
                'opening_balance': grp.get('opening_balance', 0.0),
                'period_debit': grp.get('period_debit', 0.0),
                'period_credit': grp.get('period_credit', 0.0),
                'period_balance': grp.get('period_balance', 0.0),
                'ending_debit': grp.get('ending_debit', 0.0),
                'ending_credit': grp.get('ending_credit', 0.0),
                'ending_balance': grp.get('ending_balance', 0.0),
                'accounts': [clone_account_row(a) for a in grp.get('accounts', [])],
            }

        # Ambil sections (assets, liabilities, equity) dengan groups & accounts
        sections = {}
        for sec_name in ('assets', 'liabilities', 'equity'):
            sec = data.get(sec_name, {})
            groups = sec.get('groups', [])
            sections[sec_name] = {
                'groups_before': [clone_group_row(g) for g in groups],
                'groups_after': [],  # akan diisi setelah eliminasi
            }

        # Hitung setelah eliminasi: kurangi akun yang termasuk elimination_account_ids
        def apply_elimination_to_groups(groups_before):
            groups_after = []
            for grp in groups_before:
                new_grp = clone_group_row(grp)
                # reset summary akan dihitung ulang dari akun
                for k in ('opening_debit','opening_credit','opening_balance',
                          'period_debit','period_credit','period_balance',
                          'ending_debit','ending_credit','ending_balance'):
                    new_grp[k] = 0.0
                new_accounts = []
                for acc in grp.get('accounts', []):
                    acc_after = clone_account_row(acc)
                    if acc.get('account_id') in elim_ids:
                        # Kurangi full saldo akun eliminasi dari hasil after
                        # Menghilangkan nilai akun ini (anggap di-eliminate)
                        acc_after['opening_debit'] = 0.0
                        acc_after['opening_credit'] = 0.0
                        acc_after['opening_balance'] = 0.0
                        acc_after['period_debit'] = 0.0
                        acc_after['period_credit'] = 0.0
                        acc_after['period_balance'] = 0.0
                        acc_after['ending_debit'] = 0.0
                        acc_after['ending_credit'] = 0.0
                        acc_after['ending_balance'] = 0.0
                    # akumulasi summary group dari acc_after
                    new_grp['opening_debit'] += acc_after['opening_debit']
                    new_grp['opening_credit'] += acc_after['opening_credit']
                    new_grp['opening_balance'] += acc_after['opening_balance']
                    new_grp['period_debit'] += acc_after['period_debit']
                    new_grp['period_credit'] += acc_after['period_credit']
                    new_grp['period_balance'] += acc_after['period_balance']
                    new_grp['ending_debit'] += acc_after['ending_debit']
                    new_grp['ending_credit'] += acc_after['ending_credit']
                    new_grp['ending_balance'] += acc_after['ending_balance']
                    new_accounts.append(acc_after)
                new_grp['accounts'] = new_accounts
                groups_after.append(new_grp)
            return groups_after

        for sec_name in sections.keys():
            sections[sec_name]['groups_after'] = apply_elimination_to_groups(sections[sec_name]['groups_before'])

        return {
            'status': 'success',
            'company': {'id': company.id, 'name': company.name},
            'date_from': date_from,
            'date_to': date_to,
            'elimination_account_ids': [{'id': a.id, 'code': a.code, 'name': a.name} for a in self.elimination_account_ids],
            'assets': sections['assets'],
            'liabilities': sections['liabilities'],
            'equity': sections['equity'],
        }