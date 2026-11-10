# EcoRuta 2.0

Plataforma web para conectar generadores de residuos aprovechables con recicladores en Montería, Córdoba.

## Ejecutar localmente
1. `python -m venv .venv`
2. Activar el entorno virtual.
3. `pip install -r requirements.txt`
4. `python app.py`
5. Abrir `http://127.0.0.1:5000`

## Publicación
Diseñado para Render con `render.yaml`. Configura una variable `SECRET_KEY` segura en producción.

## Nota
El mapa muestra puntos de referencia en Montería y los anuncios publicados. Para geolocalización exacta, se debe incorporar dirección/coordenadas verificadas; no se inventan ubicaciones GPS.
