# IELTS Speaking Telegram Bot

Bu bot:

- birinchi bo‘lib salom beradi;
- oddiy AI chat rejimida gaplashadi;
- IELTS Speaking exam oladi: Part 1, Part 2, Part 3;
- har javobdan keyin qisqa feedback beradi;
- exam oxirida taxminiy band score chiqaradi;
- foydalanuvchi ovozli xabar yuborsa, ovozli javob qaytaradi;
- sticker `file_id` berilsa, vaqti-vaqti bilan stiker yuboradi.

## 1. Kerakli narsalar

Python 3.10 yoki undan yangi versiya kerak.

Telegram token:

1. Telegram’da `@BotFather` ni oching.
2. `/newbot` yuboring.
3. Bot nomi va username kiriting.
4. Berilgan tokenni saqlab qo‘ying.

OpenAI API key ham kerak bo‘ladi.

## 2. O‘rnatish

```bash
pip install -r requirements.txt
```

## 3. Sozlash

`.env.example` faylidan nusxa olib `.env` deb nomlang:

```bash
copy .env.example .env
```

`.env` ichini to‘ldiring:

```env
TELEGRAM_BOT_TOKEN=botfather_tokeningiz
OPENAI_API_KEY=openai_api_keyingiz
```

Sticker qo‘shmoqchi bo‘lsangiz:

```env
STICKER_IDS=birinchi_sticker_file_id,ikkinchi_sticker_file_id
```

Sticker `file_id` keyinroq ham qo‘shsa bo‘ladi. Hozircha bo‘sh tursa, bot emoji ishlatadi.

## 4. Ishga tushirish

```bash
python bot.py
```

Telegram’da botga `/start` yuboring.

## Render’ga joylash

Bu bot polling bilan ishlaydi, shuning uchun Render’da `Background Worker` sifatida ishga tushiriladi.

GitHub’ga shu papkadagi fayllarni yuklang:

- `bot.py`
- `requirements.txt`
- `render.yaml`
- `.env.example`
- `README.md`

Render’da Blueprint orqali `render.yaml` ni tanlasangiz, servis avtomatik worker sifatida yaratiladi.

Render environment variables bo‘limiga quyidagilarni kiriting:

```env
TELEGRAM_BOT_TOKEN=botfather_tokeningiz
OPENAI_API_KEY=openai_api_keyingiz
```

Oddiy qo‘lda sozlasangiz:

- Service type: `Background Worker`
- Build command: `pip install -r requirements.txt`
- Start command: `python bot.py`

## Buyruqlar

- `/start` - botni boshlash
- `/exam` - IELTS Speaking exam boshlash
- `/chat` - oddiy chat rejimi
- `/status` - exam holati
- `/reset` - qayta boshlash

## Eslatma

Bu birinchi tayyor versiya. Keyingi bosqichda quyidagilarni qo‘shish mumkin:

- SQLite baza;
- foydalanuvchi progressi;
- admin panel;
- haqiqiy IELTS timer;
- Part 2 uchun 1 daqiqa tayyorlanish va 2 daqiqa gapirish;
- har bo‘lim uchun alohida band score.
