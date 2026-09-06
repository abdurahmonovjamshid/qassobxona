// Oddiy Django formset uchun "qator qo'shish / bitta bosishda o'chirish"
// yordamchisi. Yangi qator Django'ning `formset.empty_form`idan (hidden
// <template>) klonlanadi — shu sabab oxirgi qator o'chirilgan taqdirda ham
// "qo'shish" tugmasi ishlashda davom etadi.
// Ishlatilishi: initFormset({ containerId, prefix, templateId, onRowAdded, onRowRemoved })
// onRowAdded(rowEl) / onRowRemoved() — ixtiyoriy, qo'shimcha hisob-kitob
// (masalan real-time summalarni yangilash) uchun.
// Qaytaradi: { addRow() } — dasturiy ravishda ("+ Qo'shish" tugmasini
// bosmasdan) yangi qator qo'shish uchun, masalan bo'laklash
// spetsifikatsiyasi tanlanganda output qatorlarini avto-toldirish uchun.
function initFormset({ containerId, prefix, templateId, onRowAdded, onRowRemoved }) {
    const container = document.getElementById(containerId);
    const template = document.getElementById(templateId);
    const totalFormsInput = document.getElementById(`id_${prefix}-TOTAL_FORMS`);
    const addBtn = document.getElementById(`add-${containerId}`);
    if (!container || !totalFormsInput) return { addRow: () => null };

    function attachRemove(row) {
        const btn = row.querySelector('.row-remove-btn');
        if (btn) btn.addEventListener('click', () => {
            row.remove();
            if (onRowRemoved) onRowRemoved();
        });
    }

    container.querySelectorAll('.formset-row').forEach(attachRemove);

    function addRow() {
        if (!template) return null;
        const idx = parseInt(totalFormsInput.value, 10);
        const html = template.innerHTML.replace(/__prefix__/g, String(idx));
        const wrapper = document.createElement('div');
        wrapper.innerHTML = html;
        const newRow = wrapper.querySelector('.formset-row');
        if (!newRow) return null;
        container.appendChild(newRow);
        totalFormsInput.value = String(idx + 1);
        attachRemove(newRow);
        if (onRowAdded) onRowAdded(newRow);
        return newRow;
    }

    if (addBtn) addBtn.addEventListener('click', addRow);

    return { addRow };
}
