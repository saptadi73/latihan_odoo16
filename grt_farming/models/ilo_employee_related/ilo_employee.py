from odoo import models, fields, api, exceptions

class ILOEmployee(models.Model):
    _name = 'ilo.employee'
    _description = 'ILO Employee'

#     # Basic Fields
#     name = fields.Char(string='Name', required=True)
#     is_company = fields.Boolean(string='Is a Company', default=False)

#     # ILO Associate Selection Field
#     ilo_associate = fields.Selection([
#         ('farmers', 'Petani'),
#         ('agent', 'Agent'),
#         ('koperasi', 'Koperasi'),
#         ('ugreen', 'UGreen'),
#         ('green', 'Green')
#     ], string='ILO Associate')

#     # ILO Associate Code (auto-generated field)
#     ilo_associate_code = fields.Char(string='ILO Associate Code', readonly=True)

#     # Additional fields
#     family_members = fields.Integer(string='Family Members')
#     organization_status = fields.Selection([
#         ('member', 'Member'),
#         ('not_member', 'Not Member'),
#         ('employee', 'Employee of the Organization')
#     ], string='Organization Status')

#     organization_name = fields.Char(string='Organization Name', compute='_compute_organization_name', store=True)
#     employment_contract = fields.Binary(string='Employment Contract')
#     contract_file_name = fields.Char(string='Contract File Name', default=lambda self: self._default_contract_file_name())
#     parent_id = fields.Many2one('res.partner', string='Parent Organization')

#     # Additional Fields from res.partner
#     street = fields.Char(string='Address')
#     kelurahan = fields.Char(string='Kelurahan')
#     kecamatan = fields.Char(string='Kecamatan')
#     state_id = fields.Many2one('res.country.state', string='State')
#     country_id = fields.Many2one('res.country', string='Country')
#     tax_id = fields.Char(string='Tax ID')
#     education_level = fields.Char(string='Education Level')
#     phone = fields.Char(string='Phone Number')
#     mobile = fields.Char(string='Mobile Number')
#     email = fields.Char(string='Email')

#     # Compute organization_name from parent_id
#     @api.depends('parent_id')
#     def _compute_organization_name(self):
#         """Automatically fill organization_name from the parent company's name (if parent_id is set)."""
#         for employee in self:
#             employee.organization_name = employee.parent_id.name if employee.parent_id else False

#     # Compute the default contract file name
#     def _default_contract_file_name(self):
#         """Generate default contract file name using employee's name and associate code."""
#         if len(self) == 1:  # Ensure only one record is processed
#             return f"{self.name or ''}_{self.ilo_associate_code or ''}.pdf"
#         else:
#             return "default_contract_name.pdf"  # Fallback value if no name or associate code

#     # Validation for organization status
#     @api.constrains('organization_status', 'organization_name')
#     def _check_organization_name(self):
#         """Ensure either organization_name or parent_id is provided if status is 'member' or 'employee'."""
#         for employee in self:
#             if employee.organization_status in ['member', 'employee'] and not (employee.organization_name or employee.parent_id):
#                 raise exceptions.ValidationError(
#                     "You must provide an Organization Name or Parent Company if the employee is a member or employee."
#                 )

#     @api.model
#     def create(self, vals):
#         """Override the create method to handle automatic creation logic."""
#         return ILOEmployeeCreation(self).create_employee(vals)

#     def write(self, vals):
#         """Override the write method to handle updates."""
#         return ILOEmployeeUpdate(self).update_employee(vals)

# class ILOEmployeeCreation:
#     def __init__(self, employee_model):
#         self.employee_model = employee_model

#     def create_employee(self, vals):
#         """Handle employee creation logic."""
#         # Handle organization_name and parent_id synchronization
#         self._synchronize_organization(vals)

#         # Ensure ilo_associate_code is generated
#         if 'ilo_associate' in vals and not vals.get('ilo_associate_code'):
#             vals['ilo_associate_code'] = self._generate_ilo_associate_code(vals['ilo_associate'])

#         # Generate default contract file name if not provided
#         if not vals.get('contract_file_name'):
#             vals['contract_file_name'] = f"{vals.get('name', '')}_{vals.get('ilo_associate_code', '')}.pdf"

#         # Create the new ILOEmployee record
#         new_employee = self.employee_model.create(vals)

#         # Validate organization_name for 'member' or 'employee' status
#         new_employee._check_organization_name()

#         # Ensure stock location and warehouse creation
#         self._ensure_location_warehouse(new_employee)

#         return new_employee

#     def _synchronize_organization(self, vals):
#         """Synchronize organization_name and parent_id."""
#         if not vals.get('organization_name') and vals.get('parent_id'):
#             vals['organization_name'] = self.employee_model.env['res.partner'].browse(vals['parent_id']).name

#         if not vals.get('parent_id') and vals.get('organization_name'):
#             parent_org = self.employee_model.env['res.partner'].create({'name': vals['organization_name'], 'is_company': True})
#             vals['parent_id'] = parent_org.id

#     def _ensure_location_warehouse(self, new_employee):
#         """Ensure stock location and warehouse are generated after the employee is created."""
#         # Create a stock location for the employee
#         location_name = f"{new_employee.name}'s Stock"
#         stock_location = self._create_stock_location(location_name, new_employee)

#         # Only create a warehouse if the employee is a company
#         if new_employee.is_company:  
#             warehouse_name = f"{new_employee.name}'s Warehouse"
#             warehouse = self._create_warehouse(warehouse_name, new_employee)

#             # Link the stock location to the newly created warehouse
#             if stock_location and warehouse:
#                 stock_location.warehouse_id = warehouse.id  # Setting the warehouse relationship

#     def _create_stock_location(self, name, employee):
#         """Create or find an existing stock location for the employee."""
#         location = self.employee_model.env['ilo.stock_location'].search([('name', '=', name)], limit=1)
#         if not location:
#             return self.employee_model.env['ilo.stock_location'].create({
#                 'name': name,
#                 'location_code': name[:3].upper(),
#                 'address': employee.street or 'Unknown Address',
#                 'city': employee.city or 'Unknown City',
#                 'region': employee.state_id.name if employee.state_id else 'Unknown Region',
#                 'employee_id': employee.id,
#                 'warehouse_id': False,  # Placeholder until linked with the warehouse
#             })
#         return location

#     def _create_warehouse(self, name, employee):
#         """Create or find an existing warehouse for the employee's company."""
#         warehouse = self.employee_model.env['ilo.warehouse'].search([('warehouse_name', '=', name)], limit=1)
#         if not warehouse:
#             return self.employee_model.env['ilo.warehouse'].create({
#                 'warehouse_name': name,
#                 'warehouse_code': name[:3].upper(),
#                 'street': employee.street,
#                 'city': employee.city,
#                 'state_id': employee.state_id.id,
#                 'country_id': employee.country_id.id,
#                 'actor_id': employee.id
#             })
#         return warehouse

#     def _generate_ilo_associate_code(self, associate):
#         """Generate a unique code for the ILO associate based on the type."""
#         code_map = {
#             'farmers': ('FA', 'ilo.employee.farmers.sequence'),
#             'agent': ('AG', 'ilo.employee.agent.sequence'),
#             'koperasi': ('KO', 'ilo.employee.koperasi.sequence'),
#             'ugreen': ('UG', 'ilo.employee.ugreen.sequence'),
#             'green': ('GR', 'ilo.employee.green.sequence')
#         }
#         prefix, sequence_code = code_map.get(associate, ('', ''))
#         sequence = self.employee_model.env['ir.sequence'].next_by_code(sequence_code) or '000'
#         return f"{prefix}{sequence}"


# class ILOEmployeeUpdate:
#     def __init__(self, employee_model):
#         self.employee_model = employee_model

#     def update_employee(self, vals):
#         """Handle employee update logic."""
#         for employee in self.employee_model:
#             self._synchronize_organization(vals, employee)

#             # Ensure ilo_associate_code is generated if missing
#             if not vals.get('ilo_associate_code') and employee.ilo_associate:
#                 vals['ilo_associate_code'] = self._generate_ilo_associate_code(employee.ilo_associate)

#             # Ensure contract_file_name is generated if missing
#             if not vals.get('contract_file_name'):
#                 vals['contract_file_name'] = f"{employee.name}_{vals.get('ilo_associate_code', employee.ilo_associate_code)}.pdf"

#             # Validate organization_name for 'member' or 'employee' status
#             if 'organization_status' in vals or 'organization_name' in vals or 'parent_id' in vals:
#                 employee._check_organization_name()

#         return super(ILOEmployee, self.employee_model).write(vals)

#     def _synchronize_organization(self, vals, employee):
#         """Synchronize organization_name and parent_id."""
#         if 'organization_name' in vals and not vals.get('parent_id'):
#             parent_org = self.employee_model.env['res.partner'].create({'name': vals['organization_name'], 'is_company': True})
#             vals['parent_id'] = parent_org.id

#         if vals.get('parent_id'):
#             vals['organization_name'] = self.employee_model.env['res.partner'].browse(vals['parent_id']).name
