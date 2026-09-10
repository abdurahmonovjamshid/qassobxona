// Umumiy yordamchilar: pul formatlash va qidiruvli tanlagich (matn input +
// natijalar ro'yxati, orqada haqiqiy yashirin <select> bilan sinxron).
// Sotuv, xarid va bo'laklash formalarida ishlatiladi.
window.formatMoney = function formatMoney(n) {
    return Math.round(n).toLocaleString('ru-RU').replace(/,/g, ' ');
};

window.attachSearchPicker = function attachSearchPicker({ root, select, items, renderItem, matchText, searchText, onSelect, placeholder }) {
    const searchInput = root.querySelector('.picker-search');
    const resultsBox = root.querySelector('.picker-results');
    if (!searchInput || !resultsBox || !select) return;

    // `searchText` qidiruv uchun ishlatiladi (masalan nom + kategoriya), `matchText`
    // esa tanlangandan keyin inputga yoziladigan ko'rinish uchun (odatda faqat nom).
    // Ko'pchilik chaqiruvlar ikkalasi bir xil bo'lgani uchun `searchText` ixtiyoriy.
    searchText = searchText || matchText;

    searchInput.placeholder = placeholder || 'Qidirish...';

    function renderResults(list) {
        resultsBox.innerHTML = '';
        if (!list.length) {
            resultsBox.innerHTML = '<div class="picker-result-empty">Topilmadi</div>';
        } else {
            list.forEach((item) => {
                const el = document.createElement('div');
                el.className = 'picker-result-item';
                el.innerHTML = renderItem(item);
                el.addEventListener('mousedown', (e) => {
                    e.preventDefault();
                    select.value = item.id;
                    searchInput.value = matchText(item);
                    resultsBox.style.display = 'none';
                    onSelect(item);
                });
                resultsBox.appendChild(el);
            });
        }
        resultsBox.style.display = 'block';
    }

    searchInput.addEventListener('input', () => {
        const q = searchInput.value.trim().toLowerCase();
        select.value = '';
        if (!q) {
            resultsBox.style.display = 'none';
            return;
        }
        renderResults(items.filter((it) => searchText(it).toLowerCase().includes(q)).slice(0, 8));
    });
    searchInput.addEventListener('focus', () => {
        if (searchInput.value.trim()) {
            renderResults(items.filter((it) => searchText(it).toLowerCase().includes(searchInput.value.trim().toLowerCase())).slice(0, 8));
        } else {
            renderResults(items.slice(0, 8));
        }
    });
    document.addEventListener('click', (e) => {
        if (!root.contains(e.target)) resultsBox.style.display = 'none';
    });

    // Forma qayta ko'rsatilganda (validatsiya xatosi) oldin tanlangan qiymatni tiklash.
    if (select.value) {
        const existing = items.find((it) => String(it.id) === String(select.value));
        if (existing) {
            searchInput.value = matchText(existing);
            onSelect(existing, true);
        }
    }
};
