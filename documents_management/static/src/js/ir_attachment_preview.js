/** @odoo-module **/

import { BinaryField } from "@web/views/fields/binary/binary_field";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";

patch(BinaryField.prototype, 'attachment_share', {
    setup() {
        this._super(...arguments);
        this.messaging = useService("messaging");
    },
    async _onFilePreview(ev){
        ev.preventDefault();
        ev.stopPropagation();
        var self = this;
        
        var match = self.props.record.data.mimetype.match("(image|video|application/pdf|text)");
        if(match){
            this.messaging.get().then((messaging) => {
                const attachmentList = messaging.models["AttachmentList"].insert({
                    selectedAttachment: messaging.models["Attachment"].insert({
                        id: this.props.record.data.id,
                        filename: this.props.record.data.name,
                        name: this.props.record.data.name,
                        mimetype: this.props.record.data.mimetype,
                    }),
                });
                this.dialog = messaging.models["Dialog"].insert({
                    attachmentListOwnerAsAttachmentView: attachmentList,
                });
            });
        }else{
            alert('This file type is not supported.')
        }        
    },
    getMessaging() {
        return this.env.services.messaging && this.env.services.messaging.modelManager.messaging;
    },
})