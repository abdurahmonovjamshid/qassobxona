# PythonAnywhere'ga Deploy Qilish Qo'llanmasi

Loyiha PythonAnywhere uchun tayyorlandi:
- `config/settings.py` — `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS` endi muhit
  o'zgaruvchilari (environment variables) orqali sozlanadi, `.pythonanywhere.com`
  domeni ALLOWED_HOSTS va CSRF_TRUSTED_ORIGINS'ga qo'shildi.
- `STATIC_ROOT` qo'shildi — `collectstatic` shu papkaga (`staticfiles/`) yig'adi.
- `requirements.txt` aniq versiyalarga qat'iylashtirildi (`Django==5.2.17`, `Pillow==12.3.0`).

Quyidagi qadamlarni ketma-ket bajaring.

---

## 1. Kodni GitHub'ga yuklash

Agar hali qilinmagan bo'lsa:

```powershell
git add .
git commit -m "Prepare for PythonAnywhere deploy"
git remote add origin https://github.com/<username>/<repo>.git
git push -u origin master
```

(GitHub'siz ham bo'ladi — PythonAnywhere "Files" bo'limidan zip qilib yuklash
mumkin, lekin GitHub orqali keyingi yangilanishlarni `git pull` bilan olish
ancha qulay.)

## 2. PythonAnywhere akkount

[pythonanywhere.com](https://www.pythonanywhere.com) da bepul (**Beginner**)
akkount oching. Bepul tarifda: 1 web app, ~512MB disk, SQLite bazasi uchun
yetarli.

## 3. Kodni serverga olish

PythonAnywhere **Consoles → Bash** ni oching:

```bash
git clone https://github.com/<username>/<repo>.git qassobxona
cd qassobxona
```

## 4. Virtualenv va paketlar

Web app yaratishdan oldin, PythonAnywhere'da mavjud Python versiyalarini
tekshiring (**Web → Add a new web app** oynasida ko'rinadi — odatda 3.10–3.13
mavjud). Local muhitda Python 3.14 ishlatilgan, shuning uchun serverda **eng
yangi mavjud versiyani (3.12 yoki 3.13)** tanlang — Django 5.2 ular bilan
to'liq mos.

```bash
mkvirtualenv --python=/usr/bin/python3.12 qassobxona-venv
pip install -r requirements.txt
```

(`mkvirtualenv` PythonAnywhere'ning virtualenvwrapper buyrug'i — avtomatik
`workon qassobxona-venv` bilan faollashadi.)

## 5. Web App yaratish

**Web** tabga o'ting → **Add a new web app** → domenni tasdiqlang →
**Manual configuration** (Django variantini emas, buni tanlang, chunki loyiha
allaqachon tayyor) → mos Python versiyasini tanlang.

### Virtualenv yo'lini ko'rsatish

**Web** sahifasida **Virtualenv** bo'limiga:

```
/home/<username>/.virtualenvs/qassobxona-venv
```

### Kod joyi

**Code** bo'limida:
- **Source code**: `/home/<username>/qassobxona`
- **Working directory**: `/home/<username>/qassobxona`

## 6. WSGI faylini sozlash

**Web** sahifasidagi **WSGI configuration file** havolasini oching (masalan
`/var/www/<username>_pythonanywhere_com_wsgi.py`), butun mazmunini o'chirib,
quyidagini yozing (qiymatlarni o'zgartiring):

```python
import os
import sys

path = '/home/<username>/qassobxona'
if path not in sys.path:
    sys.path.insert(0, path)

os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'

# --- Production sozlamalari ---
os.environ['DJANGO_DEBUG'] = 'False'
os.environ['DJANGO_SECRET_KEY'] = 'BU_YERGA_YANGI_MAXFIY_KALIT'
os.environ['DJANGO_ALLOWED_HOSTS'] = '<username>.pythonanywhere.com'

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
```

Yangi maxfiy kalit (`DJANGO_SECRET_KEY`) yaratish uchun Bash konsolida:

```bash
workon qassobxona-venv
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Chiqqan qatorni yuqoridagi WSGI fayliga qo'ying. **Bu kalitni hech kimga
bermang va GitHub'ga commit qilmang.**

## 7. Migratsiya, statik fayllar, admin foydalanuvchi

Bash konsolida:

```bash
cd ~/qassobxona
workon qassobxona-venv
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser
```

## 8. Static va Media fayllar mappingi

**Web** sahifasida **Static files** bo'limiga ikkita qator qo'shing:

| URL | Directory |
|---|---|
| `/static/` | `/home/<username>/qassobxona/staticfiles` |
| `/media/`  | `/home/<username>/qassobxona/media` |

## 9. Ishga tushirish

**Web** sahifasidagi katta yashil **Reload** tugmasini bosing, so'ng
`https://<username>.pythonanywhere.com` ni oching va login sahifasi
chiqishini tekshiring.

---

## Keyingi yangilanishlarni deploy qilish

Har safar kodga o'zgartirish kiritilib GitHub'ga push qilingandan so'ng:

```bash
cd ~/qassobxona
git pull
workon qassobxona-venv
pip install -r requirements.txt      # faqat requirements o'zgarsa
python manage.py migrate             # faqat migratsiya bo'lsa
python manage.py collectstatic --noinput   # faqat static/CSS/JS o'zgarsa
```

Keyin **Web** sahifasida **Reload** tugmasini bosish yetarli.

## Nazorat ro'yxati (xatolik chiqsa tekshiring)

- `Web → Error log` — 500-xatolarning aniq sababi shu yerda ko'rinadi.
- `DEBUG=False` bo'lganda ALLOWED_HOSTS noto'g'ri bo'lsa "Bad Request (400)"
  chiqadi — WSGI fayldagi `DJANGO_ALLOWED_HOSTS` qiymatini tekshiring.
- Static fayllar (CSS) yuklanmasa — `collectstatic` ishga tushirilganini va
  Static files mappingini tekshiring, so'ng **Reload**.
- `db.sqlite3` va `media/` `.gitignore`da — GitHub'da yo'q, shuning uchun
  serverda birinchi marta bo'sh holda yaratiladi (`migrate` bilan) va admin
  orqali qayta to'ldirishga to'g'ri keladi.
