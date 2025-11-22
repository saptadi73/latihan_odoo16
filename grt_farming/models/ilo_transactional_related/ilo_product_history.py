import logging
from odoo import models, fields, api

# Set up a logger for this module
_logger = logging.getLogger(__name__)

class IloProductHistory(models.Model):
    _name = 'ilo.product.history'
    _description = 'Product History'

    name = fields.Char(string="Name", store=True)
    employee_id = fields.Many2one('res.partner', string="Responsible Employee", store=True)
    harvesting_id = fields.Many2one('ilo.production.harvesting', string="Production Harvesting", required=True)
    ownership_code_id = fields.Many2one('ownership.code', string="Ownership Code")
    ownership_line_id = fields.Many2one('ownership.line', string="Ownership Line", help="Related ownership line for this product history.")

    # New Fields
    production_code = fields.Char(string="Production Code", compute='_compute_production_code', store=True)
    goes_to = fields.Char(string="Goes To", compute='_compute_goes_to', store=True)
    then_then = fields.Many2one('ownership.code', string="Then Then", compute='_compute_then_then', store=True)
    after_that = fields.Many2one('ownership.code', string="After That", compute='_compute_after_that', store=True)

    @api.depends('harvesting_id')
    def _compute_production_code(self):
        """Compute the production code and gather info from harvesting record."""
        for record in self:
            _logger.debug(f'Computing production code for record {record.id} with harvesting_id: {record.harvesting_id}')

            # Check if harvesting_id is set
            if record.harvesting_id:
                # Retrieve the employee_id and name from harvesting_id
                if record.harvesting_id.employee_id:
                    record.employee_id = record.harvesting_id.employee_id
                    record.name = record.harvesting_id.name or record.employee_id.display_name
                    _logger.debug(f'Set employee_id to {record.employee_id} and name to {record.name} for record {record.id}')

                # Search for ownership codes related to the production_identifier
                ownership_codes = self.env['ownership.code'].search([
                    ('production_code', '=', record.harvesting_id.production_identifier)
                ])
                record.production_code = ownership_codes[0].production_code if ownership_codes else False
                _logger.debug(f'Updated production_code for record {record.id}: {record.production_code}')
            else:
                _logger.warning(f'No harvesting_id found for record {record.id}')

    @api.depends('ownership_code_id', 'production_code')
    def _compute_goes_to(self):
        """Compute the Goes To field based on matching production_code in ownership.line."""
        for record in self:
            _logger.debug(f'Computing Goes To for record {record.id} with production_code: {record.production_code}')
            if record.production_code:
                ownership_lines = self.env['ownership.line'].search([
                    ('production_code', '=', record.production_code)
                ], limit=1)
                
                record.goes_to = ownership_lines.specific_code if ownership_lines else False
                _logger.debug(f'Updated goes_to for record {record.id}: {record.goes_to}')
            else:
                _logger.warning(f'No production_code found for record {record.id}')

    # @api.depends('ownership_code_id', 'production_code', 'goes_to')
    # def _compute_then_then(self):
    #     """Compute the Then Then field based on matching goes_to with reference_code in ownership.code."""
    #     for record in self:
    #         _logger.debug(f'Computing Then Then for record {record.id} with goes_to: {record.goes_to}')
    #         if record.goes_to:
    #             ownership_code = self.env['ownership.code'].search([
    #                 ('reference_code', '=', record.goes_to)
    #             ], limit=1)
                
    #             record.then_then = ownership_code.id if ownership_code else False
    #             _logger.debug(f'Updated then_then for record {record.id}: {record.then_then}')
    #         else:
    #             _logger.warning(f'No goes_to found for record {record.id}')

    # @api.depends('ownership_code_id', 'production_code', 'then_then')
    # def _compute_after_that(self):
    #     """Compute the After That field based on matching the name of ownership.code with the reference_code of ownership.code."""
    #     for record in self:
    #         _logger.debug(f'Computing After That for record {record.id} with then_then: {record.then_then}')
    #         if record.then_then:
    #             # Search for ownership.code where the name matches the reference_code
    #             ownership_code = self.env['ownership.code'].search([
    #                 ('reference_code', '=', record.then_then)  # Match with the name of the ownership_code
    #             ], limit=1)  # Limit to one record for performance
                
    #             record.after_that = ownership_code.id if ownership_code else False
    #             _logger.debug(f'Updated after_that for record {record.id}: {record.after_that}')
    #         else:
    #             # Resetting if then_then is not set
    #             record.after_that = False
    #             _logger.warning(f'No then_then found for record {record.id}')
