# 🧪 Testing Guide - Probar Antes de Usar Fondos Reales

**IMPORTANTE**: Testea todo antes de depositar tus $1,000 USDC.

---

## 🎯 Opciones de Testing

### Opción 1: Modo Test (Simulación) ⭐ RECOMENDADA

El bot incluye un **modo de prueba** que simula trades sin ejecutarlos realmente.

#### Activar Modo Test

En `config/config.json`, cambiar:

```json
{
  "test_mode": true,
  "initial_capital": 1000,
  "max_positions": 5
}
```

O en Replit Secrets, agregar:
- Key: `TEST_MODE`
- Value: `true`

#### Qué hace el modo test:

✅ **Sí hace**:
- Lee datos reales de LunarCrush
- Genera señales reales
- Simula ejecución de trades
- Registra todo en la base de datos
- Muestra resultados en dashboard

❌ **NO hace**:
- NO ejecuta trades reales en Hyperliquid
- NO gasta dinero
- NO necesita fondos en wallet

#### Ejecutar en Modo Test

```bash
# En Replit o terminal local
python main.py --test-mode
```

Verás en los logs:
```
⚠️ RUNNING IN TEST MODE - No real trades will be executed
🤖 Initializing trading bot...
✅ Test mode: Simulating trade execution
```

---

### Opción 2: Hyperliquid Testnet

Hyperliquid tiene una **testnet** con fondos falsos.

#### Paso 1: Conectar a Testnet

En `src/hyperliquid_client.py`, cambiar:

```python
class HyperliquidClient:
    def __init__(self):
        self.testnet = True  # Cambiar a True
        self.base_url = "https://api.hyperliquid-testnet.xyz" if self.testnet else "https://api.hyperliquid.xyz"
```

#### Paso 2: Obtener Fondos de Testnet

1. Ir a [testnet.hyperliquid.xyz](https://testnet.hyperliquid.xyz)
2. Conectar tu wallet
3. Click en "Faucet" para obtener USDC de prueba
4. Recibirás ~1,000 USDC falsos

---

### Opción 3: Paper Trading (Solo LunarCrush)

Probar **solo las señales** sin conectar Hyperliquid.

#### Crear archivo `test_signals.py`

```python
import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from lunarcrush_client import LunarCrushClient
from strategies.momentum_strategy import MomentumStrategy
from strategies.altrank_strategy import AltRankStrategy
from strategies.reversal_strategy import ReversalStrategy

async def test_strategies():
    print("🧪 Testing LunarCrush Strategies\n")
    
    lc_client = LunarCrushClient()
    
    strategies = [
        MomentumStrategy(lc_client),
        AltRankStrategy(lc_client),
        ReversalStrategy(lc_client)
    ]
    
    for strategy in strategies:
        print(f"\n{'='*60}")
        print(f"Testing: {strategy.name}")
        print('='*60)
        
        try:
            signals = await strategy.analyze()
            print(f"✅ Generated {len(signals)} signals")
            
            for i, signal in enumerate(signals[:3], 1):  # Show top 3
                print(f"\nSignal #{i}:")
                print(f"  Symbol: {signal['symbol']}")
                print(f"  Side: {signal['side']}")
                print(f"  Score: {signal.get('score', 'N/A')}")
                print(f"  Reason: {signal.get('reason', 'N/A')}")
        except Exception as e:
            print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_strategies())
```

#### Ejecutar

```bash
python test_signals.py
```

Esto te mostrará qué señales genera el bot **sin ejecutar trades**.

---

## 🔍 Checklist de Testing

Antes de usar fondos reales, verifica:

### 1. LunarCrush API ✅

```bash
# Test manual
curl -H "Authorization: Bearer TU_API_KEY" \
  "https://lunarcrush.com/api/v2/coins/list"
```

Deberías ver JSON con lista de coins.

### 2. Dashboard Funciona ✅

- [ ] Dashboard carga en el navegador
- [ ] Métricas se actualizan
- [ ] Controles de estrategias funcionan
- [ ] Exportar reportes funciona

### 3. Bot Inicia Sin Errores ✅

```bash
python main.py --test-mode
```

Logs esperados:
```
✅ Modules imported successfully
✅ All environment variables configured
🤖 Initializing trading bot...
Trading Bot initialized successfully
Starting trading bot loop...
```

### 4. Estrategias Generan Señales ✅

Ejecutar `test_signals.py` y verificar que:
- [ ] Momentum genera 5-10 señales
- [ ] AltRank genera 2-5 señales
- [ ] Reversal genera 1-3 señales

### 5. Hyperliquid Connection (Opcional) ✅

Si quieres probar conexión sin ejecutar trades:

```python
from hyperliquid_client import HyperliquidClient

client = HyperliquidClient()
info = client.get_account_info()
print(f"Balance: {info}")
```

---

## 📊 Interpretar Resultados de Test

### Ejemplo de Output Esperado

```
🧪 Testing Strategy: Momentum Scalping

Scanning 150 coins...
Found 8 potential signals

Signal #1:
  Symbol: ETH
  Side: LONG
  Score: 87.5
  Reason: Social volume +52%, sentiment 68%, price +1.2%
  Entry: $3,245.00
  Target: $3,440.00 (+6%)
  Stop: $3,164.00 (-2.5%)
  
✅ Would execute: BUY 0.5 ETH @ $3,245 (5x leverage)
⚠️ TEST MODE: Trade NOT executed
```

---

## ⚠️ Problemas Comunes

### "LunarCrush API Error 401"

❌ **Problema**: API key inválida  
✅ **Solución**: Verificar que el key esté correcto en Secrets

### "No signals generated"

❌ **Problema**: Mercado muy tranquilo  
✅ **Solución**: Normal, esperar o ajustar thresholds

### "Hyperliquid connection failed"

❌ **Problema**: Private key incorrecto  
✅ **Solución**: Verificar formato del key (debe empezar con 0x)

---

## 🚀 Cuando Estés Listo para Real

Una vez que todo funcione en test mode:

1. **Desactivar test mode**:
   ```json
   { "test_mode": false }
   ```

2. **Depositar fondos** en Hyperliquid

3. **Iniciar bot** con fondos reales

4. **Monitorear** primeras 2-3 horas activamente

5. **Ajustar estrategias** según performance

---

## 💡 Recomendación

**Día 1 (Hoy)**:
- ✅ Configurar todo en Replit
- ✅ Testear en modo test 2-3 horas
- ✅ Verificar que genera señales
- ✅ Familiarizarte con el dashboard

**Día 2 (Mañana - cuando CEO deposite)**:
- ✅ Recibir fondos
- ✅ Hacer bridge a Hyperliquid
- ✅ Activar bot en modo real
- ✅ Monitorear activamente

¿Necesitas ayuda configurando alguna de estas pruebas?
