# multiverso-api — API Back-End

API REST em **Python (Flask)** responsável por persistir os favoritos de
personagens de Rick and Morty e por uma regra de negócio que busca os
episódios de cada um. É o componente back-end do MVP de componentização,
consumido pela [Interface](../multiverso-frontend).

Não fala com nenhuma API externa na maior parte das rotas: a consulta ao
Rick and Morty API para busca de personagem é feita pela Interface (no
navegador). A exceção é a rota de episódios, que é a regra de negócio
descrita abaixo.

## Autenticação

As rotas de escrita (`POST`, `PUT`, `DELETE` em `/api/favoritos`) exigem
o cabeçalho `X-API-Key` com o valor `multiverso-mvp-2026` (chave de
demonstração, definida em `app.py`). As rotas de leitura (`GET`)
continuam públicas. Sem a chave correta, a API responde `401`.

```bash
curl -X POST http://localhost:5000/api/favoritos \
  -H "Content-Type: application/json" \
  -H "X-API-Key: multiverso-mvp-2026" \
  -d '{"character_id":1,"character_name":"Rick Sanchez","status":"Alive","species":"Human"}'
```

## Rotas

| Método | Rota                            | Descrição                                                                    |
| ------ | ------------------------------- | ---------------------------------------------------------------------------- |
| GET    | `/api/favoritos`                | Lista favoritos (paginação, filtro por status/espécie, ordenação)            |
| GET    | `/api/favoritos/<id>`           | Detalhe de um favorito                                                       |
| GET    | `/api/favoritos/estatisticas`   | Contagem de favoritos por status (para o gráfico da interface)               |
| POST   | `/api/favoritos` 🔒             | Adiciona um personagem aos favoritos                                         |
| PUT    | `/api/favoritos/<id>` 🔒        | Atualiza as notas de um favorito                                             |
| DELETE | `/api/favoritos/<id>` 🔒        | Remove um favorito                                                           |
| GET    | `/api/favoritos/<id>/episodios` | **Regra de negócio**: busca os episódios do personagem na Rick and Morty API |
| GET    | `/api/health`                   | Healthcheck                                                                  |

🔒 = exige o cabeçalho `X-API-Key`.

### Parâmetros de `GET /api/favoritos`

- `page` (padrão `1`), `per_page` (padrão `6`, máx. `50`)
- `status`: `Alive`, `Dead` ou `unknown`
- `species`: busca parcial (ex: `Human`)
- `sort`: `criado_em` (padrão), `character_name` ou `status`

### Corpo esperado em `POST /api/favoritos`

```json
{
  "character_id": 1,
  "character_name": "Rick Sanchez",
  "status": "Alive",
  "species": "Human",
  "image_url": "https://rickandmortyapi.com/api/character/avatar/1.jpeg",
  "notas": ""
}
```

### Regra de negócio: `GET /api/favoritos/<id>/episodios`

Dado um favorito salvo, a API busca o personagem na Rick and Morty API
(`GET /character/{character_id}`), extrai a lista de episódios em que
ele aparece e faz uma segunda chamada (`GET /episode/{ids}`) para trazer
nome, código e data de exibição de cada episódio.

## Persistência

SQLite (`multiverso.db`), criado automaticamente na primeira execução —
sem passo manual de setup.

## Como rodar

### Docker

```bash
docker build -t multiverso-api .
docker run -p 5000:5000 multiverso-api
```

### Localmente, sem Docker

```bash
pip install -r requirements.txt
python app.py
```

A API sobe em `http://localhost:5000`.

## Estrutura

```
multiverso-api/
├── app.py
├── requirements.txt
└── Dockerfile
```
