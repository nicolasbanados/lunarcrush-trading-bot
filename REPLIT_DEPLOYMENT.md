# 🚀 Deployment en Replit - Guía Completa

Replit es **perfecto** para este bot: fácil, rápido y corre 24/7 con plan gratuito.

---

## 📋 Paso 1: Crear Repl

1. Ir a [replit.com](https://replit.com)
2. Click en **"+ Create Repl"**
3. Seleccionar **"Python"** como template
4. Nombre: `lunarcrush-trading-bot`
5. Click **"Create Repl"**

---

## 📁 Paso 2: Subir Archivos

### Opción A: Subir ZIP (Más Fácil)

1. En Replit, click en el ícono de **3 puntos** (⋮) junto a "Files"
2. Click **"Upload folder"** o **"Upload file"**
3. Subir el archivo `lunarcrush-trading-bot.zip`
4. En la terminal de Replit:

```bash
unzip lunarcrush-trading-bot.zip
mv lunarcrush-trading-bot/* .
rm -rf lunarcrush-trading-bot
```

### Opción B: Git (Alternativa)

Si subes el código a GitHub primero:

```bash
git clone https://github.com/tu-usuario/lunarcrush-bot.git .
```

---

## 🔐 Paso 3: Configurar Secrets (API Keys)

**NO uses archivo `.env` en Replit** (inseguro). Usa Secrets:

1. Click en el ícono de **🔒 Secrets** (candado) en la barra lateral
2. Agregar estos secrets:

| Key | Value |
|-----|-------|
| `LUNARCRUSH_API_KEY` | Tu API key de LunarCrush |
| `HYPERLIQUID_PRIVATE_KEY` | Tu private key de Hyperliquid |
| `HYPERLIQUID_WALLET_ADDRESS` | Tu wallet address |

---

## 📝 Paso 4: Crear `main.py` en la Raíz

Replit necesita un `main.py` en la raíz. Crear archivo:

```python
import os
import sys
import asyncio
from threading import Thread

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Import bot and API server
from main import TradingBot
from api_server import app

def run_api_server():
    """Run Flask API in background"""
    app.run(host='0.0.0.0', port=5000, debug=False)

def run_bot():
    """Run trading bot"""
    bot = TradingBot()
    asyncio.run(bot.start())

if __name__ == "__main__":
    # Start API server in background thread
    api_thread = Thread(target=run_api_server, daemon=True)
    api_thread.start()
    
    print("🚀 LunarCrush Bot Starting...")
    print("📊 Dashboard: https://your-repl-name.repl.co")
    print("🔗 API: https://your-repl-name.repl.co/api/status")
    
    # Start bot (main thread)
    run_bot()
```

---

## 📦 Paso 5: Configurar `pyproject.toml`

Replit usa `pyproject.toml` para dependencias. Crear archivo:

```toml
[tool.poetry]
name = "lunarcrush-trading-bot"
version = "1.0.0"
description = "Trading bot powered by LunarCrush"
authors = ["Your Name"]

[tool.poetry.dependencies]
python = "^3.11"
requests = "^2.31.0"
aiohttp = "^3.9.1"
flask = "^3.0.0"
flask-cors = "^4.0.0"
eth-account = "^0.10.0"
web3 = "^6.11.3"
pandas = "^2.1.4"
numpy = "^1.26.2"
python-dotenv = "^1.0.0"
pydantic = "^2.5.2"
colorlog = "^6.8.0"

[build-system]
requires = ["poetry-core"]
build-backend = "poetry.core.masonry.api"
```

---

## 🌐 Paso 6: Configurar `.replit`

Crear archivo `.replit` para configurar el entorno:

```toml
run = "python main.py"
entrypoint = "main.py"
modules = ["python-3.11"]

[nix]
channel = "stable-23_11"

[deployment]
run = ["python", "main.py"]
deploymentTarget = "cloudrun"

[[ports]]
localPort = 5000
externalPort = 80
```

---

## ▶️ Paso 7: Ejecutar el Bot

1. Click en el botón **"Run"** (▶️) en la parte superior
2. Esperar a que se instalen las dependencias (1-2 minutos)
3. Ver logs en la consola

Deberías ver:
```
🚀 LunarCrush Bot Starting...
📊 Dashboard: https://lunarcrush-trading-bot.your-username.repl.co
Trading Bot initialized successfully
Starting trading bot loop...
```

---

## 📊 Paso 8: Acceder al Dashboard

### URL del Dashboard

Tu dashboard estará en:
```
https://lunarcrush-trading-bot.your-username.repl.co
```

### Configurar Dashboard para Replit

Editar `dashboard/index.html`, buscar esta línea:

```javascript
const response = await fetch('http://localhost:5000/api/status');
```

Cambiar a:
```javascript
const response = await fetch('/api/status');
```

Hacer lo mismo para todos los `fetch()` en el archivo.

---

## 🔄 Paso 9: Mantener Bot Activo 24/7

### Problema: Replit duerme después de 1 hora

**Solución 1: UptimeRobot (Gratis)**

1. Ir a [uptimerobot.com](https://uptimerobot.com)
2. Crear cuenta gratis
3. Agregar monitor:
   - Type: **HTTP(s)**
   - URL: `https://tu-repl-name.repl.co/api/status`
   - Interval: **5 minutes**

Esto "despertará" tu Repl cada 5 minutos.

**Solución 2: Replit Always On ($7/mes)**

1. En tu Repl, ir a **Settings**
2. Activar **"Always On"**
3. Pagar $7/mes

---

## 🐛 Troubleshooting

### Error: "Module not found"

```bash
# En la terminal de Replit
poetry install
```

### Error: "Port 5000 already in use"

Cambiar puerto en `main.py`:
```python
app.run(host='0.0.0.0', port=8080)
```

### Bot se detiene después de 1 hora

Configurar UptimeRobot (ver arriba).

### Dashboard no carga datos

1. Verificar que API server está corriendo: `https://tu-repl.co/api/status`
2. Revisar logs en consola de Replit
3. Verificar que secrets están configurados

---

## 📱 Monitoreo desde Móvil

Puedes acceder al dashboard desde tu celular:
```
https://tu-repl-name.repl.co
```

---

## 🔒 Seguridad

### Hacer Repl Privado

1. Ir a **Settings** del Repl
2. Cambiar **Visibility** a **"Private"**

### Proteger Dashboard con Contraseña

Agregar en `api_server.py`:

```python
from functools import wraps
from flask import request, Response

def check_auth(username, password):
    return username == 'admin' and password == 'tu_password_aqui'

def authenticate():
    return Response('Login required', 401, 
        {'WWW-Authenticate': 'Basic realm="Login Required"'})

def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated

# Aplicar a todas las rutas
@app.route('/api/status')
@requires_auth
def get_status():
    # ... código existente
```

---

## ✅ Checklist Final

- [ ] Repl creado
- [ ] Archivos subidos
- [ ] Secrets configurados
- [ ] `main.py` en raíz creado
- [ ] Bot corriendo sin errores
- [ ] Dashboard accesible
- [ ] UptimeRobot configurado (para 24/7)
- [ ] API keys funcionando

---

## 🆘 Necesitas Ayuda?

Si tienes algún error, compárteme:
1. Screenshot del error en Replit
2. Logs de la consola
3. URL de tu Repl

¡Y te ayudo a resolverlo!
