import httpx
import logging
from app.config import MISTRAL_API_KEY, MISTRAL_API_URL

async def get_mistral_response(user_input: str) -> str:
    headers = {
        "Authorization": f"Bearer {MISTRAL_API_KEY}",
        "Content-Type": "application/json"
    }

    data = {
        "model": "mistral-tiny",
        "messages": [{"role": "user", "content": user_input}],
        "max_tokens": 200,
        "temperature": 0.7,
        "top_p": 0.9
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(MISTRAL_API_URL, json=data, headers=headers)

        if response.status_code != 200:
            logging.error(f"⚠️ Gabim nga API: {response.status_code} - {response.text}")
            return "⚠️ Nuk mund të marr përgjigje për momentin."

        result = response.json()
        logging.info(f"📡 Përgjigja nga API: {result}")  # Debug për të parë përgjigjen e plotë

        # Kontrollo nëse "choices" ekziston dhe ka përmbajtje të vlefshme
        choices = result.get("choices", [])
        if not choices or "message" not in choices[0]:
            return "⚠️ API nuk dha përgjigje të vlefshme."

        return choices[0]["message"].get("content", "Nuk ka përgjigje.")

    except Exception as e:
        logging.error(f"⚠️ Gabim në lidhje me API: {str(e)}")
        return "⚠️ Nuk mund të lidhem me serverin."
