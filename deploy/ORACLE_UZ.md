# SlideLab'ni Oracle Cloud'ning bepul serveriga o‘rnatish

Oracle Cloud "Always Free" — doim yoqiq turadigan bepul server: **2 ta ARM protsessor, 12 GB RAM, 200 GB disk**
(2026-yil iyundan beri shu hajm). Bot, PostgreSQL bazasi va slayd chizadigan Chromium bemalol sig‘adi.
O‘rnatish taxminan 30–40 daqiqa oladi.

---

## 1. Oracle hisobini ochish

1. <https://signup.cloud.oracle.com> → ro‘yxatdan o‘ting.
2. Bank kartasi so‘raladi — bu faqat tekshiruv uchun, Always Free resurslari uchun pul yechilmaydi.
3. **Home region** tanlang (keyin o‘zgartirib bo‘lmaydi). Yaqinroq bo‘lishi uchun, masalan, *Germany Central (Frankfurt)*.

## 2. Server yaratish

1. Menyu → **Compute → Instances → Create instance**.
2. **Image:** Canonical **Ubuntu 24.04** (yoki 22.04).
3. **Shape → Change shape → Ampere → VM.Standard.A1.Flex**: **2 OCPU**, **12 GB** memory.
4. **SSH keys:** "Generate a key pair for me" → **ikkala kalitni ham yuklab oling** (keyin qayta berilmaydi).
5. **Boot volume:** 100 GB.
6. **Create**. "Out of capacity" xatosi chiqsa — boshqa *Availability domain* tanlang yoki birozdan so‘ng qayta urinib ko‘ring (bepul serverlarga talab katta).
7. Server yaratilgach, **Public IP address** ni yozib oling.

## 3. 80 va 443 portlarini ochish

Instance sahifasi → **Subnet** havolasi → **Security Lists → Default Security List → Add Ingress Rules**:

| Source CIDR | IP Protocol | Destination port |
|---|---|---|
| `0.0.0.0/0` | TCP | `80` |
| `0.0.0.0/0` | TCP | `443` |

(Serverning o‘z ichidagi firewall'ni o‘rnatish skripti o‘zi ochadi.)

## 4. Bepul domen (HTTPS uchun)

Mini App va TezCheck vebhuki HTTPS manzil talab qiladi.

1. <https://www.duckdns.org> → Google yoki GitHub bilan kiring.
2. Subdomen yarating, masalan `slidelab` → **current ip** maydoniga serveringiz IP'sini yozing → *update ip*.
3. Domeningiz: `slidelab.duckdns.org`. Sertifikatni (Let's Encrypt) server o‘zi oladi va yangilab turadi.

## 5. Serverga ulanish va o‘rnatish

Windows'da PowerShell'ni oching (kalit faylini `Downloads` ga saqlagan bo‘lsangiz):

```powershell
ssh -i $HOME\Downloads\ssh-key-XXXX.key ubuntu@SERVER_IP
```

Serverda:

```bash
sudo apt-get update && sudo apt-get install -y git
git clone https://<GITHUB_TOKEN>@github.com/vimorauz-sketch/Slide_bot2.git slidelab
cd slidelab
bash deploy/install.sh
```

`<GITHUB_TOKEN>` — GitHub → Settings → Developer settings → Personal access tokens → *Fine-grained*, faqat shu repo uchun
**Contents: Read-only** ruxsati bilan.

Skript so‘raydi: bot tokeni, OpenAI kaliti, admin Telegram ID, domen va admin panel paroli. Qolganini (baza paroli,
maxfiy kalitlar) o‘zi yaratadi. Birinchi ishga tushirish 5–10 daqiqa oladi.

## 6. Railway'ni o‘chirish

Bitta bot ikki joyda ishlay olmaydi (`TelegramConflictError`). Oracle'da bot ishga tushgach, **Railway'dagi servisni
to‘xtating yoki o‘chiring**.

## 7. Tekshirish

- `https://slidelab.duckdns.org/diag` — server javob beryaptimi.
- Botga `/start`, keyin `/admin` → admin panel havolasi.
- Loglar: `cd ~/slidelab/deploy && sudo docker compose logs -f bot`

## 8. TezCheck ulash

1. TezCheck kabinetida vebhuk manzili: `https://slidelab.duckdns.org/payments/tezcheck/webhook`.
2. Serverda: `nano ~/slidelab/deploy/.env` → `TEZCHECK_API_KEY`, `TEZCHECK_CASH_DESK_CODE`, `TEZCHECK_WEBHOOK_SECRET` ni to‘ldiring.
3. `cd ~/slidelab/deploy && sudo docker compose up -d` — bot yangi sozlamalar bilan qayta ishga tushadi.

## 9. Yangilash

GitHub'ga yangi kod yuklagach, serverda:

```bash
bash ~/slidelab/deploy/update.sh
```

Baza va fayllar saqlanib qoladi. Har kuni 03:30 da baza zaxira nusxasi `~/slidelab-backups` ga olinadi
(oxirgi 14 kun saqlanadi).

## 10. Muhim: server "uxlab qolmasligi" uchun

Oracle bepul (Free Tier) hisoblarda **7 kun davomida juda kam ishlatilgan** (CPU 20% dan past) serverni qaytarib olishi mumkin.
Ishonchli yo‘l — hisobni **Pay As You Go** ga o‘tkazish (Billing → Upgrade). Always Free resurslar baribir bepul qoladi,
qaytarib olish qoidasi esa qo‘llanmaydi. O‘tgach **Budgets** bo‘limida 1 dollarlik ogohlantirish qo‘ying — tasodifan pulli
resurs yaratilsa, darhol xabar keladi.

## Railway PostgreSQL'dagi ma'lumotlarni ko‘chirish (ixtiyoriy)

Agar Railway'da PostgreSQL ishlatgan bo‘lsangiz: Railway → Postgres → *Connect* → **Public network** URL'ni oling, keyin serverda:

```bash
cd ~/slidelab/deploy
sudo docker compose exec -T db pg_dump "RAILWAY_PUBLIC_URL" --no-owner --no-acl > railway.sql
sudo docker compose exec -T db psql -U slidelab -d slidelab < railway.sql
sudo docker compose restart bot
```
