// "Yangi sotuv" formasi: katalog (kartochkalar) + savatcha (POS uslubi).
// Mijoz qidiruvli tanlagich orqali (picker.js), mahsulotlar kartochka
// ko'rinishida tanlanadi va miqdor kiritilib savatchaga qo'shiladi.
// Yakuniy submitda savatcha formset yashirin inputlariga sinxronlanadi.
(function () {
    'use strict';

    const formatMoney = window.formatMoney;
    const attachSearchPicker = window.attachSearchPicker;

    // Ombor qoldig'ini har doim "50.5" kabi aniq bitta kasr xona bilan
    // ko'rsatish uchun (haqiqiy hisob-kitoblarda to'liq aniqlik saqlanadi,
    // faqat ko'rinishda yaxlitlanadi).
    function formatStock(n) {
        return (Math.round(n * 10) / 10).toFixed(1);
    }

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

    window.SaleFormInit = function (data) {
        initCustomerPicker(data);

        const products = data.products || [];
        let cart = (data.initialCart || []).map((c) => ({
            productId: c.id,
            name: c.name,
            unit: c.unit,
            image: c.image,
            quantity: parseFloat(c.quantity) || 0,
            price: parseFloat(c.price) || 0,
            discount: parseFloat(c.discount) || 0,
        }));

        const catalogEl = document.getElementById('product-catalog');
        const catalogEmptyEl = document.getElementById('catalog-empty');
        const searchInput = document.getElementById('catalog-search');
        const categorySearchInput = document.getElementById('category-search');
        const categoryChecklistEl = document.getElementById('category-checklist');
        const showOutOfStockEl = document.getElementById('show-out-of-stock');
        const cartLinesEl = document.getElementById('cart-lines');
        const cartEmptyEl = document.getElementById('cart-empty');
        const hiddenItemsEl = document.getElementById('hidden-items');
        const totalFormsInput = document.getElementById('id_items-TOTAL_FORMS');
        const cartBarCount = document.getElementById('cart-bar-count');
        const cartBarTotal = document.getElementById('cart-bar-total');
        const grandTotalEl = document.getElementById('grand-total');
        const paidAmountInput = document.getElementById('id_paid_amount');
        const payFullBtn = document.getElementById('pay-full');
        const payHalfBtn = document.getElementById('pay-half');
        if (!catalogEl || !totalFormsInput) return;

        let currentGrandTotal = 0;

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

        function cartQtyFor(productId) {
            return cart.filter((c) => c.productId === productId).reduce((s, c) => s + c.quantity, 0);
        }

        function remainingStock(product) {
            return (parseFloat(product.stock) || 0) - cartQtyFor(product.id);
        }

        function addToCart(product, qty) {
            const existing = cart.find((c) => c.productId === product.id);
            if (existing) {
                existing.quantity = Math.round((existing.quantity + qty) * 1000) / 1000;
            } else {
                cart.push({
                    productId: product.id,
                    name: product.name,
                    unit: product.unit,
                    image: product.image,
                    quantity: qty,
                    price: parseFloat(product.price) || 0,
                    discount: 0,
                });
            }
            renderAll();
        }

        function removeFromCart(index) {
            cart.splice(index, 1);
            renderAll();
        }

        function renderCatalog() {
            const q = (searchInput.value || '').trim().toLowerCase();
            const showOOS = !!(showOutOfStockEl && showOutOfStockEl.checked);
            let filtered = products.filter((p) => checkedCategories.has(p.category));
            if (q) filtered = filtered.filter((p) => p.name.toLowerCase().includes(q));
            if (!showOOS) {
                filtered = filtered.filter((p) => remainingStock(p) > 0 || cartQtyFor(p.id) > 0);
            }
            catalogEl.innerHTML = '';
            catalogEmptyEl.classList.toggle('d-none', filtered.length > 0);
            filtered.forEach((p) => {
                const remaining = remainingStock(p);
                const stockText = remaining <= 0 ? "Omborda yo'q" : `${formatStock(remaining)} ${p.unit} mavjud`;
                const stockClass = remaining <= 0 ? 'text-danger' : 'text-muted';
                const inCartQty = cartQtyFor(p.id);
                const img = p.image
                    ? `<img src="${p.image}" class="product-card-img" alt="">`
                    : '<div class="product-card-img-placeholder">🥩</div>';
                const wrap = document.createElement('div');
                wrap.className = 'col-6 col-md-4 col-lg-3';
                wrap.innerHTML = `
                    <div class="card product-card h-100${inCartQty > 0 ? ' in-cart' : ''}">
                        ${img}
                        <div class="card-body p-2">
                            <div class="product-card-name">${p.name}</div>
                            <div class="product-card-price">${formatMoney(parseFloat(p.price))} so'm/${p.unit}</div>
                            <div class="product-card-stock ${stockClass}">${stockText}</div>
                            ${inCartQty > 0 ? `<div class="product-card-in-cart">Savatda: ${formatStock(inCartQty)} ${p.unit}</div>` : ''}
                            <div class="d-flex gap-1 mt-2">
                                <input type="number" class="form-control form-control-sm catalog-qty" inputmode="decimal" step="0.001" min="0" placeholder="kg">
                                <button type="button" class="btn btn-sm btn-primary catalog-add">+</button>
                            </div>
                            <div class="small text-danger mt-1 d-none catalog-error"></div>
                        </div>
                    </div>`;
                const qtyInput = wrap.querySelector('.catalog-qty');
                const addBtn = wrap.querySelector('.catalog-add');
                const errorEl = wrap.querySelector('.catalog-error');
                function doAdd() {
                    errorEl.classList.add('d-none');
                    const qty = parseFloat(qtyInput.value);
                    if (!qty || qty <= 0) {
                        qtyInput.focus();
                        return;
                    }
                    const avail = remainingStock(p);
                    if (qty > avail) {
                        errorEl.textContent = avail > 0
                            ? `Omborda faqat ${formatStock(avail)} ${p.unit} bor.`
                            : "Bu mahsulot omborda yo'q.";
                        errorEl.classList.remove('d-none');
                        qtyInput.focus();
                        return;
                    }
                    addToCart(p, qty);
                }
                addBtn.addEventListener('click', doAdd);
                qtyInput.addEventListener('keydown', (e) => {
                    if (e.key === 'Enter') { e.preventDefault(); doAdd(); }
                });
                catalogEl.appendChild(wrap);
            });
        }

        function updateGrandTotal() {
            let sum = 0;
            cart.forEach((it) => {
                sum += Math.max(0, it.quantity * it.price - it.discount);
            });
            currentGrandTotal = sum;
            grandTotalEl.textContent = formatMoney(sum) + " so'm";
            cartBarTotal.textContent = formatMoney(sum);
            cartBarCount.textContent = `${cart.length} mahsulot`;
        }

        function renderCart() {
            cartLinesEl.innerHTML = '';
            cartEmptyEl.classList.toggle('d-none', cart.length > 0);
            cart.forEach((item, index) => {
                const lineTotal = Math.max(0, item.quantity * item.price - item.discount);
                const img = item.image
                    ? `<img src="${item.image}" class="product-thumb" alt="">`
                    : '<div class="product-thumb-placeholder">🥩</div>';
                const row = document.createElement('div');
                row.className = 'cart-line';
                row.innerHTML = `
                    ${img}
                    <div class="flex-grow-1">
                        <div class="fw-medium small">${item.name}</div>
                        <div class="d-flex gap-1 align-items-center mt-1">
                            <input type="number" class="form-control form-control-sm cart-qty" style="width:75px" step="0.001" min="0.001" value="${item.quantity}">
                            <span class="small text-muted">${item.unit} ×</span>
                            <input type="number" class="form-control form-control-sm cart-price" style="width:95px" step="0.01" min="0" value="${item.price}">
                        </div>
                    </div>
                    <div class="text-end">
                        <div class="line-total small">${formatMoney(lineTotal)}</div>
                        <button type="button" class="row-remove-btn" title="O'chirish">✕</button>
                    </div>`;
                const qtyEl = row.querySelector('.cart-qty');
                const priceEl = row.querySelector('.cart-price');
                function liveUpdate() {
                    // Faqat shu qatorning summasini yangilaydi — butun ro'yxatni
                    // qayta chizmaydi, aks holda inputdagi fokus (va telefonda
                    // teriladigan raqam) har harfda uzilib qolardi.
                    item.quantity = parseFloat(qtyEl.value) || 0;
                    item.price = parseFloat(priceEl.value) || 0;
                    const newTotal = Math.max(0, item.quantity * item.price - item.discount);
                    row.querySelector('.line-total').textContent = formatMoney(newTotal);
                    updateGrandTotal();
                    syncHiddenFormset();
                }
                qtyEl.addEventListener('input', liveUpdate);
                priceEl.addEventListener('input', liveUpdate);
                // Fokusdan chiqqanda: ombordan ko'p miqdor kiritilgan bo'lsa
                // qoldiqqa moslashtirish, bo'sh/0 qatorlarni tozalash va
                // katalogdagi ombor ko'rsatkichini yangilash uchun to'liq
                // qayta chizish.
                function handleBlur() {
                    const product = products.find((pp) => pp.id === item.productId);
                    const stock = product ? (parseFloat(product.stock) || 0) : Infinity;
                    if (item.quantity > stock) {
                        alert(`Omborda faqat ${formatStock(stock)} ${item.unit} bor. Miqdor shunga moslashtirildi.`);
                        item.quantity = stock;
                    }
                    renderAll();
                }
                qtyEl.addEventListener('change', handleBlur);
                priceEl.addEventListener('change', renderAll);
                row.querySelector('.row-remove-btn').addEventListener('click', () => removeFromCart(index));
                cartLinesEl.appendChild(row);
            });
            updateGrandTotal();
        }

        function syncHiddenFormset() {
            hiddenItemsEl.innerHTML = '';
            totalFormsInput.value = String(cart.length);
            cart.forEach((item, i) => {
                const wrap = document.createElement('div');
                wrap.innerHTML = `
                    <input type="hidden" name="items-${i}-product" value="${item.productId}">
                    <input type="hidden" name="items-${i}-quantity" value="${item.quantity}">
                    <input type="hidden" name="items-${i}-price" value="${item.price}">
                    <input type="hidden" name="items-${i}-discount" value="${item.discount || 0}">`;
                hiddenItemsEl.appendChild(wrap);
            });
        }

        function renderAll() {
            cart = cart.filter((c) => c.quantity > 0);
            renderCart();
            syncHiddenFormset();
            renderCatalog();
        }

        searchInput.addEventListener('input', renderCatalog);
        if (showOutOfStockEl) showOutOfStockEl.addEventListener('change', renderCatalog);
        if (categorySearchInput) categorySearchInput.addEventListener('input', renderCategoryChecklist);

        if (payFullBtn) {
            payFullBtn.addEventListener('click', () => {
                paidAmountInput.value = Math.round(currentGrandTotal);
            });
        }
        if (payHalfBtn) {
            payHalfBtn.addEventListener('click', () => {
                paidAmountInput.value = Math.round(currentGrandTotal / 2);
            });
        }

        document.getElementById('sale-form').addEventListener('submit', (e) => {
            if (cart.length === 0) {
                e.preventDefault();
                alert("Kamida bitta mahsulot tanlang.");
                const offcanvasEl = document.getElementById('cartOffcanvas');
                if (window.bootstrap && offcanvasEl) {
                    window.bootstrap.Offcanvas.getOrCreateInstance(offcanvasEl).show();
                }
            }
        });

        renderCategoryChecklist();
        renderAll();
    };
})();
