# Admin orqali test qilish — yo'riqnoma

Bu faylda nima o'zgargani va admin orqali to'liq stsenariyni (xarid → bo'laklash →
sotuv → to'lov) qanday sinab ko'rish tushuntirilgan.

## Nima qo'shildi

Avval bo'sh bo'lgan quyidagi service fayllarga to'liq business logika yozildi:

- `apps/inventory/services/inventory_service.py` — ombor qoldig'ini hisoblash
  (`get_stock`), kirim/chiqim yaratish (`stock_in`, `stock_out` — chiqimda
  qoldiq yetarli emasligini tekshiradi), o'rtacha tannarxni hisoblash
  (`get_weighted_average_cost`), bekor qilishda harakatni teskari qaytarish
  (`reverse_movements`).
- `apps/purchases/services/purchase_service.py` — `confirm_purchase()` xaridni
  tasdiqlab, mahsulotni omborga kirim qiladi; `cancel_purchase()` bekor qiladi;
  `recalc_purchase_payment()` to'lovlar asosida qarzni qayta hisoblaydi.
- `apps/butchering/services/butchering_service.py` — `confirm_butchering()`
  input mahsulotni ombordan chiqarib, har bir output mahsulotni (tannarxi
  og'irlik ulushi bo'yicha taqsimlangan holda) omborga kirim qiladi, hamda
  `output_weight`/`difference`/`yield_percentage`ni hisoblaydi.
- `apps/sales/services/sale_service.py` — `confirm_sale()` har bir mahsulotni
  ombordan chiqaradi (yetarli bo'lmasa xatolik), tannarx/foyda va jami
  summani hisoblaydi.
- `apps/payments/services/payment_service.py` — to'lov yaratganda/o'chirganda
  bog'langan Sale yoki Purchase'ning `paid_amount`/`debt_amount`ini qayta
  hisoblaydi.

`Purchase` modeliga yangi **`product`** maydoni qo'shildi (migration
`apps/purchases/migrations/0002_purchase_product.py`) — xarid qilingan
butun hayvon/go'sht qaysi mahsulotga (masalan "Mol (butun)") tegishli
ekanligini bildiradi, shu orqali ombor kirimi qilinadi.

Barcha admin sahifalarida (`Purchase`, `Butchering`, `Sale`) `status`
maydoni **readonly** qilindi — endi uni faqat ro'yxat sahifasidagi
**"✅ Tasdiqlash" / "❌ Bekor qilish"** action'lari orqali o'zgartirish mumkin,
chunki faqat shu action'lar tegishli ombor harakatlarini ham yaratadi.
To'g'ridan-to'g'ri status maydonini o'zgartirib saqlasangiz, ombor
harakati yaratilmaydi.

## Ishga tushirish

```bash
cd butcher_management
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/Mac: source .venv/bin/activate
pip install -r requirements.txt

python manage.py makemigrations   # tekshirish uchun, odatda hech narsa topmaydi
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Admin: http://127.0.0.1:8000/admin/

## To'liq test stsenariysi (TZ 37-bo'lim)

1. **Products** → qo'shing:
   - `Mol (butun)`, code=`MOL-W`, category=`WHOLE`
   - `Lahm`, code=`LAHM`, sale_price=95000
   - `Qovurg'a`, code=`QOVURGA`, sale_price=80000
   - (xohlasangiz: Son, Kurak, Bo'yin, Qiyma, Suyak, Yog', Chiqit)

2. **Suppliers** → `Abdulloh fermer xo'jaligi`

3. **Customers** → `Ali aka`

4. **Purchases → Add purchase**:
   - supplier=Abdulloh, product=`Mol (butun)`, purchase_number=P-0001,
     date=bugun, animal_type=Mol, gross_weight=420, net_weight=420,
     price_per_kg=78000, paid_amount=20000000
   - Saqlang (status hali DRAFT, total_amount/debt_amount avtomatik chiqadi)
   - Ro'yxatda checkbox belgilab, action: **"✅ Tanlangan xaridlarni tasdiqlash"**
   - Natija: status=CONFIRMED, `Mol (butun)` ombor qoldig'i 420 kg bo'ladi
     (Inventory → Stock Movements'da tekshiring)

5. **Butchering → Add butchering**:
   - purchase=P-0001, input_product=`Mol (butun)`, input_weight=420, date=bugun
   - Inline "Outputs": Lahm 150, Qovurg'a 45, Son 65, Kurak 50, Bo'yin 25,
     Qiyma 30, Suyak 35, Yog' 15, Chiqit 5 (jami 420)
   - Saqlang, keyin action: **"✅ Tanlangan bo'laklashlarni tasdiqlash"**
   - Natija: `Mol (butun)` qoldig'i 0 ga tushadi, har bir output mahsulot
     omborga kiradi, `yield_percentage`=100.00 hisoblanadi, unit_cost'lar
     avtomatik to'ldiriladi

6. **Sales → Add sale**:
   - customer=Ali aka, sale_number=S-0001, date=bugun, paid_amount=500000
   - Inline "Items": Lahm 5kg × 95000; Qovurg'a 3kg × 80000
   - Saqlang, keyin action: **"✅ Tanlangan sotuvlarni tasdiqlash"**
   - Natija: total_amount=715000, ombordan Lahm/Qovurg'a kamayadi,
     har bir item uchun cost_price/profit avtomatik hisoblanadi

7. **Payments → Add payment**:
   - sale=S-0001, customer=Ali aka, amount=500000, date=bugun
   - Saqlang → Sale'ning `paid_amount`/`debt_amount`i avtomatik yangilanadi

8. **Xato holatlarni sinash**:
   - Omborda yo'q mahsulotni ko'p miqdorda sotishga urinib ko'ring →
     "Omborda yetarli mahsulot mavjud emas..." xatosi chiqishi kerak
   - Bir xil Purchase/Sale/Butchering'ni ikki marta tasdiqlashga urinib
     ko'ring → "Faqat DRAFT holatidagi ... tasdiqlash mumkin" xatosi chiqadi

## Hali qilinmagan qismlar (keyingi bosqich)

- Frontend (views/urls/templates) — hozircha faqat Django Admin ishlaydi
- Dashboard va Reports app'lari — model/view yo'q
- `accounts` app — Manager/Kassir/Omborchi rollari (Groups/Permissions)
- Testlar (`tests.py` fayllar bo'sh)
- `PurchaseExpense` (transport va h.k.) hali tannarxga qo'shilmagan
