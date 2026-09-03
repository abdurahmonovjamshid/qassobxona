// "Yangi xarid" formasi: ombor mahsuloti uchun qidiruvli (rasmli) tanlagich
// va real-time summalar (xarid summasi, xarajatlar jami, umumiy xarajat).
(function () {
    'use strict';

    const formatMoney = window.formatMoney;
    const attachSearchPicker = window.attachSearchPicker;

    function initProductPicker(products) {
        const root = document.querySelector('[data-picker="product"]');
        if (!root) return;
        const select = root.querySelector('[data-role="product-select"]');
        const thumbBox = root.querySelector('.picker-selected');

        function updateThumb(product) {
            if (!thumbBox) return;
            if (product && product.image) {
                thumbBox.innerHTML = `<img src="${product.image}" class="product-thumb" alt=""><span class="small text-muted">${product.unit}</span>`;
            } else if (product) {
                thumbBox.innerHTML = `<div class="product-thumb-placeholder">🥩</div><span class="small text-muted">${product.unit}</span>`;
            } else {
                thumbBox.innerHTML = '';
            }
        }

        attachSearchPicker({
            root, select, items: products,
            placeholder: 'Mahsulot qidiring (masalan: Mol butun)...',
            matchText: (p) => p.name,
            renderItem: (p) => `
                ${p.image ? `<img src="${p.image}" class="product-thumb">` : '<div class="product-thumb-placeholder">🥩</div>'}
                <div class="fw-medium">${p.name}</div>
            `,
            onSelect: (product) => updateThumb(product),
        });
    }

    function recalcTotals() {
        const netWeight = parseFloat(document.querySelector('[data-role="net-weight"]')?.value) || 0;
        const pricePerKg = parseFloat(document.querySelector('[data-role="price-per-kg"]')?.value) || 0;
        const purchaseAmount = netWeight * pricePerKg;

        let expensesTotal = 0;
        document.querySelectorAll('[data-role="expense-amount"]').forEach((input) => {
            expensesTotal += parseFloat(input.value) || 0;
        });

        const purchaseAmountBox = document.getElementById('purchase-amount-total');
        const expensesTotalBox = document.getElementById('expenses-total');
        const grandTotalBox = document.getElementById('grand-total');
        if (purchaseAmountBox) purchaseAmountBox.textContent = formatMoney(purchaseAmount) + " so'm";
        if (expensesTotalBox) expensesTotalBox.textContent = formatMoney(expensesTotal) + " so'm";
        if (grandTotalBox) grandTotalBox.textContent = formatMoney(purchaseAmount + expensesTotal) + " so'm";
    }

    window.PurchaseFormInit = function (products, formsetPrefix) {
        initProductPicker(products);

        ['[data-role="net-weight"]', '[data-role="price-per-kg"]'].forEach((sel) => {
            const el = document.querySelector(sel);
            if (el) el.addEventListener('input', recalcTotals);
        });

        const expenseRows = document.getElementById('expense-rows');
        if (expenseRows) {
            expenseRows.addEventListener('input', (e) => {
                if (e.target.matches('[data-role="expense-amount"]')) recalcTotals();
            });
        }

        initFormset({
            containerId: 'expense-rows',
            prefix: formsetPrefix,
            templateId: 'expense-empty-form',
            onRowAdded: recalcTotals,
            onRowRemoved: recalcTotals,
        });

        recalcTotals();
    };
})();
