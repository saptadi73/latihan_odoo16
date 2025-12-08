from odoo import models, api
import logging

_logger = logging.getLogger(__name__)

class PosConfig(models.Model):
    _inherit = 'pos.config'

    def get_pos_ui_data(self):
        # ambil payload asli
        data = super().get_pos_ui_data()

        # pastikan products ada
        products = data.get('product_product', [])

        if products:
            ids = [p['id'] for p in products]
            product_records = self.env['product.product'].browse(ids)

            # map qty_available
            stock_map = {rec.id: rec.qty_available for rec in product_records}

            for p in products:
                p['qty_available'] = stock_map.get(p['id'], 0)

        _logger.warning("POS STOCK PATCH: injected qty_available for %s products", len(products))

        return data
