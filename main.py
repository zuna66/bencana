import os
import json
import requests
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
from datetime import datetime
import pytz

# ===================== CONFIG =====================
BOT_TOKEN = ""  
CHAT_ID = -45566
LIST_FILE = "list.txt"
ALLOWED_USERS_FILE = "users.txt"  
MASTER_IDS = [1847390534]  

# ===================== ZONA WAKTU =====================
indonesia_timezone = pytz.timezone("Asia/Jakarta")  

def get_current_time():
    """Mengambil waktu saat ini di zona waktu Indonesia"""
    return datetime.now(indonesia_timezone).strftime("%Y-%m-%d %H:%M:%S")

# ===================== DOMAIN LOGIC =====================
def load_domains():
    """Memuat domain dari file list.txt, jika file kosong atau tidak valid, inisialisasi dengan data kosong"""
    if not os.path.exists(LIST_FILE):
        with open(LIST_FILE, "w") as f:
            json.dump({}, f, indent=2)
        return {}

    try:
        with open(LIST_FILE, "r") as f:
            return json.load(f)
    except json.JSONDecodeError:
        print(f"Error: File {LIST_FILE} tidak berisi JSON yang valid.")
        with open(LIST_FILE, "w") as f:
            json.dump({}, f, indent=2)
        return {}
    except Exception as e:
        print(f"Error membaca file {LIST_FILE}: {e}")
        return {}

def save_domains(domains_by_brand):
    """Menyimpan domain ke file list.txt"""
    try:
        with open(LIST_FILE, "w") as f:
            json.dump(domains_by_brand, f, indent=2)
    except Exception as e:
        print(f"Error menyimpan file list.txt: {e}")

def check_domain(domain):
    """Memeriksa status blokir domain menggunakan API eksternal"""
    url = f"https://check.skiddle.id/?domain={domain}"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        res = requests.get(url, headers=headers, timeout=10)
        res.raise_for_status()
        data = res.json()
        blocked = data.get(domain, {}).get("blocked", False)
        return {"domain": domain, "blocked": blocked}
    except requests.exceptions.RequestException as e:
        return {"domain": domain, "blocked": None, "error": f"Request error: {str(e)}"}
    except Exception as e:
        return {"domain": domain, "blocked": None, "error": f"Unexpected error: {str(e)}"}

# ===================== USER ACCESS CONTROL =====================
def load_allowed_users():
    """Memuat daftar user username yang diizinkan untuk menggunakan bot"""
    if not os.path.exists(ALLOWED_USERS_FILE):
        return []
    try:
        with open(ALLOWED_USERS_FILE, "r") as f:
            return [line.strip() for line in f if line.strip()]
    except Exception as e:
        print(f"Error membaca file: {e}")
        return []

def is_user_allowed(user_id):
    """Memeriksa apakah user diizinkan untuk mengakses bot (berdasarkan user ID atau master ID)"""
    if user_id in MASTER_IDS:
        return True
    allowed_users = load_allowed_users()
    return user_id in allowed_users

# ===================== TELEGRAM BOT COMMANDS =====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menampilkan menu utama saat bot dijalankan"""
    if not is_user_allowed(update.message.from_user.id):
        await update.message.reply_text("❌ Anda tidak memiliki izin untuk menggunakan bot ini, silahkan hubungi admin!")
        return

    
    keyboard = [
        [InlineKeyboardButton("📄 Cek Daftar Domain", callback_data="ceklist_domains")],
        [InlineKeyboardButton("➕ Tambah Site", callback_data="tambah_site")],
        [InlineKeyboardButton("🗑️ Hapus Site", callback_data="hapus_site")],
        [InlineKeyboardButton("🔍 Cek Status Domain", callback_data="cek_status_domain")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("✅ Bot Aktif!\nPilih menu di bawah untuk memulai:", reply_markup=reply_markup)

# ===================== Cek Daftar Domain =====================
async def ceklist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menampilkan daftar domain yang ada di list.txt"""
    domains_by_brand = load_domains()
    if not domains_by_brand:
        await update.callback_query.message.reply_text("❌ List domain kosong.")
        return

    current_time = get_current_time()
    response = f"📅 <b>Daftar Domain</b> pada: {current_time}\n\n"

    
    for brand, domains in domains_by_brand.items():
        response += f"🔹 <b>{brand}</b>\n"
        for domain in domains:
            response += f"- {domain}\n"

   
    if update.callback_query:
        await update.callback_query.message.reply_text(response, parse_mode='HTML')
    else:
        await update.message.reply_text(response, parse_mode='HTML')

# ===================== Cek Status Domain Secara Langsung =====================
async def cek(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Memeriksa status domain yang dikirimkan oleh pengguna"""
    if not context.args:
        await update.message.reply_text("❌ Kirimkan domain yang ingin dicek. Contoh: /cek example.com")
        return

    domain_to_check = context.args[0].strip().lower()
    
    
    result = check_domain(domain_to_check)
    if result.get("error"):
        await update.message.reply_text(f"❌ <b>{domain_to_check}</b> - <b>ERROR</b>: {result['error']}", parse_mode='HTML')
    elif result["blocked"]:
        await update.message.reply_text(f"⚠️ <b>{domain_to_check}</b> <b>DIBLOKIR</b>", parse_mode='HTML')
    else:
        await update.message.reply_text(f"✅ <b>{domain_to_check}</b> tidak diblokir.", parse_mode='HTML')

# ===================== CHECK STATUS DOMAIN UNTUK SEMUA DOMAIN DI list.txt =====================
async def cekstatus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Memeriksa status blokir untuk semua domain yang ada di list.txt"""
    domains_by_brand = load_domains()
    if not domains_by_brand:
        if update.callback_query:
            await update.callback_query.message.reply_text("❌ Tidak ada domain yang tersimpan.")
        else:
            await update.message.reply_text("❌ Tidak ada domain yang tersimpan.")
        return

    current_time = get_current_time()
    response = f"📅 <b>Status Blokir Domain</b> pada: {current_time}\n\n"

    
    blocked_domains = []
    unblocked_domains = []

    for brand, domains in domains_by_brand.items():
        for domain in domains:
            result = check_domain(domain)
            if result.get("error"):
                response += f"❌ <b>{domain}</b> - ERROR: {result['error']}\n"
            elif result["blocked"]:
                response += f"⚠️ <b>{domain}</b> DIBLOKIR\n"
                blocked_domains.append(domain)  
            else:
                unblocked_domains.append(domain)  
                response += f"✅ <b>{domain}</b> tidak diblokir.\n"

   
    if blocked_domains:
        
        admin_mentions = "@BangMeta @promaag88 @Lweiq168 @rakyatjelata123"
        response += f"\n🚨 <b>List Domain Block</b>: <b>{', '.join(blocked_domains)}</b>\n{admin_mentions}"

    
    await context.bot.send_message(chat_id=CHAT_ID, text=response, parse_mode='HTML')

# ===================== ADD DOMAIN =====================
async def addsite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menambahkan domain ke dalam list.txt tanpa memeriksa brand"""
    if not is_user_allowed(update.message.from_user.id):
        await update.message.reply_text("❌ Anda tidak memiliki izin.")
        return

    if len(context.args) < 2:
        await update.message.reply_text("❌ Format yang benar: /addsite <brand> <domain1> <domain2> ...")
        return

    brand = context.args[0].strip().lower()
    new_domains = [d.strip().lower() for d in context.args[1:] if d.strip()]
    
    domains_by_brand = load_domains()
    
    
    if brand not in domains_by_brand:
        domains_by_brand[brand] = []

    added = []
    for domain in new_domains:
        if domain not in domains_by_brand[brand]:  
            domains_by_brand[brand].append(domain)
            added.append(domain)

    if added:
        save_domains(domains_by_brand)
        await update.message.reply_text(f"✅ Domain {', '.join(added)} telah ditambahkan ke brand <b>{brand}</b>.", parse_mode='HTML')
    else:
        await update.message.reply_text("❌ Semua domain sudah ada di brand tersebut.", parse_mode='HTML')

# ===================== DELETE DOMAIN =====================
async def dellsite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menghapus domain dari list.txt"""
    if not is_user_allowed(update.message.from_user.id):
        await update.message.reply_text("❌ Anda tidak memiliki izin.")
        return

    if not context.args:
        await update.message.reply_text("❌ Kirim domain yang ingin dihapus. Contoh: /dellsite example.com")
        return

    domains_to_remove = [d.strip().lower() for d in context.args if d.strip()]
    domains_by_brand = load_domains()

    removed = []
    for brand, domains in domains_by_brand.items():
        for domain in domains_to_remove:
            if domain in domains:
                domains.remove(domain)
                removed.append(domain)
    
    if removed:
        save_domains(domains_by_brand)
        await update.message.reply_text(f"✅ Domain berhasil dihapus: {', '.join(removed)}", parse_mode='HTML')
    else:
        await update.message.reply_text("❌ Tidak ada domain yang ditemukan di daftar.", parse_mode='HTML')

# ===================== ADD USER =====================
async def adduser(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menambahkan username user ke dalam daftar yang diizinkan"""
    if update.message.from_user.id not in MASTER_IDS:
        await update.message.reply_text("❌ Anda tidak memiliki izin untuk menggunakan command ini.")
        return

    if not context.args:
        await update.message.reply_text("❌ Kirim username yang ingin ditambahkan. Contoh: /adduser username")
        return

    new_username = context.args[0].strip()

    
    allowed_users = load_allowed_users()

    if new_username in allowed_users:
        await update.message.reply_text(f"❌ Username <b>{new_username}</b> sudah ada dalam daftar.", parse_mode='HTML')
        return

    
    with open(ALLOWED_USERS_FILE, "a") as f:
        f.write(new_username + "\n")

    await update.message.reply_text(f"✅ Username <b>{new_username}</b> telah ditambahkan ke daftar yang diizinkan.", parse_mode='HTML')

# ===================== CALLBACK HANDLER =====================
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menangani tombol inline"""
    query = update.callback_query
    await query.answer()

    if query.data == "ceklist_domains":
        await query.message.reply_text("Mengambil daftar domain...")
        await ceklist(update, context)
    elif query.data == "tambah_site":
        await query.message.reply_text("Gunakan perintah /addsite <brand> <domain1> <domain2> untuk menambah domain.")
    elif query.data == "hapus_site":
        await query.message.reply_text("Gunakan perintah /dellsite <domain> untuk menghapus domain.")
    elif query.data == "cek_status_domain":
        await query.message.reply_text("Gunakan perintah /cekstatus untuk melihat status blokir domain.")

# ===================== AUTO CHECK DOMAIN EVERY 5 MINUTES =====================
async def auto_check_domains(context: ContextTypes.DEFAULT_TYPE):
    """Memeriksa status blokir untuk semua domain setiap 5 menit dan mengirimkan hasilnya"""
    domains_by_brand = load_domains()
    if not domains_by_brand:
        return

    current_time = get_current_time()
    response = f"📅 <b>Hasil Pengecekan Status Domain</b> pada: {current_time}\n\n"
    
    
    blocked_domains = []
    unblocked_domains = []

    for brand, domains in domains_by_brand.items():
        for domain in domains:
            result = check_domain(domain)
            if result.get("error"):
                response += f"❌ <b>{domain}</b> - ERROR: {result['error']}\n"
            elif result["blocked"]:
                response += f"⚠️ <b>{domain}</b> DIBLOKIR\n"
                blocked_domains.append(domain)  
            else:
                unblocked_domains.append(domain)  
                response += f"✅ <b>{domain}</b> tidak diblokir.\n"

    
    if blocked_domains:
        
        admin_mentions = "@BangMeta @promaag88 @Lweiq168 @rakyatjelata123"
        response += f"\n🚨 <b>List Domain Block</b>: <b>{', '.join(blocked_domains)}</b>\n{admin_mentions}"

        
        await context.bot.send_message(chat_id=CHAT_ID, text=response, parse_mode='HTML')
    else:
        
        pass

# ===================== MAIN BOT POLLING =====================
if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    
    job_queue = app.job_queue
    job_queue.run_repeating(auto_check_domains, interval=300, first=0)  

    
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ceklist", ceklist))
    app.add_handler(CommandHandler("addsite", addsite))
    app.add_handler(CommandHandler("cek", cek))
    app.add_handler(CommandHandler("cekstatus", cekstatus))
    app.add_handler(CommandHandler("adduser", adduser))  
    app.add_handler(CommandHandler("dellsite", dellsite))

    print("🚀 Bot Telegram aktif...")
    app.run_polling()
