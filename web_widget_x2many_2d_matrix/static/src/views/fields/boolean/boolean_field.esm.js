/** @odoo-module **/

import {patch} from "@web/core/utils/patch";
import {BooleanField} from "@web/views/fields/boolean/boolean_field";

patch(BooleanField.prototype, {
    get isReadonly() {
        if (this.props.record.bypass_readonly) {
            return false;
        }
        return this._super(...arguments);
    },
});
