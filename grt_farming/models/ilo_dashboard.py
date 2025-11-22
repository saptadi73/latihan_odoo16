from odoo import models, fields, api
import json

class ILODashboard(models.Model):
    _name = 'ilo.dashboard'
    _description = 'Custom Dashboard for ILO Programs'

    name = fields.Char(string='Name', required=True)
    date_order = fields.Date(string='Order Date', required=True)
    # Assets Data
    assets_data = fields.One2many('ilo.assets', 'dashboard_id', string='Assets Data')
    total_area_usage = fields.Float(string='Total Area Usage', compute='_compute_total_area_usage', store=True)

    # Process Percentages
    process_percentage = fields.Float(string='Process Percentage', compute='_compute_status_percentages', store=True)
    completed_percentage = fields.Float(string='Completed Percentage', compute='_compute_status_percentages', store=True)

    # MRP Production Data
    # ilo_production_data = fields.One2many('ilo.production', 'dashboard_id', string='ILO Productions')
    # ilo_process_percentage = fields.Float(string='Process Percentage', compute='_compute_ilo_status_percentages', store=True)
    # ilo_completed_percentage = fields.Float(string='Completed Percentage', compute='_compute_ilo_status_percentages', store=True)
    # regional_production_data = fields.Text(string='Regional Production Data', compute='_compute_regional_production_data', store=True)
    
    # Computing Total Area Usage
    @api.depends('assets_data.area_ha')
    def _compute_total_area_usage(self):
        for record in self:
            record.total_area_usage = sum(asset.area_ha for asset in record.assets_data)

    # Computing Status Percentages
    @api.depends('assets_data.planting_status')
    def _compute_status_percentages(self):
        for record in self:
            total_assets = len(record.assets_data)
            process_count = len(record.assets_data.filtered(lambda asset: asset.planting_status == 'proses'))
            completed_count = len(record.assets_data.filtered(lambda asset: asset.planting_status == 'selesai'))

            record.process_percentage = (process_count / total_assets) * 100 if total_assets else 0
            record.completed_percentage = (completed_count / total_assets) * 100 if total_assets else 0

    # # # Computing ILO Status Percentages
    # # @api.depends('ilo_production_data.state')
    # # def _compute_ilo_status_percentages(self):
    # #     for record in self:
    # #         total_productions = len(record.ilo_production_data)
    # #         process_count = len(record.ilo_production_data.filtered(lambda prod: prod.state == 'in_progress'))
    # #         completed_count = len(record.ilo_production_data.filtered(lambda prod: prod.state == 'done'))

    # #         record.ilo_process_percentage = (process_count / total_productions) * 100 if total_productions else 0
    # #         record.ilo_completed_percentage = (completed_count / total_productions) * 100 if total_productions else 0

    # # Computing Regional Production Data
    # @api.depends('ilo_production_data.employee_id', 'ilo_production_data.state')
    # def _compute_regional_production_data(self):
    #     for record in self:
    #         regional_data = {}
    #         for production in record.ilo_production_data:
    #             region = production.employee_id.name
    #             if region not in regional_data:
    #                 regional_data[region] = {'completed': 0, 'in_progress': 0}
    #             if production.state == 'done':
    #                 regional_data[region]['completed'] += 1
    #             else:
    #                 regional_data[region]['in_progress'] += 1
    #         record.regional_production_data = json.dumps(regional_data)