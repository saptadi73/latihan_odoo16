from odoo import models, fields

class EducationLevel(models.Model):
    _name = 'education.level'
    _description = 'Education'

    name = fields.Char(string="Education", required=True)
    description = fields.Text(string="Description")
