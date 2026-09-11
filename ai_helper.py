import os

giga = None
try:
    from gigachat import GigaChat
    api_key = os.environ.get("GIGACHAT_API_KEY")
    if api_key:
        giga = GigaChat(
            credentials=api_key,
            model="GigaChat-2",
            scope="GIGACHAT_API_PERS",
            verify_ssl_certs=False
        )
        print("✅ GigaChat инициализирован.")
    else:
        print("⚠️ GIGACHAT_API_KEY не найден.")
except Exception as e:
    print(f"⚠️ Ошибка GigaChat: {e}")


def generate_text(prompt: str):
    """Отправляет промпт в GigaChat, возвращает текст или None при ошибке."""
    if giga is None:
        return None
    try:
        response = giga.chat.create(prompt)
        return response.messages[0].content[0].text
    except Exception as e:
        print(f"Ошибка GigaChat: {e}")
        return None


def generate_briefing(
    child_name: str,
    age_months: int,
    night_sleep_min: int,
    night_wakes: int,
    wake_time_str: str,
    naps_count: int,
    first_nap_str: str,
    bedtime_str: str,
) -> str:
    """Генерирует 3-частный брифинг: Ночь / Сегодня / Фокус."""

    hours = night_sleep_min // 60
    minutes = night_sleep_min % 60
    night_str = f"{hours} ч {minutes} мин" if hours else f"{minutes} мин"

    prompt = (
        f"Ты — заботливый и знающий консультант по детскому сну. "
        f"Составь утренний брифинг для мамы на русском языке.\n\n"
        f"Данные о ребёнке:\n"
        f"- Имя: {child_name}\n"
        f"- Возраст: примерно {age_months} мес.\n"
        f"- Ночной сон: {night_str}\n"
        f"- Ночных пробуждений: {night_wakes}\n"
        f"- Время подъёма сегодня: {wake_time_str}\n"
        f"- Планируется дневных снов: {naps_count}\n"
        f"- Первый сон по плану: {first_nap_str}\n"
        f"- Укладывание на ночь: {bedtime_str}\n\n"
        f"Формат ответа — строго три части с заголовками:\n\n"
        f"🌙 НОЧЬ\n"
        f"2–4 предложения: как прошла ночь, сравнение с возрастной нормой, есть ли накопленный недосып.\n\n"
        f"📅 СЕГОДНЯ\n"
        f"2–3 предложения: чего ожидать по плану дня, как предыдущий сон влияет на следующие.\n\n"
        f"🎯 ФОКУС\n"
        f"1–2 предложения: одна конкретная рекомендация маме на сегодня.\n\n"
        f"Пиши тепло, по делу, без markdown-разметки. Общая длина — не более 1000 символов. "
        f"Не используй заголовки через #, только эмодзи."
    )

    text = generate_text(prompt)
    return text if text else ""