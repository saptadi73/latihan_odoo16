# -*- coding: utf-8 -*-
from odoo import api, models, fields
from datetime import datetime
import logging

_logger = logging.getLogger(__name__)

class ProfitLossReport(models.TransientModel):
    _name = 'account.profit.loss.report'
    _description = 'Profit & Loss Report API'
    
    @api.model
    def get_report_values(self, date_from=False, date_to=False, company_id=False):
        """Generate profit & loss data"""
        _logger.info("Starting Profit & Loss Report Generation")
        
        # Tentukan company
        if company_id:
            company = self.env['res.company'].browse(company_id)
        else:
            company = self.env.company
        
        filters = {
            'date_from': date_from or datetime.now().replace(month=1, day=1).strftime('%Y-%m-%d'),
            'date_to': date_to or datetime.now().strftime('%Y-%m-%d'),
            'company_id': company.id,
            'company_name': company.name,
        }
        
        try:
            # Akses report model dengan context
            report = self.env['report.dynamic_accounts_report.profit_and_loss']
            
            # Siapkan data untuk report dengan company filter
            report_lines = self._get_report_lines(filters, company)
            pl_lines = self._get_profit_loss_lines(filters, company)
            
            data = {
                'report_data': {
                    'filters': filters,
                    'report_lines': report_lines,
                    'pl_lines': pl_lines,
                    'name': 'Profit & Loss',
                },
                'report_name': 'Profit & Loss Report',
            }
            
            result = report.with_context(pl_report=True)._get_report_values(None, data)
            
            _logger.info(f"P&L Report generated successfully for company: {company.name}")
            return result
            
        except Exception as e:
            _logger.error(f"Error generating P&L: {str(e)}", exc_info=True)
            raise
    
    @api.model
    def get_profit_loss_direct(self, date_from=False, date_to=False, company_id=False):
        """Ambil data P&L langsung tanpa melalui report model"""
        _logger.info("Getting profit & loss data directly")
        
        # Tentukan company
        if company_id:
            company = self.env['res.company'].browse(company_id)
        else:
            company = self.env.company
        
        filters = {
            'date_from': date_from or datetime.now().replace(month=1, day=1).strftime('%Y-%m-%d'),
            'date_to': date_to or datetime.now().strftime('%Y-%m-%d'),
            'company_id': company.id,
            'company_name': company.name,
        }
        
        # Ambil data langsung dengan company filter
        pl_lines = self._get_profit_loss_lines(filters, company)
        report_lines = self._get_report_lines(filters, company)
        
        # Return dalam format yang lebih simple
        return {
            'status': 'success',
            'filters': filters,
            'profit_loss_lines': pl_lines,
            'report_lines': report_lines,
            'summary': self._calculate_summary(pl_lines),
            'company': {
                'id': company.id,
                'name': company.name,
                'currency': company.currency_id.name,
                'currency_symbol': company.currency_id.symbol,
            }
        }
    
    @api.model
    def get_all_companies_profit_loss(self, date_from=False, date_to=False):
        """Ambil P&L untuk SEMUA company"""
        _logger.info("Getting P&L for ALL companies")
        
        companies = self.env['res.company'].search([])
        _logger.info(f"Found {len(companies)} companies")
        
        results = []
        
        for company in companies:
            _logger.info(f"Processing company: {company.name}")
            
            filters = {
                'date_from': date_from or datetime.now().replace(month=1, day=1).strftime('%Y-%m-%d'),
                'date_to': date_to or datetime.now().strftime('%Y-%m-%d'),
                'company_id': company.id,
                'company_name': company.name,
            }
            
            try:
                pl_lines = self._get_profit_loss_lines(filters, company)
                summary = self._calculate_summary(pl_lines)
                
                results.append({
                    'company': {
                        'id': company.id,
                        'name': company.name,
                        'currency': company.currency_id.name,
                        'currency_symbol': company.currency_id.symbol,
                    },
                    'filters': filters,
                    'profit_loss_lines': pl_lines,
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
    
    def _get_report_lines(self, filters, company):
        """Ambil data akun move lines dengan filter company"""
        # Account types untuk P&L
        pl_account_types = ['income', 'income_other', 'expense', 'expense_depreciation', 
                           'expense_direct_cost']
        
        domain = [
            ('move_id.state', '=', 'posted'),
            ('company_id', '=', company.id),
            ('account_id.account_type', 'in', pl_account_types)
        ]
        
        if filters.get('date_from'):
            domain.append(('date', '>=', filters['date_from']))
        if filters.get('date_to'):
            domain.append(('date', '<=', filters['date_to']))
        
        _logger.info(f"Searching P&L move lines with domain: {domain}")
        move_lines = self.env['account.move.line'].search(domain)
        _logger.info(f"Found {len(move_lines)} P&L move lines for company {company.name}")
        
        result = []
        for line in move_lines:
            result.append({
                'id': line.id,
                'date': str(line.date),
                'account_id': line.account_id.id,
                'account_name': line.account_id.name,
                'account_code': line.account_id.code,
                'account_type': line.account_id.account_type,
                'debit': line.debit,
                'credit': line.credit,
                'balance': line.balance,
                'company_id': company.id,
                'company_name': company.name,
            })
        
        return result
    
    def _get_profit_loss_lines(self, filters, company):
        """Ambil profit & loss lines berdasarkan account type dengan filter company"""
        
        # Account types untuk Profit & Loss
        pl_account_types = {
            'income': ['income', 'income_other'],
            'expense': ['expense', 'expense_depreciation', 'expense_direct_cost']
        }
        
        result = {
            'income': [],
            'expense': [],
        }
        
        # Process Income
        income_accounts = self.env['account.account'].search([
            ('account_type', 'in', pl_account_types['income']),
            ('company_id', '=', company.id)
        ])
        
        _logger.info(f"Found {len(income_accounts)} income accounts for company {company.name}")
        
        for account in income_accounts:
            balance = self._get_account_balance(account, filters, company)
            
            if balance != 0:
                result['income'].append({
                    'id': account.id,
                    'code': account.code,
                    'name': account.name,
                    'type': account.account_type,
                    'balance': abs(balance),  # Income biasanya credit (negatif), jadi pakai abs
                    'company_id': company.id,
                    'company_name': company.name,
                })
        
        # Process Expense
        expense_accounts = self.env['account.account'].search([
            ('account_type', 'in', pl_account_types['expense']),
            ('company_id', '=', company.id)
        ])
        
        _logger.info(f"Found {len(expense_accounts)} expense accounts for company {company.name}")
        
        for account in expense_accounts:
            balance = self._get_account_balance(account, filters, company)
            
            if balance != 0:
                result['expense'].append({
                    'id': account.id,
                    'code': account.code,
                    'name': account.name,
                    'type': account.account_type,
                    'balance': abs(balance),  # Expense biasanya debit (positif)
                    'company_id': company.id,
                    'company_name': company.name,
                })
        
        return result
    
    def _get_account_balance(self, account, filters, company):
        """Hitung balance untuk account tertentu"""
        domain = [
            ('account_id', '=', account.id),
            ('move_id.state', '=', 'posted'),
            ('company_id', '=', company.id)
        ]
        
        if filters.get('date_from'):
            domain.append(('date', '>=', filters['date_from']))
        if filters.get('date_to'):
            domain.append(('date', '<=', filters['date_to']))
        
        move_lines = self.env['account.move.line'].search(domain)
        return sum(move_lines.mapped('balance'))
    
    def _calculate_summary(self, pl_lines):
        """Hitung summary total"""
        total_income = sum(line['balance'] for line in pl_lines['income'])
        total_expense = sum(line['balance'] for line in pl_lines['expense'])
        net_profit = total_income - total_expense
        
        # Hitung percentages
        income_percentage = 100.0 if total_income > 0 else 0.0
        expense_percentage = (total_expense / total_income * 100) if total_income > 0 else 0.0
        profit_percentage = (net_profit / total_income * 100) if total_income > 0 else 0.0
        
        return {
            'total_income': total_income,
            'total_expense': total_expense,
            'net_profit': net_profit,
            'is_profit': net_profit >= 0,
            'income_percentage': income_percentage,
            'expense_percentage': expense_percentage,
            'profit_percentage': profit_percentage,
            'gross_profit_margin': profit_percentage,
        }