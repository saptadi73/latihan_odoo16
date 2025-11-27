# -*- coding: utf-8 -*-
from odoo import api, models, fields
from datetime import datetime
import logging
_logger = logging.getLogger(__name__)

class BalanceSheetReport(models.TransientModel):
    _name = 'account.balance.sheet.report'
    _description = 'Balance Sheet Report API'
    
    @api.model
    def get_report_values(self, date_from=False, date_to=False, account_ids=False, company_id=False, analytic_account_ids=False):
        """Generate balance sheet data"""
        _logger.info("Starting Balance Sheet Report Generation")
        
        # Tentukan company
        if company_id:
            company = self.env['res.company'].browse(company_id)
        else:
            company = self.env.company
        
        # Normalisasi analytic_account_ids (boleh int, list int, atau recordset)
        if analytic_account_ids and not isinstance(analytic_account_ids, (list, tuple)):
            analytic_account_ids = [analytic_account_ids]
        
        filters = {
            'date_from': date_from or False,
            'date_to': date_to or datetime.now().strftime('%Y-%m-%d'),
            'company_id': company.id,
            'company_name': company.name,
            'analytic_account_ids': analytic_account_ids or [],
        }
        
        try:
            report = self.env['report.dynamic_accounts_report.balance_sheet']
            report_lines = self._get_report_lines(filters, company)
            bs_lines = self._get_balance_sheet_lines(filters, company)
            
            data = {
                'report_data': {
                    'filters': filters,
                    'report_lines': report_lines,
                    'bs_lines': bs_lines,
                    'name': 'Balance Sheet',
                },
                'report_name': 'Balance Sheet Report',
            }
            result = report.with_context(bs_report=True)._get_report_values(None, data)
            _logger.info(f"Report generated successfully for company: {company.name}")
            return result
        except Exception as e:
            _logger.error(f"Error generating balance sheet: {str(e)}", exc_info=True)
            raise
    
    @api.model
    def get_balance_sheet_direct(self, date_from=False, date_to=False, company_id=False, analytic_account_ids=False, apply_analytic_on_bs=False):
        """Ambil data langsung tanpa melalui report model"""
        _logger.info("Getting balance sheet data directly")
        if company_id:
            company = self.env['res.company'].browse(company_id)
        else:
            company = self.env.company

        if analytic_account_ids and not isinstance(analytic_account_ids, (list, tuple)):
            analytic_account_ids = [analytic_account_ids]
        
        filters = {
            'date_from': date_from or False,
            'date_to': date_to or datetime.now().strftime('%Y-%m-%d'),
            'company_id': company.id,
            'company_name': company.name,
            'analytic_account_ids': analytic_account_ids or [],
            'apply_analytic_on_bs': bool(apply_analytic_on_bs),  # ← baru
        }
        
        bs_lines = self._get_balance_sheet_lines(filters, company)
        report_lines = self._get_report_lines(filters, company)
        
        return {
            'status': 'success',
            'filters': filters,
            'balance_sheet_lines': bs_lines,
            'report_lines': report_lines,
            'summary': self._calculate_summary(bs_lines),
            'company': {
                'id': company.id,
                'name': company.name,
                'currency': company.currency_id.name,
                'currency_symbol': company.currency_id.symbol,
            }
        }
    
    @api.model
    def get_all_companies_balance_sheet(self, date_from=False, date_to=False):
        """Ambil balance sheet untuk SEMUA company"""
        _logger.info("Getting balance sheet for ALL companies")
        
        # Ambil semua company
        companies = self.env['res.company'].search([])
        _logger.info(f"Found {len(companies)} companies")
        
        results = []
        
        for company in companies:
            _logger.info(f"Processing company: {company.name}")
            
            filters = {
                'date_from': date_from or False,
                'date_to': date_to or datetime.now().strftime('%Y-%m-%d'),
                'company_id': company.id,
                'company_name': company.name,
            }
            
            try:
                bs_lines = self._get_balance_sheet_lines(filters, company)
                summary = self._calculate_summary(bs_lines)
                
                results.append({
                    'company': {
                        'id': company.id,
                        'name': company.name,
                        'currency': company.currency_id.name,
                        'currency_symbol': company.currency_id.symbol,
                    },
                    'filters': filters,
                    'balance_sheet_lines': bs_lines,
                    'summary': summary,
                })
            except Exception as e:
                _logger.error(f"Error processing company {company.name}: {str(e)}")
                results.append({
                    'company': {
                        'id': company.id,
                        'name': company.name,
                    },
                    'error': str(e)
                })
        
        return {
            'status': 'success',
            'total_companies': len(companies),
            'date_from': date_from,
            'date_to': date_to,
            'data': results
        }
    
    @api.model
    def get_available_companies(self):
        """Ambil daftar semua company yang tersedia"""
        companies = self.env['res.company'].search([])
        
        result = []
        for company in companies:
            result.append({
                'id': company.id,
                'name': company.name,
                'currency': company.currency_id.name,
                'currency_symbol': company.currency_id.symbol,
                'active': company.id == self.env.company.id,
            })
        
        return {
            'status': 'success',
            'total': len(result),
            'companies': result
        }
    
    def _get_report_lines(self, filters, company):
        """Ambil data akun move lines dengan filter company + analytic"""
        domain = [
            ('move_id.state', '=', 'posted'),
            ('company_id', '=', company.id)
        ]
        if filters.get('date_from'):
            domain.append(('date', '>=', filters['date_from']))
        if filters.get('date_to'):
            domain.append(('date', '<=', filters['date_to']))

        analytic_ids = filters.get('analytic_account_ids') or []
        aml = self.env['account.move.line']

        if analytic_ids:
            # Cara 1: lewat account.analytic.line (lebih cepat jika ada relasi move_line_id)
            aal = self.env['account.analytic.line'].search([
                ('account_id', 'in', analytic_ids),
                ('company_id', '=', company.id),
                ('date', '<=', filters.get('date_to') or self.env.company.currency_id._get_conversion_rate_date())
            ])
            move_line_ids = set(aal.mapped('move_line_id').ids)
            _logger.info(f"Analytic filter: {len(move_line_ids)} AML via analytic lines")

            if move_line_ids:
                domain.append(('id', 'in', list(move_line_ids)))
                move_lines = aml.search(domain)
            else:
                # Fallback ke analytic_distribution bila tidak ada move_line_id di AAL
                move_lines = aml.search(domain)
                move_lines = move_lines.filtered(
                    lambda l: l.analytic_distribution and any(str(aid) in l.analytic_distribution for aid in analytic_ids)
                )
        else:
            move_lines = aml.search(domain)

        _logger.info(f"Found {len(move_lines)} move lines for company {company.name} (analytic_ids={analytic_ids})")

        result = []
        for line in move_lines:
            result.append({
                'id': line.id,
                'date': str(line.date),
                'account_id': line.account_id.id,
                'account_name': line.account_id.name,
                'account_code': line.account_id.code,
                'debit': line.debit,
                'credit': line.credit,
                'balance': line.balance,
                # Tampilkan analytic info jika ada
                'analytic_distribution': line.analytic_distribution or {},
                'company_id': company.id,
                'company_name': company.name,
            })
        return result

    def _get_profit_loss_for_period(self, filters, company):
        """Hitung Net Profit (Income - Expense) agregat per akun dengan read_group agar tidak double."""
        aml = self.env['account.move.line']
        domain = [
            ('move_id.state', '=', 'posted'),
            ('company_id', '=', company.id),
        ]
        if filters.get('date_from'):
            domain.append(('date', '>=', filters['date_from']))
        if filters.get('date_to'):
            domain.append(('date', '<=', filters['date_to']))

        income_types = ['income', 'income_other']
        expense_types = ['expense', 'expense_depreciation', 'expense_direct_cost']

        # Ambil daftar akun per tipe
        acc_model = self.env['account.account']
        income_acc_ids = acc_model.search([('account_type', 'in', income_types), ('company_id', '=', company.id)]).ids
        expense_acc_ids = acc_model.search([('account_type', 'in', expense_types), ('company_id', '=', company.id)]).ids

        # Aggregasi kredit/debit per akun income
        income_groups = aml.read_group(
            domain + [('account_id', 'in', income_acc_ids)],
            ['debit:sum', 'credit:sum', 'account_id'],
            ['account_id'],
            lazy=False
        )
        # Aggregasi kredit/debit per akun expense
        expense_groups = aml.read_group(
            domain + [('account_id', 'in', expense_acc_ids)],
            ['debit:sum', 'credit:sum', 'account_id'],
            ['account_id'],
            lazy=False
        )

        # Neto pakai (credit - debit)
        income_net = sum((g['credit'] or 0.0) - (g['debit'] or 0.0) for g in income_groups)
        expense_net = sum((g['credit'] or 0.0) - (g['debit'] or 0.0) for g in expense_groups)
        net_profit = income_net + expense_net  # expense_net sudah negatif, jadi dijumlahkan

        _logger.info(f"[P&L] income_net={income_net}, expense_net={expense_net}, net_profit={net_profit}")
        return {
            'income_net': income_net,
            'expense_net': expense_net,
            'net_profit': net_profit,
        }

    def _get_balance_sheet_lines(self, filters, company):
        """
        Ambil balance sheet lines berdasarkan account type + analytic filter.
        PERBAIKAN: Hitung opening balance jika ada date_from.
        """
        bs_account_types = [
            # ASSETS
            'asset_receivable', 'asset_cash', 'asset_current',
            'asset_non_current', 'asset_prepayments', 'asset_fixed',
            
            # LIABILITIES
            'liability_payable', 'liability_credit_card',
            'liability_current', 'liability_non_current',
            
            # EQUITY
            'equity', 'equity_unaffected'
        ]
        accounts = self.env['account.account'].search([
            ('account_type', 'in', bs_account_types),
            ('company_id', '=', company.id)
        ])
        _logger.info(f"Found {len(accounts)} balance sheet accounts for company {company.name}")

        analytic_ids = filters.get('analytic_account_ids') or []
        apply_analytic = bool(filters.get('apply_analytic_on_bs'))
        date_from = filters.get('date_from')
        date_to = filters.get('date_to')
        result = {'assets': [], 'liabilities': [], 'equity': []}

        for account in accounts:
            aml = self.env['account.move.line']
            
            # === HITUNG OPENING BALANCE (jika ada date_from) ===
            opening_balance = 0.0
            opening_debit = 0.0
            opening_credit = 0.0
            
            if date_from:
                domain_opening = [
                    ('account_id', '=', account.id),
                    ('move_id.state', '=', 'posted'),
                    ('company_id', '=', company.id),
                    ('date', '<', date_from)  # Sebelum periode
                ]
                
                # Filter analytic untuk opening (jika apply_analytic=True dan asset)
                if analytic_ids and apply_analytic and 'asset' in account.account_type:
                    aal = self.env['account.analytic.line'].search([
                        ('account_id', 'in', analytic_ids),
                        ('company_id', '=', company.id),
                    ])
                    move_line_ids = set(aal.mapped('move_line_id').ids)
                    opening_lines = aml.search(domain_opening + [('id', 'in', list(move_line_ids))]) if move_line_ids else aml.search(domain_opening)
                    if not move_line_ids:
                        opening_lines = opening_lines.filtered(
                            lambda l: l.analytic_distribution and any(str(aid) in l.analytic_distribution for aid in analytic_ids)
                        )
                else:
                    opening_lines = aml.search(domain_opening)
                
                opening_balance = sum(opening_lines.mapped('balance'))
                opening_debit = sum(opening_lines.mapped('debit'))
                opening_credit = sum(opening_lines.mapped('credit'))
                
                _logger.info(f"Account {account.code}: opening_balance={opening_balance:.2f}")
            
            # === HITUNG MOVEMENT PERIODE ===
            domain_period = [
                ('account_id', '=', account.id),
                ('move_id.state', '=', 'posted'),
                ('company_id', '=', company.id)
            ]
            
            if date_from:
                domain_period.append(('date', '>=', date_from))
            if date_to:
                domain_period.append(('date', '<=', date_to))
            
            # Filter analytic untuk period (jika apply_analytic=True dan asset)
            if analytic_ids and apply_analytic and 'asset' in account.account_type:
                aal = self.env['account.analytic.line'].search([
                    ('account_id', 'in', analytic_ids),
                    ('company_id', '=', company.id),
                ])
                move_line_ids = set(aal.mapped('move_line_id').ids)
                period_lines = aml.search(domain_period + [('id', 'in', list(move_line_ids))]) if move_line_ids else aml.search(domain_period)
                if not move_line_ids:
                    period_lines = period_lines.filtered(
                        lambda l: l.analytic_distribution and any(str(aid) in l.analytic_distribution for aid in analytic_ids)
                    )
            else:
                period_lines = aml.search(domain_period)
            
            period_balance = sum(period_lines.mapped('balance'))
            period_debit = sum(period_lines.mapped('debit'))
            period_credit = sum(period_lines.mapped('credit'))
            
            # === TOTAL = OPENING + PERIOD ===
            total_balance = opening_balance + period_balance
            total_debit = opening_debit + period_debit
            total_credit = opening_credit + period_credit
            
            if total_balance != 0 or opening_balance != 0:  # Tampilkan jika ada opening atau movement
                account_data = {
                    'id': account.id,
                    'code': account.code,
                    'name': account.name,
                    'type': account.account_type,
                    'opening_balance': opening_balance,
                    'opening_debit': opening_debit,
                    'opening_credit': opening_credit,
                    'period_balance': period_balance,
                    'period_debit': period_debit,
                    'period_credit': period_credit,
                    'balance': total_balance,
                    'debit': total_debit,
                    'credit': total_credit,
                    'company_id': company.id,
                    'company_name': company.name,
                }
                
                if 'asset' in account.account_type:
                    result['assets'].append(account_data)
                elif 'liability' in account.account_type:
                    result['liabilities'].append(account_data)
                elif 'equity' in account.account_type:
                    result['equity'].append(account_data)

        # === HITUNG P&L UNTUK PERIODE ===
        pl = self._get_profit_loss_for_period(filters, company)
        if abs(pl['net_profit']) > 1e-6:
            is_profit = pl['net_profit'] > 0
            amount = abs(pl['net_profit'])
            
            result['liabilities'].append({
                'id': 0,
                'code': 'P&L',
                'name': 'Profit/Loss for Period',
                'type': 'liability_current',
                'opening_balance': 0.0,
                'opening_debit': 0.0,
                'opening_credit': 0.0,
                'period_balance': amount if is_profit else -amount,
                'period_debit': 0.0 if is_profit else amount,
                'period_credit': amount if is_profit else 0.0,
                'balance': -amount if is_profit else amount,  # balance = debit - credit
                'debit': 0.0 if is_profit else amount,
                'credit': amount if is_profit else 0.0,
                'company_id': company.id,
                'company_name': company.name,
            })

        return result
    
    def _calculate_summary(self, bs_lines):
        """Summary: assets apa adanya; liabilities/equity sebagai (credit - debit)."""
        total_assets = sum(line['balance'] for line in bs_lines['assets'])
        total_liabilities = sum((line['credit'] - line['debit']) for line in bs_lines['liabilities'])
        total_equity = sum((line['credit'] - line['debit']) for line in bs_lines['equity'])
        total_liabilities_equity = total_liabilities + total_equity
        return {
            'total_assets': total_assets,
            'total_liabilities': total_liabilities,
            'total_equity': total_equity,
            'total_liabilities_equity': total_liabilities_equity,
            'balanced': abs(total_assets - total_liabilities_equity) < 0.01,
            'difference': total_assets - total_liabilities_equity,
        }
    
    @api.model
    def get_accounts_by_type(self, account_types=None, company_id=False):
        """Ambil daftar account beserta type-nya"""
        _logger.info("Getting accounts by type")
        
        if company_id:
            company = self.env['res.company'].browse(company_id)
        else:
            company = self.env.company
        
        # Jika tidak ada filter type, ambil semua
        domain = [('company_id', '=', company.id)]
        if account_types:
            if not isinstance(account_types, (list, tuple)):
                account_types = [account_types]
            domain.append(('account_type', 'in', account_types))
        
        accounts = self.env['account.account'].search(domain, order='code')
        
        result = []
        for account in accounts:
            result.append({
                'id': account.id,
                'code': account.code,
                'name': account.name,
                'account_type': account.account_type,
                'account_type_label': dict(account._fields['account_type'].selection).get(account.account_type, ''),
                'company_id': company.id,
                'company_name': company.name,
                'currency': account.currency_id.name if account.currency_id else company.currency_id.name,
            })
        
        return {
            'status': 'success',
            'company': {
                'id': company.id,
                'name': company.name,
            },
            'total': len(result),
            'accounts': result
        }

    @api.model
    def get_all_account_types(self):
        """Ambil semua account types yang tersedia di sistem"""
        account_model = self.env['account.account']
        account_type_field = account_model._fields['account_type']
        
        # Ambil selection values
        types = []
        for key, label in account_type_field.selection:
            types.append({
                'key': key,
                'label': label,
            })
        
        return {
            'status': 'success',
            'total': len(types),
            'account_types': types
        }

    @api.model
    def get_accounts_grouped_by_type(self, company_id=False):
        """Ambil account grouped by type"""
        _logger.info("Getting accounts grouped by type")
        
        if company_id:
            company = self.env['res.company'].browse(company_id)
        else:
            company = self.env.company
        
        accounts = self.env['account.account'].search([
            ('company_id', '=', company.id)
        ], order='account_type, code')
        
        # Group by type
        grouped = {}
        for account in accounts:
            acc_type = account.account_type
            if acc_type not in grouped:
                grouped[acc_type] = {
                    'type': acc_type,
                    'label': dict(account._fields['account_type'].selection).get(acc_type, ''),
                    'accounts': [],
                    'count': 0
                }
            
            grouped[acc_type]['accounts'].append({
                'id': account.id,
                'code': account.code,
                'name': account.name,
            })
            grouped[acc_type]['count'] += 1
        
        return {
            'status': 'success',
            'company': {
                'id': company.id,
                'name': company.name,
            },
            'total_types': len(grouped),
            'total_accounts': len(accounts),
            'grouped': list(grouped.values())
        }

    @api.model
    def get_balance_sheet_account_types(self, company_id=False):
        """Ambil account types khusus untuk balance sheet dengan detailnya"""
        _logger.info("Getting balance sheet account types")
        
        if company_id:
            company = self.env['res.company'].browse(company_id)
        else:
            company = self.env.company
        
        bs_types = {
            'assets': [
                'asset_receivable', 'asset_cash', 'asset_current',
                'asset_non_current', 'asset_prepayments', 'asset_fixed'
            ],
            'liabilities': [
                'liability_payable', 'liability_credit_card',
                'liability_current', 'liability_non_current'
            ],
            'equity': [
                'equity', 'equity_unaffected'
            ]
        }
        
        result = {}
        
        for category, types in bs_types.items():
            result[category] = []
            
            for acc_type in types:
                accounts = self.env['account.account'].search([
                    ('account_type', '=', acc_type),
                    ('company_id', '=', company.id)
                ], order='code')
                
                account_list = []
                for account in accounts:
                    account_list.append({
                        'id': account.id,
                        'code': account.code,
                        'name': account.name,
                    })
                
                result[category].append({
                    'type': acc_type,
                    'label': dict(accounts._fields['account_type'].selection).get(acc_type, '') if accounts else '',
                    'count': len(accounts),
                    'accounts': account_list
                })
        
        return {
            'status': 'success',
            'company': {
                'id': company.id,
                'name': company.name,
            },
            'balance_sheet_types': result
        }

    @api.model
    def debug_account(self, code, date_to=False, company_id=False):
        """Debug satu akun (cek debit/credit/balance)"""
        company = self.env['res.company'].browse(company_id) if company_id else self.env.company
        date_to = date_to or datetime.now().strftime('%Y-%m-%d')
        acc = self.env['account.account'].search([
            ('code', '=', code),
            ('company_id', '=', company.id)
        ], limit=1)
        if not acc:
            return {'error': f'Account code {code} not found in company {company.name}'}
        lines = self.env['account.move.line'].search([
            ('account_id', '=', acc.id),
            ('move_id.state', '=', 'posted'),
            ('company_id', '=', company.id),
            ('date', '<=', date_to),
        ])
        return {
            'company': company.name,
            'account': {'id': acc.id, 'code': acc.code, 'name': acc.name, 'type': acc.account_type},
            'date_to': date_to,
            'line_count': len(lines),
            'debit': sum(lines.mapped('debit')),
            'credit': sum(lines.mapped('credit')),
            'balance': sum(lines.mapped('balance')),
            'sample_moves': [{
                'date': str(l.date), 'move': l.move_id.name, 'partner': l.partner_id.name,
                'debit': l.debit, 'credit': l.credit, 'balance': l.balance
            } for l in lines[:10]],
        }
    
    @api.model
    def debug_sum_account_liablity(self, company_id=False):
        """Debug total liability untuk pengecekan keseimbangan"""
        company = self.env['res.company'].browse(company_id) if company_id else self.env.company
        liability_types = [
            'liability_payable',
            'liability_credit_card',
            'liability_current',
            'liability_non_current'
        ]
        accounts = self.env['account.account'].search([
            ('account_type', 'in', liability_types),
            ('company_id', '=', company.id),
        ])
        aml = self.env['account.move.line']
        total_debit = total_credit = total_balance = 0.0
        for acc in accounts:
            lines = aml.search([
                ('account_id', '=', acc.id),
                ('move_id.state', '=', 'posted'),
                ('company_id', '=', company.id),
            ])
            total_debit += sum(lines.mapped('debit'))
            total_credit += sum(lines.mapped('credit'))
            total_balance += sum(lines.mapped('balance'))
        _logger.info(f"[LIAB DEBUG] debit={total_debit} credit={total_credit} balance={total_balance}")
        return {
            'company': {'id': company.id, 'name': company.name},
            'liability_types': liability_types,
            'total_debit': total_debit,
            'total_credit': total_credit,
            'total_balance': total_balance,
        }
    
    @api.model
    def export_all_move_lines(self, date_from=False, date_to=False, company_id=False, 
                             account_type=False, analytic_account_ids=False):
        """
        Export semua move lines dengan detail lengkap untuk validasi manual.
        Returns: list of dict dengan semua field penting per move line.
        """
        _logger.info("=== EXPORT ALL MOVE LINES ===")
        
        if company_id:
            company = self.env['res.company'].browse(company_id)
        else:
            company = self.env.company
        
        # Build domain
        domain = [
            ('move_id.state', '=', 'posted'),
            ('company_id', '=', company.id)
        ]
        
        if date_from:
            domain.append(('date', '>=', date_from))
        if date_to:
            domain.append(('date', '<=', date_to))
        
        # Filter by account type jika ada
        if account_type:
            if not isinstance(account_type, (list, tuple)):
                account_type = [account_type]
            accounts = self.env['account.account'].search([
                ('account_type', 'in', account_type),
                ('company_id', '=', company.id)
            ])
            domain.append(('account_id', 'in', accounts.ids))
        
        # Search move lines
        aml = self.env['account.move.line']
        move_lines = aml.search(domain, order='account_id, date, id')
        
        _logger.info(f"Found {len(move_lines)} move lines")
        
        result = []
        for line in move_lines:
            # Determine account group (BS category)
            acc_type = line.account_id.account_type
            if 'asset' in acc_type:
                group = 'ASSETS'
            elif 'liability' in acc_type:
                group = 'LIABILITIES'
            elif 'equity' in acc_type:
                group = 'EQUITY'
            elif 'income' in acc_type:
                group = 'INCOME'
            elif 'expense' in acc_type:
                group = 'EXPENSE'
            else:
                group = 'OTHER'
            
            # Get account group (parent)
            account_group = line.account_id.group_id
            
            result.append({
                'id': line.id,
                'date': str(line.date),
                'move_name': line.move_id.name,
                'move_id': line.move_id.id,
                'account_id': line.account_id.id,
                'account_code': line.account_id.code,
                'account_name': line.account_id.name,
                'account_type': acc_type,
                'account_group': group,
                'account_group_id': account_group.id if account_group else False,
                'account_group_name': account_group.name if account_group else '',
                'account_group_code': account_group.code_prefix_start if account_group else '',
                'partner_id': line.partner_id.id if line.partner_id else False,
                'partner_name': line.partner_id.name if line.partner_id else '',
                'label': line.name or '',
                'debit': line.debit,
                'credit': line.credit,
                'balance': line.balance,
                'analytic_distribution': line.analytic_distribution or {},
                'company_id': company.id,
                'company_name': company.name,
                'currency': line.currency_id.name if line.currency_id else company.currency_id.name,
            })
        
        return {
            'status': 'success',
            'company': {
                'id': company.id,
                'name': company.name,
                'currency': company.currency_id.name,
            },
            'filters': {
                'date_from': date_from,
                'date_to': date_to,
                'account_type': account_type,
                'analytic_account_ids': analytic_account_ids,
            },
            'total_lines': len(result),
            'move_lines': result,
        }

    @api.model
    def export_aggregated_by_account(self, date_from=False, date_to=False, company_id=False):
        """
        Export move lines agregat per account (sum debit, credit, balance per account).
        Returns: list of dict per account dengan total.
        """
        _logger.info("=== EXPORT AGGREGATED BY ACCOUNT ===")
        
        if company_id:
            company = self.env['res.company'].browse(company_id)
        else:
            company = self.env.company
        
        domain = [
            ('move_id.state', '=', 'posted'),
            ('company_id', '=', company.id)
        ]
        
        if date_from:
            domain.append(('date', '>=', date_from))
        if date_to:
            domain.append(('date', '<=', date_to))
        
        # Gunakan read_group untuk agregasi per account
        aml = self.env['account.move.line']
        groups = aml.read_group(
            domain,
            ['debit:sum', 'credit:sum', 'balance:sum', 'account_id'],
            ['account_id'],
            lazy=False
        )
        
        result = []
        for g in groups:
            account_id = g['account_id'][0] if g.get('account_id') else False
            if not account_id:
                continue
            
            account = self.env['account.account'].browse(account_id)
            acc_type = account.account_type
            account_group = account.group_id
            
            if 'asset' in acc_type:
                group = 'ASSETS'
            elif 'liability' in acc_type:
                group = 'LIABILITIES'
            elif 'equity' in acc_type:
                group = 'EQUITY'
            elif 'income' in acc_type:
                group = 'INCOME'
            elif 'expense' in acc_type:
                group = 'EXPENSE'
            else:
                group = 'OTHER'
            
            result.append({
                'account_id': account_id,
                'account_code': account.code,
                'account_name': account.name,
                'account_type': acc_type,
                'account_group': group,
                'account_group_id': account_group.id if account_group else False,
                'account_group_name': account_group.name if account_group else '',
                'account_group_code': account_group.code_prefix_start if account_group else '',
                'line_count': g['__count'],
                'debit': g['debit'] or 0.0,
                'credit': g['credit'] or 0.0,
                'balance': g['balance'] or 0.0,
                'net': (g['credit'] or 0.0) - (g['debit'] or 0.0),
            })
        
        # Sort by group then code
        result.sort(key=lambda x: (x['account_group'], x['account_code']))
        
        # Calculate group totals
        group_totals = {}
        for line in result:
            grp = line['account_group']
            if grp not in group_totals:
                group_totals[grp] = {'debit': 0.0, 'credit': 0.0, 'balance': 0.0, 'net': 0.0}
            group_totals[grp]['debit'] += line['debit']
            group_totals[grp]['credit'] += line['credit']
            group_totals[grp]['balance'] += line['balance']
            group_totals[grp]['net'] += line['net']
        
        return {
            'status': 'success',
            'company': {
                'id': company.id,
                'name': company.name,
                'currency': company.currency_id.name,
            },
            'filters': {
                'date_from': date_from,
                'date_to': date_to,
            },
            'total_accounts': len(result),
            'accounts': result,
            'group_totals': group_totals,
        }

    @api.model
    def export_income_expense_detail(self, date_from=False, date_to=False, company_id=False):
        """
        Export detail income dan expense untuk validasi P&L.
        """
        _logger.info("=== EXPORT INCOME EXPENSE DETAIL ===")
        
        if company_id:
            company = self.env['res.company'].browse(company_id)
        else:
            company = self.env.company
        
        domain = [
            ('move_id.state', '=', 'posted'),
            ('company_id', '=', company.id)
        ]
        
        if date_from:
            domain.append(('date', '>=', date_from))
        if date_to:
            domain.append(('date', '<=', date_to))
        
        income_types = ['income', 'income_other']
        expense_types = ['expense', 'expense_depreciation', 'expense_direct_cost']
        
        aml = self.env['account.move.line']
        
        # Income accounts
        income_accounts = self.env['account.account'].search([
            ('account_type', 'in', income_types),
            ('company_id', '=', company.id)
        ])
        
        income_groups = aml.read_group(
            domain + [('account_id', 'in', income_accounts.ids)],
            ['debit:sum', 'credit:sum', 'balance:sum', 'account_id'],
            ['account_id'],
            lazy=False
        )
        
        # Expense accounts
        expense_accounts = self.env['account.account'].search([
            ('account_type', 'in', expense_types),
            ('company_id', '=', company.id)
        ])
        
        expense_groups = aml.read_group(
            domain + [('account_id', 'in', expense_accounts.ids)],
            ['debit:sum', 'credit:sum', 'balance:sum', 'account_id'],
            ['account_id'],
            lazy=False
        )

        income_lines = []
        total_income_debit = 0.0
        total_income_credit = 0.0
        total_income_balance = 0.0
        
        for g in income_groups:
            if not g.get('account_id'):
                continue
            account = self.env['account.account'].browse(g['account_id'][0])
            account_group = account.group_id
            debit = g['debit'] or 0.0
            credit = g['credit'] or 0.0
            balance = g['balance'] or 0.0
            net = credit - debit
            
            income_lines.append({
                'account_id': account.id,
                'account_code': account.code,
                'account_name': account.name,
                'account_type': account.account_type,
                'account_group_id': account_group.id if account_group else False,
                'account_group_name': account_group.name if account_group else '',
                'account_group_code': account_group.code_prefix_start if account_group else '',
                'debit': debit,
                'credit': credit,
                'balance': balance,
                'net': net,
            })
            
            total_income_debit += debit
            total_income_credit += credit
            total_income_balance += balance
        
        expense_lines = []
        total_expense_debit = 0.0
        total_expense_credit = 0.0
        total_expense_balance = 0.0
        
        for g in expense_groups:
            if not g.get('account_id'):
                continue
            account = self.env['account.account'].browse(g['account_id'][0])
            account_group = account.group_id
            debit = g['debit'] or 0.0
            credit = g['credit'] or 0.0
            balance = g['balance'] or 0.0
            net = credit - debit
            
            expense_lines.append({
                'account_id': account.id,
                'account_code': account.code,
                'account_name': account.name,
                'account_type': account.account_type,
                'account_group_id': account_group.id if account_group else False,
                'account_group_name': account_group.name if account_group else '',
                'account_group_code': account_group.code_prefix_start if account_group else '',
                'debit': debit,
                'credit': credit,
                'balance': balance,
                'net': net,
            })
            
            total_expense_debit += debit
            total_expense_credit += credit
            total_expense_balance += balance
        
        # Calculate net profit
        income_net = total_income_credit - total_income_debit
        expense_net = total_expense_credit - total_expense_debit
        net_profit = income_net + expense_net  # expense_net sudah negatif, jadi dijumlahkan
        
        return {
            'status': 'success',
            'company': {
                'id': company.id,
                'name': company.name,
                'currency': company.currency_id.name,
            },
            'filters': {
                'date_from': date_from,
                'date_to': date_to,
            },
            'income': {
                'accounts': income_lines,
                'total_debit': total_income_debit,
                'total_credit': total_income_credit,
                'total_balance': total_income_balance,
                'net': income_net,
            },
            'expense': {
                'accounts': expense_lines,
                'total_debit': total_expense_debit,
                'total_credit': total_expense_credit,
                'total_balance': total_expense_balance,
                'net': expense_net,
            },
            'profit_loss': {
                'income_net': income_net,
                'expense_net': expense_net,
                'net_profit': net_profit,
                'is_profit': net_profit > 0,
            }
        }

    @api.model
    def asset_detail_group(self, date_from=False, date_to=False, company_id=False):
        """
        Export detail asset dengan grouping berdasarkan account_group_name.
        DENGAN OPENING BALANCE: Hitung saldo sebelum date_from sebagai opening.
        Returns: Asset grouped by account.group_id dengan opening, period, dan ending balance.
        """
        _logger.info("=== EXPORT ASSET DETAIL BY GROUP WITH OPENING BALANCE ===")
        
        if company_id:
            company = self.env['res.company'].browse(company_id)
        else:
            company = self.env.company

        aml = self.env['account.move.line']
        asset_types = ['asset_receivable', 'asset_cash', 'asset_current',
                       'asset_non_current', 'asset_prepayments', 'asset_fixed']

        # Get all asset accounts
        asset_accounts = self.env['account.account'].search([
            ('account_type', 'in', asset_types),
            ('company_id', '=', company.id)
        ])
        
        # Group by account_group_name
        grouped_data = {}
        
        for account in asset_accounts:
            account_group = account.group_id
            
            # Tentukan group key
            if account_group:
                group_key = account_group.id
                group_name = account_group.name
                group_code = account_group.code_prefix_start or ''
            else:
                group_key = 0
                group_name = 'Unassigned'
                group_code = ''
            
            # Initialize group jika belum ada
            if group_key not in grouped_data:
                grouped_data[group_key] = {
                    'group_id': group_key,
                    'group_name': group_name,
                    'group_code': group_code,
                    'opening_debit': 0.0,
                    'opening_credit': 0.0,
                    'opening_balance': 0.0,
                    'period_debit': 0.0,
                    'period_credit': 0.0,
                    'period_balance': 0.0,
                    'ending_debit': 0.0,
                    'ending_credit': 0.0,
                    'ending_balance': 0.0,
                    'accounts': []
                }
            
            # === HITUNG OPENING BALANCE (sebelum date_from) ===
            opening_debit = 0.0
            opening_credit = 0.0
            opening_balance = 0.0
            
            if date_from:
                domain_opening = [
                    ('account_id', '=', account.id),
                    ('move_id.state', '=', 'posted'),
                    ('company_id', '=', company.id),
                    ('date', '<', date_from)  # Sebelum periode
                ]
                opening_lines = aml.search(domain_opening)
                opening_debit = sum(opening_lines.mapped('debit'))
                opening_credit = sum(opening_lines.mapped('credit'))
                opening_balance = sum(opening_lines.mapped('balance'))
            
            # === HITUNG PERIOD MOVEMENT (dari date_from sampai date_to) ===
            domain_period = [
                ('account_id', '=', account.id),
                ('move_id.state', '=', 'posted'),
                ('company_id', '=', company.id)
            ]
            
            if date_from:
                domain_period.append(('date', '>=', date_from))
            if date_to:
                domain_period.append(('date', '<=', date_to))
            
            period_lines = aml.search(domain_period)
            period_debit = sum(period_lines.mapped('debit'))
            period_credit = sum(period_lines.mapped('credit'))
            period_balance = sum(period_lines.mapped('balance'))
            
            # === TOTAL = OPENING + PERIOD ===
            ending_debit = opening_debit + period_debit
            ending_credit = opening_credit + period_credit
            ending_balance = opening_balance + period_balance
            
            # Hanya tambahkan jika ada transaksi (opening atau period)
            if ending_balance != 0 or opening_balance != 0:
                account_data = {
                    'account_id': account.id,
                    'account_code': account.code,
                    'account_name': account.name,
                    'account_type': account.account_type,
                    'opening_debit': opening_debit,
                    'opening_credit': opening_credit,
                    'opening_balance': opening_balance,
                    'period_debit': period_debit,
                    'period_credit': period_credit,
                    'period_balance': period_balance,
                    'ending_debit': ending_debit,
                    'ending_credit': ending_credit,
                    'ending_balance': ending_balance,
                }
                grouped_data[group_key]['accounts'].append(account_data)
                
                # Sum group totals
                grouped_data[group_key]['opening_debit'] += opening_debit
                grouped_data[group_key]['opening_credit'] += opening_credit
                grouped_data[group_key]['opening_balance'] += opening_balance
                grouped_data[group_key]['period_debit'] += period_debit
                grouped_data[group_key]['period_credit'] += period_credit
                grouped_data[group_key]['period_balance'] += period_balance
                grouped_data[group_key]['ending_debit'] += ending_debit
                grouped_data[group_key]['ending_credit'] += ending_credit
                grouped_data[group_key]['ending_balance'] += ending_balance
        
        # Convert dict to sorted list (hanya group yang punya account)
        groups_list = [g for g in grouped_data.values() if g['accounts']]
        groups_list.sort(key=lambda x: (x['group_code'], x['group_name']))
        
        # Calculate grand totals
        grand_total = {
            'opening_debit': sum(g['opening_debit'] for g in groups_list),
            'opening_credit': sum(g['opening_credit'] for g in groups_list),
            'opening_balance': sum(g['opening_balance'] for g in groups_list),
            'period_debit': sum(g['period_debit'] for g in groups_list),
            'period_credit': sum(g['period_credit'] for g in groups_list),
            'period_balance': sum(g['period_balance'] for g in groups_list),
            'ending_debit': sum(g['ending_debit'] for g in groups_list),
            'ending_credit': sum(g['ending_credit'] for g in groups_list),
            'ending_balance': sum(g['ending_balance'] for g in groups_list),
        }
        
        return {
            'status': 'success',
            'company': {
                'id': company.id,
                'name': company.name,
                'currency': company.currency_id.name,
            },
            'filters': {
                'date_from': date_from,
                'date_to': date_to,
            },
            'total_groups': len(groups_list),
            'groups': groups_list,
            'grand_total': grand_total,
        }