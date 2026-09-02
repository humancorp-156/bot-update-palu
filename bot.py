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

BOT_VERSION = "15.0"


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

    return """
    <!DOCTYPE html>
    <html>

    <head>
        <title>Bot Update Order Palu</title>

        <meta
            name="viewport"
            content="width=device-width, initial-scale=1.0"
        >

        <style>

            body {
                font-family: Arial, sans-serif;
                text-align: center;
                padding-top: 80px;
                background: #f5f5f5;
            }

            .box {
                background: white;
                max-width: 500px;
                margin: auto;
                padding: 30px;
                border-radius: 15px;
                box-shadow: 0 5px 20px rgba(0,0,0,0.1);
            }

            .status {
                color: green;
                font-weight: bold;
            }

        </style>

    </head>

    <body>

        <div class="box">

            <h1>🤖 Bot Update Order</h1>

            <p>Service Area Palu</p>

            <p class="status">
                🟢 BOT ONLINE
            </p>

            <p>
                Telegram bot sedang berjalan.
            </p>

            <p>
                Version: 15.0
            </p>

        </div>

    </body>

    </html>
    """


@app.route("/health")
def health():

    return jsonify({

        "status": "online",

        "bot": "Bot Update Order Palu",

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
# ESCAPE MARKDOWN
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
# CHECK CONFIG
# =========================================================

def check_config():

    missing = []

    if not BOT_TOKEN:

        missing.append(
            "BOT_TOKEN"
        )

    if not APPS_SCRIPT_URL:

        missing.append(
            "APPS_SCRIPT_URL"
        )

    if not API_KEY:

        missing.append(
            "API_KEY"
        )

    if missing:

        logger.error(
            "Environment variable belum lengkap: %s",
            ", ".join(missing),
        )

        return False

    logger.info(
        "Environment variable lengkap."
    )

    logger.info(
        "BOT VERSION = %s",
        BOT_VERSION,
    )

    return True


# =========================================================
# DEBUG INCOMING MESSAGE
# =========================================================

async def debug_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    try:

        if not update.message:

            return

        text = (
            update.message.text
            or ""
        )

        user = (
            update.effective_user
        )

        if user:

            username = (
                user.username
                or user.full_name
                or "-"
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
# GOOGLE APPS SCRIPT
# =========================================================

def call_apps_script(payload):

    if not APPS_SCRIPT_URL:

        raise Exception(
            "APPS_SCRIPT_URL belum diatur."
        )

    request_payload = dict(
        payload
    )

    request_payload["api_key"] = API_KEY

    action = request_payload.get(
        "action",
        "-"
    )

    logger.info(
        "Mengirim request Apps Script | action=%s",
        action,
    )

    start_time = datetime.now()

    try:

        response = requests.post(

            APPS_SCRIPT_URL,

            json=request_payload,

            timeout=APPS_SCRIPT_TIMEOUT,

        )

        elapsed = (
            datetime.now()
            - start_time
        ).total_seconds()

        logger.info(
            "Apps Script response diterima | %.2f detik",
            elapsed,
        )

        response.raise_for_status()

        try:

            result = response.json()

        except Exception:

            logger.error(
                "Response Apps Script bukan JSON: %s",
                response.text[:500],
            )

            raise Exception(
                "Response Google Apps Script bukan JSON."
            )

        logger.info(
            "Apps Script result | %r",
            result,
        )

        return result

    except requests.exceptions.Timeout:

        logger.error(
            "Apps Script TIMEOUT setelah %s detik",
            APPS_SCRIPT_TIMEOUT,
        )

        raise

    except requests.exceptions.RequestException as e:

        logger.error(
            "Request Apps Script gagal: %s",
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
# START
# =========================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    message = """
👋 *BOT UPDATE ORDER*
*Service Area Palu*

📌 *Cara menggunakan:*

/update
TRACK ID : SC1002373501
ERROR CODE : SURVEI
SUB ERROR : Sudah dijadwalkan besok

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


# =========================================================
# UPDATE ORDER
# =========================================================

async def update_order(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    track_id = "-"
    error_code = "-"
    sub_error = "-"

    try:

        user_message = (
            update.message.text
            or ""
        )

        logger.info(
            "UPDATE COMMAND DITERIMA | TEXT=%r",
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

        # =================================================
        # VALIDASI FIELD
        # =================================================

        if (
            not track_id
            or not error_code
            or not sub_error
        ):

            logger.warning(
                "UPDATE FORMAT TIDAK LENGKAP | DATA=%r",
                data,
            )

            await update.message.reply_text(

                "❌ *Format tidak lengkap.*\n\n"

                "Gunakan:\n\n"

                "/update\n"

                "TRACK ID : XXXXX\n"

                "ERROR CODE : SURVEI\n"

                "SUB ERROR : Keterangan",

                parse_mode="Markdown",

            )

            return

        # =================================================
        # VALIDASI ERROR CODE
        # =================================================

        if error_code not in VALID_ERROR_CODES:

            logger.warning(
                "ERROR CODE TIDAK VALID | %s",
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

        # =================================================
        # USER
        # =================================================

        user = (
            update.effective_user
        )

        if user and user.username:

            updated_by = (
                f"@{user.username}"
            )

        elif user:

            updated_by = (
                user.full_name
                or "Unknown User"
            )

        else:

            updated_by = (
                "Unknown User"
            )

        # =================================================
        # LOG START
        # =================================================

        logger.info(
            "UPDATE START | TRACK=%s | ERROR=%s | SUBERROR=%s | USER=%s",
            track_id,
            error_code,
            sub_error,
            updated_by,
        )

        # =================================================
        # STATUS
        # =================================================

        await update.message.reply_text(
            "🔎 Sedang mencari TRACK ID..."
        )

        # =================================================
        # APPS SCRIPT
        # =================================================

        result = await asyncio.to_thread(

            call_apps_script,

            {

                "action": "update",

                "track_id": track_id,

                "error_code": error_code,

                "sub_error": sub_error,

                "user": updated_by,

            }

        )

        # =================================================
        # RESULT
        # =================================================

        success = bool(

            isinstance(
                result,
                dict
            )

            and result.get(
                "success"
            ) is True

        )

        logger.info(
            "UPDATE RESULT | success=%r | result=%r",
            success,
            result,
        )

        # =================================================
        # FAILED
        # =================================================

        if not success:

            error_message = (
                "Terjadi kesalahan pada Google Sheet."
            )

            if isinstance(
                result,
                dict
            ):

                error_message = (

                    result.get(
                        "message"
                    )

                    or result.get(
                        "error"
                    )

                    or error_message

                )

            logger.error(
                "UPDATE GAGAL | TRACK=%s | MESSAGE=%s",
                track_id,
                error_message,
            )

            await update.message.reply_text(

                "❌ *UPDATE GAGAL!*\n\n"

                + escape_markdown(
                    error_message
                ),

                parse_mode="Markdown",

            )

            return

        # =================================================
        # SUCCESS DATA
        # =================================================

        processing_ms = (

            result.get(
                "processing_ms",
                "-"
            )

            if isinstance(
                result,
                dict
            )

            else "-"

        )

        row = (

            result.get(
                "row",
                "-"
            )

            if isinstance(
                result,
                dict
            )

            else "-"

        )

        now = datetime.now().strftime(
            "%d-%m-%Y %H:%M:%S"
        )

        # =================================================
        # SUCCESS MESSAGE
        # =================================================

        success_message = (

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

            f"⚡ Proses: "
            f"*{processing_ms} ms*"

        )

        await update.message.reply_text(

            success_message,

            parse_mode="Markdown",

        )

        logger.info(

            "UPDATE BERHASIL | TRACK=%s | ROW=%s | PROCESS=%s ms",

            track_id,

            row,

            processing_ms,

        )

    # =====================================================
    # TIMEOUT
    # =====================================================

    except requests.exceptions.Timeout:

        logger.error(
            "UPDATE TIMEOUT | TRACK=%s",
            track_id,
        )

        await update.message.reply_text(

            "❌ *Google Sheet terlalu lama merespons.*\n\n"
            "Silakan coba kembali.",

            parse_mode="Markdown",

        )

    # =====================================================
    # REQUEST ERROR
    # =====================================================

    except requests.exceptions.RequestException as e:

        logger.error(
            "UPDATE REQUEST ERROR | %s",
            e,
        )

        await update.message.reply_text(

            "❌ *Gagal terhubung ke Google Sheet.*\n\n"

            + escape_markdown(
                str(e)
            ),

            parse_mode="Markdown",

        )

    # =====================================================
    # GENERAL ERROR
    # =====================================================

    except Exception as e:

        logger.exception(
            "UPDATE ERROR"
        )

        await update.message.reply_text(

            "❌ *Terjadi error pada bot.*\n\n"

            + escape_markdown(
                str(e)
            ),

            parse_mode="Markdown",

        )


# =========================================================
# CEK PERFORM
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
            }

        )

        success = bool(

            isinstance(
                result,
                dict
            )

            and result.get(
                "success"
            ) is True

        )

        if not success:

            error_message = (
                "Unknown error"
            )

            if isinstance(
                result,
                dict
            ):

                error_message = (

                    result.get(
                        "message"
                    )

                    or result.get(
                        "error"
                    )

                    or error_message

                )

            await update.message.reply_text(

                "❌ *Gagal mengambil data performa.*\n\n"

                + escape_markdown(
                    error_message
                ),

                parse_mode="Markdown",

            )

            return

        total = result.get(

            "total",

            result.get(
                "total_rows",
                0
            )

        )

        await update.message.reply_text(

            "📊 *DASHBOARD PERFORMA*\n\n"

            f"📦 Total Order: *{total}*",

            parse_mode="Markdown",

        )

    except Exception as e:

        logger.exception(
            "CEK PERFORM ERROR"
        )

        await update.message.reply_text(

            "❌ *Gagal mengambil data performa.*\n\n"

            + escape_markdown(
                str(e)
            ),

            parse_mode="Markdown",

        )


# =========================================================
# RANKING
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
            }

        )

        success = bool(

            isinstance(
                result,
                dict
            )

            and result.get(
                "success"
            ) is True

        )

        if not success:

            error_message = (
                "Unknown error"
            )

            if isinstance(
                result,
                dict
            ):

                error_message = (

                    result.get(
                        "message"
                    )

                    or result.get(
                        "error"
                    )

                    or error_message

                )

            await update.message.reply_text(

                "❌ *Gagal mengambil ranking.*\n\n"

                + escape_markdown(
                    error_message
                ),

                parse_mode="Markdown",

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

                    icon = (
                        f"{index}."
                    )

                message += (

                    f"{icon} "

                    f"*{escape_markdown(str(team))}* "

                    f"— *{total} PS*\n"

                )

        await update.message.reply_text(

            message,

            parse_mode="Markdown",

        )

    except Exception as e:

        logger.exception(
            "RANKING ERROR"
        )

        await update.message.reply_text(

            "❌ *Gagal menghitung ranking.*\n\n"

            + escape_markdown(
                str(e)
            ),

            parse_mode="Markdown",

        )


# =========================================================
# ERROR HANDLER TELEGRAM
# =========================================================

async def telegram_error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE
):

    logger.error(
        "TELEGRAM HANDLER ERROR | %s",
        context.error,
        exc_info=context.error,
    )


# =========================================================
# RUN TELEGRAM BOT
# =========================================================

def run_bot():

    logger.info(
        "========================================"
    )

    logger.info(
        "BOT UPDATE ORDER PALU STARTING"
    )

    logger.info(
        "BOT VERSION = %s",
        BOT_VERSION,
    )

    logger.info(
        "========================================"
    )

    restart_count = 0

    while True:

        loop = None

        try:

            restart_count += 1

            logger.info(
                "TELEGRAM POLLING START | ATTEMPT=%s",
                restart_count,
            )

            loop = asyncio.new_event_loop()

            asyncio.set_event_loop(
                loop
            )

            application = (

                ApplicationBuilder()

                .token(BOT_TOKEN)

                .build()

            )

            # =================================================
            # COMMAND HANDLERS
            # =================================================

            application.add_handler(

                CommandHandler(
                    "start",
                    start
                )

            )

            application.add_handler(

                CommandHandler(
                    "update",
                    update_order
                )

            )

            application.add_handler(

                CommandHandler(
                    "cekperform",
                    cek_perform
                )

            )

            application.add_handler(

                CommandHandler(
                    "ranking",
                    ranking
                )

            )

            # =================================================
            # DEBUG INCOMING MESSAGE
            #
            # group=99 supaya command handler utama
            # tetap diprioritaskan.
            # =================================================

            application.add_handler(

                MessageHandler(

                    filters.ALL,

                    debug_message,

                ),

                group=99,

            )

            # =================================================
            # ERROR HANDLER
            # =================================================

            application.add_error_handler(
                telegram_error_handler
            )

            logger.info(
                "Telegram handlers berhasil dibuat."
            )

            logger.info(
                "BOT SIAP MENERIMA PESAN."
            )

            # =================================================
            # POLLING
            # =================================================

            application.run_polling(

                drop_pending_updates=False,

                stop_signals=None,

            )

            logger.warning(
                "Telegram polling berhenti tanpa exception."
            )

        except Exception as e:

            logger.exception(
                "TELEGRAM BOT ERROR | %s",
                e,
            )

            logger.error(
                "Telegram Bot akan restart dalam 5 detik..."
            )

            time.sleep(5)

        finally:

            try:

                if loop and not loop.is_closed():

                    loop.close()

            except Exception:

                pass

            logger.info(
                "Telegram polling loop selesai."
            )

            time.sleep(1)


# =========================================================
# MAIN
# =========================================================

def main():

    if not check_config():

        logger.error(
            "Bot tidak dapat dijalankan karena config tidak lengkap."
        )

        return

    bot_thread = threading.Thread(

        target=run_bot,

        name="telegram-bot",

        daemon=True,

    )

    bot_thread.start()

    logger.info(
        "Web server berjalan pada port %s",
        PORT,
    )

    app.run(

        host="0.0.0.0",

        port=PORT,

        debug=False,

        use_reloader=False,

    )


# =========================================================
# START
# =========================================================

if __name__ == "__main__":

    main()
