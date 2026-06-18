import asyncio
import os
import random
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI
from telegram import ReplyKeyboardMarkup, Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")
STT_MODEL = os.getenv("OPENAI_STT_MODEL", "whisper-1")
TTS_MODEL = os.getenv("OPENAI_TTS_MODEL", "tts-1")
TTS_VOICE = os.getenv("OPENAI_TTS_VOICE", "alloy")
STICKER_IDS = [s.strip() for s in os.getenv("STICKER_IDS", "").split(",") if s.strip()]

client = OpenAI(api_key=OPENAI_API_KEY)

MAIN_MENU = ReplyKeyboardMarkup(
    [
        ["🗣 IELTS Speaking Exam", "💬 Oddiy chat"],
        ["📊 Exam holati", "🔄 Qayta boshlash"],
    ],
    resize_keyboard=True,
)

PART_QUESTIONS = {
    1: [
        "What do you do, do you work or study?",
        "Where do you live, and what do you like about that place?",
        "Do you prefer mornings or evenings? Why?",
        "What kind of music do you usually listen to?",
    ],
    2: [
        "Describe a person who inspired you. You should say who this person is, how you know them, what they did, and why they inspired you.",
        "Describe a place you would like to visit. You should say where it is, why you want to go there, who you would go with, and how you would feel there.",
    ],
    3: [
        "Why do some people become role models for others?",
        "Do you think young people today have enough motivation to study?",
        "How has technology changed the way people prepare for exams?",
        "Should schools teach more speaking and communication skills?",
    ],
}

EXAM_LIMITS = {1: 4, 2: 1, 3: 4}


@dataclass
class UserState:
    mode: str = "chat"
    exam_part: int = 0
    question_index: int = 0
    current_question: str = ""
    answers: list[str] = field(default_factory=list)
    history: list[dict[str, str]] = field(default_factory=list)


users: dict[int, UserState] = {}


def get_state(user_id: int) -> UserState:
    if user_id not in users:
        users[user_id] = UserState()
    return users[user_id]


def reset_exam(state: UserState) -> None:
    state.mode = "exam"
    state.exam_part = 1
    state.question_index = 0
    state.current_question = PART_QUESTIONS[1][0]
    state.answers.clear()


async def send_fun_reaction(update: Update) -> None:
    if not update.message:
        return

    if STICKER_IDS and random.random() < 0.45:
        await update.message.reply_sticker(random.choice(STICKER_IDS))
        return

    if random.random() < 0.35:
        await update.message.reply_text(random.choice(["🔥", "Zo‘r!", "Davom etamiz 😄", "Good answer!"]))


def ai_text(system_prompt: str, messages: list[dict[str, str]], max_tokens: int = 450) -> str:
    response = client.chat.completions.create(
        model=CHAT_MODEL,
        messages=[{"role": "system", "content": system_prompt}, *messages],
        temperature=0.8,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content.strip()


def transcribe_audio(path: Path) -> str:
    with path.open("rb") as audio_file:
        transcript = client.audio.transcriptions.create(
            model=STT_MODEL,
            file=audio_file,
        )
    return transcript.text.strip()


def make_voice(text: str, path: Path) -> None:
    response = client.audio.speech.create(
        model=TTS_MODEL,
        voice=TTS_VOICE,
        input=text[:3500],
        response_format="opus",
    )
    response.write_to_file(path)


async def reply_with_voice(update: Update, text: str) -> None:
    if not update.message:
        return

    await update.message.chat.send_action(ChatAction.RECORD_VOICE)
    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
        voice_path = Path(tmp.name)

    try:
        await asyncio.to_thread(make_voice, text, voice_path)
        with voice_path.open("rb") as voice_file:
            await update.message.reply_voice(voice=voice_file, caption=text[:900], reply_markup=MAIN_MENU)
    finally:
        voice_path.unlink(missing_ok=True)


def next_exam_question(state: UserState) -> str | None:
    state.question_index += 1

    if state.question_index < EXAM_LIMITS[state.exam_part]:
        questions = PART_QUESTIONS[state.exam_part]
        state.current_question = questions[state.question_index % len(questions)]
        return state.current_question

    if state.exam_part < 3:
        state.exam_part += 1
        state.question_index = 0
        state.current_question = PART_QUESTIONS[state.exam_part][0]
        return state.current_question

    state.current_question = ""
    return None


def build_exam_feedback(state: UserState, answer: str) -> str:
    system_prompt = (
        "You are a friendly but realistic IELTS Speaking examiner. "
        "The user may be Uzbek, but the IELTS exam must be mostly in English. "
        "Give short feedback, mention one strength and one improvement, then continue naturally. "
        "Do not be boring. Do not write too much. "
        "If the answer is too short, encourage the student and ask for more detail."
    )
    messages = [
        {
            "role": "user",
            "content": (
                f"IELTS Speaking Part {state.exam_part} question: {state.current_question}\n"
                f"Candidate answer: {answer}\n\n"
                "Give feedback in Uzbek + English mix. Keep it under 120 words."
            ),
        }
    ]
    return ai_text(system_prompt, messages, max_tokens=220)


def final_band_report(state: UserState) -> str:
    joined_answers = "\n\n".join(state.answers)
    system_prompt = (
        "You are an IELTS Speaking examiner. Give an estimated IELTS Speaking band score. "
        "Assess fluency, lexical resource, grammar, and pronunciation potential from text. "
        "Be honest, helpful, and concise. Use Uzbek explanations."
    )
    return ai_text(
        system_prompt,
        [
            {
                "role": "user",
                "content": f"Candidate answers:\n{joined_answers}\n\nGive final band estimate and advice.",
            }
        ],
        max_tokens=500,
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    state = get_state(update.effective_user.id)
    state.mode = "chat"
    await update.message.reply_text(
        "Salom! Men IELTS Speaking examiner va oddiy AI chat botman 😄\n\n"
        "Xohlasangiz real exam qilamiz: 3 qism bo‘ladi. Ovozli xabar yuborsangiz, men ham ovozli javob beraman.",
        reply_markup=MAIN_MENU,
    )
    await send_fun_reaction(update)


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    users[update.effective_user.id] = UserState()
    await update.message.reply_text("Hammasi yangilandi. Qaytadan boshlaymiz!", reply_markup=MAIN_MENU)


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    state = get_state(update.effective_user.id)
    if state.mode != "exam":
        await update.message.reply_text("Hozir oddiy chat rejimidasiz.", reply_markup=MAIN_MENU)
        return

    await update.message.reply_text(
        f"IELTS Speaking exam: Part {state.exam_part}, savol {state.question_index + 1}.",
        reply_markup=MAIN_MENU,
    )


async def start_exam(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    state = get_state(update.effective_user.id)
    reset_exam(state)
    await update.message.reply_text(
        "IELTS Speaking Exam boshlandi.\n\n"
        "Part 1: Introduction and interview.\n"
        f"Question 1: {state.current_question}",
        reply_markup=MAIN_MENU,
    )


async def switch_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    state = get_state(update.effective_user.id)
    state.mode = "chat"
    await update.message.reply_text("Oddiy chat rejimiga o‘tdik. Bemalol yozing yoki ovoz yuboring.", reply_markup=MAIN_MENU)


async def handle_exam_answer(update: Update, text: str, answer_by_voice: bool = False) -> None:
    state = get_state(update.effective_user.id)
    state.answers.append(
        f"Part {state.exam_part} | Question: {state.current_question}\nAnswer: {text}"
    )

    await update.message.chat.send_action(ChatAction.TYPING)
    feedback = await asyncio.to_thread(build_exam_feedback, state, text)
    next_question = next_exam_question(state)

    if next_question:
        if state.question_index == 0:
            reply = f"{feedback}\n\nPart {state.exam_part} ga o‘tamiz.\nQuestion: {next_question}"
        else:
            reply = f"{feedback}\n\nNext question: {next_question}"
    else:
        report = await asyncio.to_thread(final_band_report, state)
        state.mode = "chat"
        reply = f"{feedback}\n\nExam tugadi. Mana umumiy baho:\n\n{report}"

    await send_fun_reaction(update)
    if answer_by_voice:
        await reply_with_voice(update, reply)
    else:
        await update.message.reply_text(reply, reply_markup=MAIN_MENU)


async def handle_chat(update: Update, text: str, answer_by_voice: bool = False) -> None:
    state = get_state(update.effective_user.id)
    state.history.append({"role": "user", "content": text})
    state.history = state.history[-10:]

    system_prompt = (
        "You are a warm, energetic Uzbek-speaking Telegram AI assistant. "
        "You can help with English and IELTS, but also chat normally. "
        "Keep answers friendly, useful, and not too long. Use Uzbek as the main language."
    )

    await update.message.chat.send_action(ChatAction.TYPING)
    reply = await asyncio.to_thread(ai_text, system_prompt, state.history, 450)
    state.history.append({"role": "assistant", "content": reply})

    await send_fun_reaction(update)
    if answer_by_voice:
        await reply_with_voice(update, reply)
    else:
        await update.message.reply_text(reply, reply_markup=MAIN_MENU)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text.strip()
    state = get_state(update.effective_user.id)

    if text in {"🗣 IELTS Speaking Exam", "/exam"}:
        await start_exam(update, context)
        return
    if text in {"💬 Oddiy chat", "/chat"}:
        await switch_chat(update, context)
        return
    if text in {"📊 Exam holati", "/status"}:
        await status(update, context)
        return
    if text in {"🔄 Qayta boshlash", "/reset"}:
        await reset(update, context)
        return

    if state.mode == "exam":
        await handle_exam_answer(update, text)
    else:
        await handle_chat(update, text)


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    state = get_state(update.effective_user.id)
    voice = update.message.voice

    await update.message.chat.send_action(ChatAction.TYPING)
    file = await context.bot.get_file(voice.file_id)

    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
        voice_path = Path(tmp.name)

    try:
        await file.download_to_drive(custom_path=voice_path)
        text = await asyncio.to_thread(transcribe_audio, voice_path)
    finally:
        voice_path.unlink(missing_ok=True)

    if not text:
        await update.message.reply_text("Ovoz yaxshi eshitilmadi. Yana bir marta yuboring.", reply_markup=MAIN_MENU)
        return

    await update.message.reply_text(f"Eshitdim: {text}")

    if state.mode == "exam":
        await handle_exam_answer(update, text, answer_by_voice=True)
    else:
        await handle_chat(update, text, answer_by_voice=True)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    print(f"Xatolik: {context.error}")


def main() -> None:
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN .env faylida yo‘q.")
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY .env faylida yo‘q.")

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("exam", start_exam))
    app.add_handler(CommandHandler("chat", switch_chat))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_error_handler(error_handler)

    print("Bot ishga tushdi...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
