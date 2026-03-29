# viral-carousel-agent — Memória do Projeto

## ⚠️ AGENTE 1 — COMPLETAMENTE ESTABILIZADO — NÃO MODIFICAR

`agent1_viral_scraper.py` está 100% funcional em produção para todos os formatos
(post estático, reel, carrossel). **Não edite nenhuma função deste arquivo** sem
autorização explícita do usuário.

Funções protegidas:
- `_scrape_perfil` — chama apify/instagram-post-scraper com os parâmetros corretos
- `scrape_base_perfis` — paraleliza perfis e aciona progress_cb
- `calcular_engajamento` / `calcular_engajamento_pct` — lógica de ranking
- `formatar_ranking` — formatação do output para o Telegram
- `extrair_copy_reel` — transcrição via invideoiq/video-transcriber (URL `/p/shortCode/`, timeout 300s)
- `extrair_copy_carrossel` — OCR via Google Vision API
- `extrair_copy_post_estatico` — OCR via Google Vision API

Validado em produção: março/2026. **Próximos trabalhos são exclusivamente em agent2_research.py e além.**

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
