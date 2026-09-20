import unittest
import os
import shutil
from pathlib import Path

# Set environment variable for test database
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

        # Check default passwords
        self.assertTrue(verify_password("admin1", usernames["Admin"]["password_hash"]))
        self.assertTrue(verify_password("admin", usernames["mtto"]["password_hash"]))
        self.assertTrue(verify_password("admin", usernames["producción"]["password_hash"]))
        self.assertTrue(verify_password("admin", usernames["Dirección"]["password_hash"]))

    def test_02_login_admin(self):
        res = self.client.post("/api/auth/login", json={"username": "Admin", "password": "admin1"})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("access_token", data)
        self.assertEqual(data["user"]["role"], "Admin")
        self.assertTrue(data["permissions"]["produccion"]["can_view"])
        self.assertTrue(data["permissions"]["consumos"]["can_view"])

    def test_03_login_produccion_permissions(self):
        res = self.client.post("/api/auth/login", json={"username": "producción", "password": "admin"})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        token = data["access_token"]

        # Producción view summary OK
        res_prod = self.client.get("/api/produccion/summary", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(res_prod.status_code, 200)

        # Consumos view summary FORBIDDEN
        res_cons = self.client.get("/api/consumos/summary", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(res_cons.status_code, 403)

    def test_04_login_mtto_permissions(self):
        res = self.client.post("/api/auth/login", json={"username": "mtto", "password": "admin"})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        token = data["access_token"]

        # Producción view summary FORBIDDEN
        res_prod = self.client.get("/api/produccion/summary", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(res_prod.status_code, 403)

        # Consumos view summary OK
        res_cons = self.client.get("/api/consumos/summary", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(res_cons.status_code, 200)

    def test_05_admin_users_crud(self):
        # Admin Token
        login_res = self.client.post("/api/auth/login", json={"username": "Admin", "password": "admin1"})
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Create User
        create_res = self.client.post("/api/users", json={
            "username": "operador_test",
            "full_name": "Test Operador",
            "role": "producción",
            "password": "admin"
        }, headers=headers)
        self.assertEqual(create_res.status_code, 200)

        # List Users
        list_res = self.client.get("/api/users", headers=headers)
        self.assertEqual(list_res.status_code, 200)
        usernames = [u["username"] for u in list_res.json()]
        self.assertIn("operador_test", usernames)

if __name__ == "__main__":
    unittest.main()
