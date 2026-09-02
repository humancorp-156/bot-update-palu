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

BOT_VERSION = "20.0"

# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger("BOT_PALU")

# ============================================================
# FLASK
# ============================================================

app = Flask(__name__)


@app.route("/")
def home():
    return jsonify({
        "status": "online",
        "bot": "BOT UPDATE ORDER PALU",
        "version": BOT_VERSION,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    })


@app.route("/health")
def health():
    return jsonify({
        "status": "online",
        "bot": "BOT UPDATE ORDER PALU",
        "version": BOT_VERSION,
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
#
# VERSION 20.0
#
# FITUR:
# 1. POST JSON
# 2. FOLLOW REDIRECT
# 3. LOG FINAL URL
# 4. LOG CONTENT TYPE
# 5. LOG RESPONSE BODY
# 6. VALIDASI JSON
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

    # --------------------------------------------------------
    # COPY PAYLOAD
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # JANGAN LOG API KEY
    # --------------------------------------------------------

    safe_payload = dict(request_payload)

    if "api_key" in safe_payload:

        safe_payload["api_key"] = "***HIDDEN***"

    logger.info(
        "REQUEST PAYLOAD = %r",
        safe_payload
    )

    start_time = time.time()

    try:

        # ----------------------------------------------------
        # POST JSON
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # RESPONSE INFO
        # ----------------------------------------------------

        logger.info(
            "APPS SCRIPT RESPONSE | "
            "status=%s | %.2f sec",
            response.status_code,
            elapsed
        )

        # ----------------------------------------------------
        # FINAL URL SETELAH REDIRECT
        # ----------------------------------------------------

        logger.info(
            "APPS SCRIPT FINAL URL | %s",
            response.url
        )

        # ----------------------------------------------------
        # CONTENT TYPE
        # ----------------------------------------------------

        content_type = response.headers.get(
            "Content-Type",
            ""
        )

        logger.info(
            "APPS SCRIPT CONTENT TYPE | %s",
            content_type
        )

        # ----------------------------------------------------
        # REDIRECT HISTORY
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # RESPONSE BODY
        #
        # Maksimal 1500 karakter untuk log.
        # ----------------------------------------------------

        response_body = response.text or ""

        logger.info(
            "APPS SCRIPT BODY PREVIEW | %s",
            response_body[:1500]
        )

        # ----------------------------------------------------
        # HTTP ERROR
        # ----------------------------------------------------

        response.raise_for_status()

        # ----------------------------------------------------
        # CEK CONTENT TYPE
        # ----------------------------------------------------

        if "json" not in content_type.lower():

            logger.warning(
                "APPS SCRIPT CONTENT TYPE BUKAN JSON | %s",
                content_type
            )

        # ----------------------------------------------------
        # PARSE JSON
        # ----------------------------------------------------

        try:

            result = response.json()

        except ValueError:

            logger.error(
                "APPS SCRIPT INVALID JSON"
            )

            logger.error(
                "STATUS = %s",
                response.status_code
            )

            logger.error(
                "FINAL URL = %s",
                response.url
            )

            logger.error(
                "CONTENT TYPE = %s",
                content_type
            )

            logger.error(
                "BODY = %s",
                response_body[:3000]
            )

            raise Exception(
                "Response Google Apps Script bukan JSON.\n"
                f"HTTP Status: {response.status_code}\n"
                f"Content-Type: {content_type}\n"
                f"Final URL: {response.url}"
            )

        # ----------------------------------------------------
        # VALIDASI HASIL JSON
        # ----------------------------------------------------

        if not isinstance(result, dict):

            logger.error(
                "APPS SCRIPT JSON BUKAN OBJECT | %r",
                result
            )

            raise Exception(
                "Response Google Apps Script JSON "
                "tetapi formatnya bukan object."
            )

        # ----------------------------------------------------
        # LOG RESULT TANPA API KEY
        # ----------------------------------------------------

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

    # --------------------------------------------------------
    # TIMEOUT
    # --------------------------------------------------------

    except requests.exceptions.Timeout:

        elapsed = time.time() - start_time

        logger.error(
            "APPS SCRIPT TIMEOUT | %.2f sec",
            elapsed
        )

        raise

    # --------------------------------------------------------
    # REQUEST ERROR
    # --------------------------------------------------------

    except requests.exceptions.RequestException as e:

        logger.error(
            "APPS SCRIPT REQUEST ERROR | %s",
            e
        )

        raise

    # --------------------------------------------------------
    # GENERAL ERROR
    # --------------------------------------------------------

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

📝 <b>Keterangan</b> digunakan untuk
catatan / kondisi aktual dari tim lapangan.
"""

    await update.message.reply_text(
        message,
        parse_mode="HTML"
    )

    logger.info(
        "START COMMAND SUCCESS | USER=%s",
        update.effective_user.username
        if update.effective_user
        else "-"
    )


# ============================================================
# UPDATE ORDER
# ============================================================

async def update_order(update, context):

    track_id = "-"
    error_code = "-"
    sub_error = "-"
    keterangan = ""

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
            user_message
        )

        text = re.sub(
            r"^/update(@\w+)?",
            "",
            user_message,
            flags=re.IGNORECASE
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

        keterangan = data.get(
            "keterangan",
            ""
        )

        # ----------------------------------------------------
        # VALIDASI FORMAT
        # ----------------------------------------------------

        if (
            not track_id
            or not error_code
            or not sub_error
        ):

            logger.warning(
                "UPDATE FORMAT INVALID | DATA=%r",
                data
            )

            await update.message.reply_text(
                """
❌ <b>Format tidak lengkap.</b>

Gunakan:

<code>/update
Track Id : XXXXX
Error Code : PS
Sub Error : SURVEI
Keterangan : Catatan tim lapangan</code>
""",
                parse_mode="HTML"
            )

            return

        # ----------------------------------------------------
        # VALIDASI ERROR CODE
        # ----------------------------------------------------

        if (
            error_code.upper()
            not in VALID_ERROR_CODES
        ):

            logger.warning(
                "INVALID ERROR CODE | %s",
                error_code
            )

            error_list = "\n".join(
                f"• {escape_html(x)}"
                for x in VALID_ERROR_CODES
            )

            await update.message.reply_text(
                "❌ <b>ERROR CODE tidak valid.</b>\n\n"
                + error_list,
                parse_mode="HTML"
            )

            return

        # ----------------------------------------------------
        # KETERANGAN OPTIONAL
        # ----------------------------------------------------

        keterangan = (
            str(keterangan).strip()
            if keterangan is not None
            else ""
        )

        # ----------------------------------------------------
        # USER
        # ----------------------------------------------------

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

        logger.info(
            "UPDATE START | "
            "TRACK=%s | "
            "ERROR=%s | "
            "SUBERROR=%s | "
            "KETERANGAN=%s | "
            "USER=%s",
            track_id,
            error_code,
            sub_error,
            keterangan,
            updated_by
        )

        await update.message.reply_text(
            "🔎 Sedang mencari TRACK ID..."
        )

        # ----------------------------------------------------
        # CALL GOOGLE APPS SCRIPT
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # CHECK SUCCESS
        # ----------------------------------------------------

        success = bool(
            isinstance(result, dict)
            and result.get("success") is True
        )

        logger.info(
            "UPDATE RESULT | success=%s",
            success
        )

        # ----------------------------------------------------
        # UPDATE GAGAL
        # ----------------------------------------------------

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
                "❌ <b>UPDATE GAGAL!</b>\n\n"
                + escape_html(error_message),
                parse_mode="HTML"
            )

            return

        # ----------------------------------------------------
        # RESULT
        # ----------------------------------------------------

        if isinstance(
            result,
            dict
        ):

            row = result.get(
                "row",
                "-"
            )

            processing_ms = result.get(
                "processing_ms",
                "-"
            )

            new_keterangan = result.get(
                "new_keterangan",
                keterangan or "-"
            )

        else:

            row = "-"

            processing_ms = "-"

            new_keterangan = (
                keterangan or "-"
            )

        # ----------------------------------------------------
        # SUCCESS MESSAGE
        # ----------------------------------------------------

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

            f"📍 <b>Row:</b> "
            f"{escape_html(row)}\n"

            f"🕒 {now}\n"

            f"⚡ Proses: "
            f"<b>{escape_html(processing_ms)} ms</b>"
        )

        await update.message.reply_text(
            message,
            parse_mode="HTML"
        )

        logger.info(
            "UPDATE BERHASIL | "
            "TRACK=%s | "
            "ROW=%s | "
            "PROCESS=%s ms",
            track_id,
            row,
            processing_ms
        )

    # --------------------------------------------------------
    # TIMEOUT
    # --------------------------------------------------------

    except requests.exceptions.Timeout:

        logger.error(
            "UPDATE APPS SCRIPT TIMEOUT | TRACK=%s",
            track_id
        )

        try:

            await update.message.reply_text(
                """
❌ <b>Google Sheet terlalu lama merespons.</b>

Silakan coba kembali.
""",
                parse_mode="HTML"
            )

        except Exception:

            logger.exception(
                "FAILED TO SEND TIMEOUT MESSAGE"
            )

    # --------------------------------------------------------
    # REQUEST ERROR
    # --------------------------------------------------------

    except requests.exceptions.RequestException as e:

        logger.error(
            "UPDATE REQUEST ERROR | %s",
            e
        )

        try:

            await update.message.reply_text(
                "❌ <b>Gagal terhubung ke Google Sheet.</b>",
                parse_mode="HTML"
            )

        except Exception:

            logger.exception(
                "FAILED TO SEND REQUEST ERROR"
            )

    # --------------------------------------------------------
    # GENERAL ERROR
    # --------------------------------------------------------

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
                "FAILED TO SEND GENERAL ERROR"
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


def product_total(order_data):

    if not isinstance(
        order_data,
        dict
    ):

        return "0"

    keys = [
        "mo",
        "pda",
        "tsel",
        "indibiz",
        "datin"
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

        return str(int(total))

    return str(total)


def format_sto_report(sto):

    if not isinstance(
        sto,
        dict
    ):

        return ""

    name = safe_text(
        sto.get(
            "sto",
            "-"
        )
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
        sto.get(
            "ps_re_tsel",
            "-"
        )
    )

    fu_re = safe_percentage(
        sto.get(
            "fu_re_tsel",
            "-"
        )
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


# ============================================================
# CEKPERFORM
# ============================================================

async def cek_perform(update, context):

    try:

        if not update.message:
            return

        logger.info(
            "CEKPERFORM START | USER=%s",
            update.effective_user.username
            if update.effective_user
            else "-"
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

            error_message = (

                result.get(
                    "message",
                    "Gagal mengambil DASH PRESEN."
                )

                if isinstance(
                    result,
                    dict
                )

                else
                "Gagal mengambil DASH PRESEN."
            )

            await update.message.reply_text(
                "❌ <b>CEKPERFORM GAGAL</b>\n\n"
                + escape_html(error_message),
                parse_mode="HTML"
            )

            return

        report_date = result.get(
            "report_date",
            "-"
        )

        total = result.get(
            "total",
            {}
        )

        if not isinstance(
            total,
            dict
        ):

            total = {}

        type_totals = result.get(
            "type_totals",
            {}
        )

        if not isinstance(
            type_totals,
            dict
        ):

            type_totals = {}

        sto_data = result.get(
            "sto",
            []
        )

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

            f"📋 <b>Jumlah Order per Tipe "
            f"(Total):</b>\n"

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

        if isinstance(
            sto_data,
            list
        ):

            for sto in sto_data:

                sto_report = format_sto_report(
                    sto
                )

                if not sto_report:
                    continue

                message += (
                    "\n━━━━━━━━━━━━━━━\n\n"
                    + sto_report
                )

        max_length = 3900

        if len(message) <= max_length:

            await update.message.reply_text(
                message,
                parse_mode="HTML"
            )

        else:

            chunks = []

            current = ""

            for line in message.splitlines(
                keepends=True
            ):

                if (
                    len(current)
                    + len(line)
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
                    parse_mode="HTML"
                )

        logger.info(
            "CEKPERFORM SUCCESS | "
            "DATE=%s | STO=%s",
            report_date,
            len(sto_data)
            if isinstance(
                sto_data,
                list
            )
            else 0
        )

    except requests.exceptions.Timeout:

        logger.error(
            "CEKPERFORM APPS SCRIPT TIMEOUT"
        )

        try:

            await update.message.reply_text(
                "❌ <b>DASH PRESEN terlalu lama merespons.</b>\n\n"
                "Silakan coba lagi.",
                parse_mode="HTML"
            )

        except Exception:

            logger.exception(
                "FAILED SEND CEKPERFORM TIMEOUT"
            )

    except requests.exceptions.RequestException as e:

        logger.error(
            "CEKPERFORM REQUEST ERROR | %s",
            e
        )

        try:

            await update.message.reply_text(
                "❌ <b>Gagal terhubung ke Google Sheet.</b>",
                parse_mode="HTML"
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

        await update.message.reply_text(
            "🏆 Sedang menghitung ranking..."
        )

        result = await asyncio.to_thread(

            call_apps_script,

            {
                "action": "ranking"
            }

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

                if isinstance(
                    result,
                    dict
                )

                else "Gagal."
            )

            await update.message.reply_text(
                "❌ "
                + escape_html(message),
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

                if not isinstance(
                    item,
                    dict
                ):

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
                    f"— "
                    f"<b>{escape_html(total)} PS</b>\n"
                )

        await update.message.reply_text(
            message,
            parse_mode="HTML"
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
# FLASK
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

    restart_count = 0

    while True:

        restart_count += 1

        logger.info(
            "========================================"
        )

        logger.info(
            "TELEGRAM BOT START | "
            "VERSION=%s | "
            "ATTEMPT=%s",
            BOT_VERSION,
            restart_count
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
                drop_pending_updates=False,
                stop_signals=None
            )

            logger.warning(
                "TELEGRAM POLLING BERHENTI."
            )

        except Exception as e:

            logger.exception(
                "TELEGRAM POLLING CRASH | %s",
                e
            )

            logger.warning(
                "Telegram akan restart dalam 5 detik..."
            )

            time.sleep(5)

        finally:

            logger.info(
                "TELEGRAM BOT LOOP SELESAI | "
                "akan cek/restart..."
            )

            time.sleep(1)


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
        "Flask health server started."
    )

    run_telegram_bot()


# ============================================================
# START APPLICATION
# ============================================================

if __name__ == "__main__":

    main()
