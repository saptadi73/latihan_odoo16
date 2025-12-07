from odoo import models, fields


class ResCompany(models.Model):
    _inherit = 'res.company'

    is_dc_company = fields.Boolean(
        string='Is DC Company',
        help='Mark this company as Distribution Center'
    )
    
    is_retailer_company = fields.Boolean(
        string='Is Retailer Company',
        help='Mark this company as Retailer'
    )
    
    dc_company_id = fields.Many2one(
        'res.company',
        string='DC Company',
        help='Related DC company for this retailer',
        domain="[('is_dc_company', '=', True)]"
    )
    
    dc_warehouse_id = fields.Many2one(
        'stock.warehouse',
        string='DC Warehouse',
        help='Default DC warehouse for auto SO creation'
    )