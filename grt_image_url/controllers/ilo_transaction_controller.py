import base64
from odoo import http
from odoo.http import request
      

class OwnershipCodeImageController(http.Controller):

    @http.route(['/ownership_code/image/<int:ownership_code_id>'], type='http', auth="public", website=True)
    def ownership_code_image(self, ownership_code_id, **kwargs):
        """
        Serve the binary image stored in `product_transaction_image_ownership_code` 
        for the given OwnershipCode record.
        """
        # Fetch the record based on the ID
        record = request.env['ownership.code'].sudo().browse(ownership_code_id)

        # Check if the record exists and has an image
        if record.exists() and record.product_transaction_image_ownership_code:
            # Decode the base64-encoded image
            image_base64 = record.product_transaction_image_ownership_code
            image_data = base64.b64decode(image_base64)

            # Prepare HTTP headers
            headers = [('Content-Type', 'image/png'), ('Content-Length', str(len(image_data)))]
            return request.make_response(image_data, headers=headers)
        else:
            # Return an empty response if the image does not exist
            headers = [('Content-Type', 'image/png'), ('Content-Length', '0')]
            return request.make_response(b'', headers=headers)

class OwnershipLineImageController(http.Controller):

    @http.route(['/ownership_line/image/<int:ownership_line_id>'], type='http', auth="public", website=True)
    def ownership_line_image(self, ownership_line_id, **kwargs):
        """
        Serve the binary image stored in `product_transaction_image_ownership_line` 
        for the given OwnershipLine record.
        """
        # Fetch the record using the provided ID
        record = request.env['ownership.line'].sudo().browse(ownership_line_id)

        # Check if the record exists and has an image
        if record.exists() and record.product_transaction_image_ownership_line:
            # Decode the base64-encoded image
            image_base64 = record.product_transaction_image_ownership_line
            image_data = base64.b64decode(image_base64)

            # Set the response headers
            headers = [('Content-Type', 'image/png'), ('Content-Length', str(len(image_data)))]
            return request.make_response(image_data, headers=headers)
        else:
            # If the image does not exist, return an empty response
            headers = [('Content-Type', 'image/png'), ('Content-Length', '0')]
            return request.make_response(b'', headers=headers)   