import base64
from odoo import http
from odoo.http import request

class ProductImageController(http.Controller):

    @http.route(['/product/image/<int:product_id>'], type='http', auth="public", website=True)
    def product_image(self, product_id, **kwargs):
        # Mendapatkan record product berdasarkan ID
        product = request.env['product.product'].sudo().browse(product_id)

        # Cek apakah product dan gambar ada
        if product.exists() and product.image_1920:
            # Mengembalikan gambar sebagai respons
            image_base64 = product.image_1920
            image_data = base64.b64decode(image_base64)
            headers = [('Content-Type', 'image/png'), ('Content-Length', len(image_data))]
            return request.make_response(image_data, headers=headers)
        else:
            # kondisi image kosong
            # akan di response dengan data kosong
            headers = [('Content-Type', 'image/png'), ('Content-Length', '0')]
            return request.make_response(b'', headers=headers)