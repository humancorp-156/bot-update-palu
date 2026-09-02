```python
import os
import re
import asyncio
import logging
import threading
import requests

from datetime import datetime
from flask import Flask, jsonify

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes
)


# =========================================================
# CONFIG
# =========================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
APPS_SCRIPT_URL = os.getenv("APPS_SCRIPT_URL")
API_KEY = os.getenv("API_KEY")

PORT = int(os.getenv("PORT", "10000"))

# Timeout Google Apps Script
APPS_SCRIPT_TIMEOUT = 60


# =========================================================
# LOGGING
# =========================================================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

logger = logging.getLogger(__name__)


# =========================================================
# FLASK WEB SERVER
# =========================================================

app = Flask(__name__)


@app.route("/")
def home():

    return """
    <!DOCTYPE html>
    <html>

    <head>

        <title>Bot Update Order Palu</title>

        <meta name="viewport"
              content="width=device-width, initial-scale=1.0">

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

            h1 {
                color: #222;
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

        </div>

    </body>

    </html>
    """


@app.route("/health")
def health():

    return jsonify({

        "status": "online",

        "bot": "Bot Update Order Palu",

        "time": datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

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
    "CANCEL"

]


# =========================================================
# CHECK CONFIG
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
            "Environment variable belum lengkap: %s",
            ", ".join(missing)
        )

        return False

    logger.info("Environment variable lengkap.")

    return True


# =========================================================
# CALL GOOGLE APPS SCRIPT
# =========================================================

def call_apps_script(payload):

    if not APPS_SCRIPT_URL:

        raise Exception(
            "APPS_SCRIPT_URL belum diatur."
        )

    payload = payload.copy()

    payload["api_key"] = API_KEY

    logger.info(
        "Mengirim request ke Google Apps Script: action=%s",
        payload.get("action")
    )

    start_time = datetime.now()

    try:

        response = requests.post(

            APPS_SCRIPT_URL,

            json=payload,

            timeout=APPS_SCRIPT_TIMEOUT

        )

        elapsed = (
            datetime.now() - start_time
        ).total_seconds()

        logger.info(
            "Response Apps Script diterima dalam %.2f detik",
            elapsed
        )

        response.raise_for_status()

        try:

            result = response.json()

        except Exception:

            logger.error(
                "Response bukan JSON: %s",
                response.text[:500]
            )

            raise Exception(
                "Response Google Apps Script bukan JSON."
            )

        logger.info(
            "Response Apps Script: %s",
            result
        )

        return result

    except requests.exceptions.Timeout:

        elapsed = (
            datetime.now() - start_time
        ).total_seconds()

        logger.error(
            "Timeout Apps Script setelah %.2f detik",
            elapsed
        )

        raise

    except requests.exceptions.RequestException as e:

        logger.exception(
            "Request Apps Script gagal: %s",
            e
        )

        raise


# =========================================================
# PARSE UPDATE
# =========================================================

def parse_update(text):

    result = {}

    lines = text.splitlines()

    for line in lines:

        line = line.strip()

        if ":" not in line:
            continue

        key, value = line.split(":", 1)

        key = key.strip().upper()

        value = value.strip()

        if key == "TRACK ID":

            result["track_id"] = value

        elif key == "ERROR CODE":

            result["error_code"] = value.upper()

        elif key in [
            "SUB ERROR",
            "SUBERROR"
        ]:

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

        parse_mode="Markdown"

    )


# =========================================================
# UPDATE ORDER
# =========================================================

async def update_order(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    try:

        user_message = update.message.text or ""

        text = re.sub(

            r"^/update(@\w+)?",

            "",

            user_message,

            flags=re.IGNORECASE

        ).strip()

        data = parse_update(text)

        track_id = data.get("track_id")

        error_code = data.get("error_code")

        sub_error = data.get("sub_error")


        # =================================================
        # VALIDASI FORMAT
        # =================================================

        if not track_id or not error_code or not sub_error:

            await update.message.reply_text(

                "❌ *Format tidak lengkap.*\n\n"

                "Gunakan:\n\n"

                "/update\n"

                "TRACK ID : XXXXX\n"

                "ERROR CODE : SURVEI\n"

                "SUB ERROR : Keterangan",

                parse_mode="Markdown"

            )

            return


        # =================================================
        # VALIDASI ERROR CODE
        # =================================================

        if error_code not in VALID_ERROR_CODES:

            error_list = "\n".join(

                f"• {x}"

                for x in VALID_ERROR_CODES

            )

            await update.message.reply_text(

                "❌ *ERROR CODE tidak valid.*\n\n"

                + error_list,

                parse_mode="Markdown"

            )

            return


        # =================================================
        # USER
        # =================================================

        user = update.effective_user

        if user.username:

            updated_by = f"@{user.username}"

        else:

            updated_by = (
                user.full_name
                or "Unknown User"
            )


        # =================================================
        # PROCESS
        # =================================================

        await update.message.reply_text(

            "🔎 Sedang mencari TRACK ID..."

        )


        logger.info(
            "UPDATE START | TRACK ID=%s | ERROR=%s | USER=%s",
            track_id,
            error_code,
            updated_by
        )


        result = call_apps_script({

            "action": "update",

            "track_id": track_id,

            "error_code": error_code,

            "sub_error": sub_error,

            "user": updated_by

        })


        # =================================================
        # RESULT
        # =================================================

        # PENTING:
        # Apps Script Version 9 menggunakan "success",
        # bukan "ok".

        if not result.get("success", False):

            error_message = result.get(

                "message",

                result.get(
                    "error",
                    "Terjadi kesalahan pada Google Sheet."
                )

            )

            logger.error(
                "UPDATE GAGAL | TRACK ID=%s | ERROR=%s",
                track_id,
                error_message
            )

            await update.message.reply_text(

                "❌ *Update gagal!*\n\n"

                + escape_markdown(
                    str(error_message)
                ),

                parse_mode="Markdown"

            )

            return


        # =================================================
        # SUCCESS
        # =================================================

        now = datetime.now().strftime(

            "%d-%m-%Y %H:%M:%S"

        )


        processing_ms = result.get(
            "processing_ms",
            "-"
        )


        success_message = f"""

✅ *UPDATE BERHASIL!*

📦 *TRACK ID*

`{track_id}`

🔄 *Error Code*

*{escape_markdown(error_code)}*

📝 *Sub Error*

{escape_markdown(sub_error)}

👤 *Oleh*

{escape_markdown(updated_by)}

🕒 {now}

⚡ Proses: *{processing_ms} ms*
"""


        await update.message.reply_text(

            success_message,

            parse_mode="Markdown"

        )


        logger.info(
            "UPDATE BERHASIL | TRACK ID=%s | processing_ms=%s",
            track_id,
            processing_ms
        )


    except requests.exceptions.Timeout:

        logger.exception(
            "Timeout Apps Script"
        )

        await update.message.reply_text(

            "❌ *Google Sheet terlalu lama merespons.*\n\n"

            "Silakan coba kembali beberapa saat lagi.",

            parse_mode="Markdown"

        )


    except requests.exceptions.RequestException as e:

        logger.exception(
            "Request Apps Script gagal"
        )

        await update.message.reply_text(

            "❌ *Gagal terhubung ke Google Sheet.*\n\n"

            + escape_markdown(
                str(e)
            ),

            parse_mode="Markdown"

        )


    except Exception as e:

        logger.exception(
            "Error update order"
        )

        await update.message.reply_text(

            "❌ *Terjadi error pada bot.*\n\n"

            + escape_markdown(
                str(e)
            ),

            parse_mode="Markdown"

        )


# =========================================================
# CEK PERFORM
# =========================================================

async def cek_perform(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    try:

        await update.message.reply_text(

            "📊 Sedang mengambil data performa..."

        )


        result = call_apps_script({

            "action": "stats"

        })


        # Apps Script menggunakan "success"
        if not result.get("success", False):

            error_message = result.get(

                "message",

                result.get(
                    "error",
                    "Unknown error"
                )

            )

            await update.message.reply_text(

                "❌ Gagal mengambil data performa.\n\n"

                + escape_markdown(
                    str(error_message)
                ),

                parse_mode="Markdown"

            )

            return


        total = result.get(

            "total",

            0

        )


        stats = result.get(

            "stats",

            {}

        )


        message = f"""

📊 *DASHBOARD PERFORMA*

📦 Total Order: *{total}*

"""


        if stats:

            sorted_stats = sorted(

                stats.items(),

                key=lambda x: x[1],

                reverse=True

            )

            for status, count in sorted_stats:

                message += (

                    f"• "
                    f"{escape_markdown(str(status))}: "
                    f"*{count}*\n"

                )

        else:

            message += "Belum ada data."


        await update.message.reply_text(

            message,

            parse_mode="Markdown"

        )


    except Exception as e:

        logger.exception(

            "Error cek perform"
        )

        await update.message.reply_text(

            "❌ Gagal mengambil data performa.\n\n"

            + escape_markdown(
                str(e)
            ),

            parse_mode="Markdown"

        )


# =========================================================
# RANKING
# =========================================================

async def ranking(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    try:

        await update.message.reply_text(

            "🏆 Sedang menghitung ranking..."

        )


        result = call_apps_script({

            "action": "ranking"

        })


        # Apps Script menggunakan "success"
        if not result.get("success", False):

            error_message = result.get(

                "message",

                result.get(
                    "error",
                    "Unknown error"
                )

            )

            await update.message.reply_text(

                "❌ Gagal mengambil ranking.\n\n"

                + escape_markdown(
                    str(error_message)
                ),

                parse_mode="Markdown"

            )

            return


        ranking_data = result.get(

            "ranking",

            []

        )


        message = """

🏆 *RANKING PS TEKNISI*

"""


        medals = [

            "🥇",
            "🥈",
            "🥉"

        ]


        if not ranking_data:

            message += "Belum ada data PS."

        else:

            for index, item in enumerate(

                ranking_data,

                start=1

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

                    icon = medals[index - 1]

                else:

                    icon = f"{index}."


                message += (

                    f"{icon} "

                    f"*{escape_markdown(str(team))}* "

                    f"— *{total} PS*\n"

                )


        await update.message.reply_text(

            message,

            parse_mode="Markdown"

        )


    except Exception as e:

        logger.exception(

            "Error ranking"

        )

        await update.message.reply_text(

            "❌ Gagal menghitung ranking.\n\n"

            + escape_markdown(
                str(e)
            ),

            parse_mode="Markdown"

        )


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
        "!"

    ]

    for char in characters:

        text = text.replace(

            char,

            "\\" + char

        )

    return text


# =========================================================
# RUN TELEGRAM BOT
# =========================================================

def run_bot():

    try:

        logger.info(
            "Memulai Telegram Bot..."
        )


        # =================================================
        # FIX ASYNCIO UNTUK BACKGROUND THREAD
        # =================================================

        loop = asyncio.new_event_loop()

        asyncio.set_event_loop(loop)


        logger.info(
            "Asyncio event loop berhasil dibuat."
        )


        # =================================================
        # BUILD APPLICATION
        # =================================================

        application = (

            ApplicationBuilder()

            .token(BOT_TOKEN)

            .build()

        )


        # =================================================
        # HANDLERS
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
        # BOT READY
        # =================================================

        logger.info(
            "======================================"
        )

        logger.info(
            "BOT UPDATE ORDER PALU AKTIF"
        )

        logger.info(
            "======================================"
        )


        # =================================================
        # START POLLING
        # =================================================

        application.run_polling(

            drop_pending_updates=True,

            stop_signals=None

        )


    except Exception:

        logger.exception(

            "Telegram Bot berhenti karena error."

        )


# =========================================================
# MAIN
# =========================================================

def main():

    if not check_config():

        logger.error(

            "Bot tidak dapat dijalankan."

        )

        return


    # =====================================================
    # TELEGRAM BOT THREAD
    # =====================================================

    bot_thread = threading.Thread(

        target=run_bot,

        name="telegram-bot",

        daemon=True

    )


    bot_thread.start()


    # =====================================================
    # FLASK WEB SERVER
    # =====================================================

    logger.info(

        "Web server berjalan pada port %s",

        PORT

    )


    app.run(

        host="0.0.0.0",

        port=PORT

    )


# =========================================================
# START
# =========================================================

if __name__ == "__main__":

    main()
```
