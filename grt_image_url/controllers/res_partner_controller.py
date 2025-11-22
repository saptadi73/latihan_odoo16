import base64
from odoo import http
from odoo.http import request

class PartnerImageController(http.Controller):

    @http.route(['/partner/image/<int:partner_id>'], type='http', auth="public", website=True)
    def partner_image(self, partner_id, **kwargs):
        # Mendapatkan record partner berdasarkan ID
        partner = request.env['res.partner'].sudo().browse(partner_id)

        # Cek apakah partner dan gambar ada
        if partner.exists() and partner.image_1920:
            # Mengembalikan gambar sebagai respons
            image_base64 = partner.image_1920
            image_data = base64.b64decode(image_base64)
            headers = [('Content-Type', 'image/png'), ('Content-Length', len(image_data))]
            return request.make_response(image_data, headers=headers)
        else:
            # kondisi image kosong
            # akan di response dengan data kosong
            headers = [('Content-Type', 'image/png'), ('Content-Length', '0')]
            return request.make_response(b'', headers=headers)

    @http.route(['/partner/contract/<int:partner_id>/<string:filename>'], type='http', auth="public", website=True)
    def partner_contract(self, partner_id, filename, **kwargs):
        """Serve employment contract file as a response."""
        partner = request.env['res.partner'].sudo().browse(partner_id)
        if partner.exists() and partner.employment_contract:
            contract_base64 = partner.employment_contract
            contract_data = base64.b64decode(contract_base64)
            headers = [('Content-Type', 'application/pdf'), ('Content-Length', str(len(contract_data)))]
            return request.make_response(contract_data, headers=headers)
        else:
            headers = [('Content-Type', 'application/pdf'), ('Content-Length', '0')]
            return request.make_response(b'', headers=headers)
