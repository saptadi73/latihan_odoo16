# -*- coding: utf-8 -*-
from odoo import api, models


class InsReportProfitLoss(models.AbstractModel):
    _name = 'report.dynamic_accounts_report.profit_and_loss'

    @api.model
    def _get_report_values(self, docids, data=None):
        if self.env.context.get('pl_report'):
            if data.get('report_data'):
                data.update({
                    'doc_ids': docids,
                    'Filters': data.get('report_data')['filters'],
                    'account_data': data.get('report_data')['report_lines'],
                    'report_lines': data.get('report_data')['pl_lines'],
                    'report_name': data.get('report_name'),
                    'title': data.get('report_data')['name'],
                    'company': self.env.company,
                })
        return data