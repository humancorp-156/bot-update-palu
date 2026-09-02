import os
import re
import asyncio
import logging
import threading
import time
import requests

from datetime import datetime
from flask import Flask, jsonify

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)


# =========================================================
# CONFIG
# =========================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
APPS_SCRIPT_URL = os.getenv("APPS_SCRIPT_URL")
API_KEY = os.getenv("API_KEY")

PORT = int(os.getenv("PORT", "10000"))

APPS_SCRIPT_TIMEOUT = 45

BOT_VERSION = "16.0"


# =========================================================
# LOGGING
# =========================================================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger("BOT_PALU")


# =========================================================
# FLASK
# =========================================================

app = Flask(__name__)


@app.route("/")
def home():

    return jsonify({
        "status": "online",
        "bot": "BOT UPDATE ORDER PALU",
        "version": BOT_VERSION,
        "time": datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
    })


@app.route("/health")
def health():

    return jsonify({
        "status": "online",
        "bot": "BOT UPDATE ORDER PALU",
        "version": BOT_VERSION,
        "time": datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
    })


# =========================================================
# VALID ERROR CODE
# =========================================================

VALID_ERROR_CODES = [
    "KENDALA TEKNIK",
    "KENDALA PELANGGAN",
    "KENDALA SISTEM",
    "PS",
    "PENARIKAN",
    "SURVEI",
    "BELUM SURVEI",
    "REGISTRASI",
    "BUTUH EXPAND ODP",
    "CANCEL",
]


# =========================================================
# MARKDOWN ESCAPE
# =========================================================

def escape_markdown(text):

    if text is None:
        return ""

    text = str(text)

    characters = [
        "_",
        "*",
        "[",
        "]",
        "(",
        ")",
        "~",
        "`",
        ">",
        "#",
        "+",
        "-",
        "=",
        "|",
        "{",
        "}",
        ".",
        "!",
    ]

    for char in characters:
        text = text.replace(
            char,
            "\\" + char
        )

    return text


# =========================================================
# CONFIG CHECK
# =========================================================

def check_config():

    missing = []

    if not BOT_TOKEN:
        missing.append("BOT_TOKEN")

    if not APPS_SCRIPT_URL:
        missing.append("APPS_SCRIPT_URL")

    if not API_KEY:
        missing.append("API_KEY")

    if missing:

        logger.error(
            "CONFIG ERROR | Missing: %s",
            ", ".join(missing),
        )

        return False

    logger.info(
        "CONFIG OK | BOT_TOKEN=SET | APPS_SCRIPT_URL=SET | API_KEY=SET"
    )

    logger.info(
        "BOT VERSION = %s",
        BOT_VERSION,
    )

    return True


# =========================================================
# DEBUG EVERY INCOMING MESSAGE
# =========================================================

async def debug_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    try:

        if not update.message:
            return

        text = (
            update.message.text
            or update.message.caption
            or ""
        )

        user = update.effective_user

        if user:

            username = (
                user.username
                or user.full_name
                or str(user.id)
            )

        else:

            username = "-"

        logger.info(
            "INCOMING MESSAGE | USER=%s | TEXT=%r",
            username,
            text,
        )

    except Exception:

        logger.exception(
            "DEBUG MESSAGE ERROR"
        )


# =========================================================
# TELEGRAM ERROR HANDLER
# =========================================================

async def telegram_error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE,
):

    logger.error(
        "TELEGRAM HANDLER ERROR | %s",
        context.error,
        exc_info=context.error,
    )


# =========================================================
# GOOGLE APPS SCRIPT
# =========================================================

def call_apps_script(payload):

    if not APPS_SCRIPT_URL:

        raise Exception(
            "APPS_SCRIPT_URL belum diatur."
        )

    request_payload = dict(payload)

    request_payload["api_key"] = API_KEY

    action = request_payload.get(
        "action",
        "-"
    )

    logger.info(
        "APPS SCRIPT REQUEST | action=%s",
        action,
    )

    start_time = time.time()

    try:

        response = requests.post(
            APPS_SCRIPT_URL,
            json=request_payload,
            timeout=APPS_SCRIPT_TIMEOUT,
        )

        elapsed = (
            time.time() - start_time
        )

        logger.info(
            "APPS SCRIPT RESPONSE | status=%s | %.2f sec",
            response.status_code,
            elapsed,
        )

        response.raise_for_status()

        try:

            result = response.json()

        except Exception:

            logger.error(
                "APPS SCRIPT INVALID JSON | %s",
                response.text[:500],
            )

            raise Exception(
                "Response Google Apps Script bukan JSON."
            )

        logger.info(
            "APPS SCRIPT RESULT | %r",
            result,
        )

        return result

    except requests.exceptions.Timeout:

        logger.error(
            "APPS SCRIPT TIMEOUT | %.2f sec",
            APPS_SCRIPT_TIMEOUT,
        )

        raise

    except requests.exceptions.RequestException as e:

        logger.error(
            "APPS SCRIPT REQUEST ERROR | %s",
            e,
        )

        raise


# =========================================================
# PARSE UPDATE
# =========================================================

def parse_update(text):

    result = {}

    for line in text.splitlines():

        line = line.strip()

        if not line:
            continue

        if ":" not in line:
            continue

        key, value = line.split(
            ":",
            1
        )

        key = key.strip().upper()

        value = value.strip()

        if key == "TRACK ID":

            result["track_id"] = value

        elif key == "ERROR CODE":

            result["error_code"] = (
                value.upper()
            )

        elif key in (
            "SUB ERROR",
            "SUBERROR",
            "SUB-ERROR",
        ):

            result["sub_error"] = value

    return result


# =========================================================
# /START
# =========================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    message = """
👋 *BOT UPDATE ORDER*
*Service Area Palu*

📌 *Cara menggunakan:*

/update
Track Id : SC1002373501
Error Code : SURVEI
Sub Error : Keterangan bebas

📊 *Command:*

/cekperform
/ranking

📋 *Error Code valid:*

• KENDALA TEKNIK
• KENDALA PELANGGAN
• KENDALA SISTEM
• PS
• PENARIKAN
• SURVEI
• BELUM SURVEI
• REGISTRASI
• BUTUH EXPAND ODP
• CANCEL
"""

    await update.message.reply_text(
        message,
        parse_mode="Markdown",
    )

    logger.info(
        "START COMMAND SUCCESS | USER=%s",
        (
            update.effective_user.username
            if update.effective_user
            else "-"
        ),
    )


# =========================================================
# /UPDATE
# =========================================================

async def update_order(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    track_id = "-"
    error_code = "-"
    sub_error = "-"

    try:

        if not update.message:

            logger.warning(
                "UPDATE WITHOUT MESSAGE"
            )

            return

        user_message = (
            update.message.text
            or ""
        )

        logger.info(
            "UPDATE COMMAND RECEIVED | TEXT=%r",
            user_message,
        )

        text = re.sub(
            r"^/update(@\w+)?",
            "",
            user_message,
            flags=re.IGNORECASE,
        ).strip()

        data = parse_update(
            text
        )

        track_id = data.get(
            "track_id"
        )

        error_code = data.get(
            "error_code"
        )

        sub_error = data.get(
            "sub_error"
        )

        # -----------------------------------------------------
        # VALIDASI
        # -----------------------------------------------------

        if (
            not track_id
            or not error_code
            or not sub_error
        ):

            logger.warning(
                "UPDATE FORMAT INVALID | DATA=%r",
                data,
            )

            await update.message.reply_text(

                "❌ *Format tidak lengkap.*\n\n"

                "Gunakan:\n\n"

                "/update\n"

                "Track Id : XXXXX\n"

                "Error Code : SURVEI\n"

                "Sub Error : Keterangan",

                parse_mode="Markdown",
            )

            return

        # -----------------------------------------------------
        # ERROR CODE
        # -----------------------------------------------------

        if error_code not in VALID_ERROR_CODES:

            logger.warning(
                "INVALID ERROR CODE | %s",
                error_code,
            )

            error_list = "\n".join(
                f"• {x}"
                for x in VALID_ERROR_CODES
            )

            await update.message.reply_text(

                "❌ *ERROR CODE tidak valid.*\n\n"
                + error_list,

                parse_mode="Markdown",
            )

            return

        # -----------------------------------------------------
        # USER
        # -----------------------------------------------------

        user = update.effective_user

        if user and user.username:

            updated_by = (
                f"@{user.username}"
            )

        elif user:

            updated_by = (
                user.full_name
                or str(user.id)
            )

        else:

            updated_by = "Unknown User"

        # -----------------------------------------------------
        # LOG
        # -----------------------------------------------------

        logger.info(
            "UPDATE START | TRACK=%s | ERROR=%s | SUBERROR=%s | USER=%s",
            track_id,
            error_code,
            sub_error,
            updated_by,
        )

        # -----------------------------------------------------
        # FEEDBACK 1
        # -----------------------------------------------------

        await update.message.reply_text(
            "🔎 Sedang mencari TRACK ID..."
        )

        # -----------------------------------------------------
        # APPS SCRIPT
        # -----------------------------------------------------

        result = await asyncio.to_thread(
            call_apps_script,
            {
                "action": "update",
                "track_id": track_id,
                "error_code": error_code,
                "sub_error": sub_error,
                "user": updated_by,
            },
        )

        # -----------------------------------------------------
        # RESULT
        # -----------------------------------------------------

        success = bool(
            isinstance(result, dict)
            and result.get("success") is True
        )

        logger.info(
            "UPDATE RESULT | success=%s",
            success,
        )

        if not success:

            error_message = (
                "Update gagal."
            )

            if isinstance(
                result,
                dict
            ):

                error_message = (
                    result.get("message")
                    or result.get("error")
                    or error_message
                )

            await update.message.reply_text(

                "❌ *UPDATE GAGAL!*\n\n"
                + escape_markdown(
                    error_message
                ),

                parse_mode="Markdown",
            )

            return

        # -----------------------------------------------------
        # SUCCESS
        # -----------------------------------------------------

        row = (
            result.get("row", "-")
            if isinstance(result, dict)
            else "-"
        )

        processing_ms = (
            result.get(
                "processing_ms",
                "-"
            )
            if isinstance(result, dict)
            else "-"
        )

        now = datetime.now().strftime(
            "%d-%m-%Y %H:%M:%S"
        )

        message = (

            "✅ *UPDATE BERHASIL!*\n\n"

            f"📦 *TRACK ID*\n"
            f"`{escape_markdown(track_id)}`\n\n"

            f"🔄 *Error Code*\n"
            f"*{escape_markdown(error_code)}*\n\n"

            f"📝 *Sub Error*\n"
            f"{escape_markdown(sub_error)}\n\n"

            f"👤 *Oleh*\n"
            f"{escape_markdown(updated_by)}\n\n"

            f"📍 *Row:* {row}\n"

            f"🕒 {now}\n"

            f"⚡ Proses: *{processing_ms} ms*"
        )

        await update.message.reply_text(
            message,
            parse_mode="Markdown",
        )

        logger.info(
            "UPDATE BERHASIL | TRACK=%s | ROW=%s | PROCESS=%s ms",
            track_id,
            row,
            processing_ms,
        )

    except requests.exceptions.Timeout:

        logger.error(
            "UPDATE APPS SCRIPT TIMEOUT | TRACK=%s",
            track_id,
        )

        try:

            await update.message.reply_text(

                "❌ *Google Sheet terlalu lama merespons.*\n\n"
                "Silakan coba kembali.",

                parse_mode="Markdown",
            )

        except Exception:

            logger.exception(
                "FAILED TO SEND TIMEOUT MESSAGE"
            )

    except requests.exceptions.RequestException as e:

        logger.error(
            "UPDATE REQUEST ERROR | %s",
            e,
        )

        try:

            await update.message.reply_text(

                "❌ *Gagal terhubung ke Google Sheet.*",

                parse_mode="Markdown",
            )

        except Exception:

            logger.exception(
                "FAILED TO SEND REQUEST ERROR"
            )

    except Exception as e:

        logger.exception(
            "UPDATE ORDER ERROR"
        )

        try:

            await update.message.reply_text(

                "❌ *Terjadi error pada bot.*\n\n"
                + escape_markdown(
                    str(e)
                ),

                parse_mode="Markdown",
            )

        except Exception:

            logger.exception(
                "FAILED TO SEND GENERAL ERROR"
            )


# =========================================================
# /CEKPERFORM
# =========================================================

async def cek_perform(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    try:

        await update.message.reply_text(
            "📊 Sedang mengambil data performa..."
        )

        result = await asyncio.to_thread(
            call_apps_script,
            {
                "action": "stats",
            },
        )

        if not (
            isinstance(result, dict)
            and result.get("success") is True
        ):

            message = (
                result.get("message", "Gagal.")
                if isinstance(result, dict)
                else "Gagal."
            )

            await update.message.reply_text(
                "❌ " + str(message)
            )

            return

        total = result.get(
            "total",
            result.get(
                "total_rows",
                0
            ),
        )

        await update.message.reply_text(

            "📊 *DASHBOARD PERFORMA*\n\n"
            f"📦 Total Order: *{total}*",

            parse_mode="Markdown",
        )

    except Exception as e:

        logger.exception(
            "CEKPERFORM ERROR"
        )

        await update.message.reply_text(
            "❌ Gagal mengambil data performa."
        )


# =========================================================
# /RANKING
# =========================================================

async def ranking(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    try:

        await update.message.reply_text(
            "🏆 Sedang menghitung ranking..."
        )

        result = await asyncio.to_thread(
            call_apps_script,
            {
                "action": "ranking",
            },
        )

        if not (
            isinstance(result, dict)
            and result.get("success") is True
        ):

            message = (
                result.get("message", "Gagal.")
                if isinstance(result, dict)
                else "Gagal."
            )

            await update.message.reply_text(
                "❌ " + str(message)
            )

            return

        ranking_data = result.get(
            "ranking",
            []
        )

        message = (
            "🏆 *RANKING PS TEKNISI*\n\n"
        )

        medals = [
            "🥇",
            "🥈",
            "🥉",
        ]

        if not ranking_data:

            message += (
                "Belum ada data PS."
            )

        else:

            for index, item in enumerate(
                ranking_data,
                start=1,
            ):

                team = item.get(
                    "team",
                    "-"
                )

                total = item.get(
                    "total",
                    0
                )

                if index <= 3:

                    icon = medals[
                        index - 1
                    ]

                else:

                    icon = f"{index}."

                message += (

                    f"{icon} "
                    f"*{escape_markdown(str(team))}* "
                    f"— *{total} PS*\n"
                )

        await update.message.reply_text(
            message,
            parse_mode="Markdown",
        )

    except Exception:

        logger.exception(
            "RANKING ERROR"
        )

        await update.message.reply_text(
            "❌ Gagal menghitung ranking."
        )


# =========================================================
# FLASK SERVER
# =========================================================

def run_flask():

    logger.info(
        "FLASK HEALTH SERVER STARTING | PORT=%s",
        PORT,
    )

    app.run(
        host="0.0.0.0",
        port=PORT,
        debug=False,
        use_reloader=False,
    )


# =========================================================
# TELEGRAM BOT
# =========================================================

def run_telegram_bot():

    restart_count = 0

    while True:

        restart_count += 1

        logger.info(
            "========================================"
        )

        logger.info(
            "TELEGRAM BOT START | VERSION=%s | ATTEMPT=%s",
            BOT_VERSION,
            restart_count,
        )

        logger.info(
            "========================================"
        )

        try:

            # -------------------------------------------------
            # BUILD APPLICATION
            # -------------------------------------------------

            application = (

                ApplicationBuilder()

                .token(BOT_TOKEN)

                .concurrent_updates(True)

                .get_updates_timeout(30)

                .get_updates_connect_timeout(30)

                .get_updates_read_timeout(40)

                .get_updates_write_timeout(40)

                .poll_interval(1)

                .build()
            )

            # -------------------------------------------------
            # COMMAND HANDLERS
            # -------------------------------------------------

            application.add_handler(
                CommandHandler(
                    "start",
                    start,
                )
            )

            application.add_handler(
                CommandHandler(
                    "update",
                    update_order,
                )
            )

            application.add_handler(
                CommandHandler(
                    "cekperform",
                    cek_perform,
                )
            )

            application.add_handler(
                CommandHandler(
                    "ranking",
                    ranking,
                )
            )

            # -------------------------------------------------
            # DEBUG ALL MESSAGE
            # -------------------------------------------------

            application.add_handler(

                MessageHandler(
                    filters.ALL,
                    debug_message,
                ),

                group=99,
            )

            # -------------------------------------------------
            # ERROR HANDLER
            # -------------------------------------------------

            application.add_error_handler(
                telegram_error_handler
            )

            # -------------------------------------------------
            # VERIFY TELEGRAM CONNECTION
            # -------------------------------------------------

            logger.info(
                "Memeriksa koneksi Telegram..."
            )

            me = application.bot.get_me()

            logger.info(
                "TELEGRAM BOT CONNECTED | username=@%s | id=%s",
                me.username,
                me.id,
            )

            logger.info(
                "BOT READY — MULAI POLLING TELEGRAM"
            )

            # -------------------------------------------------
            # POLLING
            #
            # INI SEKARANG PROSES UTAMA TELEGRAM
            # -------------------------------------------------

            application.run_polling(
                drop_pending_updates=False,
                stop_signals=None,
            )

            logger.warning(
                "TELEGRAM POLLING BERHENTI."
            )

        except Exception as e:

            logger.exception(
                "TELEGRAM POLLING CRASH | %s",
                e,
            )

            logger.warning(
                "Telegram akan restart dalam 5 detik..."
            )

            time.sleep(5)

        finally:

            logger.info(
                "TELEGRAM BOT LOOP SELESAI | akan cek/restart..."
            )

            time.sleep(1)


# =========================================================
# MAIN
# =========================================================

def main():

    logger.info(
        "========================================"
    )

    logger.info(
        "BOT UPDATE ORDER PALU"
    )

    logger.info(
        "VERSION %s",
        BOT_VERSION,
    )

    logger.info(
        "========================================"
    )

    # -----------------------------------------------------
    # CHECK CONFIG
    # -----------------------------------------------------

    if not check_config():

        logger.error(
            "CONFIG TIDAK LENGKAP."
        )

        raise SystemExit(1)

    # -----------------------------------------------------
    # START FLASK AS BACKGROUND THREAD
    #
    # Flask hanya untuk health check Render.
    # Telegram tetap proses utama.
    # -----------------------------------------------------

    flask_thread = threading.Thread(
        target=run_flask,
        name="flask-health",
        daemon=True,
    )

    flask_thread.start()

    logger.info(
        "Flask health server started."
    )

    # -----------------------------------------------------
    # TELEGRAM = PROSES UTAMA
    # -----------------------------------------------------

    run_telegram_bot()


# =========================================================
# START
# =========================================================

if __name__ == "__main__":

    main()
