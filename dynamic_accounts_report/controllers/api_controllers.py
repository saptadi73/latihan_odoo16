# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
import json
import logging

_logger = logging.getLogger(__name__)

class FinancialReportsAPIController(http.Controller):
    
    # ============== BALANCE SHEET ENDPOINTS ==============
    
    @http.route('/api/balance_sheet/companies', type='http', auth='user', methods=['GET'], csrf=False)
    def get_companies(self, **kwargs):
        """Ambil daftar semua company (HTTP GET)"""
        try:
            report_obj = request.env['account.balance.sheet.report'].sudo()
            data = report_obj.get_available_companies()
            return request.make_json_response(data)
        except Exception as e:
            _logger.error(f"/api/balance_sheet/companies error: {str(e)}", exc_info=True)
            return request.make_json_response({'status': 'error', 'message': str(e)}, status=500)
    
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
    
    @http.route('/api/balance_sheet/analytic_accounts', type='json', auth='user', methods=['POST'], csrf=False)
    def get_analytic_accounts(self, **kwargs):
        """Get list of analytic accounts"""
        try:
            report_obj = request.env['account.balance.sheet.report']
            data = report_obj.get_analytic_accounts(company_id=kwargs.get('company_id'))
            return data
        except Exception as e:
            _logger.error(f"/api/balance_sheet/analytic_accounts error: {str(e)}", exc_info=True)
            return {'status': 'error', 'message': str(e)}

    @http.route('/api/balance_sheet/filter_options', type='json', auth='user', methods=['POST'], csrf=False)
    def get_filter_options(self, **kwargs):
        """Get all filter options (companies + analytic accounts) in one call"""
        try:
            report_obj = request.env['account.balance.sheet.report']
            data = report_obj.get_filter_options(company_id=kwargs.get('company_id'))
            return data
        except Exception as e:
            _logger.error(f"/api/balance_sheet/filter_options error: {str(e)}", exc_info=True)
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

    # ============== EXPORT ENDPOINTS ==============

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

    # ============== DETAIL GROUP ENDPOINTS ==============

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
        """Equity grouped by account_group_name dengan opening balance dan transaksi periode"""
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

    # ============== FINANCIAL COMBINED ENDPOINTS ==============

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
            _logger.error(f"Error: {str(e)}", exc_info=True)
            return {'status': 'error', 'message': str(e)}

    @http.route('/api/financial/combined_multi_company', type='json', auth='user', methods=['POST'], csrf=False)
    def financial_report_combined_multi_company(self, **kwargs):
        """
        Body JSON:
        {
          "company_ids": [1, 2, 3],
          "date_from": "YYYY-MM-DD",      # optional
          "date_to": "YYYY-MM-DD"         # optional
        }
        Returns: semua hasil financial_report_combined per company dalam satu payload.
        """
        try:
            company_ids = kwargs.get('company_ids')
            date_from = kwargs.get('date_from')
            date_to = kwargs.get('date_to')

            if not company_ids:
                return {'status': 'error', 'message': 'company_ids is required (int or list[int])'}

            report = request.env['account.balance.sheet.report'].sudo()
            return report.financial_report_combined_multi_company(
                company_ids=company_ids,
                date_from=date_from,
                date_to=date_to
            )
        except Exception as e:
            _logger.error("combined_multi_company API error: %s", e, exc_info=True)
            return {'status': 'error', 'message': str(e)}

    @http.route('/api/financial/with_elimination', type='json', auth='user', methods=['POST'], csrf=False)
    def financial_report_with_elimination(self, **kwargs):
        """
        Body JSON:
        {
          "date_from": "YYYY-MM-DD",
          "date_to": "YYYY-MM-DD",
          "company_ids": [1, 2, 3],
          "elimination_account_codes": ["21210030","42000042","67100041"],   # dianjurkan
          "elimination_account_ids": [35,100,101]                            # opsional (kompatibel)
        }
        """
        try:
            date_from = kwargs.get('date_from')
            date_to = kwargs.get('date_to')
            company_ids = kwargs.get('company_ids')
            elimination_account_codes = kwargs.get('elimination_account_codes')
            elimination_account_ids = kwargs.get('elimination_account_ids')

            if not company_ids:
                return {'status': 'error', 'message': 'company_ids is required'}

            report = request.env['account.balance.sheet.report'].sudo()
            return report.financial_report_with_elimination(
                date_from=date_from,
                date_to=date_to,
                company_ids=company_ids,
                elimination_account_codes=elimination_account_codes,
                elimination_account_ids=elimination_account_ids
            )
        except Exception as e:
            _logger.error("with_elimination API error: %s", e, exc_info=True)
            return {'status': 'error', 'message': str(e)}

    # ============== CONSOLIDATION ENDPOINTS ==============

    @http.route('/api/consolidation/balance_sheet', type='json', auth='user', methods=['POST'], csrf=False)
    def get_consolidated_balance_sheet(self, **kwargs):
        """Consolidation: Multi-Company Balance Sheet with Intercompany Elimination"""
        try:
            _logger.info(f"=== CONSOLIDATION REQUEST: {kwargs}")
            consolidation_obj = request.env['account.consolidation']
            data = consolidation_obj.get_consolidated_balance_sheet(
                date_from=kwargs.get('date_from'),
                date_to=kwargs.get('date_to'),
                company_ids=kwargs.get('company_ids'),
                elimination_account_ids=kwargs.get('elimination_account_ids'),
                analytic_account_ids=kwargs.get('analytic_account_ids')
            )
            return data
        except Exception as e:
            _logger.error(f"/api/consolidation/balance_sheet error: {str(e)}", exc_info=True)
            return {'status': 'error', 'message': str(e)}

    @http.route('/api/consolidation/balance_sheet_grouped', type='json', auth='user', methods=['POST'], csrf=False)
    def get_consolidated_balance_sheet_grouped(self, **kwargs):
        """Consolidation: Balance Sheet grouped by account.group with intercompany elimination"""
        try:
            _logger.info(f"=== CONSOLIDATION GROUPED REQUEST: {kwargs}")
            consolidation_obj = request.env['account.consolidation']
            data = consolidation_obj.get_consolidated_balance_sheet_grouped(
                date_from=kwargs.get('date_from'),
                date_to=kwargs.get('date_to'),
                company_ids=kwargs.get('company_ids'),
                elimination_account_ids=kwargs.get('elimination_account_ids'),
                analytic_account_ids=kwargs.get('analytic_account_ids'),
            )
            return data
        except Exception as e:
            _logger.error(f"/api/consolidation/balance_sheet_grouped error: {str(e)}", exc_info=True)
            return {'status': 'error', 'message': str(e)}

    @http.route('/api/consolidation/by_id', type='json', auth='user', methods=['POST'], csrf=False)
    def get_consolidation_by_id(self, **kwargs):
        """Get consolidation result by record ID"""
        try:
            consolidation_id = kwargs.get('consolidation_id')
            if not consolidation_id:
                return {'status': 'error', 'message': 'consolidation_id is required'}
            
            consolidation_obj = request.env['account.consolidation']
            data = consolidation_obj.get_consolidation_by_id(consolidation_id)
            return data
        except Exception as e:
            _logger.error(f"/api/consolidation/by_id error: {str(e)}", exc_info=True)
            return {'status': 'error', 'message': str(e)}

    @http.route('/api/consolidation/process', type='json', auth='user', methods=['POST'], csrf=False)
    def process_consolidation(self, **kwargs):
        """Process consolidation and save state"""
        try:
            consolidation_id = kwargs.get('consolidation_id')
            if not consolidation_id:
                return {'status': 'error', 'message': 'consolidation_id is required'}
            
            record = request.env['account.consolidation'].browse(consolidation_id)
            if not record.exists():
                return {'status': 'error', 'message': 'Consolidation record not found'}
            
            record.action_consolidate()
            return {'status': 'success', 'message': 'Consolidation processed successfully'}
        except Exception as e:
            _logger.error(f"/api/consolidation/process error: {str(e)}", exc_info=True)
            return {'status': 'error', 'message': str(e)}

    # ============== ACCOUNTS LIST ENDPOINT ==============

    @http.route('/api/accounts/list', type='json', auth='user', methods=['POST'], csrf=False)
    def get_accounts_list(self, **kwargs):
        """
        Get list accounts tanpa wajib account_type.
        Body JSON (opsional semua):
        {
          "company_id": 1,
          "search": "cash",   // filter by code/name
          "limit": 100
        }
        """
        try:
            company_id = kwargs.get('company_id')
            search = kwargs.get('search')
            limit = kwargs.get('limit', 200)

            report = request.env['account.balance.sheet.report'].sudo()
            return report.get_accounts_list(company_id=company_id, search=search, limit=limit)
        except Exception as e:
            _logger.error("get_accounts_list API error: %s", e, exc_info=True)
            return {'status': 'error', 'message': str(e)}

    @http.route('/api/financial/reports_combined_analytic', type='json', auth='user', methods=['POST'], csrf=False)
    def financial_report_combined_analytic(self, **kwargs):
        """
        Financial Combined Report dengan filter analytic account.
        Body JSON:
        {
          "date_from": "YYYY-MM-DD",
          "date_to": "YYYY-MM-DD",
          "company_id": 1,
          "analytic_account_ids": [1, 2, 3]  # list analytic account IDs
        }
        """
        try:
            date_from = kwargs.get('date_from')
            date_to = kwargs.get('date_to')
            company_id = kwargs.get('company_id')
            analytic_account_ids = kwargs.get('analytic_account_ids')

            if not company_id:
                return {'status': 'error', 'message': 'company_id is required'}

            report = request.env['account.balance.sheet.report'].sudo()
            return report.financial_report_combined_analytic(
                date_from=date_from,
                date_to=date_to,
                company_id=company_id,
                analytic_account_ids=analytic_account_ids
            )
        except Exception as e:
            _logger.error("financial_report_combined_analytic API error: %s", e, exc_info=True)
            return {'status': 'error', 'message': str(e)}


