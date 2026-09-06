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

    window.ButcheringFormInit = function ({ products, purchases, specifications, formsetPrefix, expenseFormsetPrefix }) {
        specifications = specifications || [];
        const purchaseSelect = document.querySelector('[data-role="purchase-select"]');
        const inputProductSelect = document.querySelector('[data-role="input-product-select"]');
        const specificationSelect = document.querySelector('[data-role="specification-select"]');
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

        let currentPurchaseItems = [];

        function applyPurchaseItem() {
            if (!inputProductSelect) return;
            const match = currentPurchaseItems.find((it) => String(it.product_id) === String(inputProductSelect.value));
            if (match && inputWeightInput) inputWeightInput.value = match.net_weight;
        }

        if (purchaseSelect) {
            purchaseSelect.addEventListener('change', () => {
                const purchase = purchases.find((p) => String(p.id) === String(purchaseSelect.value));
                currentPurchaseItems = purchase ? purchase.items : [];
                if (currentPurchaseItems.length === 1 && inputProductSelect) {
                    inputProductSelect.value = currentPurchaseItems[0].product_id;
                    if (inputWeightInput) inputWeightInput.value = currentPurchaseItems[0].net_weight;
                }
                updateHeader();
                recalcOutputs();
            });
        }

        if (inputProductSelect) {
            inputProductSelect.addEventListener('change', () => {
                applyPurchaseItem();
                updateHeader();
            });
        }
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

        const outputFormset = initFormset({
            containerId: 'output-rows',
            prefix: formsetPrefix,
            templateId: 'output-empty-form',
            onRowAdded: (row) => {
                updateRowThumb(row);
                recalcOutputs();
            },
            onRowRemoved: recalcOutputs,
        });

        // --- Spetsifikatsiya (bo'laklash usuli) tanlash ---
        function refreshSpecificationOptions() {
            if (!specificationSelect) return;
            const productId = inputProductSelect ? inputProductSelect.value : null;
            const matching = specifications.filter((s) => String(s.parent_product_id) === String(productId));
            specificationSelect.innerHTML = '<option value="">---------</option>';
            matching.forEach((s) => {
                const opt = document.createElement('option');
                opt.value = s.id;
                opt.textContent = s.name;
                specificationSelect.appendChild(opt);
            });
        }

        function clearOutputRows() {
            const totalFormsInput = document.getElementById(`id_${formsetPrefix}-TOTAL_FORMS`);
            if (outputRows) outputRows.querySelectorAll('.formset-row').forEach((row) => row.remove());
            if (totalFormsInput) totalFormsInput.value = '0';
        }

        function applySpecification() {
            if (!specificationSelect) return;
            const spec = specifications.find((s) => String(s.id) === String(specificationSelect.value));
            if (!spec) return;
            clearOutputRows();
            spec.items.forEach((item) => {
                const row = outputFormset.addRow();
                if (!row) return;
                const productSelect = row.querySelector('[data-role="output-product"]');
                if (productSelect) productSelect.value = item.child_product_id;
                updateRowThumb(row);
            });
            recalcOutputs();
        }

        if (inputProductSelect) inputProductSelect.addEventListener('change', refreshSpecificationOptions);
        if (specificationSelect) specificationSelect.addEventListener('change', applySpecification);
        refreshSpecificationOptions();

        function recalcExpenses() {
            let total = 0;
            document.querySelectorAll('[data-role="butchering-expense-amount"]').forEach((el) => {
                total += parseFloat(el.value) || 0;
            });
            const el = document.getElementById('butchering-expenses-total');
            if (el) el.textContent = total.toLocaleString('uz-UZ') + " so'm";
        }
        const expenseRows = document.getElementById('expense-rows');
        if (expenseRows) {
            expenseRows.addEventListener('input', (e) => {
                if (e.target.matches('[data-role="butchering-expense-amount"]')) recalcExpenses();
            });
        }
        initFormset({
            containerId: 'expense-rows',
            prefix: expenseFormsetPrefix,
            templateId: 'expense-empty-form',
            onRowAdded: recalcExpenses,
            onRowRemoved: recalcExpenses,
        });

        updateHeader();
        recalcOutputs();
        recalcExpenses();
    };
})();
