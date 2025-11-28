# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
import json
import logging

_logger = logging.getLogger(__name__)

class FinancialReportsAPIController(http.Controller):
    
    # ============== BALANCE SHEET ENDPOINTS ==============
    
    @http.route('/api/balance_sheet/companies', type='json', auth='user', methods=['GET'], csrf=False)
    def get_companies(self):
        """Ambil daftar semua company"""
        try:
            report_obj = request.env['account.balance.sheet.report']
            data = report_obj.get_available_companies()
            return data
        except Exception as e:
            _logger.error(f"Error: {str(e)}", exc_info=True)
            return {'status': 'error', 'message': str(e)}
    
    @http.route('/api/balance_sheet/by_company', type='json', auth='user', methods=['POST'], csrf=False)
    def get_balance_sheet_by_company(self, **kwargs):
        """Get balance sheet untuk company tertentu"""
        try:
            company_id = kwargs.get('company_id')
            if not company_id:
                return {'status': 'error', 'message': 'company_id is required'}
            
            report_obj = request.env['account.balance.sheet.report']
            data = report_obj.get_balance_sheet_direct(
                date_from=kwargs.get('date_from'),
                date_to=kwargs.get('date_to'),
                company_id=company_id
            )
            
            return data
        except Exception as e:
            _logger.error(f"Error: {str(e)}", exc_info=True)
            return {'status': 'error', 'message': str(e)}
    
    @http.route('/api/balance_sheet/all_companies', type='json', auth='user', methods=['POST'], csrf=False)
    def get_all_companies_balance_sheet(self, **kwargs):
        """Get balance sheet untuk SEMUA company"""
        try:
            report_obj = request.env['account.balance.sheet.report']
            data = report_obj.get_all_companies_balance_sheet(
                date_from=kwargs.get('date_from'),
                date_to=kwargs.get('date_to')
            )
            
            return data
        except Exception as e:
            _logger.error(f"Error: {str(e)}", exc_info=True)
            return {'status': 'error', 'message': str(e)}
    
    # ============== PROFIT & LOSS ENDPOINTS ==============
    
    @http.route('/api/profit_loss/by_company', type='json', auth='user', methods=['POST'], csrf=False)
    def get_profit_loss_by_company(self, **kwargs):
        """Get profit & loss untuk company tertentu"""
        try:
            company_id = kwargs.get('company_id')
            if not company_id:
                return {'status': 'error', 'message': 'company_id is required'}
            
            report_obj = request.env['account.profit.loss.report']
            data = report_obj.get_profit_loss_direct(
                date_from=kwargs.get('date_from'),
                date_to=kwargs.get('date_to'),
                company_id=company_id
            )
            
            return data
        except Exception as e:
            _logger.error(f"Error: {str(e)}", exc_info=True)
            return {'status': 'error', 'message': str(e)}
    
    @http.route('/api/profit_loss/all_companies', type='json', auth='user', methods=['POST'], csrf=False)
    def get_all_companies_profit_loss(self, **kwargs):
        """Get profit & loss untuk SEMUA company"""
        try:
            report_obj = request.env['account.profit.loss.report']
            data = report_obj.get_all_companies_profit_loss(
                date_from=kwargs.get('date_from'),
                date_to=kwargs.get('date_to')
            )
            
            return data
        except Exception as e:
            _logger.error(f"Error: {str(e)}", exc_info=True)
            return {'status': 'error', 'message': str(e)}
    
    # ============== COMBINED REPORT ==============
    
    @http.route('/api/financial_reports/complete', type='json', auth='user', methods=['POST'], csrf=False)
    def get_complete_financial_reports(self, **kwargs):
        """Get Balance Sheet & Profit Loss sekaligus"""
        try:
            company_id = kwargs.get('company_id')
            date_from = kwargs.get('date_from')
            date_to = kwargs.get('date_to')
            
            if not company_id:
                return {'status': 'error', 'message': 'company_id is required'}
            
            # Get Balance Sheet
            bs_obj = request.env['account.balance.sheet.report']
            balance_sheet = bs_obj.get_balance_sheet_direct(
                date_from=date_from,
                date_to=date_to,
                company_id=company_id
            )
            
            # Get Profit & Loss
            pl_obj = request.env['account.profit.loss.report']
            profit_loss = pl_obj.get_profit_loss_direct(
                date_from=date_from,
                date_to=date_to,
                company_id=company_id
            )
            
            return {
                'status': 'success',
                'company': balance_sheet['company'],
                'filters': balance_sheet['filters'],
                'balance_sheet': {
                    'lines': balance_sheet['balance_sheet_lines'],
                    'summary': balance_sheet['summary']
                },
                'profit_loss': {
                    'lines': profit_loss['profit_loss_lines'],
                    'summary': profit_loss['summary']
                }
            }
            
        except Exception as e:
            _logger.error(f"Error: {str(e)}", exc_info=True)
            return {'status': 'error', 'message': str(e)}

    @http.route('/api/export/all_move_lines', type='json', auth='user', methods=['POST'], csrf=False)
    def export_all_move_lines(self, **kwargs):
        """Export semua move lines detail"""
        try:
            report_obj = request.env['account.balance.sheet.report']
            data = report_obj.export_all_move_lines(
                date_from=kwargs.get('date_from'),
                date_to=kwargs.get('date_to'),
                company_id=kwargs.get('company_id'),
                account_type=kwargs.get('account_type'),
                analytic_account_ids=kwargs.get('analytic_account_ids')
            )
            return data
        except Exception as e:
            _logger.error(f"Error: {str(e)}", exc_info=True)
            return {'status': 'error', 'message': str(e)}

    @http.route('/api/export/aggregated_by_account', type='json', auth='user', methods=['POST'], csrf=False)
    def export_aggregated_by_account(self, **kwargs):
        """Export move lines agregat per account"""
        try:
            report_obj = request.env['account.balance.sheet.report']
            data = report_obj.export_aggregated_by_account(
                date_from=kwargs.get('date_from'),
                date_to=kwargs.get('date_to'),
                company_id=kwargs.get('company_id')
            )
            return data
        except Exception as e:
            _logger.error(f"Error: {str(e)}", exc_info=True)
            return {'status': 'error', 'message': str(e)}

    @http.route('/api/export/income_expense_detail', type='json', auth='user', methods=['POST'], csrf=False)
    def export_income_expense_detail(self, **kwargs):
        """Export detail income & expense untuk P&L"""
        try:
            report_obj = request.env['account.balance.sheet.report']
            data = report_obj.export_income_expense_detail(
                date_from=kwargs.get('date_from'),
                date_to=kwargs.get('date_to'),
                company_id=kwargs.get('company_id')
            )
            return data
        except Exception as e:
            _logger.error(f"/api/export/income_expense_detail error: {str(e)}", exc_info=True)
            return {'status': 'error', 'message': str(e)}

    @http.route('/api/asset/detail_group', type='json', auth='user', methods=['POST'], csrf=False)
    def asset_detail_group(self, **kwargs):
        """Asset detail grouped by account_group_name dengan opening balance dan transaksi periode"""
        try:
            report_obj = request.env['account.balance.sheet.report']
            data = report_obj.asset_detail_group(
                date_from=kwargs.get('date_from'),
                date_to=kwargs.get('date_to'),
                company_id=kwargs.get('company_id')
            )
            return data
        except Exception as e:
            _logger.error(f"/api/asset/detail_group error: {str(e)}", exc_info=True)
            return {'status': 'error', 'message': str(e)}
    
    @http.route('/api/liability/liability_group', type='json', auth='user', methods=['POST'], csrf=False)
    def asset_liability_group(self, **kwargs):
        """Asset & Liability grouped by account_group_name dengan opening balance dan transaksi periode"""
        try:
            report_obj = request.env['account.balance.sheet.report']
            data = report_obj.asset_Liability_group(
                date_from=kwargs.get('date_from'),
                date_to=kwargs.get('date_to'),
                company_id=kwargs.get('company_id')
            )
            return data
        except Exception as e:
            _logger.error(f"/api/asset/liability_group error: {str(e)}", exc_info=True)
            return {'status': 'error', 'message': str(e)}

    @http.route('/api/pl/detail_group', type='json', auth='user', methods=['POST'], csrf=False)
    def profit_loss_detail_group(self, **kwargs):
        """Profit & Loss grouped by account_group_name dengan opening & period transactions"""
        try:
            report_obj = request.env['account.balance.sheet.report']
            data = report_obj.profit_loss_detail_group(
                date_from=kwargs.get('date_from'),
                date_to=kwargs.get('date_to'),
                company_id=kwargs.get('company_id')
            )
            return data
        except Exception as e:
            _logger.error(f"/api/pl/detail_group error: {str(e)}", exc_info=True)
            return {'status': 'error', 'message': str(e)}
    
    @http.route('/api/equity/detail_group', type='json', auth='user', methods=['POST'], csrf=False)
    def equity_group(self, **kwargs):
        """Asset & Liability grouped by account_group_name dengan opening balance dan transaksi periode"""
        try:
            report_obj = request.env['account.balance.sheet.report']
            data = report_obj.equity_detail_group(
                date_from=kwargs.get('date_from'),
                date_to=kwargs.get('date_to'),
                company_id=kwargs.get('company_id')
            )
            return data
        except Exception as e:
            _logger.error(f"/api/equity/detail_group error: {str(e)}", exc_info=True)
            return {'status': 'error', 'message': str(e)}

    @http.route('/api/financial/combined', type='json', auth='user', methods=['POST'], csrf=False)
    def financial_report_combined(self, **kwargs):
        """Endpoint gabungan: Asset, Liability, Profit & Loss, Equity dalam satu response"""
        try:
            report_obj = request.env['account.balance.sheet.report']
            data = report_obj.financial_report_combined(
                date_from=kwargs.get('date_from'),
                date_to=kwargs.get('date_to'),
                company_id=kwargs.get('company_id')
            )
            return data
        except Exception as e:
            _logger.error(f"/api/financial/combined error: {str(e)}", exc_info=True)
            return {'status': 'error', 'message': str(e)}