/** @odoo-module **/
/* Copyright 2024 Tecnativa - David Vidal
   License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).*/
import {Component} from "@odoo/owl";

import {_lt} from "@web/core/l10n/translation";
import {registry} from "@web/core/registry";
import {standardFieldProps} from "@web/views/fields/standard_field_props";
import {useService} from "@web/core/utils/hooks";

export class LocationTrayMatrixField extends Component {
    static template = "stock_vlm_mgmt.location_tray_matrix";
    static props = {
        ...standardFieldProps,
        click_action: {
            type: String,
            optional: true,
        },
    };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
    }

    get value() {
        const value = this.props.record.data[this.props.name] || {};
        return {
            cells: value.cells || [],
            selected: value.selected || [],
        };
    }
    /**
     *
     * @param {Event} event
     * @returns {Object} Odoo action
     */
    async onClickCell(event) {
        const coordinates = event.currentTarget.dataset.coordinates
            .split(",")
            .map((x) => {
                return parseInt(x, 10);
            });
        if (this.props.click_action) {
            const action = await this.orm.call(
                this.props.record.resModel,
                this.props.click_action,
                [[this.props.record.resId]],
                {pos_x: coordinates[0], pos_y: coordinates[1]}
            );
            return this.action.doAction(action);
        }
        // And here we propagate the changes to the field
        const value = {...this.value};
        value.selected = coordinates;
        this.props.record.update({[this.props.name]: value});
    }
}

export const locationTrayMatrixField = {
    component: LocationTrayMatrixField,
    displayName: _lt("Tray storage layout"),
    supportedTypes: ["serialized"],
    extractProps: ({attrs, options}) => {
        if ("click_action" in options) {
            return {click_action: options.click_action};
        }
        return {};
    },
};

registry.category("fields").add("location_tray_matrix", locationTrayMatrixField);
