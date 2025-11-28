from odoo import models, fields, api
from odoo.exceptions import UserError

class Rental(models.Model):
    _name = 'truck_rental.rental'
    _description = 'Truck Rental Record'

    customer_id = fields.Many2one('res.partner', string='Customer', required=True)
    truck_id = fields.Many2one('fleet.vehicle', string='Truck', required=True)
    rental_start_date = fields.Date(string='Rental Start Date', required=True)
    rental_end_date = fields.Date(string='Rental End Date', required=True)
    total_rental_cost = fields.Float(string='Total Rental Cost', compute='_compute_total_rental_cost', store=True)

    # Link to Sale Order
    sale_order_id = fields.Many2one('sale.order', string='Sale Order', readonly=True)
    # Product jasa untuk rental (set via company config atau hardcoded)
    rental_service_product_id = fields.Many2one(
        'product.product', string='Rental Service Product',
        domain=[('type', '=', 'service')],
        help='Produk jasa untuk baris SO rental. Jika kosong, ambil default dari company.'
    )

    @api.depends('rental_start_date', 'rental_end_date', 'truck_id')
    def _compute_total_rental_cost(self):
        for record in self:
            if record.rental_start_date and record.rental_end_date and record.truck_id:
                rental_days = (record.rental_end_date - record.rental_start_date).days + 1
                daily_rate = getattr(record.truck_id, 'daily_rate', 0.0) or 0.0
                record.total_rental_cost = rental_days * daily_rate
            else:
                record.total_rental_cost = 0.0

    @api.model
    def create(self, vals):
        rental = super().create(vals)
        rental._create_sale_order()
        return rental

    def _create_sale_order(self):
        """Buat Sale Order otomatis dengan 1 baris produk jasa rental."""
        self.ensure_one()
        if self.sale_order_id:
            return  # Sudah ada SO

        # Ambil produk jasa
        product = self.rental_service_product_id or self._get_default_rental_service_product()
        if not product:
            raise UserError('Produk jasa rental tidak ditemukan. Isi Rental Service Product atau buat default.')

        # Hitung qty (hari) dan price_unit (tarif harian)
        if not self.rental_start_date or not self.rental_end_date or not self.truck_id:
            raise UserError('Tanggal rental dan truck harus diisi untuk membuat SO.')

        rental_days = (self.rental_end_date - self.rental_start_date).days + 1
        daily_rate = getattr(self.truck_id, 'daily_rate', 0.0) or 0.0
        if daily_rate <= 0:
            raise UserError('Daily rate truck tidak valid (harus > 0).')

        # Buat SO
        so_vals = {
            'partner_id': self.customer_id.id,
            'date_order': fields.Datetime.now(),
            'order_line': [
                (0, 0, {
                    'product_id': product.id,
                    'name': f"Rental {self.truck_id.display_name or 'Truck'} - {rental_days} hari",
                    'product_uom_qty': rental_days,
                    'product_uom': product.uom_id.id,
                    'price_unit': daily_rate,
                })
            ],
        }
        so = self.env['sale.order'].create(so_vals)
        self.sale_order_id = so.id

    def _get_default_rental_service_product(self):
        """Cari produk default untuk rental service. Bisa set via company config atau search by name."""
        # Opsi 1: Hardcoded by internal reference
        product = self.env['product.product'].search([
            ('default_code', '=', 'RENTAL_SERVICE'),
            ('type', '=', 'service')
        ], limit=1)
        if product:
            return product

        # Opsi 2: Search by name contains 'Rental'
        product = self.env['product.product'].search([
            ('name', 'ilike', 'rental'),
            ('type', '=', 'service')
        ], limit=1)
        return product

    def action_view_sale_order(self):
        """Smart button untuk membuka SO."""
        self.ensure_one()
        if not self.sale_order_id:
            raise UserError('Belum ada Sale Order.')
        return {
            'type': 'ir.actions.act_window',
            'name': 'Sale Order',
            'res_model': 'sale.order',
            'view_mode': 'form',
            'target': 'current',
            'res_id': self.sale_order_id.id,
        }