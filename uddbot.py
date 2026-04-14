#!/usr/bin/env python3
"""
uddbot.py — UrbanDramaDetective Telegram bot.
Scrapes WorldStar HipHop, The Shade Room, and AllHipHop for content ideas.

Bot-to-bot: Listens for READY_SIGNAL messages from @MindLyftBot in the
YouTube Automation Hub group (-1003989231611) and distributes the
YouTube link to configured channels.
"""

import os
import json
import html
import logging
from collections import OrderedDict
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters
)
from scraper import scrape_site, scrape_all, search_content

load_dotenv()
logging.basicConfig(format="%(asctime)s [%(levelname)s] %(message)s", level=logging.INFO)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# BUG-12 fix: validate required env vars at startup, fail fast with clear error
# ---------------------------------------------------------------------------
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TELEGRAM_TOKEN:
    raise EnvironmentError("TELEGRAM_BOT_TOKEN is not set. UDDBot cannot start.")

JARVIS_GROUP_ID   = int(os.getenv("JARVIS_GROUP_CHAT_ID", "-1003989231611"))
OWNER_CHAT_ID     = os.getenv("OWNER_CHAT_ID")

# BUG-03 fix: authenticate by bot user ID, not username (username is Optional in Telegram API)
# Set MINDLYFT_BOT_ID in Railway env vars — get it by sending /start to @userinfobot
# while logged in as MindLyftBot, or by calling getMe on the MindLyft token.
MINDLYFT_BOT_ID   = int(os.getenv("MINDLYFT_BOT_ID", "0"))


# ---------------------------------------------------------------------------
# BUG-08 fix: dedup using OrderedDict (evicts oldest entry, no mass clear)
# ---------------------------------------------------------------------------
_seen_message_ids: OrderedDict = OrderedDict()
_DEDUP_MAX = 500


def _is_new_message(message_id: int) -> bool:
    if message_id in _seen_message_ids:
        return False
    _seen_message_ids[message_id] = True
    if len(_seen_message_ids) > _DEDUP_MAX:
        _seen_message_ids.popitem(last=False)  # evict oldest
    return True


# ---------------------------------------------------------------------------
# BUG-05 fix: robust READY_SIGNAL parser using plain JSON (no markdown fences)
# ---------------------------------------------------------------------------

def _parse_ready_payload(text: str) -> dict | None:
    """
    Parse a READY_SIGNAL message from MindLyftBot.
    Format: "READY_SIGNAL\n{json}"
    Returns the payload dict or None if parsing fails.
    """
    if not text.startswith("READY_SIGNAL"):
        return None
    try:
        # Everything after the first newline is raw JSON
        _, _, raw = text.partition("\n")
        return json.loads(raw.strip())
    except (json.JSONDecodeError, ValueError) as e:
        log.warning(f"Failed to parse READY_SIGNAL payload: {e}")
        return None


# ---------------------------------------------------------------------------
# Existing command handlers
# ---------------------------------------------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👀 *UrbanDramaDetective Bot*\n\nYour content research assistant.\n\n"
        "/stories — Latest from all sites\n/shaderoom — The Shade Room\n"
        "/worldstar — WorldStar HipHop\n/allhiphop — AllHipHop News\n"
        "/search <query> — Search for content\n/help — Show this menu",
        parse_mode="Markdown"
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start(update, context)

async def stories_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 Pulling stories from all sites...", parse_mode="Markdown")
    all_stories = scrape_all()
    total = sum(len(v) for v in all_stories.values())
    if total == 0:
        await update.message.reply_text("❌ No stories found. Try again in a moment.")
        return
    for site_key, stories in all_stories.items():
        if not stories:
            continue
        label = site_key.replace("shaderoom","The Shade Room").replace("worldstar","WorldStar").replace("allhiphop","AllHipHop")
        lines = [f"📰 *{label}*\n"]
        for s in stories[:5]:
            lines.append(f"• [{s['title'][:80]}]({s['url']})")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown", disable_web_page_preview=True)

async def site_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE, site_key: str):
    labels = {"shaderoom":"The Shade Room","worldstar":"WorldStar HipHop","allhiphop":"AllHipHop"}
    label = labels.get(site_key, site_key)
    await update.message.reply_text(f"🔍 Pulling from *{label}*...", parse_mode="Markdown")
    stories = scrape_site(site_key)
    if not stories:
        await update.message.reply_text(f"❌ Nothing found from {label} right now.")
        return
    lines = [f"📰 *{label}*\n"]
    for s in stories[:10]:
        lines.append(f"• [{s['title'][:80]}]({s['url']})")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown", disable_web_page_preview=True)

async def shaderoom_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await site_cmd(update, context, "shaderoom")

async def worldstar_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await site_cmd(update, context, "worldstar")

async def allhiphop_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await site_cmd(update, context, "allhiphop")

async def search_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = " ".join(context.args) if context.args else ""
    if not query:
        await update.message.reply_text("Usage: `/search <topic>`\n\nExample: `/search Drake beef`", parse_mode="Markdown")
        return
    await update.message.reply_text(f"🔍 Searching for: *{query}*...", parse_mode="Markdown")
    results = search_content(query)
    if not results:
        await update.message.reply_text("No results found.")
        return
    lines = [f"🔍 *Results: {query}*\n"]
    for r in results:
        lines.append(f"• [{r['title'][:80]}]({r['url']})")
        if r["snippet"]:
            lines.append(f"  _{r['snippet'][:100]}_")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown", disable_web_page_preview=True)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat.id == JARVIS_GROUP_ID:
        return
    query = update.message.text.strip()
    await update.message.reply_text(f"🔍 Searching for: *{query}*...", parse_mode="Markdown")
    results = search_content(query)
    if not results:
        await update.message.reply_text("No results found. Try `/stories` to see what's trending.")
        return
    lines = [f"🔍 *{query}*\n"]
    for r in results[:5]:
        lines.append(f"• [{r['title'][:80]}]({r['url']})")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown", disable_web_page_preview=True)


# ---------------------------------------------------------------------------
# Bot-to-bot: READY_SIGNAL listener
# ---------------------------------------------------------------------------

async def handle_ready_signal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Fires when a message arrives in the YouTube Automation Hub group.
    Only acts on READY_SIGNAL messages from MindLyftBot (validated by user ID).
    """
    msg = update.message
    if not msg:
        return

    # BUG-08 fix: rolling dedup
    if not _is_new_message(msg.message_id):
        log.debug(f"Duplicate message_id {msg.message_id} — skipping.")
        return

    # BUG-03 fix: validate by numeric user ID, not username
    sender = msg.from_user
    if not sender:
        return
    if MINDLYFT_BOT_ID and sender.id != MINDLYFT_BOT_ID:
        return  # not from MindLyftBot — ignore silently

    text = msg.text or ""
    payload = _parse_ready_payload(text)
    if not payload:
        return

    video_url = payload.get("video_url", "")
    title     = payload.get("title", "New MindLyft video")

    log.info(f"✅ READY_SIGNAL received from MindLyftBot: {video_url}")

    # BUG-04 fix: use HTML parse mode + html.escape() on user data
    safe_title = html.escape(title[:80])
    safe_url   = html.escape(video_url)

    # ── Action 1: Acknowledge in the group ──
    ack = (
        f"✅ <b>[UDDBot ACK]</b>\n"
        f"MindLyft video received and logged.\n\n"
        f'🎥 <a href="{safe_url}">{safe_title}</a>'
    )
    # BUG-06 fix: wrap sends in try/except
    try:
        await context.bot.send_message(
            chat_id=JARVIS_GROUP_ID,
            text=ack,
            parse_mode="HTML",
            disable_web_page_preview=False,
        )
    except Exception as e:
        log.error(f"❌ Failed to send group ACK: {e}")

    # ── Action 2: Ping owner's personal chat ──
    if OWNER_CHAT_ID:
        owner_msg = (
            f"🔔 <b>MindLyft video just dropped!</b>\n\n"
            f"📺 {safe_title}\n"
            f"🔗 {safe_url}"
        )
        try:
            await context.bot.send_message(
                chat_id=int(OWNER_CHAT_ID),
                text=owner_msg,
                parse_mode="HTML",
            )
            log.info(f"📨 Owner notified at {OWNER_CHAT_ID}")
        except Exception as e:
            log.error(f"❌ Failed to notify owner: {e}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    log.info("👀 UDDBot starting...")

    if MINDLYFT_BOT_ID == 0:
        log.warning("⚠️  MINDLYFT_BOT_ID not set — [READY] signals will be accepted from ANY sender in the group. Set this env var for security.")

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start",     start))
    app.add_handler(CommandHandler("help",      help_cmd))
    app.add_handler(CommandHandler("stories",   stories_cmd))
    app.add_handler(CommandHandler("shaderoom", shaderoom_cmd))
    app.add_handler(CommandHandler("worldstar", worldstar_cmd))
    app.add_handler(CommandHandler("allhiphop", allhiphop_cmd))
    app.add_handler(CommandHandler("search",    search_cmd))

    # BUG-07 note: if group gets promoted to supergroup, update JARVIS_GROUP_CHAT_ID env var
    app.add_handler(MessageHandler(
        filters.Chat(JARVIS_GROUP_ID) & filters.TEXT & ~filters.COMMAND,
        handle_ready_signal,
    ))

    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & ~filters.Chat(JARVIS_GROUP_ID),
        handle_message,
    ))

    log.info("✅ UDDBot is live — listening for READY_SIGNAL from MindLyftBot")
    app.run_polling()


if __name__ == "__main__":
    main()
