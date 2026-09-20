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
        self.assertIn("mtto", usernames)
        self.assertIn("producción", usernames)
        self.assertIn("Dirección", usernames)

        self.assertTrue(verify_password("admin1", usernames["Admin"]["password_hash"]))
        self.assertTrue(verify_password("admin", usernames["mtto"]["password_hash"]))

    def test_02_login_produccion_tunel_lavado(self):
        res = self.client.post("/api/auth/login", json={"username": "producción", "password": "admin"})
        self.assertEqual(res.status_code, 200)
        token = res.json()["access_token"]

        res_prod = self.client.get("/api/produccion/summary", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(res_prod.status_code, 200)
        data = res_prod.json()
        
        # Check Tunel de Lavado Custom Card Fields
        tunel = next(m for m in data["maquinas"] if m["id"] == "TUNEL_LAVADO")
        self.assertEqual(tunel["subtitulo_resumen"], "Resumen turno actual")
        self.assertIn("turno_info", tunel)
        self.assertEqual(tunel["turno_info"]["nombre"], "Turno Mañana")
        self.assertIn("indicadores_turno", tunel)
        self.assertIn("promedio_carga", tunel["indicadores_turno"])
        self.assertIn("promedio_tiempo_carga", tunel["indicadores_turno"])
        self.assertIn("cantidad_cargas", tunel["indicadores_turno"])

if __name__ == "__main__":
    unittest.main()
