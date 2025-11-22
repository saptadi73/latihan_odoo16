from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)


class ILOCustomWarehouse(models.Model):
    _name = 'ilo.warehouse'
    _description = 'ILO Custom Warehouse'

    name = fields.Char(string='Name', compute='_compute_name', store=True)
    warehouse_name = fields.Char(string='Warehouse Name', required=True)
    warehouse_code = fields.Char(string='Warehouse Code')
    company_id = fields.Many2one('res.company', string='Company')

    # Agent Information
    actor_id = fields.Many2one('res.partner', string='Agent', required=True)
    actor_name = fields.Char(related='actor_id.name', string='Agent Name', store=True)
    actor_code = fields.Char(related='actor_id.ilo_associate_code', string='Agent Code', store=True)

    # Address Information
    street = fields.Char(string='Street')
    city = fields.Char(string='City/Regency')
    state_id = fields.Many2one('res.country.state', string='State/Province')
    country_id = fields.Many2one('res.country', string='Country')

    # New Fields for Kabupaten/Kecamatan/Kelurahan
    kabupaten_id = fields.Many2one('res.kabupaten', string='Kabupaten/Kota')
    kecamatan = fields.Char(string='Kecamatan')
    kelurahan = fields.Char(string='Kelurahan')

    # Stock locations related to this warehouse
    location_ids = fields.One2many('ilo.stock_location', 'warehouse_id', string='Stock Locations', ondelete='cascade')
    
    # Stock Moves related to this warehouse
    stock_move_ids = fields.One2many('ilo.stock_move', 'warehouse_id', string='Stock Moves', ondelete='cascade')



    @api.depends('warehouse_name')
    def _compute_name(self):
        for record in self:
            record.name = record.warehouse_name



    @api.model
    def create(self, vals):
        warehouse = super(ILOCustomWarehouse, self).create(vals)
        return warehouse



