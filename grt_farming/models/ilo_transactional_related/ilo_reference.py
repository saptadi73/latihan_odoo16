from odoo import models, fields, api, exceptions, _
import logging

_logger = logging.getLogger(__name__)


class IloReference(models.Model):
    _name = 'ilo.reference'
    _description = 'Reference Link Model'

    name = fields.Char(string='Name', compute='_compute_name', store=True)

    ownership_code_id = fields.Many2one('ownership.code', string='Ownership Code')
    reference_link_ids = fields.One2many('ilo.reference.link', 'ilo_reference_id', string='References')
    child_reference_ids = fields.One2many('ilo.reference.link', 'parent_reference_id', string='Child References')  # New field for child references

    def action_populate_summary(self):
        summary_model = self.env['ilo.reference.summary']
        summary_model.populate_reference_summary()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Reference Summary',
            'res_model': 'ilo.reference.summary',
            'view_mode': 'tree,form',
            'target': 'current',
        }

    @api.depends('ownership_code_id')
    def _compute_name(self):
        for record in self:
            if record.ownership_code_id:
                record.name = f'Reference for {record.ownership_code_id.reference_code}'
                _logger.debug("Computed name for record %s: %s", record.id, record.name)
            else:
                record.name = _('Unnamed Reference')
                _logger.warning("No ownership code found for record %s, setting name to 'Unnamed Reference'", record.id)

    @api.model
    def create_reference_from_ownership(self, ownership_code, ownership_line=None):
        _logger.info("Creating/updating reference for ownership code: %s", ownership_code.reference_code)

        # Handle multiple reference codes
        reference_codes = ownership_code.reference_code.split(', ')  # Assuming reference_code is a comma-separated string

        ref = None  # Initialize ref to None

        for reference_one in reference_codes:
            if ownership_line and ownership_line.specific_code == reference_one:
                reference_one = ownership_line.specific_code

            reference_two = ownership_code.name

            ownership_line_record = self.env['ownership.line'].search(
                [('specific_code', '=', reference_one)], limit=1)

            if not ownership_line_record:
                _logger.warning("No ownership line found for specific_code: %s", reference_one)
                continue  # Skip this iteration if no ownership line is found

            # Check for existing reference using ownership_code_id
            existing_reference = self.search([
                ('ownership_code_id', '=', ownership_code.id),
                ('reference_link_ids.reference', '=', reference_one)  # Ensure unique reference
            ], limit=1)

            if existing_reference:
                _logger.info("Found existing reference, updating the chain for reference: %s", reference_two)
                existing_reference.update_reference_chain(ownership_code.name, ownership_code.id)
                ref = existing_reference  # Mark ref as existing reference
            else:
                _logger.info("No existing reference found, creating a new reference chain for ownership code: %s", ownership_code.reference_code)
                ref = self.create({
                    'ownership_code_id': ownership_code.id,
                    'reference_link_ids': [
                        (0, 0, {'reference': reference_one, 'ownership_line_id': ownership_line_record.id}),
                        (0, 0, {'reference': reference_two, 'ownership_code_id': ownership_code.id}),
                    ]
                })

                for link in ref.reference_link_ids:
                    link.parent_reference_id = ref.id  # Set the parent reference ID

        if ref:
            # Call populate_reference_summary only if a reference was created or updated
            self.env['ilo.reference.summary'].populate_reference_summary()
        else:
            _logger.warning("No references were created for ownership code: %s", ownership_code.reference_code)

        return ref


    def update_reference_chain(self, new_reference, ownership_code_id):
        _logger.info("Updating reference chain with new reference: %s for ownership code ID: %s", new_reference, ownership_code_id)

        existing_references = self.reference_link_ids.mapped('reference')
        if new_reference not in existing_references:
            self.write({
                'reference_link_ids': [(0, 0, {'reference': new_reference, 'ownership_code_id': ownership_code_id})]
            })
            _logger.info("Added new reference to the chain: %s", new_reference)
        else:
            _logger.debug("Reference %s already exists in the chain", new_reference)


    def update_reference_on_new_ownership(self, ownership_code):
        _logger.info("Updating reference chain for new ownership code: %s", ownership_code.reference_code)

        # Split the reference code into multiple codes if they are separated by commas
        reference_codes = ownership_code.reference_code.split(', ')  # Adjust the delimiter as needed

        for reference_code in reference_codes:
            # Search for existing references matching the current reference code
            ref = self.search([('reference_link_ids.reference', '=', reference_code)])

            if ref:
                # Update the reference chain with the new reference
                ref.update_reference_chain(ownership_code.name, ownership_code.id)
                _logger.info("Updated reference chain for ownership code: %s", reference_code)

                # Check if this reference code exists in any of the summary's reference_2, reference_3, or reference_4 fields
                summaries = self.env['ilo.reference.summary'].search([
                    '|', '|',
                    ('reference_2', '=', reference_code),
                    ('reference_3', '=', reference_code),
                    ('reference_4', '=', reference_code)
                ])

                # If matching summaries are found, update the next available slot in each
                for summary in summaries:
                    _logger.info("Existing summary found for reference code: %s; updating next available slot.", reference_code)

                    summary_data = {}

                    # Update the next available reference field and its corresponding data
                    if not summary.reference_3:
                        summary_data.update({
                            'reference_3': ownership_code.name,
                            'date_order_3': ownership_code.date_order,
                            'actor_3': ownership_code.destination_actor.id,
                            'kabupaten_3': ownership_code.kabupaten_id.id
                        })
                    elif not summary.reference_4:
                        summary_data.update({
                            'reference_4': ownership_code.name,
                            'date_order_4': ownership_code.date_order,
                            'actor_4': ownership_code.destination_actor.id,
                            'kabupaten_4': ownership_code.kabupaten_id.id
                        })
                    elif not summary.reference_5:
                        summary_data.update({
                            'reference_5': ownership_code.name,
                            'date_order_5': ownership_code.date_order,
                            'actor_5': ownership_code.destination_actor.id,
                            'kabupaten_5': ownership_code.kabupaten_id.id
                        })

                    # Update the latest_quantity field with the latest total_requested_quantity from ownership_code
                    summary_data.update({
                        'latest_quantity': ownership_code.total_requested_quantity
                    })

                    # Update the 'date_modified' field to the current timestamp
                    summary_data.update({
                        'date_modified': fields.Datetime.now()  # Set to current date and time
                    })

                    # Write updates to the summary only if there are fields to change
                    if summary_data:
                        summary.write(summary_data)
                        _logger.info("Updated summary record with new reference and latest_quantity: %s", ownership_code.name)
                    else:
                        _logger.info("All reference fields are already populated; no update necessary.")
            else:
                _logger.info("No matching reference chain found for ownership_code: %s", reference_code)
           
class IloReferenceLink(models.Model):
    _name = 'ilo.reference.link'
    _description = 'Dynamic Reference Link'

    name = fields.Char(string='Name', compute='_compute_name', store=True)
    ilo_reference_id = fields.Many2one('ilo.reference', string='Reference Chain', ondelete='cascade', required=True)
    reference = fields.Char(string='Reference', required=True)
    sequence = fields.Integer(string='Sequence', default=10)
    ownership_line_id = fields.Many2one('ownership.line', string='Ownership Line')
    ownership_code_id = fields.Many2one('ownership.code', string='Ownership Code')
    parent_reference_id = fields.Many2one('ilo.reference', string='Parent Reference', ondelete='cascade')  # New field for parent reference


    _order = 'sequence'
        
    @api.depends('reference')
    def _compute_name(self):
        """Automatically compute the name for reference link."""
        for record in self:
            record.name = f'Link: {record.reference}'

    def action_view_ownership_code(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Ownership Code',
            'res_model': 'ownership.code',
            'res_id': self.ownership_code_id.id,  # Use the ID of the ownership.code
            'view_mode': 'form',
            'target': 'inline',  # Open in a popup
        }
    
    def action_view_ownership_line(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Ownership Line',
            'res_model': 'ownership.line',
            'res_id': self.ownership_line_id.id,  # Use the ID of the ownership.line
            'view_mode': 'form',
            'target': 'inline',  # Use 'inline' to open in a popup
        }




class IloReferenceSummary(models.Model):
    _name = 'ilo.reference.summary'
    _description = 'Summary Table for References'

# 1st
    reference_1 = fields.Char(string='Initial Reference')
    date_order_1 = fields.Date(string='Initial Date Order')
    actor_1 = fields.Many2one('res.partner', string='Initial Actor')
    actor_ilo_associate_1 = fields.Selection(
        selection=[
            ('farmers', 'Petani'),
            ('agent', 'Agent'),
            ('koperasi', 'Koperasi'),
            ('ugreen', 'UGreen'),
            ('green', 'Green'),
        ],
        string='1st Associate',
        related='actor_1.ilo_associate',
        store=True
    )
    kabupaten_1 = fields.Many2one('res.kabupaten', string='Initial Kabupaten')

# 2nd
    reference_2 = fields.Char(string='Secondary Reference')
    date_order_2 = fields.Date(string='Secondary Date Order')
    actor_2 = fields.Many2one('res.partner', string='Secondary Actor')
    actor_ilo_associate_2 = fields.Selection(
        selection=[
            ('farmers', 'Petani'),
            ('agent', 'Agent'),
            ('koperasi', 'Koperasi'),
            ('ugreen', 'UGreen'),
            ('green', 'Green'),
        ],
        string='2nd Associate',
        related='actor_2.ilo_associate',
        store=True
    )
    kabupaten_2 = fields.Many2one('res.kabupaten', string='Secondary Kabupaten')

# 3rd
    # New single field for the latest quantity

    reference_3 = fields.Char(string='3rd Reference')
    date_order_3 = fields.Date(string='3rd Date Order')
    actor_3 = fields.Many2one('res.partner', string='3rd Actor')
    actor_ilo_associate_3 = fields.Selection(
        selection=[
            ('farmers', 'Petani'),
            ('agent', 'Agent'),
            ('koperasi', 'Koperasi'),
            ('ugreen', 'UGreen'),
            ('green', 'Green'),
        ],
        string='3rd Associate',
        related='actor_3.ilo_associate',
        store=True
    )
    kabupaten_3 = fields.Many2one('res.kabupaten', string='3rd Kabupaten')

# 4th
    reference_4 = fields.Char(string='4th Reference')
    date_order_4 = fields.Date(string='4th Date Order')
    actor_4 = fields.Many2one('res.partner', string='4th Actor')
    actor_ilo_associate_4 = fields.Selection(
        selection=[
            ('farmers', 'Petani'),
            ('agent', 'Agent'),
            ('koperasi', 'Koperasi'),
            ('ugreen', 'UGreen'),
            ('green', 'Green'),
        ],
        string='4th Associate',
        related='actor_4.ilo_associate',
        store=True
    )
    kabupaten_4 = fields.Many2one('res.kabupaten', string='4th Kabupaten')

# 5th
    reference_5 = fields.Char(string='5th Reference')
    date_order_5 = fields.Date(string='5th Date Order')
    actor_5 = fields.Many2one('res.partner', string='5th Actor')
    actor_ilo_associate_5 = fields.Selection(
        selection=[
            ('farmers', 'Petani'),
            ('agent', 'Agent'),
            ('koperasi', 'Koperasi'),
            ('ugreen', 'UGreen'),
            ('green', 'Green'),
        ],
        string='5th Associate',
        related='actor_5.ilo_associate',
        store=True
    )
    kabupaten_5 = fields.Many2one('res.kabupaten', string='5th Kabupaten')

# Misc
    product_uom_id = fields.Many2one('uom.uom', string='Unit of Measure', default=lambda self: self.env.ref('uom.product_uom_kgm').id)
    state = fields.Char(string='State', compute='_compute_state')

    latest_quantity = fields.Float(string='Latest Quantity')
    date_created = fields.Datetime(string='Date Created', default=fields.Datetime.now)
    date_modified = fields.Datetime(string='Date Modified', compute='_compute_date_modified', store=True)

    @api.depends('reference_3', 'reference_4', 'reference_5')
    def _compute_date_modified(self):
        """Update the 'date_modified' whenever a field changes."""
        for record in self:
            record.date_modified = fields.Datetime.now()

    @api.depends('actor_ilo_associate_1', 'actor_ilo_associate_2', 'actor_ilo_associate_3', 
                'actor_ilo_associate_4', 'actor_ilo_associate_5')
    def _compute_state(self):
        for record in self:
            # Check for actor_ilo_associate fields and set state accordingly
            if record.actor_ilo_associate_5:
                record.state = record.actor_ilo_associate_5.capitalize()  # Set state based on actor_ilo_associate_5
            elif record.actor_ilo_associate_4:
                record.state = record.actor_ilo_associate_4.capitalize()  # Set state based on actor_ilo_associate_4
            elif record.actor_ilo_associate_3:
                record.state = record.actor_ilo_associate_3.capitalize()  # Set state based on actor_ilo_associate_3
            elif record.actor_ilo_associate_2:
                record.state = record.actor_ilo_associate_2.capitalize()  # Set state based on actor_ilo_associate_2
            elif record.actor_ilo_associate_1:
                record.state = record.actor_ilo_associate_1.capitalize()  # Set state based on actor_ilo_associate_1
            else:
                record.state = 'Unknown'  # Default state if no actor_ilo_associate is set

    @api.model
    def populate_reference_summary(self):
        existing_summaries = self.search([])
        references = self.env['ilo.reference'].search([])

        for ref in references:
            if ref.reference_link_ids:
                # Gather references, dates, actors, kabupaten values
                table_entry = {
                    'reference_1': ref.reference_link_ids[0].reference if len(ref.reference_link_ids) > 0 else False,
                    'date_order_1': ref.reference_link_ids[0].ownership_line_id.date_order if len(ref.reference_link_ids) > 0 else False,
                    'actor_1': ref.reference_link_ids[0].ownership_line_id.source_actor.id if len(ref.reference_link_ids) > 0 and ref.reference_link_ids[0].ownership_line_id.source_actor else False,
                    'kabupaten_1': ref.reference_link_ids[0].ownership_line_id.kabupaten_id.id if len(ref.reference_link_ids) > 0 and ref.reference_link_ids[0].ownership_line_id.kabupaten_id else False,

                    'reference_2': ref.reference_link_ids[1].reference if len(ref.reference_link_ids) > 1 else False,
                    'date_order_2': ref.reference_link_ids[1].ownership_code_id.date_order if len(ref.reference_link_ids) > 1 else False,
                    'actor_2': ref.reference_link_ids[1].ownership_code_id.destination_actor.id if len(ref.reference_link_ids) > 1 and ref.reference_link_ids[1].ownership_code_id.destination_actor else False,
                    'kabupaten_2': ref.reference_link_ids[1].ownership_code_id.kabupaten_id.id if len(ref.reference_link_ids) > 1 and ref.reference_link_ids[1].ownership_code_id.kabupaten_id else False,

                    'reference_3': ref.reference_link_ids[2].reference if len(ref.reference_link_ids) > 2 else False,
                    'date_order_3': ref.reference_link_ids[2].ownership_code_id.date_order if len(ref.reference_link_ids) > 2 else False,
                    'actor_3': ref.reference_link_ids[2].ownership_code_id.destination_actor.id if len(ref.reference_link_ids) > 2 and ref.reference_link_ids[2].ownership_code_id.destination_actor else False,
                    'kabupaten_3': ref.reference_link_ids[2].ownership_code_id.kabupaten_id.id if len(ref.reference_link_ids) > 2 and ref.reference_link_ids[2].ownership_code_id.kabupaten_id else False,

                    'reference_4': ref.reference_link_ids[3].reference if len(ref.reference_link_ids) > 3 else False,
                    'date_order_4': ref.reference_link_ids[3].ownership_code_id.date_order if len(ref.reference_link_ids) > 3 else False,
                    'actor_4': ref.reference_link_ids[3].ownership_code_id.destination_actor.id if len(ref.reference_link_ids) > 3 and ref.reference_link_ids[3].ownership_code_id.destination_actor else False,
                    'kabupaten_4': ref.reference_link_ids[3].ownership_code_id.kabupaten_id.id if len(ref.reference_link_ids) > 3 and ref.reference_link_ids[3].ownership_code_id.kabupaten_id else False,

                    'reference_5': ref.reference_link_ids[4].reference if len(ref.reference_link_ids) > 4 else False,
                    'date_order_5': ref.reference_link_ids[4].ownership_code_id.date_order if len(ref.reference_link_ids) > 4 else False,
                    'actor_5': ref.reference_link_ids[4].ownership_code_id.destination_actor.id if len(ref.reference_link_ids) > 4 and ref.reference_link_ids[4].ownership_code_id.destination_actor else False,
                    'kabupaten_5': ref.reference_link_ids[4].ownership_code_id.kabupaten_id.id if len(ref.reference_link_ids) > 4 and ref.reference_link_ids[4].ownership_code_id.kabupaten_id else False,
                    
                    # Gather the latest quantity from the last reference link
                    'latest_quantity': ref.reference_link_ids[-1].ownership_code_id.total_requested_quantity if ref.reference_link_ids else 0.0,
                }
                _logger.debug("Processing reference: %s", ref.id)

                # Check for an existing summary with the same reference, actor, kabupaten, and quantities
                existing_summary = existing_summaries.filtered(lambda s: (
                    s.reference_1 == table_entry['reference_1'] and
                    s.reference_2 == table_entry['reference_2'] and
                    s.reference_3 == table_entry['reference_3'] and
                    s.reference_4 == table_entry['reference_4'] and
                    s.reference_5 == table_entry['reference_5'] and
                    s.actor_1 == table_entry['actor_1'] and
                    s.actor_2 == table_entry['actor_2'] and
                    s.actor_3 == table_entry['actor_3'] and
                    s.actor_4 == table_entry['actor_4'] and
                    s.actor_5 == table_entry['actor_5'] and
                    s.kabupaten_1 == table_entry['kabupaten_1'] and
                    s.kabupaten_2 == table_entry['kabupaten_2'] and
                    s.kabupaten_3 == table_entry['kabupaten_3'] and
                    s.kabupaten_4 == table_entry['kabupaten_4'] and
                    s.kabupaten_5 == table_entry['kabupaten_5'] and
                    s.latest_quantity == table_entry['latest_quantity']  # Match the latest quantity
                ))

                if existing_summary:
                    _logger.info("Updating existing summary for reference: %s", ref.id)
                    existing_summary.write(table_entry)
                else:
                    _logger.info("Creating new summary for reference: %s", ref.id)
                    self.create(table_entry)

        _logger.info("Population of reference summary table completed.")






class IloReferenceMigration(models.TransientModel):
    _name = 'ilo.reference.migration'
    _description = 'Migration for IloReference'

    @api.model
    def migrate_ilo_reference(self):
        _logger.info("Starting migration of IloReference data...")

        # Fetch existing records from the old IloReference model
        old_references = self.env['ilo.reference'].search([])

        for old_ref in old_references:
            try:
                # Prepare the data for the new IloReference model
                # Migrate production_code from Char to Many2one
                if old_ref.production_code:
                    # Find the associated ilo.production.harvesting record
                    harvesting_record = self.env['ilo.production.harvesting'].search([
                        ('production_identifier', '=', old_ref.production_code)
                    ], limit=1)

                    # Set the production_code to the found harvesting record if it exists
                    production_code = harvesting_record.id if harvesting_record else False
                else:
                    production_code = False

                reference_one = old_ref.reference_one
                reference_two = old_ref.reference_two

                # Find the associated ownership_code based on the existing logic
                ownership_code = self.env['ownership.code'].search([
                    ('reference_code', '=', reference_two)
                ], limit=1)

                if not ownership_code:
                    _logger.warning("No matching ownership code found for reference_two: %s", reference_two)
                    continue  # Skip this record if no ownership code is found

                # Now find reference_three using the existing logic
                reference_three = self.find_reference_three(reference_two)

                # Create the new IloReference record
                new_ref = self.env['ilo.reference'].create({
                    'production_code': production_code,  # Set Many2one field
                    'ownership_code_id': ownership_code.id,  # Link to ownership code
                    'reference_link_ids': [
                        (0, 0, {'reference': reference_one}),
                        (0, 0, {'reference': reference_two, 'ownership_code_id': ownership_code.id}),
                        (0, 0, {'reference': reference_three}),
                    ],
                })

                _logger.info("Migrated IloReference: Old ID: %s -> New ID: %s", old_ref.id, new_ref.id)

            except Exception as e:
                _logger.error("Failed to migrate IloReference ID %s: %s", old_ref.id, str(e))

        _logger.info("Migration completed successfully.")

    def find_reference_three(self, reference_two_name):
        """Find reference_three by searching for the next ownership_code."""
        _logger.info("Looking for next ownership code where reference_code matches reference_two: %s", reference_two_name)

        # Search for ownership_code where the reference_code matches the reference_two's ownership_code.name
        ownership_code = self.env['ownership.code'].search([('reference_code', '=', reference_two_name)], limit=1)

        if ownership_code:
            _logger.info("Found matching ownership_code for reference_three: %s", ownership_code.name)
            return ownership_code.name  # Return the next ownership_code's name as reference_three
        return False
    

# from odoo import models, fields, api, exceptions, _
# import logging

# _logger = logging.getLogger(__name__)

# class IloReferenceAlternative(models.Model):
#     _name = 'ilo.reference.alternative'
#     _description = 'Reference Link Model'

#     # Adding production_code field
#     production_code = fields.Char(string='Production Code', readonly=True)
    
#     reference_one = fields.Char(string='Reference One', required=True)
#     reference_two = fields.Char(string='Reference Two', readonly=True)
#     reference_three = fields.Char(string='Reference Three', readonly=True)

#     @api.model
#     def create_reference_from_ownership(self, ownership_code):
#         """Create or update references based on the ownership code, including production_code."""
#         _logger.info("Creating/updating reference for ownership code: %s", ownership_code.reference_code)

#         # Get the production_code from ownership_code
#         production_code = ownership_code.production_code

#         # Reference Two: The ownership_code.name (the current ownership_code's name)
#         reference_two = ownership_code.name
#         # Reference One: The ownership_code.reference_code (the reference_code of the current ownership_code)
#         reference_one = ownership_code.reference_code

#         # Search for any existing reference where either reference_one or reference_two matches
#         ref = self.search([
#             '|', 
#             ('reference_one', '=', reference_one), 
#             ('reference_two', '=', reference_one)
#         ], limit=1)

#         if ref:
#             # If a reference exists, update reference_three if needed
#             _logger.info("Found existing reference, updating reference_three")
#             ref.update_reference_three_if_needed(reference_two)
#             # Ensure production_code is set from ownership_code
#         else:
#             # If no reference exists, create a new one
#             _logger.info("No existing reference found, creating a new reference with production_code")
#             ref = self.create({
#                 'production_code': production_code,
#                 'reference_one': reference_one,
#                 'reference_two': reference_two,
#                 'reference_three': self.find_reference_three(reference_two),  # Find and set reference_three
#             })
#             _logger.info("Created new reference: %s", ref)

#         return ref

#     def find_reference_three(self, reference_two_name):
#         """Find reference_three by searching for the next ownership_code."""
#         _logger.info("Looking for next ownership code where reference_code matches reference_two: %s", reference_two_name)

#         # Search for ownership_code where the reference_code matches the reference_two's ownership_code.name
#         ownership_code = self.env['ownership.code'].search([('reference_code', '=', reference_two_name)], limit=1)

#         if ownership_code:
#             _logger.info("Found matching ownership_code for reference_three: %s", ownership_code.name)
#             return ownership_code.name  # Return the next ownership_code's name as reference_three
#         return False

#     def update_reference_three_if_needed(self, reference_two):
#         """Update reference_three if it hasn't been set yet."""
#         _logger.info("Checking if reference_three needs to be updated for reference_two: %s", reference_two)

#         # Update reference_three only if it's empty
#         if not self.reference_three:
#             _logger.info("Reference_three is empty, finding and updating reference_three")
#             reference_three = self.find_reference_three(reference_two)
#             if reference_three:
#                 self.write({'reference_three': reference_three})
#                 _logger.info("Updated reference_three: %s", reference_three)

#     @api.model
#     def update_reference_three_on_new_ownership(self, ownership_code):
#         """Update reference_three when a new ownership_code is created."""
#         _logger.info("Updating references for new ownership_code: %s", ownership_code.reference_code)

#         # Find the reference where reference_two matches the new ownership_code's reference_code and reference_three is empty
#         ref = self.search([
#             ('reference_two', '=', ownership_code.reference_code),
#             ('reference_three', '=', False)
#         ], limit=1)

#         if ref:
#             # Update reference_three with the new ownership_code's name
#             ref.write({'reference_three': ownership_code.name})
#             _logger.info("Updated reference_three: %s", ownership_code.name)
#         else:
#             _logger.info("No matching reference found for ownership_code: %s", ownership_code.reference_code)