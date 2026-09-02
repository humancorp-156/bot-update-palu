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


# =========================================================
# CONFIG
# =========================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
APPS_SCRIPT_URL = os.getenv("APPS_SCRIPT_URL")
API_KEY = os.getenv("API_KEY")

PORT = int(os.getenv("PORT", "10000"))

APPS_SCRIPT_TIMEOUT = 45

BOT_VERSION = "18.0"


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
# HTML ESCAPE
# =========================================================

def escape_html(text):

    if text is None:
        return ""

    return html.escape(str(text))


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

    error = context.error

    logger.error(
        "TELEGRAM HANDLER ERROR | %s",
        error,
        exc_info=error,
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

            result["error_code"] = value.upper()

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

    if not update.message:
        return

    message = """
👋 <b>BOT UPDATE ORDER</b>
<b>Service Area Palu</b>

📌 <b>Cara menggunakan:</b>

<code>/update
Track Id : SC1002373501
Error Code : SURVEI
Sub Error : Keterangan bebas</code>

📊 <b>Command:</b>

/cekperform
/ranking

📋 <b>Error Code valid:</b>

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
        parse_mode="HTML",
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

        data = parse_update(text)

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
        # VALIDASI FORMAT
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
                """
❌ <b>Format tidak lengkap.</b>

Gunakan:

<code>/update
Track Id : XXXXX
Error Code : SURVEI
Sub Error : Keterangan</code>
""",
                parse_mode="HTML",
            )

            return

        # -----------------------------------------------------
        # VALIDASI ERROR CODE
        # -----------------------------------------------------

        if error_code not in VALID_ERROR_CODES:

            logger.warning(
                "INVALID ERROR CODE | %s",
                error_code,
            )

            error_list = "\n".join(
                f"• {escape_html(x)}"
                for x in VALID_ERROR_CODES
            )

            await update.message.reply_text(
                "❌ <b>ERROR CODE tidak valid.</b>\n\n"
                + error_list,
                parse_mode="HTML",
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
        # FEEDBACK
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

            error_message = "Update gagal."

            if isinstance(result, dict):

                error_message = (
                    result.get("message")
                    or result.get("error")
                    or error_message
                )

            await update.message.reply_text(
                "❌ <b>UPDATE GAGAL!</b>\n\n"
                + escape_html(error_message),
                parse_mode="HTML",
            )

            return

        # -----------------------------------------------------
        # SUCCESS
        # -----------------------------------------------------

        if isinstance(result, dict):

            row = result.get(
                "row",
                "-"
            )

            processing_ms = result.get(
                "processing_ms",
                "-"
            )

        else:

            row = "-"
            processing_ms = "-"

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

            f"👤 <b>Oleh</b>\n"
            f"{escape_html(updated_by)}\n\n"

            f"📍 <b>Row:</b> {escape_html(row)}\n"

            f"🕒 {now}\n"

            f"⚡ Proses: <b>{escape_html(processing_ms)} ms</b>"
        )

        await update.message.reply_text(
            message,
            parse_mode="HTML",
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
                """
❌ <b>Google Sheet terlalu lama merespons.</b>

Silakan coba kembali.
""",
                parse_mode="HTML",
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
                "❌ <b>Gagal terhubung ke Google Sheet.</b>",
                parse_mode="HTML",
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
                "❌ <b>Terjadi error pada bot.</b>\n\n"
                + escape_html(str(e)),
                parse_mode="HTML",
            )

        except Exception:

            logger.exception(
                "FAILED TO SEND GENERAL ERROR"
            )


# =========================================================
# HELPER CEKPERFORM
# =========================================================

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


def product_total(order_data):

    if not isinstance(order_data, dict):
        return "0"

    keys = [
        "mo",
        "pda",
        "tsel",
        "indibiz",
        "datin",
    ]

    total = 0

    for key in keys:

        value = order_data.get(
            key,
            0
        )

        try:

            number = float(
                str(value)
                .replace(",", ".")
                .strip()
            )

            total += number

        except Exception:

            continue

    if total == int(total):

        return str(
            int(total)
        )

    return str(total)


def format_sto_report(sto):

    if not isinstance(sto, dict):
        return ""

    name = safe_text(
        sto.get("sto", "-")
    )

    order_total = product_total(
        sto.get("order", {})
    )

    belum_survey = product_total(
        sto.get("belum_survey", {})
    )

    survey = product_total(
        sto.get("survey", {})
    )

    kendala_teknik = product_total(
        sto.get("kendala_teknik", {})
    )

    kendala_non_teknik = product_total(
        sto.get("kendala_non_teknik", {})
    )

    cancel = product_total(
        sto.get("cancel", {})
    )

    penarikan = product_total(
        sto.get("penarikan_instalasi", {})
    )

    aktivasi = product_total(
        sto.get("aktivasi", {})
    )

    real_ps = product_total(
        sto.get("real_ps", {})
    )

    estimasi_ps = product_total(
        sto.get("estimasi_ps", {})
    )

    ps_re = safe_percentage(
        sto.get("ps_re_tsel", "-")
    )

    fu_re = safe_percentage(
        sto.get("fu_re_tsel", "-")
    )

    return (
        f"<b>🏢 STO {name}</b>\n\n"

        f"📦 Jumlah Order       : {order_total}\n"
        f"🆕 Belum Survey       : {belum_survey}\n"
        f"🔍 Survey             : {survey}\n"
        f"⚠️ Kendala Teknik     : {kendala_teknik}\n"
        f"🛠 Kendala Non Teknik : {kendala_non_teknik}\n"
        f"❌ Cancel             : {cancel}\n"
        f"🔌 Penarikan & Inst   : {penarikan}\n"
        f"⚡ Aktivasi           : {aktivasi}\n"
        f"✅ Real PS            : {real_ps}\n"
        f"📐 Estimasi PS        : {estimasi_ps}\n"
        f"📈 PS/RE TSEL         : {ps_re}\n"
        f"📈 FU/RE TSEL         : {fu_re}\n"
    )


# =========================================================
# /CEKPERFORM
# =========================================================

async def cek_perform(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    try:

        if not update.message:
            return

        logger.info(
            "CEKPERFORM START | USER=%s",
            (
                update.effective_user.username
                if update.effective_user
                else "-"
            ),
        )

        await update.message.reply_text(
            "📊 Sedang mengambil data performa..."
        )

        result = await asyncio.to_thread(
            call_apps_script,
            {
                "action": "stats",
            },
        )

        # -----------------------------------------------------
        # VALIDASI RESPONSE
        # -----------------------------------------------------

        if not (
            isinstance(result, dict)
            and result.get("success") is True
        ):

            error_message = (
                result.get(
                    "message",
                    "Gagal mengambil DASH PRESEN."
                )
                if isinstance(result, dict)
                else "Gagal mengambil DASH PRESEN."
            )

            await update.message.reply_text(
                "❌ <b>CEKPERFORM GAGAL</b>\n\n"
                + escape_html(error_message),
                parse_mode="HTML",
            )

            return

        # -----------------------------------------------------
        # DATA
        # -----------------------------------------------------

        report_date = result.get(
            "report_date",
            "-"
        )

        total = result.get(
            "total",
            {}
        )

        type_totals = result.get(
            "type_totals",
            {}
        )

        sto_data = result.get(
            "sto",
            []
        )

        # -----------------------------------------------------
        # HEADER
        # -----------------------------------------------------

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
            f"{safe_number(total.get('estimasi_ps'))}\n"

            f"📈 PS/RE TSEL (85%)   : "
            f"{safe_percentage(total.get('ps_re_tsel'))}\n"

            f"📈 FU/RE TSEL (90%)   : "
            f"{safe_percentage(total.get('fu_re_tsel'))}\n\n"

            f"📋 <b>Jumlah Order per Tipe (Total):</b>\n"

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

        # -----------------------------------------------------
        # STO
        # -----------------------------------------------------

        if isinstance(sto_data, list):

            for sto in sto_data:

                sto_report =
                    format_sto_report(sto)

                if not sto_report:
                    continue

                message += (
                    "\n━━━━━━━━━━━━━━━\n\n"
                    + sto_report
                )

        # -----------------------------------------------------
        # TELEGRAM MESSAGE LIMIT
        #
        # Telegram sekitar 4096 karakter.
        # Kita pecah dengan aman jika diperlukan.
        # -----------------------------------------------------

        max_length = 3900

        if len(message) <= max_length:

            await update.message.reply_text(
                message,
                parse_mode="HTML",
            )

        else:

            chunks = []

            current = ""

            for line in message.splitlines(
                keepends=True
            ):

                if (
                    len(current) +
                    len(line)
                    > max_length
                ):

                    if current:
                        chunks.append(
                            current
                        )

                    current = line

                else:

                    current += line


            if current:
                chunks.append(
                    current
                )


            for chunk in chunks:

                await update.message.reply_text(
                    chunk,
                    parse_mode="HTML",
                )

        logger.info(
            "CEKPERFORM SUCCESS | DATE=%s | STO=%s",
            report_date,
            len(sto_data)
            if isinstance(sto_data, list)
            else 0,
        )

    except requests.exceptions.Timeout:

        logger.error(
            "CEKPERFORM APPS SCRIPT TIMEOUT"
        )

        try:

            await update.message.reply_text(
                "❌ <b>DASH PRESEN terlalu lama merespons.</b>\n\n"
                "Silakan coba lagi.",
                parse_mode="HTML",
            )

        except Exception:

            logger.exception(
                "FAILED SEND CEKPERFORM TIMEOUT"
            )

    except requests.exceptions.RequestException as e:

        logger.error(
            "CEKPERFORM REQUEST ERROR | %s",
            e,
        )

        try:

            await update.message.reply_text(
                "❌ <b>Gagal terhubung ke Google Sheet.</b>",
                parse_mode="HTML",
            )

        except Exception:

            logger.exception(
                "FAILED SEND CEKPERFORM REQUEST ERROR"
            )

    except Exception as e:

        logger.exception(
            "CEKPERFORM ERROR"
        )

        try:

            await update.message.reply_text(
                "❌ <b>Gagal mengambil data performa.</b>\n\n"
                + escape_html(str(e)),
                parse_mode="HTML",
            )

        except Exception:

            logger.exception(
                "FAILED SEND CEKPERFORM ERROR"
            )


# =========================================================
# /RANKING
# =========================================================

async def ranking(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    try:

        if not update.message:
            return

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
                result.get(
                    "message",
                    "Gagal."
                )
                if isinstance(result, dict)
                else "Gagal."
            )

            await update.message.reply_text(
                "❌ " + escape_html(message),
                parse_mode="HTML",
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

                    icon = medals[
                        index - 1
                    ]

                else:

                    icon = f"{index}."

                message += (
                    f"{icon} "
                    f"<b>{escape_html(team)}</b> "
                    f"— <b>{escape_html(total)} PS</b>\n"
                )

        await update.message.reply_text(
            message,
            parse_mode="HTML",
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

        application = None

        try:

            application = (
                ApplicationBuilder()
                .token(BOT_TOKEN)
                .concurrent_updates(True)
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
            # DEBUG ALL INCOMING MESSAGE
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
            # START POLLING
            #
            # BAGIAN INI DIPERTAHANKAN DARI VERSI
            # YANG SUDAH BERHASIL DI RENDER.
            # -------------------------------------------------

            logger.info(
                "BOT READY — MULAI POLLING TELEGRAM"
            )

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
    # FLASK BACKGROUND
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
