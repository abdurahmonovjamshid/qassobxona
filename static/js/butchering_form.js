// "Yangi bo'laklash" formasi: xarid tanlanganda mahsulot/vazn avtomatik
// to'ldiriladi, sarlavhada bo'laklanayotgan mahsulot ko'rinadi, va
// output jami / farq / yield% real-time hisoblanadi.
(function () {
    'use strict';

    function productById(products, id) {
        return products.find((p) => String(p.id) === String(id));
    }

    function thumbHtml(product, size) {
        const cls = size === 'lg' ? '-lg' : '';
        if (product && product.image) {
            return `<img src="${product.image}" class="product-thumb${cls}" alt="">`;
        }
        return `<div class="product-thumb-placeholder${cls}">🥩</div>`;
    }

    window.ButcheringFormInit = function ({ products, purchases, formsetPrefix }) {
        const purchaseSelect = document.querySelector('[data-role="purchase-select"]');
        const inputProductSelect = document.querySelector('[data-role="input-product-select"]');
        const inputWeightInput = document.querySelector('[data-role="input-weight"]');
        const headerThumb = document.getElementById('input-product-thumb');
        const headerName = document.getElementById('input-product-name');
        const headerWeight = document.getElementById('input-weight-display');
        const outputTotalEl = document.getElementById('output-total');
        const diffTotalEl = document.getElementById('diff-total');
        const yieldTotalEl = document.getElementById('yield-total');
        const outputRows = document.getElementById('output-rows');

        function updateHeader() {
            const product = inputProductSelect ? productById(products, inputProductSelect.value) : null;
            if (headerThumb) headerThumb.innerHTML = thumbHtml(product, 'lg');
            if (headerName) headerName.textContent = product ? product.name : 'Mahsulot tanlanmagan';
            const weight = parseFloat(inputWeightInput ? inputWeightInput.value : 0) || 0;
            if (headerWeight) headerWeight.textContent = weight.toFixed(3) + ' kg';
        }

        function recalcOutputs() {
            let outputTotal = 0;
            outputRows.querySelectorAll('[data-role="output-qty"]').forEach((el) => {
                outputTotal += parseFloat(el.value) || 0;
            });
            const inputWeight = parseFloat(inputWeightInput ? inputWeightInput.value : 0) || 0;
            const diff = inputWeight - outputTotal;
            const yieldPct = inputWeight > 0 ? (outputTotal / inputWeight) * 100 : 0;

            if (outputTotalEl) outputTotalEl.textContent = outputTotal.toFixed(3) + ' kg';
            if (diffTotalEl) {
                diffTotalEl.textContent = diff.toFixed(3) + ' kg';
                diffTotalEl.classList.toggle('text-danger', diff < 0);
                diffTotalEl.classList.toggle('text-success', diff >= 0);
            }
            if (yieldTotalEl) {
                yieldTotalEl.textContent = yieldPct.toFixed(1) + '%';
                yieldTotalEl.classList.toggle('text-danger', diff < 0);
            }
        }

        function updateRowThumb(row) {
            const select = row.querySelector('[data-role="output-product"]');
            const holder = row.querySelector('.output-thumb');
            if (!select || !holder) return;
            const product = productById(products, select.value);
            holder.innerHTML = thumbHtml(product);
        }

        if (purchaseSelect) {
            purchaseSelect.addEventListener('change', () => {
                const purchase = purchases.find((p) => String(p.id) === String(purchaseSelect.value));
                if (purchase) {
                    if (inputProductSelect && purchase.product_id) inputProductSelect.value = purchase.product_id;
                    if (inputWeightInput) inputWeightInput.value = purchase.net_weight;
                }
                updateHeader();
                recalcOutputs();
            });
        }

        if (inputProductSelect) inputProductSelect.addEventListener('change', updateHeader);
        if (inputWeightInput) {
            inputWeightInput.addEventListener('input', () => {
                updateHeader();
                recalcOutputs();
            });
        }

        if (outputRows) {
            outputRows.querySelectorAll('.formset-row').forEach(updateRowThumb);
            outputRows.addEventListener('input', (e) => {
                if (e.target.matches('[data-role="output-qty"]')) recalcOutputs();
            });
            outputRows.addEventListener('change', (e) => {
                if (e.target.matches('[data-role="output-product"]')) {
                    updateRowThumb(e.target.closest('.formset-row'));
                }
            });
        }

        initFormset({
            containerId: 'output-rows',
            prefix: formsetPrefix,
            templateId: 'output-empty-form',
            onRowAdded: (row) => {
                updateRowThumb(row);
                recalcOutputs();
            },
            onRowRemoved: recalcOutputs,
        });

        updateHeader();
        recalcOutputs();
    };
})();
