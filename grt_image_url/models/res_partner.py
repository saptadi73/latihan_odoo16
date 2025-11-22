from odoo import models, fields, api
# import requests

class ResPartner(models.Model):
    _inherit = 'res.partner'

    image_1920_url = fields.Char(string='Image URL', compute='_compute_image_1920')

    @api.depends('image_1920')
    def _compute_image_1920(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        for record in self:
            # record.image_1920_url = f"{base_url}/web/image?model=res.partner&id={record.id}&field=image_1920"
            if record.image_1920:
                record.image_1920_url = f"{base_url}/partner/image/{record.id}"
            else:
                record.image_1920_url = False
