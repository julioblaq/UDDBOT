#!/usr/bin/env python3
"""
uddbot.py — UrbanDramaDetective Telegram bot.
Scrapes WorldStar HipHop, The Shade Room, and AllHipHop for content ideas.
"""

import os
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
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

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

def main():
    log.info("👀 UDDBot starting...")
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start",     start))
    app.add_handler(CommandHandler("help",      help_cmd))
    app.add_handler(CommandHandler("stories",   stories_cmd))
    app.add_handler(CommandHandler("shaderoom", shaderoom_cmd))
    app.add_handler(CommandHandler("worldstar", worldstar_cmd))
    app.add_handler(CommandHandler("allhiphop", allhiphop_cmd))
    app.add_handler(CommandHandler("search",    search_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    log.info("✅ UDDBot is live")
    app.run_polling()

if __name__ == "__main__":
    main()
