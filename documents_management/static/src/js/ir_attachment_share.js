/** @odoo-module */

import { FormRenderer } from '@web/views/form/form_renderer';
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";

const { onMounted, onPatched, useEnv } = owl;

patch(FormRenderer.prototype, 'attachment_share', {
    setup() {
        this._super(...arguments);
        this.action = useService("action");
        onPatched(this._renderShareButton.bind(this));
        onMounted(this._renderShareButton.bind(this));
    },
    _renderShareButton(){
        if (this.props.record.resModel === 'ir.attachment'){
            const $sharebutton = $('<div>');
            $sharebutton.addClass("attachment_share_button");
            $sharebutton.append($('<button>').addClass("btn btn-primary").append($('<i class="fa fa-share-alt"/>')));
            $sharebutton.on('click', this._clickShareButton.bind(this));
            const $sheet = $('.o_form_sheet');
            if (this.props.record.resId && this.props.record.data.datas){
                $sheet.append($sharebutton);
            }
        }
    },
    _clickShareButton: function(ev) {
        ev.stopPropagation();
        ev.preventDefault();            
        var self = this;
        this.action.doAction({
            type: 'ir.actions.act_window',
            name: this.env._t('Share Attachments'),
            res_model: 'ir.attachment.share',
            views: [[false, 'form']],
            view_mode: 'form',
            target: 'new',
            context: {
                active_model : self.props.record.resModel || false,
                default_res_id : self.props.record.resId || false,
                active_id : self.props.record.resId || false,
            }
        })
    },
})

export default FormRenderer;