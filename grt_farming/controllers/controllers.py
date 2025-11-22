from odoo import http
from odoo.http import request, Response
import json
from odoo.addons.ILO_farming_perspective.models.api_integration import (
    ClassRPCInheritedCustom, ClassRPCAssets, ClassRPCDashboard, ClassRPCQrCode
)

class APIController(http.Controller):

    def get_api_key(self):
        api_key = request.httprequest.headers.get('Authorization')
        return api_key.replace('Bearer ', '') if api_key else None

    def authenticate(self):
        api_key = self.get_api_key()
        valid_key = '677f2788624379176fa174215f803400fbee2965'
        return api_key == valid_key

    def handle_error(self, e):
        return Response(
            json.dumps({'error': str(e)}),
            content_type='application/json',
            status=500
        )

    def get_odoo_client(self, client_class):
        # This method should return an instance of the Odoo client.
        return client_class(request.env)

    # Sale Order Routes
    @http.route('/api/sale_order/create', type='json', auth='none', methods=['POST'])
    def create_sale_order(self, **kwargs):
        odoo_custom_client = self.get_odoo_client(ClassRPCInheritedCustom)
        try:
            result = odoo_custom_client.create_sale_order(**kwargs)
            return {
                'status': 'success',
                'data': result,
                'message': 'Sale order created successfully'
            }
        except Exception as e:
            return self.handle_error(e)

    @http.route('/api/sale_order/read/<int:sale_order_id>', type='json', auth='none', methods=['GET'])
    def read_sale_order(self, sale_order_id):
        odoo_custom_client = self.get_odoo_client(ClassRPCInheritedCustom)
        try:
            result = odoo_custom_client.read_sale_order(sale_order_id)
            return {'status': 'success', 'data': result}
        except Exception as e:
            return self.handle_error(e)

    @http.route('/api/sale_order/update/<int:sale_order_id>', type='json', auth='none', methods=['PUT'])
    def update_sale_order(self, sale_order_id, **values):
        odoo_custom_client = self.get_odoo_client(ClassRPCInheritedCustom)
        try:
            result = odoo_custom_client.update_sale_order(sale_order_id, values)
            return {'status': 'success', 'data': result, 'message': 'Sale order updated successfully'}
        except Exception as e:
            return self.handle_error(e)

    @http.route('/api/sale_order/delete/<int:sale_order_id>', type='json', auth='none', methods=['DELETE'])
    def delete_sale_order(self, sale_order_id):
        odoo_custom_client = self.get_odoo_client(ClassRPCInheritedCustom)
        try:
            result = odoo_custom_client.delete_sale_order(sale_order_id)
            return {'status': 'success', 'data': result, 'message': 'Sale order deleted successfully'}
        except Exception as e:
            return self.handle_error(e)

    # Employee Routes
    @http.route('/api/employee/create', type='json', auth='none', methods=['POST'])
    def create_employee(self, **kwargs):
        odoo_custom_client = self.get_odoo_client(ClassRPCInheritedCustom)
        try:
            result = odoo_custom_client.create_employee(**kwargs)
            return {'status': 'success', 'data': result, 'message': 'Employee created successfully'}
        except Exception as e:
            return self.handle_error(e)

    @http.route('/api/employee/read/<int:employee_id>', type='json', auth='none', methods=['GET'])
    def read_employee(self, employee_id):
        odoo_custom_client = self.get_odoo_client(ClassRPCInheritedCustom)
        try:
            result = odoo_custom_client.read_employee(employee_id)
            return {'status': 'success', 'data': result}
        except Exception as e:
            return self.handle_error(e)

    @http.route('/api/employee/update/<int:employee_id>', type='json', auth='none', methods=['PUT'])
    def update_employee(self, employee_id, **values):
        odoo_custom_client = self.get_odoo_client(ClassRPCInheritedCustom)
        try:
            result = odoo_custom_client.update_employee(employee_id, values)
            return {'status': 'success', 'data': result, 'message': 'Employee updated successfully'}
        except Exception as e:
            return self.handle_error(e)

    @http.route('/api/employee/delete/<int:employee_id>', type='json', auth='none', methods=['DELETE'])
    def delete_employee(self, employee_id):
        odoo_custom_client = self.get_odoo_client(ClassRPCInheritedCustom)
        try:
            result = odoo_custom_client.delete_employee(employee_id)
            return {'status': 'success', 'data': result, 'message': 'Employee deleted successfully'}
        except Exception as e:
            return self.handle_error(e)

    # Project Routes
    @http.route('/api/project/create', type='json', auth='none', methods=['POST'])
    def create_project(self, **kwargs):
        odoo_custom_client = self.get_odoo_client(ClassRPCInheritedCustom)
        try:
            result = odoo_custom_client.create_project(**kwargs)
            return {'status': 'success', 'data': result, 'message': 'Project created successfully'}
        except Exception as e:
            return self.handle_error(e)

    @http.route('/api/project/read/<int:project_id>', type='json', auth='none', methods=['GET'])
    def read_project(self, project_id):
        odoo_custom_client = self.get_odoo_client(ClassRPCInheritedCustom)
        try:
            result = odoo_custom_client.read_project(project_id)
            return {'status': 'success', 'data': result}
        except Exception as e:
            return self.handle_error(e)

    @http.route('/api/project/update/<int:project_id>', type='json', auth='none', methods=['PUT'])
    def update_project(self, project_id, **values):
        odoo_custom_client = self.get_odoo_client(ClassRPCInheritedCustom)
        try:
            result = odoo_custom_client.update_project(project_id, values)
            return {'status': 'success', 'data': result, 'message': 'Project updated successfully'}
        except Exception as e:
            return self.handle_error(e)

    @http.route('/api/project/delete/<int:project_id>', type='json', auth='none', methods=['DELETE'])
    def delete_project(self, project_id):
        odoo_custom_client = self.get_odoo_client(ClassRPCInheritedCustom)
        try:
            result = odoo_custom_client.delete_project(project_id)
            return {'status': 'success', 'data': result, 'message': 'Project deleted successfully'}
        except Exception as e:
            return self.handle_error(e)

    # MRP Production Routes
    @http.route('/api/mrp_production/create', type='json', auth='none', methods=['POST'])
    def create_mrp_production(self, **kwargs):
        odoo_custom_client = self.get_odoo_client(ClassRPCInheritedCustom)
        try:
            result = odoo_custom_client.create_mrp_production(**kwargs)
            return {'status': 'success', 'data': result, 'message': 'MRP Production created successfully'}
        except Exception as e:
            return self.handle_error(e)

    @http.route('/api/mrp_production/read/<int:mrp_production_id>', type='json', auth='none', methods=['GET'])
    def read_mrp_production(self, mrp_production_id):
        odoo_custom_client = self.get_odoo_client(ClassRPCInheritedCustom)
        try:
            result = odoo_custom_client.read_mrp_production(mrp_production_id)
            return {'status': 'success', 'data': result}
        except Exception as e:
            return self.handle_error(e)

    @http.route('/api/mrp_production/update/<int:mrp_production_id>', type='json', auth='none', methods=['PUT'])
    def update_mrp_production(self, mrp_production_id, **values):
        odoo_custom_client = self.get_odoo_client(ClassRPCInheritedCustom)
        try:
            result = odoo_custom_client.update_mrp_production(mrp_production_id, values)
            return {'status': 'success', 'data': result, 'message': 'MRP Production updated successfully'}
        except Exception as e:
            return self.handle_error(e)

    @http.route('/api/mrp_production/delete/<int:mrp_production_id>', type='json', auth='none', methods=['DELETE'])
    def delete_mrp_production(self, mrp_production_id):
        odoo_custom_client = self.get_odoo_client(ClassRPCInheritedCustom)
        try:
            result = odoo_custom_client.delete_mrp_production(mrp_production_id)
            return {'status': 'success', 'data': result, 'message': 'MRP Production deleted successfully'}
        except Exception as e:
            return self.handle_error(e)

    # Stock Quant Routes
    @http.route('/api/stock_quant/create', type='json', auth='none', methods=['POST'])
    def create_stock_quant(self, **kwargs):
        odoo_custom_client = self.get_odoo_client(ClassRPCInheritedCustom)
        try:
            result = odoo_custom_client.create_stock_quant(**kwargs)
            return {'status': 'success', 'data': result, 'message': 'Stock Quant created successfully'}
        except Exception as e:
            return self.handle_error(e)

    @http.route('/api/stock_quant/read/<int:stock_quant_id>', type='json', auth='none', methods=['GET'])
    def read_stock_quant(self, stock_quant_id):
        odoo_custom_client = self.get_odoo_client(ClassRPCInheritedCustom)
        try:
            result = odoo_custom_client.read_stock_quant(stock_quant_id)
            return {'status': 'success', 'data': result}
        except Exception as e:
            return self.handle_error(e)

    @http.route('/api/stock_quant/update/<int:stock_quant_id>', type='json', auth='none', methods=['PUT'])
    def update_stock_quant(self, stock_quant_id, **values):
        odoo_custom_client = self.get_odoo_client(ClassRPCInheritedCustom)
        try:
            result = odoo_custom_client.update_stock_quant(stock_quant_id, values)
            return {'status': 'success', 'data': result, 'message': 'Stock Quant updated successfully'}
        except Exception as e:
            return self.handle_error(e)

    @http.route('/api/stock_quant/delete/<int:stock_quant_id>', type='json', auth='none', methods=['DELETE'])
    def delete_stock_quant(self, stock_quant_id):
        odoo_custom_client = self.get_odoo_client(ClassRPCInheritedCustom)
        try:
            result = odoo_custom_client.delete_stock_quant(stock_quant_id)
            return {'status': 'success', 'data': result, 'message': 'Stock Quant deleted successfully'}
        except Exception as e:
            return self.handle_error(e)

    # Stock Inventory Routes
    @http.route('/api/stock_inventory/create', type='json', auth='none', methods=['POST'])
    def create_stock_inventory(self, **kwargs):
        odoo_custom_client = self.get_odoo_client(ClassRPCInheritedCustom)
        try:
            result = odoo_custom_client.create_stock_inventory(**kwargs)
            return {'status': 'success', 'data': result, 'message': 'Stock Inventory created successfully'}
        except Exception as e:
            return self.handle_error(e)

    @http.route('/api/stock_inventory/read/<int:stock_inventory_id>', type='json', auth='none', methods=['GET'])
    def read_stock_inventory(self, stock_inventory_id):
        odoo_custom_client = self.get_odoo_client(ClassRPCInheritedCustom)
        try:
            result = odoo_custom_client.read_stock_inventory(stock_inventory_id)
            return {'status': 'success', 'data': result}
        except Exception as e:
            return self.handle_error(e)

    @http.route('/api/stock_inventory/update/<int:stock_inventory_id>', type='json', auth='none', methods=['PUT'])
    def update_stock_inventory(self, stock_inventory_id, **values):
        odoo_custom_client = self.get_odoo_client(ClassRPCInheritedCustom)
        try:
            result = odoo_custom_client.update_stock_inventory(stock_inventory_id, values)
            return {'status': 'success', 'data': result, 'message': 'Stock Inventory updated successfully'}
        except Exception as e:
            return self.handle_error(e)

    @http.route('/api/stock_inventory/delete/<int:stock_inventory_id>', type='json', auth='none', methods=['DELETE'])
    def delete_stock_inventory(self, stock_inventory_id):
        odoo_custom_client = self.get_odoo_client(ClassRPCInheritedCustom)
        try:
            result = odoo_custom_client.delete_stock_inventory(stock_inventory_id)
            return {'status': 'success', 'data': result, 'message': 'Stock Inventory deleted successfully'}
        except Exception as e:
            return self.handle_error(e)

    # QR Code Routes
    @http.route('/api/qrcode/generate', type='json', auth='none', methods=['POST'])
    def generate_qrcode(self, **kwargs):
        odoo_custom_client = self.get_odoo_client(ClassRPCQrCode)
        try:
            result = odoo_custom_client.generate_qrcode(**kwargs)
            return {'status': 'success', 'data': result, 'message': 'QR Code generated successfully'}
        except Exception as e:
            return self.handle_error(e)
