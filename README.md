# Scripta OJS Bridge

Bridge seguro para conectar GPT Actions con la API REST de OJS de Scripta Scientia.

## Nombre recomendado del repositorio

`scripta-ojs-bridge`

## Nombre recomendado del servicio en Render

`scripta-ojs-bridge`

## Variables de entorno en Render

Configurar en Render:

```txt
OJS_BASE_URL=https://scriptascientia.com/sasc/api/v1
OJS_API_TOKEN=TU_LLAVE_API_NUEVA_DE_OJS
BRIDGE_TOKEN=UN_TOKEN_PRIVADO_LARGO
```

No subir nunca `.env` ni tokens reales al repositorio.

## Comando de inicio

```bash
uvicorn app:app --host 0.0.0.0 --port $PORT
```

## Pruebas

Health check:

```bash
curl -i https://TU-SERVICIO.onrender.com/health
```

Listar números:

```bash
curl -i \
-H "Authorization: Bearer TU_BRIDGE_TOKEN" \
https://TU-SERVICIO.onrender.com/issues
```

Listar envíos:

```bash
curl -i \
-H "Authorization: Bearer TU_BRIDGE_TOKEN" \
https://TU-SERVICIO.onrender.com/submissions
```

Obtener envío:

```bash
curl -i \
-H "Authorization: Bearer TU_BRIDGE_TOKEN" \
https://TU-SERVICIO.onrender.com/submissions/ID_DEL_ENVIO
```

## Endpoints disponibles

- `GET /health`
- `GET /issues`
- `GET /issues/{issue_id}`
- `GET /submissions`
- `GET /submissions/{submission_id}`
- `GET /submissions/{submission_id}/publications`
- `GET /submissions/{submission_id}/participants`
- `GET /submissions/{submission_id}/files`
- `GET /users`
- `GET /users/{user_id}`
