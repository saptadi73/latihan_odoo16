from odoo import models, api
import logging

_logger = logging.getLogger(__name__)


class StockRule(models.Model):
    _inherit = 'stock.rule'

    def _run_buy(self, procurements):
        """
        Override native _run_buy to tag PO dengan orderpoint_id
        untuk memudahkan cron job detect PO dari reordering
        """
        result = super()._run_buy(procurements)
        
        for procurement in procurements:
            values = procurement.values
            orderpoint_id = values.get('orderpoint_id')
            
            if not orderpoint_id:
                continue
            
            # Find created PO
            group = values.get('group_id')
            if group:
                po = self.env['purchase.order'].search([
                    ('group_id', '=', group.id),
                    ('state', '=', 'draft'),
                ], limit=1, order='create_date desc')
                
                if po:
                    orderpoint = self.env['stock.warehouse.orderpoint'].browse(orderpoint_id)
                    po.sudo().write({
                        'orderpoint_id': orderpoint.id,
                        'dc_company_id': orderpoint.dc_company_id.id if orderpoint.dc_company_id else False,
                    })
                    _logger.info("PO %s tagged with orderpoint %s", po.name, orderpoint.name)
        
        return result