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

        from datetime import datetime, timedelta
        from app.turnos_sync import get_cached_turnos
        from app.routers.produccion_router import get_current_jornada_date, get_shift_start_end_iso

        turnos_cache = get_cached_turnos()
        turno_act = turnos_cache.get("turno_actual", {})
        jornada_fecha = turno_act.get("fecha") or get_current_jornada_date()
        hora_inicio = turno_act.get("hora_inicio", "06:00")
        hora_fin = turno_act.get("hora_fin", "14:00")
        start_iso, end_iso = get_shift_start_end_iso(jornada_fecha, hora_inicio, hora_fin)
        dt_start = datetime.strptime(start_iso, "%Y-%m-%d %H:%M:%S")
        carga_dt = dt_start + timedelta(minutes=30)
        carga_ts_str = carga_dt.strftime("%d/%m/%Y %H:%M:%S")

        sample_payload = {
            "site": "Elis Lavanderia Industrial",
            "device": "Lenovo ThinkCentre PLC FX3U (HELMS Protocol)",
            "load_id": 703,
            "timestamp": carga_ts_str,
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

    def test_07_filtered_shift_dashboard(self):
        res = self.client.post("/api/auth/login", json={"username": "producción", "password": "admin"})
        self.assertEqual(res.status_code, 200)
        token = res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 1. Metadata query (sin parámetros)
        res_meta = self.client.get("/api/produccion/tunel-lavado/dashboard-filtrado", headers=headers)
        self.assertEqual(res_meta.status_code, 200)
        meta_data = res_meta.json()
        self.assertIn("shift_active", meta_data)

        # 2. Ingest test loads in tunel_cargas for active shift
        from datetime import datetime, timedelta
        from app.database import get_db_connection

        if meta_data.get("shift_active"):
            t_curr = meta_data["turno"]
            h_s_str = t_curr["hora_inicio"]
            dt_s = datetime.strptime(f"{t_curr['fecha']} {h_s_str}:00", "%Y-%m-%d %H:%M:%S")
            dt_c1 = dt_s + timedelta(minutes=15)
            dt_c2 = dt_s + timedelta(minutes=45)
            dt_f1 = dt_s
            dt_f2 = dt_s + timedelta(hours=2)

            conn = get_db_connection()
            conn.execute("""
                INSERT OR REPLACE INTO tunel_cargas (load_id, site, device, timestamp, timestamp_iso, cliente, categoria, peso_kg, tiempo_entre_cargas_seg)
                VALUES 
                    (9901, 'Elis', 'PLC', 'test', ?, 101, 1, 60.0, 120),
                    (9902, 'Elis', 'PLC', 'test', ?, 102, 2, 58.5, 130)
            """, (dt_c1.strftime("%Y-%m-%d %H:%M:%S"), dt_c2.strftime("%Y-%m-%d %H:%M:%S")))
            conn.commit()
            conn.close()

            # 3. Filtered query within active shift range
            h_desde = dt_f1.strftime("%H:%M")
            h_hasta = dt_f2.strftime("%H:%M")
            res_filt = self.client.get(f"/api/produccion/tunel-lavado/dashboard-filtrado?hora_desde={h_desde}&hora_hasta={h_hasta}", headers=headers)
            self.assertEqual(res_filt.status_code, 200)
            f_data = res_filt.json()

            self.assertIn("indicadores_destacados", f_data)
            self.assertIn("grafica_avance", f_data)
            self.assertIn("turno_info", f_data)
            self.assertGreaterEqual(f_data["indicadores_destacados"]["cargas_totales_turno"]["valor"], "1 cargas")

        # 4. Conventional hourly slots test (06:30 to 08:50 -> 06:00-07:00, 07:00-08:00, 08:00-09:00)
        res_conv = self.client.get("/api/produccion/tunel-lavado/dashboard-filtrado?hora_desde=06:30&hora_hasta=08:50", headers=headers)
        self.assertEqual(res_conv.status_code, 200)
        conv_data = res_conv.json()
        if conv_data.get("shift_active"):
            self.assertEqual(conv_data["grafica_avance"]["labels"], ["06:00 - 07:00", "07:00 - 08:00", "08:00 - 09:00"])

        # 5. Error case: hora_hasta <= hora_desde within same day
        res_err = self.client.get("/api/produccion/tunel-lavado/dashboard-filtrado?hora_desde=12:00&hora_hasta=08:00", headers=headers)
        self.assertEqual(res_err.status_code, 400)

    def test_08_comparar_turnos_ranking(self):
        res = self.client.post("/api/auth/login", json={"username": "producción", "password": "admin"})
        self.assertEqual(res.status_code, 200)
        token = res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 1. Ranking por total_kg
        res_rank = self.client.get(
            "/api/produccion/turnos/ranking?fecha_inicio=2026-09-20&fecha_fin=2026-09-26&criterio=total_kg",
            headers=headers
        )
        self.assertEqual(res_rank.status_code, 200)
        rank_data = res_rank.json()
        self.assertEqual(rank_data["status"], "success")
        self.assertIn("ranking", rank_data)
        self.assertLessEqual(len(rank_data["ranking"]), 5)

        # Verificar orden descendente
        if len(rank_data["ranking"]) > 1:
            for i in range(len(rank_data["ranking"]) - 1):
                self.assertGreaterEqual(
                    rank_data["ranking"][i]["criterio_valor"],
                    rank_data["ranking"][i + 1]["criterio_valor"]
                )

        # 2. Ranking por ikprod
        res_ik = self.client.get(
            "/api/produccion/turnos/ranking?fecha_inicio=2026-09-20&fecha_fin=2026-09-26&criterio=ikprod",
            headers=headers
        )
        self.assertEqual(res_ik.status_code, 200)

        # 3. Error case: criterio inválido
        res_bad_crit = self.client.get(
            "/api/produccion/turnos/ranking?fecha_inicio=2026-09-20&fecha_fin=2026-09-26&criterio=invalido",
            headers=headers
        )
        self.assertEqual(res_bad_crit.status_code, 400)

        # 4. Error case: fecha_fin < fecha_inicio
        res_bad_dates = self.client.get(
            "/api/produccion/turnos/ranking?fecha_inicio=2026-09-25&fecha_fin=2026-09-20&criterio=total_kg",
            headers=headers
        )
        self.assertEqual(res_bad_dates.status_code, 400)

    def test_09_turnos_totales_periodo(self):
        res = self.client.post("/api/auth/login", json={"username": "producción", "password": "admin"})
        self.assertEqual(res.status_code, 200)
        token = res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 1. Consulta válida de período
        res_tot = self.client.get(
            "/api/produccion/turnos/totales-periodo?fecha_inicio=2026-09-20&hora_inicio=06:00&fecha_fin=2026-09-27&hora_fin=22:00",
            headers=headers
        )
        self.assertEqual(res_tot.status_code, 200)
        tot_data = res_tot.json()
        self.assertEqual(tot_data["status"], "success")
        self.assertIn("ventana_solicitada", tot_data)
        self.assertIn("totales", tot_data)
        self.assertIn("total_kg", tot_data["totales"])
        self.assertIn("total_cargas", tot_data["totales"])
        self.assertIn("kg_hora", tot_data["totales"])
        self.assertIn("ikprod", tot_data["totales"])
        self.assertIn("turnos_concatenados", tot_data)

        # 2. Error case: fecha fin < fecha inicio
        res_err_dates = self.client.get(
            "/api/produccion/turnos/totales-periodo?fecha_inicio=2026-09-26&hora_inicio=14:00&fecha_fin=2026-09-25&hora_fin=10:00",
            headers=headers
        )
        self.assertEqual(res_err_dates.status_code, 400)

        # 3. Error case: formato inválido
        res_bad_fmt = self.client.get(
            "/api/produccion/turnos/totales-periodo?fecha_inicio=fecha-invalida&hora_inicio=06:00",
            headers=headers
        )
        self.assertEqual(res_bad_fmt.status_code, 400)

    def test_10_calandras_produccion_kpis_and_charts(self):
        res = self.client.post("/api/auth/login", json={"username": "producción", "password": "admin"})
        self.assertEqual(res.status_code, 200)
        token = res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 1. Verificar en summary que CALANDRA_2 y CALANDRA_3 incluyan métricas de producción y gráficas
        res_sum = self.client.get("/api/produccion/summary", headers=headers)
        self.assertEqual(res_sum.status_code, 200)
        maquinas = {m["id"]: m for m in res_sum.json()["maquinas"]}

        self.assertIn("CALANDRA_2", maquinas)
        self.assertIn("CALANDRA_3", maquinas)

        cal2 = maquinas["CALANDRA_2"]
        self.assertIn("produccion_calandra", cal2)
        p2 = cal2["produccion_calandra"]
        self.assertIn("prendas_totales", p2)
        self.assertIn("kgs_totales", p2)
        self.assertIn("tiempo_valle_min", p2)
        self.assertIn("prendas_hora", p2)
        self.assertIn("kg_hora", p2)
        self.assertIn("desglose_calandra2", p2)
        self.assertIn("prendas_grandes", p2["desglose_calandra2"])
        self.assertIn("prendas_pequenas", p2["desglose_calandra2"])
        self.assertIn("grafica_hora_a_hora", p2)
        self.assertIn("labels", p2["grafica_hora_a_hora"])
        self.assertIn("prendas", p2["grafica_hora_a_hora"])
        self.assertIn("tiempo_valle", p2["grafica_hora_a_hora"])

        cal3 = maquinas["CALANDRA_3"]
        self.assertIn("produccion_calandra", cal3)
        p3 = cal3["produccion_calandra"]
        self.assertIn("prendas_totales", p3)
        self.assertIn("kgs_totales", p3)
        self.assertIn("tiempo_valle_min", p3)
        self.assertIn("prendas_hora", p3)
        self.assertIn("kg_hora", p3)
        self.assertIn("grafica_hora_a_hora", p3)

        # 2. Endpoint en vivo de calandras
        res_live = self.client.get("/api/produccion/calandras/live", headers=headers)
        self.assertEqual(res_live.status_code, 200)
        live_data = res_live.json()
        self.assertEqual(live_data["status"], "success")
        self.assertIn("calandra_2", live_data)
        self.assertIn("calandra_3", live_data)

        # 3. Verificar que las tarjetas son clicables para acceder al dashboard ampliado
        self.assertTrue(cal2["clickable"])
        self.assertTrue(cal3["clickable"])
        self.assertEqual(cal2["dashboard_url"], "#calandra_2")
        self.assertEqual(cal3["dashboard_url"], "#calandra_3")

        # 4. Verificar endpoints de Dashboard Ampliado para Calandra 2 y Calandra 3
        res_dash2 = self.client.get("/api/produccion/calandras/CALANDRA_2/dashboard", headers=headers)
        self.assertEqual(res_dash2.status_code, 200)
        dash2 = res_dash2.json()
        self.assertEqual(dash2["status"], "success")
        self.assertEqual(dash2["maquina_id"], "CALANDRA_2")
        self.assertIn("indicadores", dash2)
        self.assertIn("grafica_hora_a_hora", dash2)

        res_dash3 = self.client.get("/api/produccion/calandras/CALANDRA_3/dashboard", headers=headers)
        self.assertEqual(res_dash3.status_code, 200)
        dash3 = res_dash3.json()
        self.assertEqual(dash3["status"], "success")
        self.assertEqual(dash3["maquina_id"], "CALANDRA_3")
        self.assertIn("indicadores", dash3)
        self.assertIn("grafica_hora_a_hora", dash3)

        # 5. Si no hay turno activo, verificar que las métricas sean 0
        if not dash2.get("is_turno_activo"):
            self.assertEqual(dash2["indicadores"]["prendas_totales"], 0)
            self.assertEqual(dash2["indicadores"]["kgs_totales"], 0.0)
            self.assertEqual(dash2["indicadores"]["tiempo_valle_min"], 0.0)

    def test_11_calandras_shift_json_persistence(self):
        res = self.client.post("/api/auth/login", json={"username": "producción", "password": "admin"})
        self.assertEqual(res.status_code, 200)
        token = res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 1. Guardar turno 1 para Calandra 2
        res_save2 = self.client.post("/api/produccion/calandras/CALANDRA_2/guardar-turno-json?fecha=2026-09-27&turno_numero=1", headers=headers)
        self.assertEqual(res_save2.status_code, 200)
        d2_save = res_save2.json()
        self.assertEqual(d2_save["status"], "success")
        self.assertEqual(d2_save["turno_identificador"], "Turno 1")
        self.assertEqual(d2_save["maquina"], "CALANDRA_2")
        self.assertIn("indicadores_dashboard", d2_save)
        self.assertIn("desglose_hora_a_hora", d2_save)
        self.assertIn("labels", d2_save["desglose_hora_a_hora"])
        self.assertIn("prendas", d2_save["desglose_hora_a_hora"])
        self.assertIn("tiempo_valle_min", d2_save["desglose_hora_a_hora"])
        shift_key_2 = d2_save["shift_key"]

        # 2. Guardar turno 2 para Calandra 2
        res_save2_t2 = self.client.post("/api/produccion/calandras/CALANDRA_2/guardar-turno-json?fecha=2026-09-27&turno_numero=2", headers=headers)
        self.assertEqual(res_save2_t2.status_code, 200)
        self.assertEqual(res_save2_t2.json()["turno_identificador"], "Turno 2")

        # 3. Guardar turno 1 para Calandra 3
        res_save3 = self.client.post("/api/produccion/calandras/CALANDRA_3/guardar-turno-json?fecha=2026-09-27&turno_numero=1", headers=headers)
        self.assertEqual(res_save3.status_code, 200)
        d3_save = res_save3.json()
        self.assertEqual(d3_save["status"], "success")
        self.assertEqual(d3_save["turno_identificador"], "Turno 1")
        self.assertEqual(d3_save["maquina"], "CALANDRA_3")
        shift_key_3 = d3_save["shift_key"]

        # 4. Consultar historial de turnos guardados para Calandra 2
        res_hist2 = self.client.get("/api/produccion/calandras/CALANDRA_2/turnos-historial", headers=headers)
        self.assertEqual(res_hist2.status_code, 200)
        h2 = res_hist2.json()
        self.assertEqual(h2["status"], "success")
        self.assertGreaterEqual(h2["total"], 2)
        turnos_nombres = [t["turno_identificador"] for t in h2["turnos"]]
        self.assertIn("Turno 1", turnos_nombres)
        self.assertIn("Turno 2", turnos_nombres)

        # 5. Consultar detalle de turno por shift_key para Calandra 2
        res_det2 = self.client.get(f"/api/produccion/calandras/CALANDRA_2/turnos-historial/{shift_key_2}", headers=headers)
        self.assertEqual(res_det2.status_code, 200)
        det2 = res_det2.json()
        self.assertEqual(det2["shift_key"], shift_key_2)
        self.assertEqual(det2["turno_identificador"], "Turno 1")
        self.assertIn("meta_info", det2)
        self.assertIn("indicadores_dashboard", det2)
        self.assertIn("desglose_hora_a_hora", det2)

        # 6. Consultar fechas disponibles
        res_fechas = self.client.get("/api/produccion/calandras/CALANDRA_2/turnos-fechas", headers=headers)
        self.assertEqual(res_fechas.status_code, 200)
        self.assertIn("2026-09-27", res_fechas.json()["fechas"])

if __name__ == "__main__":
    unittest.main()



