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
        print("⚠️ GIGACHAT_API_KEY не найден. Брифинги будут стандартные.")
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