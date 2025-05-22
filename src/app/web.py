import requests
from contextlib import contextmanager
import json

class HttpJsonFetcher:
    def __init__(self, base_url: str = "http://site.dejavu:8083"):
        self.base_url = base_url
        self.session = requests.Session()
    
    @contextmanager
    def session_context(self):
        try:
            yield self.session
        finally:
            self.session.close()
    
    def get_json_list(self, endpoint: str = "/get_json_list") -> dict:
        """Синхронное получение JSON-списка"""
        url = f"{self.base_url}{endpoint}"
        try:
            with self.session_context() as session:
                response = session.get(url, timeout=10)
                response.raise_for_status()
                return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Ошибка соединения: {str(e)}")
            return None
        except json.JSONDecodeError as e:
            print(f"Ошибка парсинга JSON: {str(e)}")
            return None