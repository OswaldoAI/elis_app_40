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
        try:
            if os.path.exists("test_elis_40.db"):
                os.remove("test_elis_40.db")
        except Exception:
            pass

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
        self.assertIn("hprod", dash_data["indicadores_destacados"])
        self.assertIn("ikprod", dash_data["indicadores_destacados"])


    def test_03_mqtt_save_and_real_metrics(self):
        from app.mqtt_subscriber import save_carga_to_db
        from datetime import datetime
        
        conn = get_db_connection()
        conn.execute("DELETE FROM tunel_cargas")
        conn.commit()
        conn.close()

        today_str = datetime.now().strftime("%d/%m/%Y")
        sample_payload = {
            "site": "Elis Lavanderia Industrial",
            "device": "Lenovo ThinkCentre PLC FX3U (HELMS Protocol)",
            "load_id": 703,
            "timestamp": f"{today_str} 09:30:00",
            "cliente": 150,
            "categoria": 4,
            "peso_kg": 59,
            "tiempo_entre_cargas_seg": 185,
            "raw_hex": "1A40 10DC"
        }

        res_save = save_carga_to_db(sample_payload)
        self.assertTrue(res_save)


        res = self.client.post("/api/auth/login", json={"username": "producción", "password": "admin"})
        token = res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        res_dash = self.client.get("/api/produccion/tunel-lavado/dashboard", headers=headers)
        dash_data = res_dash.json()
        self.assertEqual(dash_data["indicadores_destacados"]["kg_totales_turno"]["valor"], "59 kg")
        self.assertEqual(dash_data["indicadores_destacados"]["cargas_totales_turno"]["valor"], "1 cargas")

    def test_04_shift_json_persistence(self):
        res = self.client.post("/api/auth/login", json={"username": "producción", "password": "admin"})
        token = res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 1. Get dynamic shift JSON package
        res_pkg = self.client.get("/api/produccion/turnos/json-paquete", headers=headers)
        self.assertEqual(res_pkg.status_code, 200)
        pkg = res_pkg.json()
        self.assertIn("shift_key", pkg)
        self.assertIn("meta_info", pkg)
        self.assertIn("indicadores_ampliados", pkg)
        self.assertIn("totales_promedios", pkg)
        self.assertIn("desglose_horario", pkg)

        # 2. Explicitly save shift JSON
        res_save = self.client.post("/api/produccion/turnos/guardar-json", headers=headers)
        self.assertEqual(res_save.status_code, 200)
        self.assertEqual(res_save.json()["status"], "success")

        # 3. List history JSON
        res_hist = self.client.get("/api/produccion/turnos/historial-json", headers=headers)
        self.assertEqual(res_hist.status_code, 200)
        hist = res_hist.json()
        self.assertGreaterEqual(hist["total"], 1)

        # 4. Fetch specific shift JSON by key
        shift_key = pkg["shift_key"]
        res_key = self.client.get(f"/api/produccion/turnos/historial-json/{shift_key}", headers=headers)
        self.assertEqual(res_key.status_code, 200)
        self.assertEqual(res_key.json()["shift_key"], shift_key)

        # 5. Fetch available dates for turnos
        res_dates = self.client.get("/api/produccion/turnos/fechas-disponibles", headers=headers)
        self.assertEqual(res_dates.status_code, 200)
        self.assertIn("fechas", res_dates.json())

        # 6. Fetch shifts for a specific date
        fecha_test = pkg["meta_info"]["fecha"]
        res_shifts = self.client.get(f"/api/produccion/turnos/por-fecha/{fecha_test}", headers=headers)
        self.assertEqual(res_shifts.status_code, 200)
        self.assertIn("turnos", res_shifts.json())

        # 7. Fetch quick comparison results table (resultados_turnos)
        res_res = self.client.get("/api/produccion/turnos/resultados", headers=headers)
        self.assertEqual(res_res.status_code, 200)
        self.assertIn("resultados", res_res.json())
        self.assertGreaterEqual(res_res.json()["total"], 1)
        r0 = res_res.json()["resultados"][0]
        self.assertIn("total_kg", r0)
        self.assertIn("ikprod", r0)
        self.assertIn("total_cargas", r0)
        self.assertIn("rango_horario", r0)
        self.assertIn("fecha", r0)

        # 8. Fetch quick comparison results filtered by date
        res_res_date = self.client.get(f"/api/produccion/turnos/resultados/por-fecha/{fecha_test}", headers=headers)
        self.assertEqual(res_res_date.status_code, 200)
        self.assertIn("resultados", res_res_date.json())

    def test_05_consumos_process_cards(self):
        res = self.client.post("/api/auth/login", json={"username": "Admin", "password": "admin1"})
        token = res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        res_c = self.client.get("/api/consumos/summary", headers=headers)
        self.assertEqual(res_c.status_code, 200)
        c_data = res_c.json()

        self.assertIn("generales", c_data)
        self.assertIn("desglose_agua", c_data)
        self.assertIn("desglose_gas", c_data)
        self.assertIn("desglose_electricidad", c_data)

        # Check all 14 process cards
        self.assertIn("agua_general", c_data["generales"])
        self.assertIn("gas_general", c_data["generales"])
        self.assertIn("energia_electrica", c_data["generales"])
        self.assertIn("agua_tunel_lavadoras", c_data["desglose_agua"])
        self.assertIn("gas_tunel_vt", c_data["desglose_gas"])
        self.assertIn("gas_calandra_1", c_data["desglose_gas"])
        self.assertIn("gas_calandra_2", c_data["desglose_gas"])
        self.assertIn("gas_calandra_3", c_data["desglose_gas"])
        self.assertIn("gas_caldera_1", c_data["desglose_gas"])
        self.assertIn("gas_caldera_2", c_data["desglose_gas"])
        self.assertIn("elec_tunel", c_data["desglose_electricidad"])
        self.assertIn("elec_calandra_1", c_data["desglose_electricidad"])
        self.assertIn("elec_calandra_2", c_data["desglose_electricidad"])
        self.assertIn("elec_calandra_3", c_data["desglose_electricidad"])

    def test_06_agua_tunel_telemetria(self):
        res = self.client.post("/api/auth/login", json={"username": "Admin", "password": "admin1"})
        token = res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 1. Post new pulse ingestion (50 pulses = 5.0 m3)
        payload = {"pulsos": 50, "caudal_m3h": 22.5, "dispositivo": "Test Contador Agua"}
        res_ing = self.client.post("/api/consumos/agua-tunel/ingesta", json=payload, headers=headers)
        self.assertEqual(res_ing.status_code, 200)

        # 2. Query telemetry & date range filter
        res_tel = self.client.get("/api/consumos/agua-tunel/telemetria", headers=headers)
        self.assertEqual(res_tel.status_code, 200)
        t_data = res_tel.json()
        self.assertEqual(t_data["variable"], "AGUA_TUNEL_LAVADORAS")
        self.assertGreaterEqual(t_data["total_pulsos"], 50)

        # 3. Test generic telemetry endpoint for Caldera 1
        res_cal = self.client.get("/api/consumos/telemetria?variable=caldera1", headers=headers)
        self.assertEqual(res_cal.status_code, 200)
        cal_data = res_cal.json()
        self.assertEqual(cal_data["variable"], "caldera1")
        self.assertGreaterEqual(cal_data["total_registros"], 1)

if __name__ == "__main__":
    unittest.main()

