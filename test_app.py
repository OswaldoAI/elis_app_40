import unittest
import os
from pathlib import Path

os.environ["DB_PATH"] = "test_elis_40.db"

from fastapi.testclient import TestClient
from app.main import app
from app.seed import seed_database
from app.auth import verify_password, hash_password
from app.database import get_db_connection

class TestElis4App(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        seed_database()
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        if os.path.exists("test_elis_40.db"):
            os.remove("test_elis_40.db")

    def test_01_users_seeded_correctly(self):
        conn = get_db_connection()
        users = conn.execute("SELECT username, role, password_hash FROM users").fetchall()
        conn.close()
        
        usernames = {u["username"]: u for u in users}
        self.assertIn("Admin", usernames)
        self.assertTrue(verify_password("admin1", usernames["Admin"]["password_hash"]))

    def test_02_tunel_lavado_dashboard(self):
        res = self.client.post("/api/auth/login", json={"username": "producción", "password": "admin"})
        self.assertEqual(res.status_code, 200)
        token = res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Check Summary Clickable card
        res_prod = self.client.get("/api/produccion/summary", headers=headers)
        self.assertEqual(res_prod.status_code, 200)
        tunel = next(m for m in res_prod.json()["maquinas"] if m["id"] == "TUNEL_LAVADO")
        self.assertTrue(tunel["clickable"])

        # Check Dashboard endpoint
        res_dash = self.client.get("/api/produccion/tunel-lavado/dashboard", headers=headers)
        self.assertEqual(res_dash.status_code, 200)
        dash_data = res_dash.json()
        
        self.assertIn("indicadores_destacados", dash_data)
        self.assertIn("kg_totales_turno", dash_data["indicadores_destacados"])
        self.assertIn("cargas_totales_turno", dash_data["indicadores_destacados"])
        self.assertIn("kpi_productividad_iprod", dash_data["indicadores_destacados"])

if __name__ == "__main__":
    unittest.main()
