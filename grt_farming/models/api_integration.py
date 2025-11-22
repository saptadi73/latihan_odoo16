import requests
import json
import logging

# Set up logging for better debugging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# api key ILO 677f2788624379176fa174215f803400fbee2965

class OdooJSONRPCClient:
    def __init__(self, url, db, username, password):
        self.url = url
        self.db = db
        self.username = username
        self.password = password
        self.headers = {'Content-Type': 'application/json'}  # Initialize headers before authenticate
        self.uid = self.authenticate()  # Now call authenticate after initializing headers

    def authenticate(self):
        """Authenticate user and obtain UID. Return None if authentication fails."""
        try:
            response = requests.post(f'{self.url}/web/session/authenticate', json={
                'params': {
                    'db': self.db,
                    'login': self.username,
                    'password': self.password,
                }
            }, headers=self.headers, timeout=10)  # Added timeout to prevent hanging
            response.raise_for_status()
            result = response.json()
            if result.get('result'):
                uid = result['result'].get('uid')
                if uid:
                    logger.info(f'Authenticated with UID: {uid}')
                    return uid
            logger.error(f'Authentication failed: {result}')
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f'Authentication error: {e}')
            return None

    def call(self, model, method, args=None, kwargs=None):
        """Call Odoo model methods via RPC."""
        if not self.uid:
            logger.error("Cannot make a call without a valid authentication.")
            return None
        
        try:
            payload = {
                'model': model,
                'method': method,
                'args': args or [],
                'kwargs': kwargs or {},
                'context': {'lang': 'en_US'}  # You can make this dynamic if needed
            }
            logger.info(f'Calling {model}.{method} with args: {args} and kwargs: {kwargs}')
            response = requests.post(f'{self.url}/web/dataset/call_kw', json=payload, headers=self.headers, timeout=10)
            response.raise_for_status()
            result = response.json()
            if 'error' in result:
                logger.error(f"Odoo Error: {result['error']}")
            return result.get('result')
        except requests.exceptions.RequestException as e:
            logger.error(f'Error calling method {method} on model {model}: {e}')
            return None
        except json.JSONDecodeError as e:
            logger.error(f'JSON decode error: {e}')
            return None

    def get_model_fields(self, model):
        """Retrieve the fields of the given model."""
        return self.call(model, 'fields_get', [], {'attributes': ['string', 'type']})



class ClassRPCInheritedCustom(OdooJSONRPCClient):
    """General CRUD operations on any model with field validation."""
    
    def create_record(self, model, values):
        """Create a new record in the specified model."""
        model_fields = self.get_model_fields(model)
        if model_fields is None:
            logger.error(f"Could not retrieve fields for model {model}")
            return None
        filtered_values = {key: values[key] for key in values if key in model_fields}
        return self.call(model, 'create', [filtered_values])

    def read_record(self, model, record_id):
        """Read a record by its ID."""
        return self.call(model, 'read', [record_id])

    def update_record(self, model, record_id, values):
        """Update an existing record."""
        model_fields = self.get_model_fields(model)
        if model_fields is None:
            logger.error(f"Could not retrieve fields for model {model}")
            return None
        filtered_values = {key: values[key] for key in values if key in model_fields}
        return self.call(model, 'write', [record_id, filtered_values])

    def delete_record(self, model, record_id):
        """Delete a record by its ID."""
        return self.call(model, 'unlink', [record_id])


# class ClassRPCSaleOrder(ClassRPCInheritedCustom):
#     """CRUD operations for Sale Order."""
    
#     def create_sale_order(self, **kwargs):
#         return self.create_record('sale.order', kwargs)

#     def read_sale_order(self, sale_order_id):
#         return self.read_record('sale.order', sale_order_id)

#     def update_sale_order(self, sale_order_id, values):
#         return self.update_record('sale.order', sale_order_id, values)

#     def delete_sale_order(self, sale_order_id):
#         return self.delete_record('sale.order', sale_order_id)
    

# class ClassRPCPurchaseOrder(ClassRPCInheritedCustom):
#     """CRUD operations for Purchase Order."""
#     def create_purchase_order(self, **kwargs):
#         return self.create_record('purchase.order', kwargs)

#     def read_purchase_order(self, purchase_order_id):
#         return self.read_record('purchase.order', purchase_order_id)

#     def update_purchase_order(self, purchase_order_id, values):
#         return self.update_record('purchase.order', purchase_order_id, values)

#     def delete_purchase_order(self, purchase_order_id):
#         return self.delete_record('purchase.order', purchase_order_id)


class ClassRPCEmployee(ClassRPCInheritedCustom):
    """CRUD operations for Employee."""
    
    def create_employee(self, **kwargs):
        return self.create_record('res.partner', kwargs)

    def read_employee(self, employee_id):
        return self.read_record('res.partner', employee_id)

    def update_employee(self, employee_id, values):
        return self.update_record('res.partner', employee_id, values)

    def delete_employee(self, employee_id):
        return self.delete_record('res.partner', employee_id)


class ClassRPCProject(ClassRPCInheritedCustom):
    """CRUD operations for Project."""
    
    def create_project(self, **kwargs):
        return self.create_record('project.project', kwargs)

    def read_project(self, project_id):
        return self.read_record('project.project', project_id)

    def update_project(self, project_id, values):
        return self.update_record('project.project', project_id, values)

    def delete_project(self, project_id):
        return self.delete_record('project.project', project_id)


class ClassRPCMRPProduction(ClassRPCInheritedCustom):
    """CRUD operations for MRP Production."""
    
    def create_mrp_production(self, **kwargs):
        return self.create_record('mrp.production', kwargs)

    def read_mrp_production(self, mrp_production_id):
        return self.read_record('mrp.production', mrp_production_id)

    def update_mrp_production(self, mrp_production_id, values):
        return self.update_record('mrp.production', mrp_production_id, values)

    def delete_mrp_production(self, mrp_production_id):
        return self.delete_record('mrp.production', mrp_production_id)


class ClassRPCStockQuant(ClassRPCInheritedCustom):
    """CRUD operations for Stock Quant."""
    
    def create_stock_quant(self, **kwargs):
        return self.create_record('stock.quant', kwargs)

    def read_stock_quant(self, stock_quant_id):
        return self.read_record('stock.quant', stock_quant_id)

    def update_stock_quant(self, stock_quant_id, values):
        return self.update_record('stock.quant', stock_quant_id, values)

    def delete_stock_quant(self, stock_quant_id):
        return self.delete_record('stock.quant', stock_quant_id)


class ClassRPCAssets(OdooJSONRPCClient):
    """CRUD operations for ILO Assets."""
    
    def get_fields(self, model):
        return self.call(model, 'fields_get')

    def create_asset(self, **kwargs):
        fields = self.get_fields('ilo.assets')
        valid_fields = {k: v for k, v in kwargs.items() if k in fields}
        return self.call('ilo.assets', 'create', [valid_fields])

    def read_asset(self, asset_id):
        return self.call('ilo.assets', 'read', [asset_id])

    def update_asset(self, asset_id, values):
        fields = self.get_fields('ilo.assets')
        valid_fields = {k: v for k, v in values.items() if k in fields}
        return self.call('ilo.assets', 'write', [asset_id, valid_fields])

    def delete_asset(self, asset_id):
        return self.call('ilo.assets', 'unlink', [asset_id])


class ClassRPCDashboard(OdooJSONRPCClient):
    """CRUD operations for Dashboard."""
    
    def get_fields(self, model):
        return self.call(model, 'fields_get')

    def create_dashboard(self, **kwargs):
        fields = self.get_fields('ilo.dashboard')
        valid_fields = {k: v for k, v in kwargs.items() if k in fields}
        return self.call('ilo.dashboard', 'create', [valid_fields])

    def read_dashboard(self, dashboard_id):
        return self.call('ilo.dashboard', 'read', [dashboard_id])

    def update_dashboard(self, dashboard_id, values):
        fields = self.get_fields('ilo.dashboard')
        valid_fields = {k: v for k, v in values.items() if k in fields}
        return self.call('ilo.dashboard', 'write', [dashboard_id, valid_fields])

    def delete_dashboard(self, dashboard_id):
        return self.call('ilo.dashboard', 'unlink', [dashboard_id])


class ClassRPCQrCode(OdooJSONRPCClient):
    """CRUD operations for QR Code."""
    
    def get_fields(self, model):
        return self.call(model, 'fields_get')

    def create_qr_code(self, **kwargs):
        fields = self.get_fields('qr.code')
        valid_fields = {k: v for k, v in kwargs.items() if k in fields}
        return self.call('qr.code', 'create', [valid_fields])

    def read_qr_code(self, qr_code_id):
        return self.call('qr.code', 'read', [qr_code_id])

    def update_qr_code(self, qr_code_id, values):
        fields = self.get_fields('qr.code')
        valid_fields = {k: v for k, v in values.items() if k in fields}
        return self.call('qr.code', 'write', [qr_code_id, valid_fields])

    def delete_qr_code(self, qr_code_id):
        return self.call('qr.code', 'unlink', [qr_code_id])


# Initialize the client with your Odoo instance details
odoo_client = OdooJSONRPCClient(
    url='http://localhost:8069',
    db='DatabaseBaru',
    username='admin',
    password='admin'
)
