Hoje, os providers identificados no código são estes:

1. Anime Fire
Arquivo: src/Providers/AnimeFireProvider.php
Nome retornado: Anime Fire
Slug retornado: anime-fire
has_ads: false
is_embed: false
Base URL definida no provider: https://animefire.plus/video/
O endpoint de busca do episódio é montado como BASE_URL + slug + "/{episodio}".  ￼

2. Animes Online CC
Arquivo: src/Providers/AnimesOnlineCCProvider.php
Nome retornado: Animes Online CC
Slug retornado: animes-online-cc
has_ads: false
is_embed: true
Base URL definida no provider: https://animesonlinecc.to/episodio/
O endpoint de busca do episódio é montado como baseUrl + slug + "-episodio-" + episodio.  ￼

3. Superflix
Arquivo: src/Providers/SuperflixProvider.php
Nome retornado: Superflix
Slug retornado: superflix
has_ads: true
is_embed: true
Base URL definida no provider: https://superflixapi.top/serie/
O endpoint de busca do episódio é montado como baseUrl + slug + "/{season}/{episode}".  ￼

A resposta final da API é montada em ResponseSupport::providerData(), que devolve exatamente esta estrutura por provider: name, slug, has_ads, is_embed e episodes. Então, ao consultar um episódio, é isso que você deve esperar no JSON de retorno.  ￼

Em resumo, o mapa atual do seu diretório é este:
	•	src/Kernel.php: quais providers estão realmente ativos
	•	src/Providers/AnimeFireProvider.php
	•	src/Providers/AnimesOnlineCCProvider.php
	•	src/Providers/SuperflixProvider.php
	•	src/Support/ResponseSupport.php: como eles aparecem no retorno da API  