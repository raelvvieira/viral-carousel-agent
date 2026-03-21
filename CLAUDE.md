# viral-carousel-agent — Memória do Projeto

## Scraping de Instagram (agent1_viral_scraper.py)

Actor principal: `apify/instagram-post-scraper` ($1.50/1K posts — mais barato disponível)

Parâmetros de entrada:
- `username`: array de usernames (ex: `["pedrosobral"]`)
- `resultsLimit`: limite de posts por perfil (ex: `10`)
- `onlyPostsNewerThan`: filtro de data nativo (ex: `"5 days"`)
- `skipPinnedPosts`: `True` para evitar posts fixados antigos

Campos de saída relevantes:
- Views: `videoPlayCount` ou `videoViewCount` (usar fallback para ambos)
- Likes: `likesCount`
- Comentários: `commentsCount`
- Shares: `sharesCount`
- Saves: `savesCount`
- Usuário: `ownerUsername`
- Seguidores: `ownerFollowersCount`
- Legenda: `caption`
- Timestamp: `timestamp`
- Tipo: `type` / `productType` (video/reel/sidecar)
- Código curto: `shortCode`

Custo estimado: 10 perfis × 10 posts = ~$0.15 por run completo
