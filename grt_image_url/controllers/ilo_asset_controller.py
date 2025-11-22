import base64
from odoo import http
from odoo.http import request

class AssetImageController(http.Controller):

    @http.route(['/ilo_asset/image/<int:asset_id>'], type='http', auth="public", website=True)
    def asset_image(self, asset_id, **kwargs):
        """Serve the asset image for the given asset_id."""
        # Use the `sudo` method to bypass record rules for public access
        record = request.env['ilo.assets'].sudo().browse(asset_id)

        # Check if the record exists and has an image
        if record.exists() and record.asset_image:
            # Decode the Base64 image
            image_base64 = record.asset_image
            image_data = base64.b64decode(image_base64)

            # Prepare the HTTP response
            headers = [('Content-Type', 'image/png'), ('Content-Length', len(image_data))]
            return request.make_response(image_data, headers=headers)
        else:
            # Return an empty response for missing images
            headers = [('Content-Type', 'image/png'), ('Content-Length', '0')]
            return request.make_response(b'', headers=headers)

    @http.route(['/ilo_asset/geojson/<int:asset_id>/<string:filename>'], type='http', auth="public", website=True)
    def asset_shapefile(self, asset_id, filename, **kwargs):
        """Serve the GeoJSON shapefile for the given asset_id and filename."""
        # Use the `sudo` method to bypass record rules for public access
        record = request.env['ilo.assets'].sudo().browse(asset_id)

        # Check if the record exists and if the filename matches the record's `shp_filename`
        if record.exists() and record.shp_file and record.shp_filename == filename.replace("_", " "):
            # Decode the Base64 shapefile
            shp_file_base64 = record.shp_file
            shp_file_data = base64.b64decode(shp_file_base64)

            # Prepare the HTTP response
            headers = [
                ('Content-Type', 'application/json'),
                ('Content-Disposition', f'attachment; filename="{record.shp_filename}"'),
                ('Content-Length', len(shp_file_data))
            ]
            return request.make_response(shp_file_data, headers=headers)
        else:
            # Return an empty response for mismatched filenames or missing files
            headers = [('Content-Type', 'application/json'), ('Content-Length', '0')]
            return request.make_response(b'', headers=headers)