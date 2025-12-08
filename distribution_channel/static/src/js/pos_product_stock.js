/** @odoo-module **/

import { PosGlobalState } from "@point_of_sale/app/store/pos_global_state";
import { patch } from "@web/core/utils/patch";

patch(PosGlobalState.prototype, "distribution_channel.StockLoader", {

    async loadServerData() {
        // 1. Jalankan loader asli
        await super.loadServerData();

        // 2. Ambil ulang product dengan qty_available
        const stock_data = await this.rpc({
            model: "product.product",
            method: "search_read",
            args: [[], ["id", "qty_available"]],
        });

        // 3. Map stock ke produk POS
        for (const p of stock_data) {
            const prod = this.db.product_by_id[p.id];
            if (prod) {
                prod.qty_available = p.qty_available ?? 0;
            }
        }

        console.warn("[DC POS] Stock loaded into POS:", stock_data.length, "products");
    },
});
