# Aparthotel Paros — Sistema de gestión

Sistema de gestión para un aparthotel de 100 departamentos (10 pisos × 10 unidades):
check-in y check-out, ocupación, facturación e ingresos.

El proyecto ofrece **tres interfaces** sobre la misma lógica de negocio:

| Interfaz | Archivo | Almacenamiento |
|---|---|---|
| Consola (menú de texto) | `main.py` | `data.json` |
| Escritorio (Tkinter) | `app_gui.py` | `data.json` |
| Dashboard web | `index.html` + `api.py` | Supabase |

Las dos primeras comparten la clase `HotelManager` y el mismo archivo local, así que
los cambios hechos en una se ven en la otra al recargar. El dashboard web es
independiente: reimplementa la lógica en JavaScript y guarda su estado en la nube.

## Requisitos

- Python 3.8 o superior.
- Para las interfaces de consola y escritorio: **nada más**. Sólo usan la biblioteca
  estándar (Tkinter viene incluido con CPython en Windows).
- Para el dashboard web: las dependencias de `requirements.txt`.

## Instalación

```bash
git clone https://github.com/04n1thn1/index.git
cd index
```

Las interfaces de consola y escritorio ya funcionan:

```bash
python main.py      # menú de texto
python app_gui.py   # ventana de escritorio
```

En Windows, `pythonw.exe app_gui.py` la abre sin ventana de consola detrás.

## Dashboard web

Requiere una cuenta de [Supabase](https://supabase.com) con una tabla `hotel_data`
que tenga una columna `id` (entero) y una columna `data` (`jsonb`).

```bash
python -m venv venv
venv\Scripts\activate          # en Linux/macOS: source venv/bin/activate
pip install -r requirements.txt
```

Configura las cuatro variables de entorno — la aplicación **no arranca** si falta
alguna, e indica cuál en el mensaje de error:

| Variable | Descripción |
|---|---|
| `SUPABASE_URL` | URL del proyecto de Supabase |
| `SUPABASE_KEY` | Clave de API con permiso de lectura/escritura sobre `hotel_data` |
| `APP_USER` | Usuario para acceder al dashboard |
| `APP_PASSWORD` | Contraseña para acceder al dashboard |

> **Las credenciales deben ser ASCII.** La autenticación HTTP Basic no admite tildes
> ni `ñ` de forma confiable, así que la aplicación las rechaza al arrancar en vez de
> fallar con un error 401 sin explicación.

Luego:

```bash
uvicorn api:app --reload
```

El dashboard queda en `http://127.0.0.1:8000` y pedirá usuario y contraseña.

Abrir `index.html` directamente desde el disco **no** muestra datos reales: todas las
peticiones fallan y la página se llena con datos de ejemplo. Hay que pasar siempre
por el servidor.

### Despliegue

Pensado para [Render](https://render.com) u otro servicio equivalente. Configura las
cuatro variables de entorno en el panel y usa este comando de arranque:

```
uvicorn api:app --host 0.0.0.0 --port $PORT
```

`GET /health` responde sin autenticación y sin datos, para el monitoreo del servicio.

## Estructura

```
models.py          Dataclass Room, tipos de departamento y helpers de formato
main.py            HotelManager (lógica de negocio) + interfaz de consola
app_gui.py         Interfaz gráfica Tkinter
index.html         Dashboard web (HTML/CSS/JS en un solo archivo)
api.py             Backend FastAPI que sirve el dashboard y habla con Supabase
requirements.txt   Dependencias (sólo del backend web)
data.json          Estado local, se genera solo la primera vez
```

Los tipos de departamento son `standard` (2 dormitorios), `suite` (3) y `vip` (4),
con tarifas por noche distintas. Los montos están en pesos chilenos.

## Formato de datos

Ambos backends usan claves camelCase (`checkinDate`, `checkoutDate`) y fechas ISO
`YYYY-MM-DD`. Los ingresos se acumulan sólo al hacer el check-out.

Ten en cuenta que los dos almacenamientos **divergen en una clave**: el local guarda
`guestHistory` (historial por huésped) y el web guarda `operationalTasks` (tareas
operativas). Ninguno de los dos entiende la clave del otro, así que copiar un
respaldo de uno a otro descarta esa parte silenciosamente.

## Licencia

[MIT](LICENSE)
