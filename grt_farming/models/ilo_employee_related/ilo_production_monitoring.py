from odoo import api, fields, models

class IloEmployeeProductionMonitoring(models.Model):
    _name = 'ilo.production_monitoring'
    _description = 'Employee Production Monitoring'

    employee_id = fields.Many2one('res.partner', string="Employee", required=True)
    total_planted_quantity = fields.Float(string="Total Planted Quantity", compute='_compute_total_planted_quantity', store=True)
    total_harvested_quantity = fields.Float(string="Total Harvested Quantity", compute='_compute_total_harvested_quantity', store=True)

    planting_data = fields.One2many('ilo.production_planting', 'monitoring_id', string="Planting Data")
    harvesting_data = fields.One2many('ilo.production.harvesting', 'monitoring_id', string="Harvesting Data")

    @api.depends('planting_data.quantity')
    def _compute_total_planted_quantity(self):
        for record in self:
            # Summing up quantities from One2many relation planting_data
            record.total_planted_quantity = sum(record.planting_data.mapped('quantity'))

    @api.depends('harvesting_data.final_quantity')
    def _compute_total_harvested_quantity(self):
        for record in self:
            # Summing up quantities from One2many relation harvesting_data
            record.total_harvested_quantity = sum(record.harvesting_data.mapped('final_quantity'))

