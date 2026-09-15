# Qassobxona — Android ilova (Capacitor)

Bu ilova alohida "native" UI yozilmagan — mavjud Django saytingizni
(WebView ichida) o'raydi. Ya'ni **backendga (shablon/view) kiritilgan
o'zgarishlar APK qayta yig'ilmasdan darhol ko'rinadi** — faqat quyidagi
hollarda qayta yig'ish (rebuild) kerak bo'ladi:

- ilova nomi/ikonkasi o'zgarsa,
- `capacitor.config.json`dagi `server.url` (backend manzili) o'zgarsa.

## 1. Bir martalik sozlash (bu mashinada allaqachon amalga oshirilgan)

- Node.js — o'rnatilgan.
- Eclipse Temurin JDK 17 — o'rnatilgan.
- Android SDK (command-line tools, platform-tools, build-tools 34,
  platform 34) — `C:\Android\sdk` ichida o'rnatilmoqda.
- `npm install` — Capacitor paketlari o'rnatildi.
- `npx cap add android` — `android/` papkasi yaratildi.

Bu qadamlarni qayta bajarish shart emas — faqat quyidagi "APK yasash"
qismini takrorlaysiz.

## 2. Backend manzilini sozlash — MUHIM

`capacitor.config.json` faylida `server.url` **doimiy (barqaror) manzil**
bo'lishi kerak, aks holda har safar server manzili o'zgarganda ilovani
qayta yig'ib, Telegram orqali qayta yuborishga to'g'ri keladi:

```json
"server": { "url": "https://SIZNING-DOMENINGIZ", "cleartext": false }
```

Variantlar:
- **PythonAnywhere** (`config/settings.py`da allaqachon ruxsat berilgan) —
  eng barqaror, bepul tarif ham ishlaydi: `https://<username>.pythonanywhere.com`.
- **ngrok bilan barqaror (reserved) domen** — bepul ngrok har safar
  tasodifiy URL beradi (bunda har safar rebuild kerak bo'ladi!); pullik
  ngrok tarifida "reserved domain" olsangiz, u doim bir xil bo'ladi.

`server.url`ni o'zgartirgach: `npx cap sync android` ishga tushiring
(o'zgarishni `android/` loyihasiga ko'chiradi), keyin pastdagi "3-qadam"
bilan APK yasang.

## 3. APK yasash (har safar shu — ~1-2 daqiqa)

```
cd mobile
npx cap sync android
cd android
.\gradlew.bat assembleDebug
```

Tayyor fayl: `android\app\build\outputs\apk\debug\app-debug.apk`

Bu **debug** APK — sinov/ichki foydalanish uchun yetarli (Telegram orqali
yuborib, telefonda o'rnatish mumkin: "Noma'lum manbalardan o'rnatish"ga
ruxsat berish kerak bo'ladi). Agar Play Store'ga chiqarish yoki imzolangan
(signed release) versiya kerak bo'lsa — alohida ayting, kalit (keystore)
yaratib beraman.

## 4. Telefonga o'rnatish / Telegram orqali tarqatish

1. `app-debug.apk` faylini Telegram'da o'zingizga yoki foydalanuvchilarga
   "Fayl" sifatida yuboring (rasm sifatida emas — Telegram rasm/hujjat
   formatini siqib, faylni buzib qo'yishi mumkin bo'lgan joylarga
   yubormang, "Fayl biriktirish" tugmasidan foydalaning).
2. Telefonda faylni oching → "O'rnatish" (birinchi marta "Noma'lum
   manbadan o'rnatishga ruxsat berish" so'raladi — ruxsat bering).

## Loyihaning tuzilishi

- `capacitor.config.json` — ilova nomi, appId, backend manzili.
- `www/` — mahalliy fallback sahifa (asosiy kontent `server.url`dan
  jonli yuklanadi, bu papka faqat internet yo'q paytida ko'rinadi).
- `android/` — Gradle/Android loyihasi (Capacitor avtomatik yaratgan).
