# elis_app_40

Sistema de Supervisión de la Planta Lavandería Industrial **ELIS NÁJERA 4.0**.

## 🚀 Características Principales

- **Interfaz Industrial**: Fondo oscuro con encabezado blanco radiante y menú lateral navegable.
- **Página de Inicio (`/inicio`)**: Tarjetas de métricas globales y vista principal con `industria_40.png`.
- **Módulo de Producción**: Tarjetas gráficas y telemetría en tiempo real para:
  - 🌊 **Túnel de Lavado**
  - 🌀 **Túnel VT**
  - 📜 **Calandra 2**
  - 👁️ **Calandra 3** (Integración con visión por IA)
- **Módulo de Consumos**: Monitoreo de potencia eléctrica (kW), agua (m³/h, reciclaje) y vapor/gas (bar).
- **Gestión de Usuarios & Autenticación JWT**:
  - Roles: `Admin`, `Dirección`, `producción`, `mtto`.
  - Contraseñas por defecto: `admin1` para Admin y `admin` para el resto.
  - Panel exclusivo de Admin para CRUD de usuarios y contraseñas.
  - Matriz de permisos de módulos editable desde el panel de administración.
  - Efecto visual degradado/bloqueado (🔒) para módulos sin permisos.
- **Despliegue Docker**: Empaquetado para Jetson Server A (`elis_industry4_app`).

## 🛠️ Tecnologías Utilizadas

- **Backend**: Python (FastAPI, SQLite, Uvicorn, Passlib, PyJWT)
- **Frontend**: HTML5, CSS3, JavaScript / TypeScript
- **Contenedores**: Docker, Docker Compose
- **Servidor IoT / IA**: NVIDIA Jetson Tegra ARM64
