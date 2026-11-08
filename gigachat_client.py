import os
import time
import uuid
import urllib3
import requests
from dotenv import load_dotenv

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
load_dotenv()

OAUTH_URL = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
API_URL = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"

class GigaChatClient:
    def __init__(self, credentials=None, model=None, scope=None):
        self.credentials = credentials or os.getenv("GIGACHAT_CREDENTIALS")
        self.model = model or os.getenv("GIGACHAT_MODEL", "GigaChat-Pro")
        self.scope = scope or os.getenv("GIGACHAT_SCOPE", "GIGACHAT_API_PERS")
        self.access_token = None
        self.token_expires_at = 0

        if not self.credentials:
            raise ValueError(
                "GIGACHAT_CREDENTIALS не найден! Укажите его в файле .env или передайте в конструктор."
            )

    def _get_token(self, max_retries=5):
        now = time.time()
        # Refresh if expires in less than 60 seconds
        if self.access_token and now < self.token_expires_at - 60:
            return self.access_token

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "RqUID": str(uuid.uuid4()),
            "Authorization": f"Basic {self.credentials}",
        }
        data = {"scope": self.scope}

        last_exc = None
        for attempt in range(max_retries):
            try:
                resp = requests.post(OAUTH_URL, headers=headers, data=data, verify=False, timeout=25)
                resp.raise_for_status()
                payload = resp.json()
                self.access_token = payload["access_token"]
                self.token_expires_at = payload.get("expires_at", now + 1800000) / 1000.0
                return self.access_token
            except Exception as e:
                last_exc = e
                wait_t = 1.5 * (attempt + 1)
                time.sleep(wait_t)
        raise last_exc

    def complete(self, messages, temperature=0.1, max_tokens=1000, max_retries=5):
        """Sends chat completion request with automatic retry on 429/connection issues."""
        token = self._get_token()
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
        }
        body = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        for attempt in range(max_retries):
            try:
                resp = requests.post(API_URL, headers=headers, json=body, verify=False, timeout=60)
                if resp.status_code == 429:
                    wait_time = 2.0 * (attempt + 1)
                    print(f"[429 Rate Limit] Пауза {wait_time}с перед повторной попыткой {attempt+1}/{max_retries}...")
                    time.sleep(wait_time)
                    continue

                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"]
            except requests.RequestException as e:
                if attempt == max_retries - 1:
                    raise
                print(f"[Ошибка сети] {e}. Повтор через 2с...")
                time.sleep(2)

        raise RuntimeError("Превышено число попыток обращения к GigaChat API")


if __name__ == "__main__":
    try:
        client = GigaChatClient()
        print("Проверка подключения к GigaChat...")
        res = client.complete([{"role": "user", "content": "Ответь одним словом: тест пройден?"}])
        print("Ответ модели:", res)
    except Exception as err:
        print("Ошибка проверки:", err)
