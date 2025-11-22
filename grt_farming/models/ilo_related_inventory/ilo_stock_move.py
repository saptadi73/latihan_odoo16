from odoo import models, fields, api, exceptions, _
import logging

_logger = logging.getLogger(__name__)

class ILOStockMove(models.Model):
    _name = 'ilo.stock_move'
    _description = 'ILO Stock Move'

    # Product Information
    product_id = fields.Many2one('product.product', string='Product', required=True)

    # Location Information
    source_employee_location = fields.Many2one(
        'res.partner', 
        string='Source Employee', 
        compute='_compute_employee_locations', 
        store=True
    )
    location_id = fields.Many2one('ilo.stock_location', string='Source Location', required=True)
    source_employee_ilo_associate = fields.Char(
        string='Source Employee ILO Associate', 
        compute='_compute_employee_ilo_details', 
        store=True
    )
    source_employee_ilo_associate_code = fields.Char(
        string='Source Employee ILO Associate Code', 
        compute='_compute_employee_ilo_details', 
        store=True
    )


    destination_employee_location = fields.Many2one(
        'res.partner', 
        string='Destination Employee', 
        compute='_compute_employee_locations', 
        store=True
    )
    location_dest_id = fields.Many2one('ilo.stock_location', string='Destination Location', required=True)
    destination_employee_ilo_associate = fields.Char(
        string='Destination Employee ILO Associate', 
        compute='_compute_employee_ilo_details', 
        store=True
    )
    destination_employee_ilo_associate_code = fields.Char(
        string='Destination Employee ILO Associate Code', 
        compute='_compute_employee_ilo_details', 
        store=True
    )
    warehouse_id = fields.Many2one('ilo.warehouse', string='Warehouse', ondelete='cascade')

    # Quantity and Unit
    quantity = fields.Float(string='Quantity', required=True, store=True)
    product_uom_id = fields.Many2one('uom.uom', string='Unit of Measure', required=True)

    # Date
    date = fields.Date(string='Date', default=fields.Date.context_today)

    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('waiting', 'Waiting'),
        ('confirmed', 'Confirmed'),
        ('assigned', 'Assigned'),
        ('done', 'Done'),
        ('cancel', 'Cancelled'),
    ], string='Status', default='draft')

    # Link to Inventory
    inventory_id = fields.Many2one('ilo.inventory', string='Related Inventory')

    # Fields for enhanced tracking
    movement_type = fields.Selection([('in', 'In'), ('out', 'Out')], string='Movement Type', compute='_compute_movement_type', store=True)
    movement_date = fields.Datetime(string='Movement Date', default=fields.Datetime.now)

    
    @api.depends('location_id', 'location_dest_id')
    def _compute_employee_locations(self):
        for record in self:
            record.source_employee_location = record.location_id.employee_id if record.location_id else False
            record.destination_employee_location = record.location_dest_id.employee_id if record.location_dest_id else False

    @api.depends('location_id', 'location_dest_id')
    def _compute_employee_ilo_details(self):
        for record in self:
            # Source Location Details
            if record.location_id:
                record.source_employee_ilo_associate = record.location_id.employee_ilo_associate
                record.source_employee_ilo_associate_code = record.location_id.employee_ilo_associate_code
            else:
                record.source_employee_ilo_associate = False
                record.source_employee_ilo_associate_code = False
            
            # Destination Location Details
            if record.location_dest_id:
                record.destination_employee_ilo_associate = record.location_dest_id.employee_ilo_associate
                record.destination_employee_ilo_associate_code = record.location_dest_id.employee_ilo_associate_code
            else:
                record.destination_employee_ilo_associate = False
                record.destination_employee_ilo_associate_code = False
    
    def create_move(self, product_id, location_id, location_dest_id, quantity, product_uom_id):
        if quantity <= 0:
            raise exceptions.UserError(_("Quantity must be greater than zero."))

        # Additional validation for product and locations could be added here

        move = self.create({
            'product_id': product_id,
            'location_id': location_id,
            'location_dest_id': location_dest_id,
            'quantity': quantity,
            'product_uom_id': product_uom_id,
            'state': 'draft',
            'movement_date': fields.Datetime.now(),  # Set default movement date
        })
        return move

    @api.depends('location_id', 'location_dest_id')
    def _compute_movement_type(self):
        for move in self:
            # If only destination is set, it's an inbound movement (stock coming in)
            if move.location_id and move.location_dest_id:
                move.movement_type = 'out'
            # If both are set, assume inbound (as it's moving to a destination)
            else:
                move.movement_type = 'in'

    def action_confirm(self):
        for move in self:
            if not move.movement_type:
                move._compute_movement_type()  # Recompute if movement_type is missing
            if move.state not in ['draft', 'cancel']:
                raise exceptions.UserError(_("Only draft or canceled moves can be confirmed."))
            move.state = 'confirmed'
            _logger.debug("Stock move %s confirmed.", move.id)
            move.action_assign()


    def action_assign(self):
        """Assign the stock move, updating relevant quantities and states."""
        for move in self:
            if move.state not in ['draft', 'confirmed']:
                raise exceptions.UserError(_("Only draft or confirmed stock moves can be assigned. Current state: %s") % move.state)

            # Update the state to assigned
            move.state = 'assigned'
            _logger.debug("Stock move %s assigned.", move.id)

    def action_done(self):
        """Mark the stock move as done and finalize stock adjustments."""
        for move in self:
            if move.state != 'assigned':
                raise exceptions.UserError(_("Only assigned stock moves can be marked as done. Current state: %s") % move.state)

            # Perform any additional actions needed to finalize the stock move
            # This could include updating quantities, logging movements, etc.
            move._update_locations()
            # Mark the move as done

            _logger.debug("Stock move %s marked as done.", move.id)

            # Log the movement completion
            move.movement_date = fields.Datetime.now()  # Update the movement date
            move.state = 'done'

    def _update_locations(self):
        for move in self:
            if not move.movement_type:
                move._compute_movement_type()  # Recompute if movement_type is missing

            source_location = move.location_id
            destination_location = move.location_dest_id

            if not source_location or not destination_location:
                raise exceptions.UserError('Source or destination location not found.')

            # Fetch the source location quant
            source_quant = self.env['ilo.quant'].search([
                ('product_id', '=', move.product_id.id),
                ('location_id', '=', source_location.id)
            ], limit=1)

            # Ensure source location has enough stock for outbound movements
            if move.movement_type == 'out' and (not source_quant or source_quant.quantity_available < move.quantity):
                raise exceptions.UserError(_('Insufficient stock for product %s in source location %s.') % (move.product_id.name, source_location.name))

            # Adjust source location quantity for outgoing movement
            source_quant.adjust_quantity_available(-move.quantity)

            # Adjust the destination location quant
            dest_quant = self.env['ilo.quant'].search([
                ('product_id', '=', move.product_id.id),
                ('location_id', '=', destination_location.id)
            ], limit=1)

            if not dest_quant:
                dest_quant = self.env['ilo.quant'].create({
                    'product_id': move.product_id.id,
                    'quantity_available': 0,
                    'location_id': destination_location.id,
                    'product_uom_id': move.product_uom_id.id,
                })

            # Increase destination quantity for inbound movement
            dest_quant.adjust_quantity_available(move.quantity)

            move.movement_date = fields.Datetime.now()

    def action_cancel(self):
        """Cancel the stock move and reverse stock changes."""
        for move in self:
            if move.state == 'done':
                # Reverse stock changes
                move._reverse_stock_movement()

            # Mark the move as canceled
            move.state = 'cancel'
            _logger.debug("Stock move %s canceled.", move.id)

    @api.model
    def _reverse_stock_movement(self):
        for move in self:
            if not move.movement_type:
                move._compute_movement_type()  # Ensure movement_type is available
            
            source_location = move.location_id
            destination_location = move.location_dest_id

            source_quant = self.env['ilo.quant'].search([
                ('product_id', '=', move.product_id.id),
                ('location_id', '=', source_location.id)
            ], limit=1)

            dest_quant = self.env['ilo.quant'].search([
                ('product_id', '=', move.product_id.id),
                ('location_id', '=', destination_location.id)
            ], limit=1)

            # Revert based on movement_type
            if move.movement_type == 'in':
                if source_quant:
                    source_quant.adjust_quantity_available(-move.quantity)
                if dest_quant:
                    dest_quant.adjust_quantity_available(move.quantity)
            else:  # For 'out' movements
                if source_quant:
                    source_quant.adjust_quantity_available(move.quantity)
                if dest_quant:
                    dest_quant.adjust_quantity_available(-move.quantity)

            # Log the reversed movement
            source_location.log_product_movement(
                product=move.product_id,
                movement_type='in' if move.movement_type == 'out' else 'out',
                quantity=move.quantity,
                source=destination_location,
                destination=source_location
            )
            destination_location.log_product_movement(
                product=move.product_id,
                movement_type=move.movement_type,
                quantity=move.quantity,
                source=destination_location,
                destination=source_location
            )