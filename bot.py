import os
import re
import json
import logging
from datetime import datetime

import gspread
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes
)


# ==========================================
# LOAD CONFIG
# ==========================================

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
WORKSHEET_NAME = os.getenv(
    "WORKSHEET_NAME",
    "SERVICE AREA PALU"
)

ERROR_CODE_HEADER = os.getenv(
    "ERROR_CODE_HEADER",
    "SUBERROR"
)

SUB_ERROR_HEADER = os.getenv(
    "SUB_ERROR_HEADER",
    "KETERANGAN"
)

GOOGLE_CREDENTIALS_JSON = os.getenv(
    "GOOGLE_CREDENTIALS_JSON"
)


# ==========================================
# LOGGING
# ==========================================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

logger = logging.getLogger(__name__)


# ==========================================
# VALID ERROR CODE
# ==========================================

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


# ==========================================
# GOOGLE SHEETS
# ==========================================

def get_worksheet():

    if not GOOGLE_CREDENTIALS_JSON:
        raise Exception(
            "GOOGLE_CREDENTIALS_JSON belum diatur di Environment."
        )

    try:

        credentials_info = json.loads(
            GOOGLE_CREDENTIALS_JSON
        )

    except json.JSONDecodeError:

        raise Exception(
            "GOOGLE_CREDENTIALS_JSON tidak valid."
        )

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]

    credentials = Credentials.from_service_account_info(
        credentials_info,
        scopes=scopes
    )

    gc = gspread.authorize(credentials)

    spreadsheet = gc.open_by_key(
        SPREADSHEET_ID
    )

    worksheet = spreadsheet.worksheet(
        WORKSHEET_NAME
    )

    return spreadsheet, worksheet


# ==========================================
# CREATE LOG SHEET
# ==========================================

def get_log_sheet(spreadsheet):

    try:

        log_sheet = spreadsheet.worksheet(
            "BOT_LOG"
        )

    except gspread.WorksheetNotFound:

        log_sheet = spreadsheet.add_worksheet(
            title="BOT_LOG",
            rows=1000,
            cols=10
        )

        log_sheet.append_row([
            "TIMESTAMP",
            "TRACK ID",
            "ERROR CODE",
            "SUB ERROR",
            "OLEH"
        ])

    return log_sheet


# ==========================================
# FIND COLUMN
# ==========================================

def find_column(headers, column_name):

    column_name = column_name.strip().upper()

    for index, header in enumerate(headers):

        if str(header).strip().upper() == column_name:

            return index + 1

    return None


# ==========================================
# PARSE UPDATE
# ==========================================

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


# ==========================================
# START
# ==========================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    message = """
👋 *BOT UPDATE ORDER*
Service Area Palu

📌 Cara menggunakan:

/update
TRACK ID : CONTOH_TRACK_ID
ERROR CODE : SURVEI
SUB ERROR : Sudah dijadwalkan besok

📊 Command:

/cekperform - Cek performa
/ranking - Ranking teknisi

📋 Error Code valid:

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


# ==========================================
# UPDATE ORDER
# ==========================================

async def update_order(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user_message = update.message.text

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


    # ======================================
    # VALIDASI FORMAT
    # ======================================

    if not track_id or not error_code or not sub_error:

        await update.message.reply_text(
            "❌ Format tidak lengkap.\n\n"
            "Gunakan:\n\n"
            "/update\n"
            "TRACK ID : XXXXX\n"
            "ERROR CODE : SURVEI\n"
            "SUB ERROR : Keterangan"
        )

        return


    # ======================================
    # VALIDASI ERROR CODE
    # ======================================

    if error_code not in VALID_ERROR_CODES:

        error_list = "\n".join(
            f"• {x}"
            for x in VALID_ERROR_CODES
        )

        await update.message.reply_text(
            "❌ ERROR CODE tidak valid.\n\n"
            f"{error_list}"
        )

        return


    try:

        await update.message.reply_text(
            "🔎 Sedang mencari TRACK ID..."
        )


        # ==================================
        # OPEN GOOGLE SHEET
        # ==================================

        spreadsheet, worksheet = get_worksheet()


        # ==================================
        # GET ALL DATA
        # ==================================

        all_values = worksheet.get_all_values()


        if len(all_values) < 2:

            await update.message.reply_text(
                "❌ Google Sheet tidak memiliki data."
            )

            return


        headers = all_values[0]


        # ==================================
        # FIND COLUMNS
        # ==================================

        track_column = find_column(
            headers,
            "TRACK ID"
        )

        error_column = find_column(
            headers,
            ERROR_CODE_HEADER
        )

        sub_error_column = find_column(
            headers,
            SUB_ERROR_HEADER
        )


        if not track_column:

            await update.message.reply_text(
                "❌ Kolom TRACK ID tidak ditemukan."
            )

            return


        if not error_column:

            await update.message.reply_text(
                f"❌ Kolom {ERROR_CODE_HEADER} "
                "tidak ditemukan."
            )

            return


        if not sub_error_column:

            await update.message.reply_text(
                f"❌ Kolom {SUB_ERROR_HEADER} "
                "tidak ditemukan."
            )

            return


        # ==================================
        # SEARCH TRACK ID
        # ==================================

        found_row = None


        for row_number, row in enumerate(
            all_values[1:],
            start=2
        ):

            if len(row) < track_column:
                continue

            sheet_track_id = str(
                row[track_column - 1]
            ).strip()


            if (
                sheet_track_id.upper()
                == track_id.upper()
            ):

                found_row = row_number

                break


        # ==================================
        # TRACK ID NOT FOUND
        # ==================================

        if not found_row:

            await update.message.reply_text(
                "❌ TRACK ID tidak ditemukan.\n\n"
                f"📦 {track_id}"
            )

            return


        # ==================================
        # UPDATE GOOGLE SHEET
        # ==================================

        worksheet.update_cell(
            found_row,
            error_column,
            error_code
        )

        worksheet.update_cell(
            found_row,
            sub_error_column,
            sub_error
        )


        # ==================================
        # USERNAME
        # ==================================

        user = update.effective_user

        if user.username:

            updated_by = f"@{user.username}"

        else:

            updated_by = user.full_name


        # ==================================
        # SAVE LOG
        # ==================================

        log_sheet = get_log_sheet(
            spreadsheet
        )

        now = datetime.now().strftime(
            "%d-%m-%Y %H:%M:%S"
        )

        log_sheet.append_row([
            now,
            track_id,
            error_code,
            sub_error,
            updated_by
        ])


        # ==================================
        # SUCCESS MESSAGE
        # ==================================

        success_message = f"""
✅ *Update berhasil!*

📦 TRACK ID
`{track_id}`

🔄 Error Code
*{error_code}*

📝 Sub Error
*{sub_error}*

👤 Oleh
{updated_by}

🕒 {now}
"""

        await update.message.reply_text(
            success_message,
            parse_mode="Markdown"
        )


    except Exception as e:

        logger.exception(
            "Terjadi error saat update order"
        )

        await update.message.reply_text(
            "❌ Terjadi error saat mengakses "
            "Google Sheet.\n\n"
            "Silakan hubungi PIC bot."
        )


# ==========================================
# CEK PERFORM
# ==========================================

async def cek_perform(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    try:

        await update.message.reply_text(
            "📊 Sedang mengambil data performa..."
        )


        _, worksheet = get_worksheet()

        all_values = worksheet.get_all_values()


        if not all_values:

            await update.message.reply_text(
                "❌ Google Sheet kosong."
            )

            return


        headers = all_values[0]


        error_column = find_column(
            headers,
            ERROR_CODE_HEADER
        )


        if not error_column:

            await update.message.reply_text(
                "❌ Kolom Error Code "
                "tidak ditemukan."
            )

            return


        counts = {}


        for row in all_values[1:]:

            if len(row) < error_column:
                continue


            status = row[
                error_column - 1
            ].strip().upper()


            if not status:

                status = "BELUM DIUPDATE"


            counts[status] = (
                counts.get(status, 0) + 1
            )


        total = len(all_values) - 1


        message = f"""
📊 *DASHBOARD PERFORMA*

📦 Total Order: *{total}*

"""


        for status, count in sorted(
            counts.items(),
            key=lambda x: x[1],
            reverse=True
        ):

            message += (
                f"• {status}: *{count}*\n"
            )


        await update.message.reply_text(
            message,
            parse_mode="Markdown"
        )


    except Exception as e:

        logger.exception(
            "Error saat cek performa"
        )

        await update.message.reply_text(
            "❌ Gagal mengambil data performa."
        )


# ==========================================
# RANKING
# ==========================================

async def ranking(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    try:

        await update.message.reply_text(
            "🏆 Sedang menghitung ranking..."
        )


        _, worksheet = get_worksheet()

        data = worksheet.get_all_values()


        if not data:

            await update.message.reply_text(
                "❌ Google Sheet kosong."
            )

            return


        headers = data[0]


        team_column = find_column(
            headers,
            "TEAM"
        )

        error_column = find_column(
            headers,
            ERROR_CODE_HEADER
        )


        if not team_column:

            await update.message.reply_text(
                "❌ Kolom TEAM tidak ditemukan."
            )

            return


        if not error_column:

            await update.message.reply_text(
                "❌ Kolom Error Code "
                "tidak ditemukan."
            )

            return


        ranking_data = {}


        for row in data[1:]:

            if (
                len(row) < team_column
                or len(row) < error_column
            ):

                continue


            team = row[
                team_column - 1
            ].strip()


            status = row[
                error_column - 1
            ].strip().upper()


            if team and status == "PS":

                ranking_data[team] = (
                    ranking_data.get(team, 0)
                    + 1
                )


        sorted_ranking = sorted(
            ranking_data.items(),
            key=lambda x: x[1],
            reverse=True
        )


        message = """
🏆 *RANKING PS TEKNISI*

"""


        medals = [
            "🥇",
            "🥈",
            "🥉"
        ]


        for index, (team, total) in enumerate(
            sorted_ranking,
            start=1
        ):

            if index <= 3:

                icon = medals[index - 1]

            else:

                icon = f"{index}."


            message += (
                f"{icon} *{team}* — "
                f"{total} PS\n"
            )


        if not sorted_ranking:

            message += "Belum ada data PS."


        await update.message.reply_text(
            message,
            parse_mode="Markdown"
        )


    except Exception as e:

        logger.exception(
            "Error saat ranking"
        )

        await update.message.reply_text(
            "❌ Gagal menghitung ranking."
        )


# ==========================================
# MAIN
# ==========================================

def main():

    if not BOT_TOKEN:

        print(
            "ERROR: BOT_TOKEN belum diisi!"
        )

        return


    if not SPREADSHEET_ID:

        print(
            "ERROR: SPREADSHEET_ID belum diisi!"
        )

        return


    if not GOOGLE_CREDENTIALS_JSON:

        print(
            "ERROR: GOOGLE_CREDENTIALS_JSON "
            "belum diisi!"
        )

        return


    application = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
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


    print("=" * 40)
    print("BOT UPDATE ORDER AKTIF")
    print("=" * 40)


    application.run_polling(
        drop_pending_updates=True
    )


if __name__ == "__main__":

    main()
