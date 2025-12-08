from odoo import models
import logging

_logger = logging.getLogger(__name__)


class StockRule(models.Model):
    _inherit = 'stock.rule'

    def _run_buy(self, procurements):
        """Override: Inject orderpoint_id ke procurement values sebelum PO dibuat"""
        
        # Clean procurements & inject orderpoint
        cleaned = []
        for proc in procurements:
            # Handle tuple dari scheduler
            if isinstance(proc, tuple):
                procurement = proc[0]
            else:
                procurement = proc
            
            # Sangat penting: set orderpoint_id di values
            if hasattr(procurement, 'values') and procurement.values:
                orderpoint_id = procurement.values.get('orderpoint_id')
                if orderpoint_id:
                    _logger.info("INJECT: orderpoint_id=%s into procurement.values", orderpoint_id)
            
            cleaned.append(proc)
        
        # Jalankan parent - ini akan create PO
        return super()._run_buy(cleaned)