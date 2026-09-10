// "Yangi bo'laklash" formasi: input mahsulot qidiruvli tanlagich (picker.js)
// orqali tanlanadi, sarlavhada bo'laklanayotgan mahsulot va ombor qoldig'i
// ko'rinadi. Chiqish (output) mahsulotlari sotuv/xarid sahifalaridagi kabi
// mahsulot kartochkasi ko'rinishida chiqadi — spetsifikatsiya (bo'laklash
// usuli) tanlanganda shu retseptdagi mahsulotlar uchun kartochkalar
// avtomatik hosil bo'ladi, foydalanuvchi faqat kg/dona kiritadi. Submitda
// kartochkalar formset yashirin inputlariga sinxronlanadi.
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

    // Ombor qoldig'ini "50.5" kabi bitta kasr xona bilan ko'rsatish uchun.
    function formatStock(n) {
        return (Math.round(n * 10) / 10).toFixed(1);
    }

    function renderProductPickerItem(p) {
        return `<div><span class="badge bg-secondary-subtle text-dark me-1">${p.category_label || p.category}</span>${p.name}</div>`;
    }

    // Mahsulot nomi bo'yicha VA kategoriya nomi bo'yicha ham qidirish mumkin
    // bo'lishi uchun (masalan "sigir" deb yozilsa shu kategoriyadagi barcha
    // mahsulotlar chiqadi) — inputga esa faqat mahsulot nomi yoziladi.
    function productSearchText(p) {
        return `${p.category_label || p.category || ''} ${p.name}`;
    }

    window.ButcheringFormInit = function ({ products, specifications, initialOutputs, formsetPrefix, expenseFormsetPrefix }) {
        specifications = specifications || [];
        const attachSearchPicker = window.attachSearchPicker;
        const inputProductSelect = document.querySelector('[data-role="input-product-select"]');
        const specificationSelect = document.querySelector('[data-role="specification-select"]');
        const inputWeightInput = document.querySelector('[data-role="input-weight"]');
        const inputPiecesInput = document.querySelector('[data-role="input-pieces"]');
        const headerThumb = document.getElementById('input-product-thumb');
        const headerName = document.getElementById('input-product-name');
        const headerWeight = document.getElementById('input-weight-display');
        const headerStock = document.getElementById('input-stock-display');

        // Bo'laklashga faqat kamida bitta faol spetsifikatsiyaga ega
        // mahsulotlar tanlanishi mumkin (backend queryset bilan mos).
        const inputProductIds = new Set(specifications.map((s) => String(s.parent_product_id)));
        const inputProducts = products.filter((p) => inputProductIds.has(String(p.id)));
        const outputTotalEl = document.getElementById('output-total');
        const diffTotalEl = document.getElementById('diff-total');
        const yieldTotalEl = document.getElementById('yield-total');
        const outputCardsEl = document.getElementById('output-cards');
        const outputCardsEmptyEl = document.getElementById('output-cards-empty');
        const hiddenOutputsEl = document.getElementById('hidden-outputs');
        const totalFormsInput = document.getElementById(`id_${formsetPrefix}-TOTAL_FORMS`);

        let outputs = (initialOutputs || []).map((o) => ({
            productId: o.id,
            name: o.name,
            image: o.image,
            quantity: parseFloat(o.quantity) || 0,
            pieces: parseInt(o.pieces, 10) || 0,
        }));

        function updateHeader() {
            const product = inputProductSelect ? productById(products, inputProductSelect.value) : null;
            if (headerThumb) headerThumb.innerHTML = thumbHtml(product, 'lg');
            if (headerName) headerName.textContent = product ? product.name : 'Mahsulot tanlanmagan';
            const weight = parseFloat(inputWeightInput ? inputWeightInput.value : 0) || 0;
            const pieces = parseInt(inputPiecesInput ? inputPiecesInput.value : 0, 10) || 0;
            if (headerWeight) headerWeight.textContent = `${weight.toFixed(3)} kg / ${pieces} dona`;
            if (headerStock) {
                if (product) {
                    const stock = parseFloat(product.stock) || 0;
                    const stockPieces = parseInt(product.stock_pieces, 10) || 0;
                    headerStock.textContent = `Ombor qoldig'i: ${formatStock(stock)} kg / ${stockPieces} dona`;
                    if (inputWeightInput) inputWeightInput.max = stock;
                    if (inputPiecesInput) inputPiecesInput.max = stockPieces;
                } else {
                    headerStock.textContent = "Ombor qoldig'i: —";
                    if (inputWeightInput) inputWeightInput.removeAttribute('max');
                    if (inputPiecesInput) inputPiecesInput.removeAttribute('max');
                }
            }
        }

        // Kiritilgan vazn/son ombor qoldig'idan oshib ketsa, qoldiqqa moslashtiradi.
        function clampInputToStock() {
            const product = inputProductSelect ? productById(products, inputProductSelect.value) : null;
            if (!product) return;
            const stock = parseFloat(product.stock) || 0;
            const stockPieces = parseInt(product.stock_pieces, 10) || 0;
            if (inputWeightInput) {
                const weight = parseFloat(inputWeightInput.value) || 0;
                if (weight > stock) {
                    alert(`Omborda faqat ${formatStock(stock)} kg "${product.name}" bor. Vazn shunga moslashtirildi.`);
                    inputWeightInput.value = stock;
                }
            }
            if (inputPiecesInput) {
                const pieces = parseInt(inputPiecesInput.value, 10) || 0;
                if (pieces > stockPieces) {
                    alert(`Omborda faqat ${stockPieces} dona "${product.name}" bor. Soni shunga moslashtirildi.`);
                    inputPiecesInput.value = stockPieces;
                }
            }
            updateHeader();
            recalcOutputs();
        }

        function recalcOutputs() {
            let outputTotal = 0;
            let piecesTotal = 0;
            outputs.forEach((o) => { outputTotal += o.quantity; piecesTotal += o.pieces; });
            const inputWeight = parseFloat(inputWeightInput ? inputWeightInput.value : 0) || 0;
            const diff = inputWeight - outputTotal;
            const yieldPct = inputWeight > 0 ? (outputTotal / inputWeight) * 100 : 0;

            if (outputTotalEl) outputTotalEl.textContent = `${outputTotal.toFixed(3)} kg / ${piecesTotal} dona`;
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

        function syncHiddenFormset() {
            hiddenOutputsEl.innerHTML = '';
            totalFormsInput.value = String(outputs.length);
            outputs.forEach((o, i) => {
                const wrap = document.createElement('div');
                wrap.innerHTML = `
                    <input type="hidden" name="${formsetPrefix}-${i}-product" value="${o.productId}">
                    <input type="hidden" name="${formsetPrefix}-${i}-quantity" value="${o.quantity}">
                    <input type="hidden" name="${formsetPrefix}-${i}-pieces" value="${o.pieces || 0}">`;
                hiddenOutputsEl.appendChild(wrap);
            });
        }

        function removeOutput(index) {
            outputs.splice(index, 1);
            renderOutputCards();
        }

        function renderOutputCards() {
            outputCardsEl.innerHTML = '';
            outputCardsEmptyEl.classList.toggle('d-none', outputs.length > 0);
            outputs.forEach((o, index) => {
                const product = productById(products, o.productId);
                const img = product && product.image
                    ? `<img src="${product.image}" class="product-card-img" alt="">`
                    : '<div class="product-card-img-placeholder">🥩</div>';
                const categoryBadge = product
                    ? `<span class="badge bg-secondary-subtle text-dark me-1">${product.category_label || product.category}</span>`
                    : '';
                const wrap = document.createElement('div');
                wrap.className = 'col-6 col-md-4 col-lg-3';
                wrap.innerHTML = `
                    <div class="card product-card h-100">
                        ${img}
                        <div class="card-body p-2">
                            <div class="product-card-name">${categoryBadge}${o.name}</div>
                            <div class="d-flex gap-1 mt-2">
                                <input type="number" class="form-control form-control-sm output-qty" inputmode="decimal" step="0.001" min="0" placeholder="kg" value="${o.quantity || ''}">
                                <input type="number" class="form-control form-control-sm output-pieces" inputmode="numeric" step="1" min="0" placeholder="dona" value="${o.pieces || ''}">
                            </div>
                            <button type="button" class="btn btn-sm btn-outline-danger w-100 mt-2 output-remove">✕ O'chirish</button>
                        </div>
                    </div>`;
                const qtyEl = wrap.querySelector('.output-qty');
                const piecesEl = wrap.querySelector('.output-pieces');
                function liveUpdate() {
                    o.quantity = parseFloat(qtyEl.value) || 0;
                    o.pieces = parseInt(piecesEl.value, 10) || 0;
                    recalcOutputs();
                    syncHiddenFormset();
                }
                qtyEl.addEventListener('input', liveUpdate);
                piecesEl.addEventListener('input', liveUpdate);
                wrap.querySelector('.output-remove').addEventListener('click', () => removeOutput(index));
                outputCardsEl.appendChild(wrap);
            });
            recalcOutputs();
            syncHiddenFormset();
        }

        function handleInputProductChange() {
            refreshSpecificationOptions();
            updateHeader();
            clampInputToStock();
        }

        if (attachSearchPicker && inputProductSelect) {
            const pickerRoot = document.querySelector('[data-picker="input-product"]');
            if (pickerRoot) {
                attachSearchPicker({
                    root: pickerRoot, select: inputProductSelect, items: inputProducts,
                    placeholder: 'Mahsulot yoki kategoriya nomini yozing...',
                    matchText: (p) => p.name,
                    searchText: productSearchText,
                    renderItem: renderProductPickerItem,
                    onSelect: handleInputProductChange,
                });
            }
        }
        if (inputWeightInput) {
            inputWeightInput.addEventListener('input', () => { updateHeader(); recalcOutputs(); });
            inputWeightInput.addEventListener('change', clampInputToStock);
        }
        if (inputPiecesInput) {
            inputPiecesInput.addEventListener('input', updateHeader);
            inputPiecesInput.addEventListener('change', clampInputToStock);
        }

        // --- Spetsifikatsiya (bo'laklash usuli) tanlash ---
        function refreshSpecificationOptions() {
            if (!specificationSelect) return;
            const productId = inputProductSelect ? inputProductSelect.value : null;
            const matching = specifications.filter((s) => String(s.parent_product_id) === String(productId));
            const currentValue = specificationSelect.value;
            specificationSelect.innerHTML = '<option value="">---------</option>';
            matching.forEach((s) => {
                const opt = document.createElement('option');
                opt.value = s.id;
                opt.textContent = s.name;
                specificationSelect.appendChild(opt);
            });
            if (matching.some((s) => String(s.id) === String(currentValue))) {
                specificationSelect.value = currentValue;
            }
        }

        function applySpecification() {
            if (!specificationSelect) return;
            const spec = specifications.find((s) => String(s.id) === String(specificationSelect.value));
            if (!spec) return;
            outputs = spec.items.map((item) => {
                const product = productById(products, item.child_product_id);
                return {
                    productId: item.child_product_id,
                    name: product ? product.name : '',
                    image: product ? product.image : null,
                    quantity: 0,
                    pieces: 0,
                };
            });
            renderOutputCards();
        }

        if (specificationSelect) specificationSelect.addEventListener('change', applySpecification);
        refreshSpecificationOptions();

        // --- Qo'shimcha xarajatlar (mavjud formset.js naqshi) ---
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
        renderOutputCards();
        recalcExpenses();
    };
})();
