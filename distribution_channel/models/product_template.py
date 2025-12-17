from odoo import models, fields


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    weight_per_unit = fields.Float(
        string='Weight Per Unit (kg)',
        digits='Stock Weight',
        help='Weight of a single unit in kilograms'
    )
    
    volume_per_unit = fields.Float(
        string='Volume Per Unit (m³)',
        digits='Product Unit of Measure',
        help='Volume of a single unit in cubic meters'
    )
    
    case_width = fields.Float(
        string='Case Width (cm)',
        help='Width of the case/box in centimeters'
    )
    
    case_height = fields.Float(
        string='Case Height (cm)',
        help='Height of the case/box in centimeters'
    )
    
    case_depth = fields.Float(
        string='Case Depth (cm)',
        help='Depth of the case/box in centimeters'
    )
    
    case_weight = fields.Float(
        string='Case Weight (kg)',
        digits='Stock Weight',
        help='Total weight of the case/box with contents'
    )
    
    dry_weight_per_unit = fields.Float(
        string='Dry Weight Per Unit (kg)',
        digits='Stock Weight',
        help='Weight without moisture content'
    )
    
    gloss_weight_per_unit = fields.Float(
        string='Gloss Weight Per Unit (kg)',
        digits='Stock Weight',
        help='Weight with glossy coating'
    )

    def _compute_case_volume(self):
        """Compute case volume from dimensions"""
        for record in self:
            if record.case_width and record.case_height and record.case_depth:
                # Volume in cm³, convert to m³
                volume_cm3 = record.case_width * record.case_height * record.case_depth
                record.case_volume = volume_cm3 / 1_000_000
            else:
                record.case_volume = 0.0

    case_volume = fields.Float(
        string='Case Volume (m³)',
        compute='_compute_case_volume',
        store=True,
        help='Computed volume from case dimensions'
    )