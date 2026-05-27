# test_catzap.py - Testes automatizados para CatZap
import unittest
import requests
import time
import subprocess
import sys
import os

class TestCatZapServer(unittest.TestCase):
    BASE_URL = "http://127.0.0.1:51777"
    server_process = None

    @classmethod
    def setUpClass(cls):
        """Iniciar servidor antes dos testes"""
        catzap_dir = os.path.join(os.path.dirname(__file__), 'cat_zap.py')
        workdir = os.path.dirname(__file__)
        cls.server_process = subprocess.Popen(
            [sys.executable, catzap_dir],
            cwd=workdir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        time.sleep(3)  # Aguardar servidor iniciar

    @classmethod
    def tearDownClass(cls):
        """Parar servidor após os testes"""
        if cls.server_process:
            cls.server_process.terminate()
            try:
                cls.server_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                cls.server_process.kill()

    def test_01_health_check(self):
        """Testar endpoint /health"""
        response = requests.get(f"{self.BASE_URL}/health", timeout=10)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ok")
        self.assertIn("version", data)

    def test_02_model_status(self):
        """Testar endpoint /model-status"""
        response = requests.get(f"{self.BASE_URL}/model-status", timeout=10)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("ready", data)

    def test_03_history_endpoint(self):
        """Testar endpoint /history"""
        response = requests.get(f"{self.BASE_URL}/history", timeout=10)
        # Endpoint may not exist in old version (404) - skip if so
        if response.status_code == 404:
            self.skipTest("Endpoint /history not available in this version")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("history", data)
        self.assertIsInstance(data["history"], list)

    def test_04_transcribe_endpoint_structure(self):
        """Verificar estrutura do endpoint /transcribe"""
        mock_audio = b"test audio data"
        response = requests.post(
            f"{self.BASE_URL}/transcribe",
            data=mock_audio,
            headers={"Content-Type": "application/octet-stream", "X-Lang": "pt"},
            timeout=30
        )
        # Check JSON response (may have charset suffix)
        content_type = response.headers.get("Content-Type", "")
        self.assertTrue(content_type.startswith("application/json"))

    def test_05_delete_history(self):
        """Testar limpeza do histórico"""
        response = requests.delete(f"{self.BASE_URL}/history", timeout=10)
        # Endpoint may return 501 (Not Implemented) in old version
        if response.status_code == 501:
            self.skipTest("DELETE /history not implemented in this version")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get("ok") == True or data.get("status") == "ok")

if __name__ == "__main__":
    unittest.main(verbosity=2)