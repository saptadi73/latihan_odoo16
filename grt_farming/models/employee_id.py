from odoo import models, fields

class EmployeeILO(models.Model):
    _name = 'employee.ilo'
    _inherit = 'res.partner'