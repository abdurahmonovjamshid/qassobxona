// "Yangi xarid" formasi: sotuv sahifasidagi kabi mahsulot katalogi
// (qidiruv + kategoriya filtri) va savatcha — har bir qatorda netto vazn,
// soni, narx/kg va umumiy summa kiritiladi (narx/kg va summa bir-biridan
// avtomatik hisoblanadi: qaysi biri tahrirlansa, ikkinchisi shunga qarab
// yangilanadi). Submitda savatcha formset yashirin inputlariga
// sinxronlanadi. Pastda qo'shimcha xarajatlar formset.js naqshi bilan qoladi.
(function () {
    'use strict';

    const formatMoney = window.formatMoney;

    window.PurchaseFormInit = function ({ products, initialCart, expenseFormsetPrefix }) {
        let cart = (initialCart || []).map((c) => ({
            productId: c.id,
            name: c.name,
            unit: c.unit,
            image: c.image,
            netWeight: parseFloat(c.net_weight) || 0,
            pieces: parseInt(c.pieces, 10) || 0,
            pricePerKg: parseFloat(c.price_per_kg) || 0,
        }));

        const catalogEl = document.getElementById('product-catalog');
        const catalogEmptyEl = document.getElementById('catalog-empty');
        const searchInput = document.getElementById('catalog-search');
        const categorySearchInput = document.getElementById('category-search');
        const categoryChecklistEl = document.getElementById('category-checklist');
        const cartLinesEl = document.getElementById('cart-lines');
        const cartEmptyEl = document.getElementById('cart-empty');
        const hiddenItemsEl = document.getElementById('hidden-items');
        const totalFormsInput = document.getElementById('id_items-TOTAL_FORMS');
        const cartBarCount = document.getElementById('cart-bar-count');
        const cartBarTotal = document.getElementById('cart-bar-total');
        const itemsTotalEls = [document.getElementById('items-total'), document.getElementById('items-total-2')];
        const paidAmountInput = document.getElementById('id_paid_amount');
        const payFullBtn = document.getElementById('pay-full');
        const payHalfBtn = document.getElementById('pay-half');
        if (!catalogEl || !totalFormsInput) return;

        // To'lov mahsulotlar summasiga (netto x narx) nisbatan hisoblanadi —
        // xaridning supplierga qarzi ham shu summadan iborat (qo'shimcha
        // xarajatlar supplierga emas, tannarxga qo'shiladi).
        let currentItemsTotal = 0;
        // Foydalanuvchi to'lov maydonini o'zi tahrirlagach (yoki tugma bosgach),
        // avtomatik to'ldirish to'xtaydi — aks holda uning kiritgan qiymati
        // ustidan yozib yuborilmasligi kerak.
        let paidAmountTouched = paidAmountInput ? parseFloat(paidAmountInput.value || '0') !== 0 : true;
        if (paidAmountInput) {
            paidAmountInput.addEventListener('input', () => { paidAmountTouched = true; });
        }
        if (payFullBtn) {
            payFullBtn.addEventListener('click', () => {
                paidAmountTouched = true;
                if (paidAmountInput) paidAmountInput.value = Math.round(currentItemsTotal);
            });
        }
        if (payHalfBtn) {
            payHalfBtn.addEventListener('click', () => {
                paidAmountTouched = true;
                if (paidAmountInput) paidAmountInput.value = Math.round(currentItemsTotal / 2);
            });
        }

        // --- Kategoriya checklisti ---
        const allCategories = [];
        const seenCategories = new Set();
        products.forEach((p) => {
            if (p.category && !seenCategories.has(p.category)) {
                seenCategories.add(p.category);
                allCategories.push({ code: p.category, label: p.category_label || p.category });
            }
        });
        const checkedCategories = new Set(allCategories.map((c) => c.code));

        function renderCategoryChecklist() {
            if (!categoryChecklistEl) return;
            const q = (categorySearchInput.value || '').trim().toLowerCase();
            categoryChecklistEl.innerHTML = '';
            allCategories
                .filter((c) => c.label.toLowerCase().includes(q))
                .forEach((c) => {
                    const id = `cat-${c.code}`;
                    const wrap = document.createElement('div');
                    wrap.className = 'form-check';
                    wrap.innerHTML = `
                        <input class="form-check-input" type="checkbox" id="${id}"${checkedCategories.has(c.code) ? ' checked' : ''}>
                        <label class="form-check-label" for="${id}">${c.label}</label>`;
                    wrap.querySelector('input').addEventListener('change', (e) => {
                        if (e.target.checked) checkedCategories.add(c.code);
                        else checkedCategories.delete(c.code);
                        renderCatalog();
                    });
                    categoryChecklistEl.appendChild(wrap);
                });
        }

        function addToCart(product, netWeight, pieces, pricePerKg) {
            // Bitta mahsulot bir nechta alohida qatorda bo'lishi mumkin
            // (masalan turli narx/vaznli hayvonlar) — birlashtirilmaydi.
            cart.push({
                productId: product.id,
                name: product.name,
                unit: product.unit,
                image: product.image,
                netWeight: netWeight || 0,
                pieces: pieces || 0,
                pricePerKg: pricePerKg || 0,
            });
            renderAll();
        }

        function removeFromCart(index) {
            cart.splice(index, 1);
            renderAll();
        }

        function renderCatalog() {
            const q = (searchInput.value || '').trim().toLowerCase();
            let filtered = products.filter((p) => checkedCategories.has(p.category));
            if (q) filtered = filtered.filter((p) => p.name.toLowerCase().includes(q));
            catalogEl.innerHTML = '';
            catalogEmptyEl.classList.toggle('d-none', filtered.length > 0);
            filtered.forEach((p) => {
                const inCartLines = cart.filter((c) => c.productId === p.id);
                const inCartNet = inCartLines.reduce((s, c) => s + c.netWeight, 0);
                const inCartPieces = inCartLines.reduce((s, c) => s + c.pieces, 0);
                const inCartSumma = inCartLines.reduce((s, c) => s + c.netWeight * c.pricePerKg, 0);
                const avgPrice = inCartNet > 0 ? inCartSumma / inCartNet : 0;
                const img = p.image
                    ? `<img src="${p.image}" class="product-card-img" alt="">`
                    : '<div class="product-card-img-placeholder">🥩</div>';
                const wrap = document.createElement('div');
                wrap.className = 'col-6 col-md-4 col-lg-3';
                wrap.innerHTML = `
                    <div class="card product-card h-100${inCartLines.length > 0 ? ' in-cart' : ''}">
                        ${img}
                        <div class="card-body p-2">
                            <div class="product-card-name"><span class="badge bg-secondary-subtle text-dark me-1">${p.category_label || p.category}</span>${p.name}</div>
                            ${inCartLines.length > 0 ? `<div class="product-card-in-cart">Tanlangan: ${inCartNet.toFixed(3)} kg, ${inCartPieces} dona, ${formatMoney(avgPrice)} so'm/kg</div>` : ''}
                            <div class="d-flex flex-wrap gap-1 mt-2">
                                <input type="number" class="form-control form-control-sm catalog-net" inputmode="decimal" step="0.001" min="0" placeholder="Netto kg">
                                <input type="number" class="form-control form-control-sm catalog-pieces" inputmode="numeric" step="1" min="0" placeholder="Soni">
                                <input type="number" class="form-control form-control-sm catalog-price" inputmode="decimal" step="0.01" min="0" placeholder="Narx/kg">
                            </div>
                            <button type="button" class="btn btn-sm btn-primary w-100 mt-2 catalog-add">+ Qo'shish</button>
                            <div class="small text-danger mt-1 d-none catalog-error"></div>
                        </div>
                    </div>`;
                const netInput = wrap.querySelector('.catalog-net');
                const piecesInput = wrap.querySelector('.catalog-pieces');
                const priceInput = wrap.querySelector('.catalog-price');
                const errorEl = wrap.querySelector('.catalog-error');
                function doAdd() {
                    errorEl.classList.add('d-none');
                    const net = parseFloat(netInput.value) || 0;
                    const pieces = parseInt(piecesInput.value, 10) || 0;
                    const price = parseFloat(priceInput.value) || 0;
                    if (net <= 0) {
                        errorEl.textContent = "Netto vazn (kg) kiriting.";
                        errorEl.classList.remove('d-none');
                        netInput.focus();
                        return;
                    }
                    addToCart(p, net, pieces, price);
                }
                wrap.querySelector('.catalog-add').addEventListener('click', doAdd);
                [netInput, piecesInput, priceInput].forEach((el) => {
                    el.addEventListener('keydown', (e) => {
                        if (e.key === 'Enter') { e.preventDefault(); doAdd(); }
                    });
                });
                catalogEl.appendChild(wrap);
            });
        }

        function updateItemsTotal() {
            let sum = 0;
            cart.forEach((it) => { sum += it.netWeight * it.pricePerKg; });
            currentItemsTotal = sum;
            itemsTotalEls.forEach((el) => { if (el) el.textContent = formatMoney(sum) + " so'm"; });
            if (cartBarTotal) cartBarTotal.textContent = formatMoney(sum);
            if (cartBarCount) cartBarCount.textContent = `${cart.length} mahsulot`;
            if (paidAmountInput && !paidAmountTouched) paidAmountInput.value = Math.round(sum);
            if (window.PurchaseFormRecalcGrandTotal) window.PurchaseFormRecalcGrandTotal();
            renderCatalog();
            return sum;
        }

        function renderCart() {
            cartLinesEl.innerHTML = '';
            cartEmptyEl.classList.toggle('d-none', cart.length > 0);
            cart.forEach((item, index) => {
                const lineTotal = item.netWeight * item.pricePerKg;
                const img = item.image
                    ? `<img src="${item.image}" class="product-thumb" alt="">`
                    : '<div class="product-thumb-placeholder">🥩</div>';
                const row = document.createElement('div');
                row.className = 'cart-line flex-wrap';
                row.innerHTML = `
                    ${img}
                    <div class="flex-grow-1">
                        <div class="fw-medium small">${item.name}</div>
                        <div class="d-flex gap-1 flex-wrap align-items-center mt-1">
                            <input type="number" class="form-control form-control-sm cart-net" style="width:90px" step="0.001" min="0" placeholder="Netto kg" value="${item.netWeight || ''}">
                            <input type="number" class="form-control form-control-sm cart-pieces" style="width:70px" step="1" min="0" placeholder="Soni" value="${item.pieces || ''}">
                            <input type="number" class="form-control form-control-sm cart-price" style="width:100px" step="0.01" min="0" placeholder="Narx/kg" value="${item.pricePerKg || ''}">
                            <input type="number" class="form-control form-control-sm cart-summa" style="width:110px" step="1" min="0" placeholder="Summa" value="${lineTotal || ''}">
                        </div>
                    </div>
                    <div class="text-end">
                        <div class="line-total small">${formatMoney(lineTotal)}</div>
                        <button type="button" class="row-remove-btn" title="O'chirish">✕</button>
                    </div>`;
                const netEl = row.querySelector('.cart-net');
                const piecesEl = row.querySelector('.cart-pieces');
                const priceEl = row.querySelector('.cart-price');
                const summaEl = row.querySelector('.cart-summa');
                function updateLineTotalDisplay() {
                    const total = item.netWeight * item.pricePerKg;
                    row.querySelector('.line-total').textContent = formatMoney(total);
                    updateItemsTotal();
                    syncHiddenFormset();
                }
                function onNetOrPieces() {
                    item.netWeight = parseFloat(netEl.value) || 0;
                    item.pieces = parseInt(piecesEl.value, 10) || 0;
                    // Netto o'zgarganda narx/kg saqlanadi, summa shunga qarab qayta hisoblanadi.
                    summaEl.value = (item.netWeight * item.pricePerKg) || '';
                    updateLineTotalDisplay();
                }
                function onPrice() {
                    item.pricePerKg = parseFloat(priceEl.value) || 0;
                    summaEl.value = (item.netWeight * item.pricePerKg) || '';
                    updateLineTotalDisplay();
                }
                function onSumma() {
                    const summa = parseFloat(summaEl.value) || 0;
                    item.pricePerKg = item.netWeight > 0 ? summa / item.netWeight : 0;
                    priceEl.value = item.pricePerKg ? Math.round(item.pricePerKg * 100) / 100 : '';
                    updateLineTotalDisplay();
                }
                netEl.addEventListener('input', onNetOrPieces);
                piecesEl.addEventListener('input', onNetOrPieces);
                priceEl.addEventListener('input', onPrice);
                summaEl.addEventListener('input', onSumma);
                row.querySelector('.row-remove-btn').addEventListener('click', () => removeFromCart(index));
                cartLinesEl.appendChild(row);
            });
            updateItemsTotal();
        }

        function syncHiddenFormset() {
            hiddenItemsEl.innerHTML = '';
            totalFormsInput.value = String(cart.length);
            cart.forEach((item, i) => {
                const wrap = document.createElement('div');
                wrap.innerHTML = `
                    <input type="hidden" name="items-${i}-product" value="${item.productId}">
                    <input type="hidden" name="items-${i}-net_weight" value="${item.netWeight}">
                    <input type="hidden" name="items-${i}-pieces" value="${item.pieces || 0}">
                    <input type="hidden" name="items-${i}-price_per_kg" value="${item.pricePerKg}">`;
                hiddenItemsEl.appendChild(wrap);
            });
        }

        function renderAll() {
            renderCart();
            syncHiddenFormset();
            renderCatalog();
        }

        searchInput.addEventListener('input', renderCatalog);
        if (categorySearchInput) categorySearchInput.addEventListener('input', renderCategoryChecklist);

        document.getElementById('purchase-form').addEventListener('submit', (e) => {
            if (cart.length === 0) {
                e.preventDefault();
                alert("Kamida bitta mahsulot tanlang.");
                const offcanvasEl = document.getElementById('cartOffcanvas');
                if (window.bootstrap && offcanvasEl) {
                    window.bootstrap.Offcanvas.getOrCreateInstance(offcanvasEl).show();
                }
            }
        });

        // --- Qo'shimcha xarajatlar (mavjud formset.js naqshi) ---
        function recalcExpensesAndGrandTotal() {
            let expensesTotal = 0;
            document.querySelectorAll('[data-role="expense-amount"]').forEach((input) => {
                expensesTotal += parseFloat(input.value) || 0;
            });
            const itemsTotal = cart.reduce((s, it) => s + it.netWeight * it.pricePerKg, 0);
            const expensesTotalBox = document.getElementById('expenses-total');
            const grandTotalBox = document.getElementById('grand-total');
            if (expensesTotalBox) expensesTotalBox.textContent = formatMoney(expensesTotal) + " so'm";
            if (grandTotalBox) grandTotalBox.textContent = formatMoney(itemsTotal + expensesTotal) + " so'm";
        }
        window.PurchaseFormRecalcGrandTotal = recalcExpensesAndGrandTotal;

        const expenseRows = document.getElementById('expense-rows');
        if (expenseRows) {
            expenseRows.addEventListener('input', (e) => {
                if (e.target.matches('[data-role="expense-amount"]')) recalcExpensesAndGrandTotal();
            });
        }
        initFormset({
            containerId: 'expense-rows',
            prefix: expenseFormsetPrefix,
            templateId: 'expense-empty-form',
            onRowAdded: recalcExpensesAndGrandTotal,
            onRowRemoved: recalcExpensesAndGrandTotal,
        });

        renderCategoryChecklist();
        renderAll();
        recalcExpensesAndGrandTotal();
    };
})();
