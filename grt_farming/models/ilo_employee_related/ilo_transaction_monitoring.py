from odoo import api, fields, models, exceptions

class IloEmployeeTransactionMonitoring(models.Model):
    _name = 'ilo.transaction_monitoring'
    _description = 'Employee Transaction Monitoring'

    employee_id = fields.Many2one('res.partner', string="Employee", required=True)

    # Monitoring Transactions (One2Many with ownership.line)
    source_transaction_ids = fields.One2many('ownership.line', 'source_actor', string="Transactions as Seller")
    destination_transaction_ids = fields.One2many('ownership.line', 'destination_actor', string="Transactions as Buyer")

    # Computed transaction counts for different roles and associate types
    total_transactions_as_seller = fields.Integer(string="Total Transactions as Seller", compute='_compute_total_transactions_as_seller')
    total_transactions_as_buyer = fields.Integer(string="Total Transactions as Buyer", compute='_compute_total_transactions_as_buyer')
    total_transactions = fields.Integer(string="Total Transactions", compute='_compute_total_transactions')

    @api.depends('source_transaction_ids')
    def _compute_total_transactions_as_seller(self):
        for record in self:
            record.total_transactions_as_seller = len(record.source_transaction_ids)

    @api.depends('destination_transaction_ids')
    def _compute_total_transactions_as_buyer(self):
        for record in self:
            record.total_transactions_as_buyer = len(record.destination_transaction_ids)

    @api.depends('source_transaction_ids', 'destination_transaction_ids')
    def _compute_total_transactions(self):
        for record in self:
            record.total_transactions = len(record.source_transaction_ids) + len(record.destination_transaction_ids)
