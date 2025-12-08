odoo.define('distribution_channel.main', function (require) {
    'use strict';

    const core = require('web.core');
    const rpc = require('web.rpc');
    const QWeb = core.qweb;

    // Log ketika module load
    console.log('Distribution Channel module loaded');

    // Render DC Badge
    const renderDcBadge = function(dcCompany) {
        if (dcCompany) {
            return QWeb.render('distribution_channel.DcBadge', {
                dc_company: dcCompany
            });
        }
        return '';
    };

    // Render Stock Warning
    const renderStockWarning = function(qtyAvailable) {
        return QWeb.render('distribution_channel.StockWarning', {
            qty_available: qtyAvailable
        });
    };

    // Render Monitor Status
    const renderMonitorStatus = function(state, createDate) {
        return QWeb.render('distribution_channel.MonitorStatus', {
            state: state,
            create_date: createDate
        });
    };

    // RPC: Sync DC Sales Orders
    const syncDcSalesOrders = function() {
        return rpc.query({
            model: 'purchase.order',
            method: '_cron_create_dc_sales_orders',
            args: [],
        }).then(function(result) {
            console.log('✓ DC SO sync completed:', result);
            return result;
        }).catch(function(error) {
            console.error('✗ DC SO sync failed:', error);
        });
    };

    // RPC: Get PO Candidates
    const getPoCandidates = function() {
        return rpc.query({
            model: 'purchase.order',
            method: 'search',
            args: [[
                ('dc_sales_order_id', '=', False),
                ('orderpoint_id', '!=', False),
                ('state', 'in', ['draft', 'sent', 'to approve', 'purchase']),
            ]],
        });
    };

    // RPC: Get Monitor Status
    const getMonitorStatus = function() {
        return rpc.query({
            model: 'dc.order.monitor',
            method: 'search_read',
            args: [[], ['id', 'state', 'create_date', 'retailer_po_id', 'dc_sales_order_id']],
            kwargs: { limit: 10, order: 'create_date desc' },
        });
    };

    console.log('Distribution Channel QWeb templates loaded');

    // Export functions
    return {
        renderDcBadge: renderDcBadge,
        renderStockWarning: renderStockWarning,
        renderMonitorStatus: renderMonitorStatus,
        syncDcSalesOrders: syncDcSalesOrders,
        getPoCandidates: getPoCandidates,
        getMonitorStatus: getMonitorStatus,
    };
});