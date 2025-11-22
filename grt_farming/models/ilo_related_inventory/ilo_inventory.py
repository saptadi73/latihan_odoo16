from odoo import models, fields, api, exceptions, _

class ILOInventory(models.Model):
    _name = 'ilo.inventory'
    _description = 'ILO Inventory'

    name = fields.Char(string='Name')

    # Product Information
    product_id = fields.Many2one('product.product', string='Product', required=True)
    product_name = fields.Char(related='product_id.name', string='Product Name', store=True)
    product_code = fields.Char(related='product_id.batch_code', string='Product Code', store=True)

    # Seller Information
    seller_id = fields.Many2one('res.partner', string='Seller')
    seller_name = fields.Char(related='seller_id.name', string='Seller Name', store=True)
    seller_location = fields.Char(string='Seller Location')

    # Quantity and Unit
    quantity = fields.Float(string='Quantity', required=True)
    product_uom_id = fields.Many2one('uom.uom', string='Unit of Measure', required=True)

    # Price
    price = fields.Float(string='Price')

    # Additional fields
    warehouse_id = fields.Many2one('ilo.warehouse', string='Warehouse')
    location_ids = fields.Many2many('ilo.stock_location', string='Stock Location')
    inventory_line_ids = fields.One2many('ilo.inventory_line','inventory_id', string='Inventory Lines')
    category = fields.Selection([
        ('agen', 'Agen'),
        ('koperasi', 'Koperasi'),
        ('ugreen', 'UGreen')
    ], string='Category')
    status = fields.Selection([
        ('masuk', 'Masuk'),
        ('keluar', 'Keluar')
    ], string='Status', default='masuk')
    date = fields.Date(string='Date', default=fields.Date.context_today)

    # Stock Movement
    stock_move_ids = fields.One2many('ilo.stock_move', 'inventory_id', string='Stock Moves')

    @api.model
    def create(self, vals):
        """Override create method to automatically generate stock moves if needed."""
        record = super(ILOInventory, self).create(vals)
        if vals.get('quantity'):
            record._generate_stock_moves()
        return record

    def write(self, vals):
        """Override write method to update stock moves based on quantity changes."""
        for record in self:
            if 'quantity' in vals:
                old_quantity = record.quantity
                new_quantity = vals['quantity']
                if old_quantity != new_quantity:
                    record._update_stock_moves(old_quantity, new_quantity)
        return super(ILOInventory, self).write(vals)

    def _generate_stock_moves(self):
        """Generate stock moves based on the inventory."""
        move_vals = {
            'product_id': self.product_id.id,
            'quantity': self.quantity,
            'location_id': self.warehouse_id.id,
            'location_dest_id': self.seller_id.id,
            'state': 'done',
            'date': self.date,
            'inventory_id': self.id,
        }
        self.env['ilo.stock_move'].create(move_vals)

    def _update_stock_moves(self, old_quantity, new_quantity):
        """Update stock moves based on changes in quantity."""
        if old_quantity < new_quantity:
            move_vals = {
                'product_id': self.product_id.id,
                'quantity': new_quantity - old_quantity,
                'location_id': self.warehouse_id.id,
                'location_dest_id': self.seller_id.id,
                'state': 'done',
                'date': self.date,
                'inventory_id': self.id,
            }
            self.env['ilo.stock_move'].create(move_vals)
        elif old_quantity > new_quantity:
            move_vals = {
                'product_id': self.product_id.id,
                'quantity': old_quantity - new_quantity,
                'location_id': self.seller_id.id,
                'location_dest_id': self.warehouse_id.id,
                'state': 'done',
                'date': self.date,
                'inventory_id': self.id,
            }
            self.env['ilo.stock_move'].create(move_vals)

class ILOInventoryLine(models.Model):
    _name = 'ilo.inventory_line'
    _description = 'ILO Inventory Line'

    inventory_id = fields.Many2one('ilo.inventory', string='Inventory')
    product_id = fields.Many2one('product.product', string='Product')
    quantity_counted = fields.Float(string='Quantity Counted')
