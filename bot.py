import logging
import os
import json
import random
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatPermissions
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("BOT_TOKEN", "8643395157:AAEU-mgPjCxoa0INMl1kwWSdEPSt1iKJwbE")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "highsecurityprison20110403")
DATA_FILE = "group_data.json"
MAX_STRIKES = 3

CHANNEL_RULES = (
    "\n\n📌 *bot by fucckeddream*\n"
    "1\\. Запрещены любые оскорбления\n"
    "2\\. Запрещены DDOS/SWAT/DOX"
)

RANKS = [
    (0,     "🥚 Новичок"),
    (100,   "🐣 Птенец"),
    (500,   "🐥 Пользователь"),
    (1500,  "⚔️ Воин"),
    (3000,  "🛡️ Ветеран"),
    (6000,  "💎 Элита"),
    (12000, "👑 Легенда"),
    (25000, "🌟 Бессмертный"),
]

def get_rank(xp):
    rank = RANKS[0][1]
    for t, n in RANKS:
        if xp >= t: rank = n
    return rank

def next_rank_info(xp):
    for t, n in RANKS:
        if xp < t: return t, n
    return None, None

# ── DATA ──────────────────────────────────────────────────────────────────────
def load():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"admins": [], "users": {}, "settings": {"fun_enabled": True}}

def save(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_user(data, user_id, username="", full_name=""):
    uid = str(user_id)
    if uid not in data["users"]:
        data["users"][uid] = {
            "username": username, "full_name": full_name,
            "coins": 100, "xp": 0, "nickname": "",
            "pet_size": 10, "pet_last": "", "work_last": "", "daily_last": "",
            "married_to": "", "proposals": [], "msg_count": 0,
            "strikes": 0, "muted_until": "", "banned": False,
        }
    u = data["users"][uid]
    for k, v in [("strikes",0),("muted_until",""),("banned",False)]:
        if k not in u: u[k] = v
    return u

def dn(u): return u.get("nickname") or u.get("full_name") or u.get("username") or "Неизвестный"

def is_admin(uid): return uid in load()["admins"]

def is_fun():
    d = load()
    return d.get("settings", {}).get("fun_enabled", True)

# ── GUARDS ────────────────────────────────────────────────────────────────────
async def req_admin(update):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Только для администраторов бота.")
        return False
    return True

async def req_fun(update):
    if not is_fun():
        await update.message.reply_text("🔒 Развлечения отключены администратором.")
        return False
    return True

def get_target(update):
    if update.message.reply_to_message:
        return update.message.reply_to_message.from_user
    return None

# ── HELPERS ───────────────────────────────────────────────────────────────────
def parse_duration(s):
    s = s.strip().lower()
    try:
        if s.endswith("m"): return int(s[:-1])
        if s.endswith("h"): return int(s[:-1]) * 60
        if s.endswith("d"): return int(s[:-1]) * 1440
        return int(s)
    except ValueError:
        return None

def fmt_dur(m):
    if m < 60: return f"{m} мин"
    if m < 1440: return f"{m//60} ч"
    return f"{m//1440} д"

# ════════════════════════════════════════════════════════════════════════════════
#  AUTH
# ════════════════════════════════════════════════════════════════════════════════
async def admin_cmd(update, ctx):
    user = update.effective_user
    if not ctx.args:
        await update.message.reply_text("🔑 /admin <пароль>"); return
    if " ".join(ctx.args) == ADMIN_PASSWORD:
        data = load()
        if user.id not in data["admins"]:
            data["admins"].append(user.id); save(data)
        await update.message.reply_text("✅ Ты теперь администратор бота!")
    else:
        await update.message.reply_text("❌ Неверный пароль.")

async def revoke_cmd(update, ctx):
    data = load()
    if update.effective_user.id in data["admins"]:
        data["admins"].remove(update.effective_user.id); save(data)
        await update.message.reply_text("✅ Права сняты.")

# ════════════════════════════════════════════════════════════════════════════════
#  MODERATION
# ════════════════════════════════════════════════════════════════════════════════
async def ban_cmd(update, ctx):
    if not await req_admin(update): return
    t = get_target(update)
    if not t: await update.message.reply_text("↩️ Ответь на сообщение нарушителя."); return
    reason = " ".join(ctx.args) if ctx.args else "Нарушение правил"
    data = load(); u = get_user(data, t.id, t.username or "", t.full_name)
    u["banned"] = True; save(data)
    try:
        await ctx.bot.ban_chat_member(update.effective_chat.id, t.id)
        await update.message.reply_text(f"🔨 *{dn(u)}* забанен.\n📋 {reason}", parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")

async def unban_cmd(update, ctx):
    if not await req_admin(update): return
    t = get_target(update)
    if not t: await update.message.reply_text("↩️ Ответь на сообщение."); return
    data = load(); u = get_user(data, t.id, t.username or "", t.full_name)
    u["banned"] = False; u["strikes"] = 0; save(data)
    try:
        await ctx.bot.unban_chat_member(update.effective_chat.id, t.id, only_if_banned=True)
        await update.message.reply_text(f"✅ *{dn(u)}* разбанен.", parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")

async def kick_cmd(update, ctx):
    if not await req_admin(update): return
    t = get_target(update)
    if not t: await update.message.reply_text("↩️ Ответь на сообщение нарушителя."); return
    reason = " ".join(ctx.args) if ctx.args else "Нарушение правил"
    cid = update.effective_chat.id
    data = load(); u = get_user(data, t.id, t.username or "", t.full_name); save(data)
    try:
        await ctx.bot.ban_chat_member(cid, t.id)
        await ctx.bot.unban_chat_member(cid, t.id)
        await update.message.reply_text(f"👟 *{dn(u)}* кикнут.\n📋 {reason}", parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")

async def mute_cmd(update, ctx):
    if not await req_admin(update): return
    t = get_target(update)
    if not t: await update.message.reply_text("↩️ Ответь на сообщение."); return
    dur_str = ctx.args[0] if ctx.args else "10m"
    mins = parse_duration(dur_str)
    if mins is None: await update.message.reply_text("❌ Формат: 10m / 2h / 1d"); return
    reason = " ".join(ctx.args[1:]) if len(ctx.args) > 1 else "Нарушение правил"
    until = datetime.utcnow() + timedelta(minutes=mins)
    data = load(); u = get_user(data, t.id, t.username or "", t.full_name)
    u["muted_until"] = until.isoformat(); save(data)
    try:
        await ctx.bot.restrict_chat_member(
            update.effective_chat.id, t.id,
            permissions=ChatPermissions(can_send_messages=False), until_date=until
        )
        await update.message.reply_text(
            f"🔇 *{dn(u)}* замьючен на *{fmt_dur(mins)}*.\n📋 {reason}", parse_mode="Markdown"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")

async def unmute_cmd(update, ctx):
    if not await req_admin(update): return
    t = get_target(update)
    if not t: await update.message.reply_text("↩️ Ответь на сообщение."); return
    data = load(); u = get_user(data, t.id, t.username or "", t.full_name)
    u["muted_until"] = ""; save(data)
    try:
        await ctx.bot.restrict_chat_member(
            update.effective_chat.id, t.id,
            permissions=ChatPermissions(
                can_send_messages=True, can_send_media_messages=True,
                can_send_polls=True, can_send_other_messages=True,
                can_add_web_page_previews=True,
            )
        )
        await update.message.reply_text(f"🔊 *{dn(u)}* размьючен.", parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")

async def strike_cmd(update, ctx):
    if not await req_admin(update): return
    t = get_target(update)
    if not t: await update.message.reply_text("↩️ Ответь на сообщение нарушителя."); return
    reason = " ".join(ctx.args) if ctx.args else "Нарушение правил"
    data = load(); u = get_user(data, t.id, t.username or "", t.full_name)
    u["strikes"] = u.get("strikes", 0) + 1
    strikes = u["strikes"]; save(data)
    if strikes >= MAX_STRIKES:
        u["banned"] = True; save(data)
        try: await ctx.bot.ban_chat_member(update.effective_chat.id, t.id)
        except Exception: pass
        await update.message.reply_text(
            f"🚫 *{dn(u)}* — страйк {strikes}/{MAX_STRIKES} → *автобан*!\n📋 {reason}",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            f"⚠️ *{dn(u)}* — страйк *{strikes}/{MAX_STRIKES}*\n"
            f"📋 {reason}\n❗ Ещё {MAX_STRIKES-strikes} страйк(ов) → бан.",
            parse_mode="Markdown"
        )

async def unstrike_cmd(update, ctx):
    if not await req_admin(update): return
    t = get_target(update)
    if not t: await update.message.reply_text("↩️ Ответь на сообщение."); return
    data = load(); u = get_user(data, t.id, t.username or "", t.full_name)
    if u["strikes"] > 0: u["strikes"] -= 1
    save(data)
    await update.message.reply_text(
        f"✅ Страйк снят. У *{dn(u)}* — *{u['strikes']}/{MAX_STRIKES}*.", parse_mode="Markdown"
    )

async def warn_cmd(update, ctx):
    if not await req_admin(update): return
    t = get_target(update)
    if not t: await update.message.reply_text("↩️ Ответь на сообщение нарушителя."); return
    reason = " ".join(ctx.args) if ctx.args else "Нарушение правил"
    data = load(); u = get_user(data, t.id, t.username or "", t.full_name); save(data)
    await update.message.reply_text(
        f"⚠️ *{dn(u)}*, предупреждение!\n📋 {reason}\n_Следующие нарушения — мут или бан._",
        parse_mode="Markdown"
    )

async def ro_cmd(update, ctx):
    """Read-only режим."""
    if not await req_admin(update): return
    t = get_target(update)
    if not t: await update.message.reply_text("↩️ Ответь на сообщение."); return
    dur_str = ctx.args[0] if ctx.args else "30m"
    mins = parse_duration(dur_str)
    if mins is None: await update.message.reply_text("❌ Формат: 30m / 2h / 1d"); return
    until = datetime.utcnow() + timedelta(minutes=mins)
    data = load(); u = get_user(data, t.id, t.username or "", t.full_name); save(data)
    try:
        await ctx.bot.restrict_chat_member(
            update.effective_chat.id, t.id,
            permissions=ChatPermissions(can_send_messages=False), until_date=until
        )
        await update.message.reply_text(
            f"📖 *{dn(u)}* → режим чтения на *{fmt_dur(mins)}*.", parse_mode="Markdown"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")

async def purge_cmd(update, ctx):
    """Удалить N последних сообщений."""
    if not await req_admin(update): return
    try:
        count = min(int(ctx.args[0]) if ctx.args else 5, 50)
    except ValueError:
        await update.message.reply_text("❌ /purge 10"); return
    import asyncio
    cid = update.effective_chat.id
    mid = update.message.message_id
    deleted = 0
    for i in range(mid, mid - count - 1, -1):
        try: await ctx.bot.delete_message(cid, i); deleted += 1
        except Exception: pass
    note = await ctx.bot.send_message(cid, f"🗑️ Удалено *{deleted}* сообщений.", parse_mode="Markdown")
    await asyncio.sleep(5)
    try: await note.delete()
    except Exception: pass

async def userinfo_cmd(update, ctx):
    if not await req_admin(update): return
    t = get_target(update)
    if not t: await update.message.reply_text("↩️ Ответь на сообщение пользователя."); return
    data = load(); u = get_user(data, t.id, t.username or "", t.full_name)
    muted_str = ""
    if u.get("muted_until"):
        try:
            until = datetime.fromisoformat(u["muted_until"])
            if until > datetime.utcnow():
                muted_str = f"\n🔇 Мут до: {until.strftime('%d.%m %H:%M')} UTC"
        except Exception: pass
    await update.message.reply_text(
        f"🔍 *Инфо*\n\n"
        f"👤 {dn(u)}\n🆔 `{t.id}`\n📛 @{t.username or '—'}\n"
        f"⚠️ Страйков: {u.get('strikes',0)}/{MAX_STRIKES}\n"
        f"🚫 Забанен: {'да' if u.get('banned') else 'нет'}"
        f"{muted_str}\n"
        f"💬 Сообщений: {u.get('msg_count',0)}\n"
        f"💰 Монет: {u.get('coins',0)}\n"
        f"⭐ XP: {u.get('xp',0)} ({get_rank(u.get('xp',0))})",
        parse_mode="Markdown"
    )

async def funoff_cmd(update, ctx):
    if not await req_admin(update): return
    data = load()
    if "settings" not in data: data["settings"] = {}
    data["settings"]["fun_enabled"] = False; save(data)
    await update.message.reply_text(
        "🔒 *Режим строгой модерации.*\nРазвлечения отключены.\n"
        "Активны только команды модерации.", parse_mode="Markdown"
    )

async def funon_cmd(update, ctx):
    if not await req_admin(update): return
    data = load()
    if "settings" not in data: data["settings"] = {}
    data["settings"]["fun_enabled"] = True; save(data)
    await update.message.reply_text("🎉 *Развлечения включены!*", parse_mode="Markdown")

# ════════════════════════════════════════════════════════════════════════════════
#  FUN / ECONOMY
# ════════════════════════════════════════════════════════════════════════════════
async def profile(update, ctx):
    if not await req_fun(update): return
    user = update.effective_user
    data = load(); u = get_user(data, user.id, user.username or "", user.full_name); save(data)
    rank = get_rank(u["xp"]); nxt, nxt_name = next_rank_info(u["xp"])
    married = ""
    if u.get("married_to"):
        p = data["users"].get(u["married_to"], {}); married = f"\n💍 В браке с: *{dn(p)}*"
    progress = ""
    if nxt:
        pct = int((u["xp"]/nxt)*20); bar = "█"*pct + "░"*(20-pct)
        progress = f"\n`[{bar}]` до {nxt_name}"
    await update.message.reply_text(
        f"👤 *{dn(u)}*\n🏅 {rank}\n⭐ {u['xp']} XP{progress}\n"
        f"💰 {u['coins']} монет\n🐾 Питомец: {u['pet_size']} см\n"
        f"⚠️ Страйков: {u.get('strikes',0)}/{MAX_STRIKES}\n💬 {u['msg_count']} сообщ."
        f"{married}", parse_mode="Markdown"
    )

async def set_nick(update, ctx):
    if not await req_fun(update): return
    if not ctx.args: await update.message.reply_text("✏️ /nick <никнейм>"); return
    nick = " ".join(ctx.args)[:32]
    data = load(); u = get_user(data, update.effective_user.id, update.effective_user.username or "", update.effective_user.full_name)
    u["nickname"] = nick; save(data)
    await update.message.reply_text(f"✅ Ник: *{nick}*", parse_mode="Markdown")

async def balance(update, ctx):
    if not await req_fun(update): return
    data = load(); u = get_user(data, update.effective_user.id); save(data)
    await update.message.reply_text(f"💰 *{u['coins']} монет*", parse_mode="Markdown")

async def give_coins(update, ctx):
    if not await req_fun(update): return
    user = update.effective_user
    if not update.message.reply_to_message or not ctx.args:
        await update.message.reply_text("↩️ /give <сумма> (reply)"); return
    try:
        amount = int(ctx.args[0])
        if amount <= 0: raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Некорректная сумма."); return
    t = update.message.reply_to_message.from_user
    data = load()
    s = get_user(data, user.id, user.username or "", user.full_name)
    r = get_user(data, t.id, t.username or "", t.full_name)
    if s["coins"] < amount: await update.message.reply_text("❌ Недостаточно монет."); return
    s["coins"] -= amount; r["coins"] += amount; save(data)
    await update.message.reply_text(f"✅ *{dn(s)}* → *{dn(r)}*: *{amount} монет*", parse_mode="Markdown")

async def add_coins(update, ctx):
    if not await req_admin(update): return
    if not update.message.reply_to_message or not ctx.args:
        await update.message.reply_text("/addcoins <сумма> (reply)"); return
    try: amount = int(ctx.args[0])
    except ValueError: await update.message.reply_text("❌ Некорректная сумма."); return
    t = update.message.reply_to_message.from_user
    data = load(); u = get_user(data, t.id, t.username or "", t.full_name)
    u["coins"] += amount; save(data)
    await update.message.reply_text(f"✅ *{dn(u)}* +*{amount} монет*", parse_mode="Markdown")

async def daily(update, ctx):
    if not await req_fun(update): return
    user = update.effective_user
    data = load(); u = get_user(data, user.id, user.username or "", user.full_name)
    now = datetime.utcnow(); last = u.get("daily_last")
    if last:
        diff = now - datetime.fromisoformat(last)
        if diff < timedelta(hours=22):
            rem = timedelta(hours=22) - diff
            h = int(rem.total_seconds())//3600; m = (int(rem.total_seconds())%3600)//60
            await update.message.reply_text(f"⏳ Следующий бонус через *{h}ч {m}м*.", parse_mode="Markdown"); return
    reward = random.randint(50, 200)
    u["coins"] += reward; u["xp"] += 10; u["daily_last"] = now.isoformat(); save(data)
    await update.message.reply_text(f"🎁 *+{reward} монет* и *+10 XP*!\n💰 {u['coins']}", parse_mode="Markdown")

JOBS = [
    ("🧑‍💻 поработал программистом", 80, 300),("🚕 развозил пассажиров", 50, 150),
    ("🍕 доставлял пиццу", 40, 120),("🏗️ строил здания", 60, 200),
    ("🎨 нарисовал картину", 70, 250),("📦 фасовал товары", 45, 130),
    ("🎮 стримил игры", 30, 400),("📝 написал статью", 55, 180),
]

async def work(update, ctx):
    if not await req_fun(update): return
    user = update.effective_user
    data = load(); u = get_user(data, user.id, user.username or "", user.full_name)
    now = datetime.utcnow(); last = u.get("work_last")
    if last and now - datetime.fromisoformat(last) < timedelta(hours=1):
        m = int((timedelta(hours=1)-(now-datetime.fromisoformat(last))).total_seconds()/60)
        await update.message.reply_text(f"😴 Работа через *{m} мин*.", parse_mode="Markdown"); return
    job, mn, mx = random.choice(JOBS); earned = random.randint(mn, mx)
    u["coins"] += earned; u["xp"] += 5; u["work_last"] = now.isoformat(); save(data)
    await update.message.reply_text(f"💼 {job} — *+{earned} монет*!\n💰 {u['coins']} | ⭐ {u['xp']} XP", parse_mode="Markdown")

async def pet_cmd(update, ctx):
    if not await req_fun(update): return
    user = update.effective_user
    data = load(); u = get_user(data, user.id, user.username or "", user.full_name)
    now = datetime.utcnow(); last = u.get("pet_last")
    if last and now - datetime.fromisoformat(last) < timedelta(hours=6):
        rem = timedelta(hours=6)-(now-datetime.fromisoformat(last))
        h = int(rem.total_seconds())//3600; m = (int(rem.total_seconds())%3600)//60
        await update.message.reply_text(f"🐾 Кормление через *{h}ч {m}м*. Сейчас: *{u['pet_size']} см*", parse_mode="Markdown"); return
    growth = random.randint(-3, 10); u["pet_size"] = max(1, u["pet_size"]+growth); u["pet_last"] = now.isoformat(); save(data)
    emoji = "📈" if growth > 0 else ("📉" if growth < 0 else "➡️")
    msg = "подрос" if growth > 0 else ("усох" if growth < 0 else "не изменился")
    await update.message.reply_text(f"🐾 Питомец {msg}! {emoji}\n📏 *{u['pet_size']} см*", parse_mode="Markdown")

async def pet_top(update, ctx):
    if not await req_fun(update): return
    data = load()
    top = sorted(data["users"].items(), key=lambda x: x[1].get("pet_size",0), reverse=True)[:10]
    text = "🏆 *Топ питомцев:*\n\n"
    for i,(uid,u) in enumerate(top,1):
        medal = {1:"🥇",2:"🥈",3:"🥉"}.get(i,f"{i}.")
        text += f"{medal} {dn(u)} — *{u.get('pet_size',0)} см*\n"
    await update.message.reply_text(text, parse_mode="Markdown")

async def top_xp(update, ctx):
    if not await req_fun(update): return
    data = load()
    top = sorted(data["users"].items(), key=lambda x: x[1].get("xp",0), reverse=True)[:10]
    text = "🏆 *Топ по XP:*\n\n"
    for i,(uid,u) in enumerate(top,1):
        medal = {1:"🥇",2:"🥈",3:"🥉"}.get(i,f"{i}.")
        text += f"{medal} {dn(u)} — {get_rank(u.get('xp',0))} | *{u.get('xp',0)} XP*\n"
    await update.message.reply_text(text, parse_mode="Markdown")

async def top_coins(update, ctx):
    if not await req_fun(update): return
    data = load()
    top = sorted(data["users"].items(), key=lambda x: x[1].get("coins",0), reverse=True)[:10]
    text = "💰 *Топ богачей:*\n\n"
    for i,(uid,u) in enumerate(top,1):
        medal = {1:"🥇",2:"🥈",3:"🥉"}.get(i,f"{i}.")
        text += f"{medal} {dn(u)} — *{u.get('coins',0)} монет*\n"
    await update.message.reply_text(text, parse_mode="Markdown")

SLOTS = ["🍒","🍋","🍊","🍇","⭐","💎","7️⃣"]

async def casino(update, ctx):
    if not await req_fun(update): return
    user = update.effective_user
    if not ctx.args: await update.message.reply_text("🎰 /casino <ставка>"); return
    data = load(); u = get_user(data, user.id, user.username or "", user.full_name)
    try:
        bet = int(ctx.args[0])
        if bet <= 0 or bet > u["coins"]: raise ValueError
    except ValueError:
        await update.message.reply_text(f"❌ Некорректная ставка. У тебя {u['coins']} монет."); return
    s1,s2,s3 = [random.choice(SLOTS) for _ in range(3)]
    line = f"{s1} | {s2} | {s3}"
    if s1==s2==s3=="7️⃣": mult,result = 10,"🎉 ДЖЕКПОТ!"
    elif s1==s2==s3: mult,result = 5,"🎊 Три в ряд!"
    elif s1==s2 or s2==s3 or s1==s3: mult,result = 2,"✨ Два совпадения!"
    else: mult,result = 0,"😔 Не повезло..."
    if mult:
        won = bet*mult; u["coins"] += won-bet; u["xp"] += 3
        msg = f"{result}\n{line}\n\n+*{won} монет* (x{mult})!\n💰 {u['coins']}"
    else:
        u["coins"] -= bet
        msg = f"{result}\n{line}\n\n-*{bet} монет*\n💰 {u['coins']}"
    save(data)
    await update.message.reply_text(f"🎰 *Слоты*\n\n{msg}", parse_mode="Markdown")

async def flip(update, ctx):
    if not await req_fun(update): return
    user = update.effective_user
    if len(ctx.args) < 2: await update.message.reply_text("🪙 /flip <орёл/решка> <ставка>"); return
    choice = ctx.args[0].lower().replace("орел","орёл")
    if choice not in ("орёл","решка"): await update.message.reply_text("❌ орёл или решка"); return
    data = load(); u = get_user(data, user.id, user.username or "", user.full_name)
    try:
        bet = int(ctx.args[1])
        if bet <= 0 or bet > u["coins"]: raise ValueError
    except ValueError:
        await update.message.reply_text(f"❌ Некорректная ставка. У тебя {u['coins']}."); return
    result = random.choice(["орёл","решка"])
    if choice == result: u["coins"] += bet; u["xp"] += 2; msg = f"🪙 *{result}* — угадал! +*{bet}*"
    else: u["coins"] -= bet; msg = f"🪙 *{result}* — не угадал. -*{bet}*"
    save(data)
    await update.message.reply_text(f"{msg}\n💰 {u['coins']}", parse_mode="Markdown")

async def dice_game(update, ctx):
    if not await req_fun(update): return
    user = update.effective_user
    if not ctx.args: await update.message.reply_text("🎲 /dice <ставка>"); return
    data = load(); u = get_user(data, user.id, user.username or "", user.full_name)
    try:
        bet = int(ctx.args[0])
        if bet <= 0 or bet > u["coins"]: raise ValueError
    except ValueError:
        await update.message.reply_text(f"❌ Некорректная ставка. У тебя {u['coins']}."); return
    p,b = random.randint(1,6),random.randint(1,6)
    if p > b: u["coins"] += bet; u["xp"] += 2; r = f"🎲 {p} vs {b} — Победа! +*{bet}*"
    elif p < b: u["coins"] -= bet; r = f"🎲 {p} vs {b} — Поражение. -*{bet}*"
    else: r = f"🎲 {p} vs {b} — Ничья!"
    save(data)
    await update.message.reply_text(f"{r}\n💰 {u['coins']}", parse_mode="Markdown")

async def roulette(update, ctx):
    if not await req_fun(update): return
    user = update.effective_user
    if len(ctx.args) < 2: await update.message.reply_text("🎡 /roulette <красное/чёрное/0-36> <ставка>"); return
    data = load(); u = get_user(data, user.id, user.username or "", user.full_name)
    try:
        bet = int(ctx.args[-1])
        if bet <= 0 or bet > u["coins"]: raise ValueError
    except ValueError:
        await update.message.reply_text(f"❌ Некорректная ставка. У тебя {u['coins']}."); return
    choice = ctx.args[0].lower(); spin = random.randint(0,36)
    reds = {1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36}
    color = "🔴" if spin in reds else ("⚫" if spin else "🟢")
    if choice in ("красное","красный"): won = spin in reds; mult = 2
    elif choice in ("чёрное","чёрный"): won = spin not in reds and spin != 0; mult = 2
    else:
        try: num = int(choice); won = spin == num; mult = 36
        except ValueError: await update.message.reply_text("❌ красное / чёрное / число 0-36"); return
    if won:
        gain = bet*mult-bet; u["coins"] += gain; u["xp"] += 3; result = f"✅ +*{gain} монет*"
    else:
        u["coins"] -= bet; result = f"❌ -*{bet} монет*"
    save(data)
    await update.message.reply_text(f"🎡 Выпало: *{spin}* {color}\n{result}\n💰 {u['coins']}", parse_mode="Markdown")

async def propose(update, ctx):
    if not await req_fun(update): return
    user = update.effective_user
    if not update.message.reply_to_message: await update.message.reply_text("💍 Ответь на сообщение."); return
    t = update.message.reply_to_message.from_user
    if t.id == user.id: await update.message.reply_text("😅 Нельзя жениться на себе."); return
    data = load()
    u = get_user(data, user.id, user.username or "", user.full_name)
    tv = get_user(data, t.id, t.username or "", t.full_name)
    if u.get("married_to"): await update.message.reply_text("💔 Ты уже в браке. /divorce"); return
    if tv.get("married_to"): await update.message.reply_text(f"💔 {dn(tv)} уже в браке."); return
    if str(user.id) in tv.get("proposals",[]): await update.message.reply_text("⏳ Уже отправлял предложение."); return
    if "proposals" not in tv: tv["proposals"] = []
    tv["proposals"].append(str(user.id)); save(data)
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("💍 Принять", callback_data=f"marry_accept_{user.id}"),
        InlineKeyboardButton("❌ Отклонить", callback_data=f"marry_decline_{user.id}"),
    ]])
    await update.message.reply_text(
        f"💍 *{dn(u)}* делает предложение *{dn(tv)}*!\n{dn(tv)}, согласен(на)?",
        parse_mode="Markdown", reply_markup=kb
    )

async def marry_callback(update, ctx):
    query = update.callback_query; await query.answer()
    user = query.from_user; parts = query.data.split("_")
    action, proposer_id = parts[1], int(parts[2])
    data = load()
    u = get_user(data, user.id, user.username or "", user.full_name)
    p = get_user(data, proposer_id)
    if str(proposer_id) not in u.get("proposals",[]): await query.edit_message_text("❌ Предложение недействительно."); return
    u["proposals"].remove(str(proposer_id))
    if action == "accept":
        u["married_to"] = str(proposer_id); p["married_to"] = str(user.id); save(data)
        await query.edit_message_text(f"🎊 *{dn(p)}* и *{dn(u)}* теперь в браке! 💍", parse_mode="Markdown")
    else:
        save(data)
        await query.edit_message_text(f"💔 *{dn(u)}* отклонил(а) предложение.", parse_mode="Markdown")

async def divorce(update, ctx):
    if not await req_fun(update): return
    user = update.effective_user
    data = load(); u = get_user(data, user.id, user.username or "", user.full_name)
    if not u.get("married_to"): await update.message.reply_text("💭 Ты не в браке."); return
    partner = data["users"].get(u["married_to"], {})
    u["married_to"] = ""
    if partner: partner["married_to"] = ""
    save(data)
    await update.message.reply_text(f"💔 *{dn(u)}* и *{dn(partner)}* развелись.", parse_mode="Markdown")

# ── CHANNEL POST ──────────────────────────────────────────────────────────────
async def channel_post(update, ctx):
    """
    Когда пост появляется в канале — Telegram автоматически пересылает его
    в группу обсуждений. Это создаёт сообщение с forward_from_message_id.
    Ловим ЭТО сообщение в группе и отвечаем на него.
    """
    post = update.channel_post
    if not post: return
    # Сохраняем message_id поста и chat_id канала
    # Обработка происходит через discussion_reply_handler ниже
    pass

async def discussion_reply_handler(update, ctx):
    """
    Ловим сообщения в группе обсуждений, которые являются
    автоматическим форвардом поста из канала (is_automatic_forward=True).
    Отвечаем на них правилами.
    """
    msg = update.message
    if not msg: return
    # Telegram автоматически форвардит пост канала в группу обсуждений
    # Такое сообщение имеет флаг is_automatic_forward=True
    if not getattr(msg, "is_automatic_forward", False): return
    try:
        await msg.reply_text(
            CHANNEL_RULES,
            parse_mode="MarkdownV2",
        )
    except Exception as e:
        logger.warning("discussion_reply error: %s", e)

# ── XP on message ─────────────────────────────────────────────────────────────
async def on_message(update, ctx):
    user = update.effective_user
    if not user or user.is_bot: return
    data = load(); u = get_user(data, user.id, user.username or "", user.full_name)
    u["msg_count"] = u.get("msg_count",0) + 1
    if u["msg_count"] % 5 == 0: u["xp"] += 2
    save(data)

# ── /help ─────────────────────────────────────────────────────────────────────
async def help_cmd(update, ctx):
    fun = is_fun()
    fun_block = (
        "\n🎮 *Развлечения*\n"
        "/profile — профиль\n/nick <ник>\n/top — топ XP\n/top\\_coins\n"
        "/balance\n/daily — бонус\n/work — работа\n/give <сумма> (reply)\n"
        "/casino <ставка>\n/flip <орёл/решка> <ставка>\n"
        "/dice <ставка>\n/roulette <цвет/число> <ставка>\n"
        "/pet — питомец\n/pet\\_top\n/propose (reply)\n/divorce"
    ) if fun else "\n🔒 *Развлечения отключены* (/funon для включения)"
    await update.message.reply_text(
        "📖 *Команды бота*\n\n"
        "⚙️ *Модерация* (бот-админы)\n"
        "/ban [причина] (reply)\n"
        "/unban (reply)\n"
        "/kick [причина] (reply)\n"
        "/mute <10m/2h/1d> [причина] (reply)\n"
        "/unmute (reply)\n"
        "/ro <время> (reply) — режим чтения\n"
        "/strike [причина] (reply)\n"
        "/unstrike (reply)\n"
        "/warn [причина] (reply)\n"
        "/purge <N> — удалить сообщения\n"
        "/userinfo (reply)\n"
        "/addcoins <сумма> (reply)\n"
        "/funoff — выкл. развлечения\n"
        "/funon — вкл. развлечения\n\n"
        "🔑 *Авторизация*\n"
        "/admin <пароль>\n"
        "/revoke"
        f"{fun_block}",
        parse_mode="Markdown"
    )

# ── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    app = ApplicationBuilder().token(TOKEN).build()
    for cmd, fn in [
        ("start", help_cmd), ("help", help_cmd),
        ("admin", admin_cmd), ("revoke", revoke_cmd),
        ("ban", ban_cmd), ("unban", unban_cmd), ("kick", kick_cmd),
        ("mute", mute_cmd), ("unmute", unmute_cmd),
        ("ro", ro_cmd), ("purge", purge_cmd),
        ("strike", strike_cmd), ("unstrike", unstrike_cmd),
        ("warn", warn_cmd), ("userinfo", userinfo_cmd),
        ("funoff", funoff_cmd), ("funon", funon_cmd),
        ("addcoins", add_coins),
        ("profile", profile), ("nick", set_nick), ("balance", balance),
        ("give", give_coins), ("daily", daily), ("work", work),
        ("pet", pet_cmd), ("pet_top", pet_top),
        ("top", top_xp), ("top_coins", top_coins),
        ("casino", casino), ("flip", flip), ("dice", dice_game), ("roulette", roulette),
        ("propose", propose), ("divorce", divorce),
    ]:
        app.add_handler(CommandHandler(cmd, fn))
    app.add_handler(CallbackQueryHandler(marry_callback, pattern="^marry_"))
    app.add_handler(MessageHandler(filters.UpdateType.CHANNEL_POSTS, channel_post))
    # Ловим автофорвард поста в группе обсуждений
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, discussion_reply_handler), group=1)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))
    logger.info("Group bot started")
    app.run_polling()

if __name__ == "__main__":
    main()
