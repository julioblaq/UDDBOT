#!/usr/bin/env python3
"""
uddbot.py — UrbanDramaDetective Telegram bot.
Scrapes WorldStar HipHop, The Shade Room, and AllHipHop for content ideas.

Bot-to-bot: Listens for [READY] signals from @MindLyftBot in the
YouTube Automation Hub group (-1003989231611) and distributes the
YouTube link to configured channels.
"""

import os
import json
import logging
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

TELEGRAM_TOKEN     = os.getenv("TELEGRAM_BOT_TOKEN")
JARVIS_GROUP_ID    = int(os.getenv("JARVIS_GROUP_CHAT_ID", "-1003989231611"))
MINDLYFT_BOT_NAME  = "MindLyftBot"

# Optional: personal chat to ping when a video drops
OWNER_CHAT_ID      = os.getenv("OWNER_CHAT_ID")   # your personal Telegram chat ID


# ---------------------------------------------------------------------------
# Existing command handlers (unchanged)
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
    # Skip group messages that aren't [READY] signals — handled separately
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
# Bot-to-bot: [READY] signal listener
# ---------------------------------------------------------------------------

# Simple in-memory dedup — prevents acting on the same message_id twice
_seen_message_ids: set = set()


def _parse_ready_payload(text: str) -> dict | None:
    """
    Parse a [READY] message from MindLyftBot.
    Returns the payload dict or None if parsing fails.
    """
    if not text.startswith("[READY]"):
        return None
    try:
        # Strip the [READY] prefix and any markdown code fences
        raw = text.replace("[READY]", "").strip()
        raw = raw.strip("`").strip()
        if raw.startswith("json"):
            raw = raw[4:].strip()
        return json.loads(raw)
    except (json.JSONDecodeError, ValueError) as e:
        log.warning(f"Failed to parse [READY] payload: {e}")
        return None


async def handle_ready_signal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Fires when a message arrives in the YouTube Automation Hub group.
    Only acts on [READY] messages from @MindLyftBot.
    """
    msg = update.message
    if not msg:
        return

    # Dedup by message_id
    if msg.message_id in _seen_message_ids:
        return
    _seen_message_ids.add(msg.message_id)
    # Keep set from growing forever
    if len(_seen_message_ids) > 500:
        _seen_message_ids.clear()

    # Validate source — must be from MindLyftBot
    sender = msg.from_user
    if not sender or sender.username != MINDLYFT_BOT_NAME:
        return

    text = msg.text or ""
    payload = _parse_ready_payload(text)
    if not payload:
        return

    video_url = payload.get("video_url", "")
    title     = payload.get("title", "New MindLyft video")

    log.info(f"✅ [READY] received from MindLyftBot: {video_url}")

    # ── Action 1: Acknowledge in the group ──
    ack = (
        f"✅ *[UDDBot ACK]*\n"
        f"MindLyft video received and logged.\n\n"
        f"🎥 [{title[:80]}]({video_url})"
    )
    await context.bot.send_message(
        chat_id=JARVIS_GROUP_ID,
        text=ack,
        parse_mode="Markdown",
        disable_web_page_preview=False,
    )

    # ── Action 2: Ping owner's personal chat (if configured) ──
    if OWNER_CHAT_ID:
        owner_msg = (
            f"🔔 *MindLyft video just dropped!*\n\n"
            f"📺 {title[:80]}\n"
            f"🔗 {video_url}"
        )
        await context.bot.send_message(
            chat_id=int(OWNER_CHAT_ID),
            text=owner_msg,
            parse_mode="Markdown",
        )
        log.info(f"📨 Owner notified at {OWNER_CHAT_ID}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    log.info("👀 UDDBot starting...")
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # Existing command handlers
    app.add_handler(CommandHandler("start",     start))
    app.add_handler(CommandHandler("help",      help_cmd))
    app.add_handler(CommandHandler("stories",   stories_cmd))
    app.add_handler(CommandHandler("shaderoom", shaderoom_cmd))
    app.add_handler(CommandHandler("worldstar", worldstar_cmd))
    app.add_handler(CommandHandler("allhiphop", allhiphop_cmd))
    app.add_handler(CommandHandler("search",    search_cmd))

    # Bot-to-bot: listen for [READY] signals in the Jarvis group
    app.add_handler(MessageHandler(
        filters.Chat(JARVIS_GROUP_ID) & filters.TEXT & ~filters.COMMAND,
        handle_ready_signal,
    ))

    # DM fallback for regular users
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & ~filters.Chat(JARVIS_GROUP_ID),
        handle_message,
    ))

    log.info("✅ UDDBot is live — listening for [READY] signals from MindLyftBot")
    app.run_polling()

if __name__ == "__main__":
    main()
