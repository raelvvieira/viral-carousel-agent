# viral-carousel-agent — Memória do Projeto

## ⚠️ ETAPA ESTABILIZADA — NÃO MODIFICAR

As funções de busca de conteúdo viral em `agent1_viral_scraper.py` estão em produção e
funcionando corretamente. **Não altere** as seguintes funções sem autorização explícita:

- `_scrape_perfil` — chama apify/instagram-post-scraper com os parâmetros corretos
- `scrape_base_perfis` — paraleliza perfis e aciona progress_cb
- `calcular_engajamento` / `calcular_engajamento_pct` — lógica de ranking
- `formatar_ranking` — formatação do output para o Telegram

Motivo: configuração validada em produção (março/2026). Qualquer mudança nessas funções
requer teste end-to-end completo e aprovação explícita do usuário.

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
