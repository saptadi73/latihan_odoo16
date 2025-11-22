import base64
from odoo import http
from odoo.http import request
      

class ProductionHarvestingImageController(http.Controller):

    @http.route(['/production_harvesting/image/<int:harvesting_id>'], type='http', auth="public", website=True)
    def production_harvesting_image(self, harvesting_id, **kwargs):
        # Use the automatic `id` field to fetch the record
        record = request.env['ilo.production.harvesting'].sudo().browse(harvesting_id)

        # Check if the record exists and has an image
        if record.exists() and record.production_harvesting_image:
            image_base64= record.production_harvesting_image
            image_data = base64.b64decode(image_base64)
            headers = [('Content-Type', 'image/png'), ('Content-Length', len(image_data))]
            return request.make_response(image_data, headers=headers)
        else:
            headers = [('Content-Type', 'image/png'), ('Content-Length', '0')]
            return request.make_response(b'', headers=headers)
        

class ProductionPlantingImageController(http.Controller):

    @http.route(['/production_planting/image/<int:record_id>'], type='http', auth="public", website=True)
    def production_planting_image(self, record_id, **kwargs):
        # Fetch the record with sudo to bypass permissions
        record = request.env['ilo.production_planting'].sudo().browse(record_id)

        # Check if the record exists and has an image
        if record.exists() and record.production_planting_image:
            # Decode the base64 image data
            image_base64=record.production_planting_image
            image_data = base64.b64decode(image_base64)
            headers = [('Content-Type', 'image/png'), ('Content-Length', len(image_data))]
            return request.make_response(image_data, headers=headers)
        else:
            # Return an empty response if no image exists
            headers = [('Content-Type', 'image/png'), ('Content-Length', '0')]
            return request.make_response(b'', headers=headers)