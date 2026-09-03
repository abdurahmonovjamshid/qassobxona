// "Yangi sotuv" formasi: mijoz/mahsulot qidiruvli tanlagichi (picker.js),
// qator o'chirish (bitta bosishda), va real-time qator/umumiy summa
// hisoblagichi.
(function () {
    'use strict';

    const formatMoney = window.formatMoney;
    const attachSearchPicker = window.attachSearchPicker;

    function initCustomerPicker(data) {
        const root = document.querySelector('[data-picker="customer"]');
        if (!root) return;
        const select = root.querySelector('[data-role="customer-select"]');
        attachSearchPicker({
            root, select, items: data.customers,
            placeholder: 'Mijoz ismini qidiring...',
            matchText: (c) => c.name,
            renderItem: (c) => `<div><div class="fw-medium">${c.name}</div><div class="small text-muted">${c.phone || ''}</div></div>`,
            onSelect: () => {},
        });
    }

    function initProductRow(row, data) {
        const root = row.querySelector('[data-picker="product"]');
        const select = row.querySelector('[data-role="product-select"]');
        const qtyInput = row.querySelector('[data-role="qty"]');
        const priceInput = row.querySelector('[data-role="price"]');
        const discountInput = row.querySelector('[data-role="discount"]');
        const lineTotalEl = row.querySelector('.line-total');
        const removeBtn = row.querySelector('.row-remove-btn');
        const thumbBox = root ? root.querySelector('.picker-selected') : null;

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

        function recalcRow() {
            const qty = parseFloat(qtyInput.value) || 0;
            const price = parseFloat(priceInput.value) || 0;
            const discount = parseFloat(discountInput.value) || 0;
            const total = Math.max(0, qty * price - discount);
            if (lineTotalEl) lineTotalEl.textContent = formatMoney(total);
            row.dataset.lineTotal = String(total);
            recalcGrandTotal();
        }

        if (root && select) {
            attachSearchPicker({
                root, select, items: data.products,
                placeholder: 'Mahsulot qidiring...',
                matchText: (p) => p.name,
                renderItem: (p) => `
                    ${p.image ? `<img src="${p.image}" class="product-thumb">` : '<div class="product-thumb-placeholder">🥩</div>'}
                    <div><div class="fw-medium">${p.name}</div><div class="small text-muted">${formatMoney(parseFloat(p.price))} so'm/${p.unit}</div></div>
                `,
                onSelect: (product, isInitial) => {
                    updateThumb(product);
                    if (!isInitial && !priceInput.value) {
                        priceInput.value = product.price;
                    }
                    recalcRow();
                },
            });
        }

        [qtyInput, priceInput, discountInput].forEach((el) => {
            if (el) el.addEventListener('input', recalcRow);
        });

        if (removeBtn) {
            removeBtn.addEventListener('click', () => {
                row.remove();
                recalcGrandTotal();
            });
        }

        recalcRow();
    }

    function recalcGrandTotal() {
        const box = document.getElementById('grand-total');
        if (!box) return;
        let sum = 0;
        document.querySelectorAll('#item-rows .formset-row').forEach((row) => {
            sum += parseFloat(row.dataset.lineTotal || '0');
        });
        box.textContent = formatMoney(sum) + " so'm";
    }

    function initAddRow(data) {
        const addBtn = document.getElementById('add-item-rows');
        const template = document.getElementById('item-empty-form');
        const tbody = document.getElementById('item-rows');
        const totalFormsInput = document.getElementById('id_items-TOTAL_FORMS');
        if (!addBtn || !template || !tbody || !totalFormsInput) return;

        addBtn.addEventListener('click', () => {
            const idx = parseInt(totalFormsInput.value, 10);
            const html = template.innerHTML.replace(/__prefix__/g, String(idx));
            const wrapper = document.createElement('div');
            wrapper.innerHTML = html;
            const newRow = wrapper.querySelector('tr.formset-row');
            if (!newRow) return;
            tbody.appendChild(newRow);
            totalFormsInput.value = String(idx + 1);
            initProductRow(newRow, data);
        });
    }

    window.SaleFormInit = function (data) {
        initCustomerPicker(data);
        document.querySelectorAll('#item-rows .formset-row').forEach((row) => initProductRow(row, data));
        initAddRow(data);
        recalcGrandTotal();
    };
})();
