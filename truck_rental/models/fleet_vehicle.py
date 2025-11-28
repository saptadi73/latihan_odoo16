from odoo import models, fields

class FleetVehicle(models.Model):
    _inherit = 'fleet.vehicle'

    daily_rate = fields.Float(string='Daily Rental Rate', help='Tarif sewa per hari')