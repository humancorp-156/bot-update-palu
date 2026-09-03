import os
import re
import asyncio
import logging
import threading
import time
import html
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


# ============================================================
# CONFIG
# ============================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
APPS_SCRIPT_URL = os.getenv("APPS_SCRIPT_URL")
API_KEY = os.getenv("API_KEY")

PORT = int(os.getenv("PORT", "10000"))

APPS_SCRIPT_TIMEOUT = 45

BOT_VERSION = "21.0"

INSTANCE_ID = (
    os.getenv("RENDER_SERVICE_ID")
    or os.getenv("HOSTNAME")
    or "LOCAL"
)


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger("BOT_PALU")


# ============================================================
# FLASK HEALTH SERVER
# ============================================================

app = Flask(__name__)


@app.route("/")
def home():

    return jsonify({
        "status": "online",
        "bot": "BOT UPDATE ORDER PALU",
        "version": BOT_VERSION,
        "instance": INSTANCE_ID,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    })


@app.route("/health")
def health():

    return jsonify({
        "status": "online",
        "bot": "BOT UPDATE ORDER PALU",
        "version": BOT_VERSION,
        "instance": INSTANCE_ID,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    })


# ============================================================
# VALID ERROR CODE
# ============================================================

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


# ============================================================
# HTML ESCAPE
# ============================================================

def escape_html(text):

    if text is None:
        return ""

    return html.escape(str(text))


# ============================================================
# CHECK CONFIG
# ============================================================

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
            ", ".join(missing)
        )

        return False

    logger.info(
        "CONFIG OK | BOT_TOKEN=SET | APPS_SCRIPT_URL=SET | API_KEY=SET"
    )

    logger.info(
        "BOT VERSION = %s",
        BOT_VERSION
    )

    logger.info(
        "BOT INSTANCE = %s",
        INSTANCE_ID
    )

    logger.info(
        "APPS SCRIPT URL = %s",
        APPS_SCRIPT_URL
    )

    return True


# ============================================================
# DEBUG MESSAGE
# ============================================================

async def debug_message(update, context):

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
            text
        )

    except Exception:

        logger.exception(
            "DEBUG MESSAGE ERROR"
        )


# ============================================================
# TELEGRAM ERROR HANDLER
# ============================================================

async def telegram_error_handler(update, context):

    error = context.error

    logger.error(
        "TELEGRAM HANDLER ERROR | %s",
        error,
        exc_info=error
    )


# ============================================================
# GOOGLE APPS SCRIPT REQUEST
# ============================================================

def call_apps_script(payload):

    if not APPS_SCRIPT_URL:
        raise Exception(
            "APPS_SCRIPT_URL belum diatur."
        )

    if not API_KEY:
        raise Exception(
            "API_KEY belum diatur."
        )

    request_payload = dict(payload)

    request_payload["api_key"] = API_KEY

    action = request_payload.get(
        "action",
        "-"
    )

    logger.info(
        "=================================================="
    )

    logger.info(
        "APPS SCRIPT REQUEST START"
    )

    logger.info(
        "ACTION = %s",
        action
    )

    logger.info(
        "TARGET URL = %s",
        APPS_SCRIPT_URL
    )

    safe_payload = dict(request_payload)

    if "api_key" in safe_payload:
        safe_payload["api_key"] = "***HIDDEN***"

    logger.info(
        "REQUEST PAYLOAD = %r",
        safe_payload
    )

    start_time = time.time()

    try:

        response = requests.post(

            APPS_SCRIPT_URL,

            json=request_payload,

            timeout=APPS_SCRIPT_TIMEOUT,

            allow_redirects=True,

            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": (
                    "BOT-UPDATE-ORDER-PALU/"
                    + BOT_VERSION
                ),
            }

        )

        elapsed = time.time() - start_time

        logger.info(
            "APPS SCRIPT RESPONSE | status=%s | %.2f sec",
            response.status_code,
            elapsed
        )

        logger.info(
            "APPS SCRIPT FINAL URL | %s",
            response.url
        )

        content_type = response.headers.get(
            "Content-Type",
            ""
        )

        logger.info(
            "APPS SCRIPT CONTENT TYPE | %s",
            content_type
        )

        if response.history:

            logger.info(
                "APPS SCRIPT REDIRECT COUNT | %s",
                len(response.history)
            )

            for index, redirect in enumerate(
                response.history,
                start=1
            ):

                logger.info(
                    "REDIRECT %s | status=%s | url=%s",
                    index,
                    redirect.status_code,
                    redirect.url
                )

        else:

            logger.info(
                "APPS SCRIPT REDIRECT COUNT | 0"
            )

        response_body = response.text or ""

        logger.info(
            "APPS SCRIPT BODY PREVIEW | %s",
            response_body[:1500]
        )

        response.raise_for_status()

        try:

            result = response.json()

        except ValueError:

            logger.error(
                "APPS SCRIPT INVALID JSON"
            )

            raise Exception(
                "Response Google Apps Script bukan JSON."
            )

        if not isinstance(result, dict):

            raise Exception(
                "Response Google Apps Script JSON "
                "tetapi bukan object."
            )

        logger.info(
            "APPS SCRIPT RESULT | %r",
            result
        )

        logger.info(
            "APPS SCRIPT REQUEST SUCCESS | %.2f sec",
            elapsed
        )

        logger.info(
            "=================================================="
        )

        return result

    except Exception:

        logger.exception(
            "APPS SCRIPT CALL ERROR"
        )

        raise


# ============================================================
# PARSE UPDATE
# ============================================================

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

            result["error_code"] = value.upper()

        elif key in (
            "SUB ERROR",
            "SUBERROR",
            "SUB-ERROR",
        ):

            result["sub_error"] = value

        elif key in (
            "KETERANGAN",
            "KETERANGAN LAPANGAN",
            "CATATAN",
            "CATATAN LAPANGAN",
        ):

            result["keterangan"] = value

    return result


# ============================================================
# START
# ============================================================

async def start(update, context):

    if not update.message:
        return

    message = """
👋 <b>BOT UPDATE ORDER</b>
<b>Service Area Palu</b>

📌 <b>Cara menggunakan:</b>

<code>/update
Track Id : SC1002373501
Error Code : PS
Sub Error : SURVEI
Keterangan : PELANGGAN MINTA JADWAL ULANG</code>

📊 <b>Command:</b>

/cekperform
/ranking
"""

    await update.message.reply_text(
        message,
        parse_mode="HTML"
    )

    logger.info(
        "START SUCCESS"
    )


# ============================================================
# UPDATE ORDER
# ============================================================

async def update_order(update, context):

    try:

        if not update.message:
            return

        user_message = (
            update.message.text
            or ""
        )

        logger.info(
            "UPDATE COMMAND RECEIVED | TEXT=%r",
            user_message
        )

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
        keterangan = data.get("keterangan", "")

        if (
            not track_id
            or not error_code
            or not sub_error
        ):

            await update.message.reply_text(
                "❌ <b>Format tidak lengkap.</b>\n\n"
                "<code>/update\n"
                "Track Id : XXXXX\n"
                "Error Code : PS\n"
                "Sub Error : SURVEI\n"
                "Keterangan : Catatan</code>",
                parse_mode="HTML"
            )

            return

        if error_code.upper() not in VALID_ERROR_CODES:

            await update.message.reply_text(
                "❌ <b>ERROR CODE tidak valid.</b>",
                parse_mode="HTML"
            )

            return

        user = update.effective_user

        if user and user.username:
            updated_by = f"@{user.username}"

        elif user:
            updated_by = (
                user.full_name
                or str(user.id)
            )

        else:
            updated_by = "Unknown User"

        await update.message.reply_text(
            "🔎 Sedang mencari TRACK ID..."
        )

        result = await asyncio.to_thread(

            call_apps_script,

            {
                "action": "update",
                "track_id": track_id,
                "error_code": error_code,
                "sub_error": sub_error,
                "keterangan": keterangan,
                "user": updated_by,
            }

        )

        if result.get("success") is not True:

            error_message = (
                result.get("message")
                or result.get("error")
                or "Update gagal."
            )

            await update.message.reply_text(
                "❌ <b>UPDATE GAGAL!</b>\n\n"
                + escape_html(error_message),
                parse_mode="HTML"
            )

            return

        row = result.get("row", "-")

        processing_ms = result.get(
            "processing_ms",
            "-"
        )

        new_keterangan = result.get(
            "new_keterangan",
            keterangan or "-"
        )

        now = datetime.now().strftime(
            "%d-%m-%Y %H:%M:%S"
        )

        message = (

            "✅ <b>UPDATE BERHASIL!</b>\n\n"

            f"📦 <b>TRACK ID</b>\n"
            f"<code>{escape_html(track_id)}</code>\n\n"

            f"🔄 <b>Error Code</b>\n"
            f"<b>{escape_html(error_code)}</b>\n\n"

            f"📝 <b>Sub Error</b>\n"
            f"{escape_html(sub_error)}\n\n"

            f"📋 <b>Keterangan</b>\n"
            f"{escape_html(new_keterangan)}\n\n"

            f"👤 <b>Oleh</b>\n"
            f"{escape_html(updated_by)}\n\n"

            f"📍 Row: {escape_html(row)}\n"
            f"🕒 {now}\n"
            f"⚡ Proses: <b>{escape_html(processing_ms)} ms</b>"
        )

        await update.message.reply_text(
            message,
            parse_mode="HTML"
        )

        logger.info(
            "UPDATE SUCCESS | TRACK=%s",
            track_id
        )

    except Exception as e:

        logger.exception(
            "UPDATE ORDER ERROR"
        )

        try:

            await update.message.reply_text(
                "❌ <b>Terjadi error pada bot.</b>\n\n"
                + escape_html(str(e)),
                parse_mode="HTML"
            )

        except Exception:

            logger.exception(
                "FAILED SEND ERROR"
            )


# ============================================================
# CEKPERFORM HELPERS
# ============================================================

def safe_text(value):

    if value is None:
        return "-"

    text = str(value).strip()

    if not text:
        return "-"

    return escape_html(text)


def safe_number(value):

    if value is None:
        return "0"

    text = str(value).strip()

    if not text:
        return "0"

    if text.startswith("#"):
        return "-"

    return escape_html(text)


def safe_percentage(value):

    if value is None:
        return "-"

    text = str(value).strip()

    if not text:
        return "-"

    if text.startswith("#"):
        return "-"

    return escape_html(text)


# ============================================================
# CEKPERFORM
# ============================================================

async def cek_perform(update, context):

    try:

        if not update.message:
            return

        logger.info(
            "CEKPERFORM COMMAND RECEIVED"
        )

        await update.message.reply_text(
            "📊 Sedang mengambil data performa..."
        )

        result = await asyncio.to_thread(

            call_apps_script,

            {
                "action": "stats"
            }

        )

        if not (
            isinstance(result, dict)
            and result.get("success") is True
        ):

            message = (
                result.get(
                    "message",
                    "Gagal mengambil data."
                )
            )

            await update.message.reply_text(
                "❌ <b>CEKPERFORM GAGAL</b>\n\n"
                + escape_html(message),
                parse_mode="HTML"
            )

            return

        # ====================================================
        # FORMAT TOTAL
        # ====================================================

        report_date = result.get(
            "report_date",
            "-"
        )

        total = result.get("total")

        # Jika Apps Script hanya mengirim angka:
        # {"total":80469}
        if isinstance(total, (int, float, str)):

            message = (

                f"📊 <b>REPORT PROGRES — "
                f"{safe_text(report_date)}</b>\n\n"

                f"📦 <b>TOTAL ORDER : "
                f"{safe_number(total)}</b>\n\n"

                f"⚠️ <b>Data breakdown belum dikirim "
                f"oleh Google Apps Script.</b>\n\n"

                f"Apps Script harus mengirim "
                f"jumlah survey, PS, kendala, "
                f"STO dan tipe order."
            )

            await update.message.reply_text(
                message,
                parse_mode="HTML"
            )

            logger.warning(
                "CEKPERFORM FORMAT MINIMAL | TOTAL=%s",
                total
            )

            return

        # ====================================================
        # FORMAT LENGKAP
        # ====================================================

        if not isinstance(total, dict):

            logger.error(
                "FORMAT STATS INVALID | RESULT=%r",
                result
            )

            await update.message.reply_text(
                "❌ <b>FORMAT DATA CEKPERFORM TIDAK SESUAI.</b>\n\n"
                "Google Apps Script mengirim format data "
                "yang tidak sesuai dengan BOT.",
                parse_mode="HTML"
            )

            return

        type_totals = result.get(
            "type_totals",
            {}
        )

        if not isinstance(type_totals, dict):
            type_totals = {}

        message = (

            f"📊 <b>REPORT PROGRES — "
            f"{safe_text(report_date)}</b>\n"

            f"<i>(Total seluruh STO)</i>\n\n"

            f"<b>📌 TOTAL</b>\n\n"

            f"📦 Jumlah Order       : "
            f"{safe_number(total.get('jumlah_order'))}\n"

            f"🆕 Belum Survey       : "
            f"{safe_number(total.get('belum_survey'))}\n"

            f"🔍 Survey             : "
            f"{safe_number(total.get('survey'))}\n"

            f"⚠️ Kendala Teknik     : "
            f"{safe_number(total.get('kendala_teknik'))}\n"

            f"🛠 Kendala Non Teknik : "
            f"{safe_number(total.get('kendala_non_teknik'))}\n"

            f"❌ Cancel             : "
            f"{safe_number(total.get('cancel'))}\n"

            f"🔌 Penarikan & Inst   : "
            f"{safe_number(total.get('penarikan_instalasi'))}\n"

            f"⚡ Aktivasi           : "
            f"{safe_number(total.get('aktivasi'))}\n"

            f"✅ Real PS            : "
            f"{safe_number(total.get('real_ps'))}\n"

            f"📐 Estimasi PS        : "
            f"{safe_number(total.get('estimasi_ps'))}\n\n"

            f"📋 <b>Jumlah Order per Tipe:</b>\n"

            f"• MO       : "
            f"{safe_number(type_totals.get('mo'))}\n"

            f"• PDA      : "
            f"{safe_number(type_totals.get('pda'))}\n"

            f"• TSEL     : "
            f"{safe_number(type_totals.get('tsel'))}\n"

            f"• INDI BIZ : "
            f"{safe_number(type_totals.get('indibiz'))}\n"

            f"• DATIN    : "
            f"{safe_number(type_totals.get('datin'))}\n"
        )

        await update.message.reply_text(
            message,
            parse_mode="HTML"
        )

        logger.info(
            "CEKPERFORM SUCCESS"
        )

    except Exception as e:

        logger.exception(
            "CEKPERFORM ERROR"
        )

        try:

            await update.message.reply_text(
                "❌ <b>Gagal mengambil data performa.</b>\n\n"
                + escape_html(str(e)),
                parse_mode="HTML"
            )

        except Exception:

            logger.exception(
                "FAILED SEND CEKPERFORM ERROR"
            )


# ============================================================
# RANKING
# ============================================================

async def ranking(update, context):

    try:

        if not update.message:
            return

        logger.info(
            "RANKING COMMAND RECEIVED"
        )

        await update.message.reply_text(
            "🏆 Sedang menghitung ranking..."
        )

        result = await asyncio.to_thread(

            call_apps_script,

            {
                "action": "ranking"
            }

        )

        if result.get("success") is not True:

            message = (
                result.get("message")
                or "Gagal."
            )

            await update.message.reply_text(
                "❌ " + escape_html(message),
                parse_mode="HTML"
            )

            return

        ranking_data = result.get(
            "ranking",
            []
        )

        message = (
            "🏆 <b>RANKING PS TEKNISI</b>\n\n"
        )

        medals = [
            "🥇",
            "🥈",
            "🥉"
        ]

        if not ranking_data:

            message += (
                "Belum ada data PS."
            )

        else:

            for index, item in enumerate(
                ranking_data,
                start=1
            ):

                if not isinstance(item, dict):
                    continue

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
                    f"<b>{escape_html(team)}</b> "
                    f"— "
                    f"<b>{escape_html(total)} PS</b>\n"
                )

        await update.message.reply_text(
            message,
            parse_mode="HTML"
        )

        logger.info(
            "RANKING SUCCESS"
        )

    except Exception:

        logger.exception(
            "RANKING ERROR"
        )

        try:

            await update.message.reply_text(
                "❌ Gagal menghitung ranking."
            )

        except Exception:

            logger.exception(
                "FAILED SEND RANKING ERROR"
            )


# ============================================================
# FLASK SERVER
# ============================================================

def run_flask():

    logger.info(
        "FLASK HEALTH SERVER STARTING | PORT=%s",
        PORT
    )

    app.run(
        host="0.0.0.0",
        port=PORT,
        debug=False,
        use_reloader=False
    )


# ============================================================
# TELEGRAM BOT
# ============================================================

def run_telegram_bot():

    logger.info(
        "========================================"
    )

    logger.info(
        "TELEGRAM BOT START"
    )

    logger.info(
        "VERSION = %s",
        BOT_VERSION
    )

    logger.info(
        "INSTANCE = %s",
        INSTANCE_ID
    )

    logger.info(
        "========================================"
    )

    application = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .concurrent_updates(False)
        .build()
    )

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

    application.add_handler(
        MessageHandler(
            filters.ALL,
            debug_message
        ),
        group=99
    )

    application.add_error_handler(
        telegram_error_handler
    )

    logger.info(
        "BOT READY — MULAI POLLING TELEGRAM"
    )

    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True
    )


# ============================================================
# MAIN
# ============================================================

def main():

    logger.info(
        "========================================"
    )

    logger.info(
        "BOT UPDATE ORDER PALU"
    )

    logger.info(
        "VERSION %s",
        BOT_VERSION
    )

    logger.info(
        "INSTANCE %s",
        INSTANCE_ID
    )

    logger.info(
        "========================================"
    )

    if not check_config():

        logger.error(
            "CONFIG TIDAK LENGKAP."
        )

        raise SystemExit(1)

    flask_thread = threading.Thread(

        target=run_flask,

        name="flask-health",

        daemon=True
    )

    flask_thread.start()

    logger.info(
        "FLASK HEALTH SERVER STARTED"
    )

    run_telegram_bot()


# ============================================================
# START APPLICATION
# ============================================================

if __name__ == "__main__":

    main()
