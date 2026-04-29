// SUGOIAPI — goanime_scraper.go
//
// Scrapa o catálogo completo do AnimeFire (PT-BR) sem limite de títulos.
// Para cada anime encontrado: lista todos os episódios, resolve a URL HLS,
// valida o link e grava em sources/anime_fire.m3u.
//
// Executado pelo GitHub Actions antes do pipeline.py.
// URLs são sessão-based e expiram em ~24h — por isso o refresh é diário.
//
// Uso:
//   go run goanime_scraper.go
//
// Requisitos:
//   go get github.com/alvarorichard/Goanime/pkg/goanime
//   go get github.com/PuerkitoBio/goquery

package main

import (
	"bufio"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"sync"
	"time"

	"github.com/PuerkitoBio/goquery"
	"github.com/alvarorichard/Goanime/pkg/goanime"
	"github.com/alvarorichard/Goanime/pkg/goanime/types"
)

// ─── Configurações ───────────────────────────────────────────────────────────

const (
	BASE_URL       = "https://animefire.plus"
	LISTING_URL    = "https://animefire.plus/animes?page=%d"
	OUTPUT_FILE    = "sources/anime_fire.m3u"
	WORKERS        = 6   // goroutines paralelas (respeita rate limit)
	REQUEST_DELAY  = 400 // ms entre requests por worker
	TIMEOUT_SEC    = 15  // timeout por request
	MAX_PAGES      = 300 // segurança — AnimeFire tem ~200 páginas
	RETRY_ATTEMPTS = 3
)

var (
	httpClient = &http.Client{Timeout: time.Duration(TIMEOUT_SEC) * time.Second}
	reSlug     = regexp.MustCompile(`/animes/([a-z0-9\-]+)`)
)

// ─── Estrutura de resultado ───────────────────────────────────────────────────

type M3UEntry struct {
	Name       string
	Group      string
	Logo       string
	EpLabel    string
	StreamURL  string
}

// ─── Descoberta do catálogo ───────────────────────────────────────────────────

// fetchPage busca uma página do listing e retorna os slugs encontrados.
func fetchPage(page int) ([]string, bool) {
	url := fmt.Sprintf(LISTING_URL, page)

	var body io.Reader
	for attempt := 0; attempt < RETRY_ATTEMPTS; attempt++ {
		resp, err := httpClient.Get(url)
		if err != nil || resp.StatusCode != 200 {
			time.Sleep(time.Duration(attempt+1) * 800 * time.Millisecond)
			continue
		}
		body = resp.Body
		defer resp.Body.Close()
		break
	}
	if body == nil {
		return nil, false
	}

	doc, err := goquery.NewDocumentFromReader(body)
	if err != nil {
		return nil, false
	}

	var slugs []string
	doc.Find("a[href]").Each(func(_ int, s *goquery.Selection) {
		href, exists := s.Attr("href")
		if !exists {
			return
		}
		m := reSlug.FindStringSubmatch(href)
		if len(m) == 2 {
			slug := m[1]
			// Filtra slugs de episódio (contêm traço seguido de numero no fim)
			if !strings.HasSuffix(slug, "-todos-os-episodios") {
				slugs = append(slugs, slug)
			}
		}
	})

	// Página vazia = chegamos no fim
	hasNext := doc.Find("a.page-link[rel='next']").Length() > 0 ||
		doc.Find(".pagination .next").Length() > 0

	return dedupe(slugs), hasNext
}

// crawlCatalog percorre todas as páginas do listing e retorna URLs de anime.
func crawlCatalog() []string {
	fmt.Println("📚 Iniciando varredura do catálogo AnimeFire...")
	var allSlugs []string
	seen := map[string]bool{}

	for page := 1; page <= MAX_PAGES; page++ {
		slugs, hasNext := fetchPage(page)
		added := 0
		for _, s := range slugs {
			if !seen[s] {
				seen[s] = true
				allSlugs = append(allSlugs, s)
				added++
			}
		}
		fmt.Printf("  Página %3d → %3d novos slugs (total: %d)\n", page, added, len(allSlugs))

		if !hasNext || added == 0 {
			fmt.Printf("  ✅ Catálogo completo — %d páginas\n\n", page)
			break
		}
		time.Sleep(300 * time.Millisecond)
	}

	return allSlugs
}

// ─── Resolução de episódios via GoAnime pkg ──────────────────────────────────

// processAnime usa o pkg goanime para resolver episódios e URLs de stream.
func processAnime(client *goanime.Client, slug string) []M3UEntry {
	animeURL := fmt.Sprintf("%s/animes/%s", BASE_URL, slug)

	// Constrói objeto Anime minimal para buscar episódios
	anime := &types.Anime{
		URL:    animeURL,
		Name:   slugToName(slug),
		Source: types.SourceAnimeFire,
	}

	// Busca episódios
	episodes, err := client.GetAnimeEpisodes(anime)
	if err != nil || len(episodes) == 0 {
		return nil
	}

	var entries []M3UEntry
	for _, ep := range episodes {
		// Resolve URL de stream
		streamURL, _, err := client.GetEpisodeStreamURL(anime, ep, &goanime.StreamOptions{
			Quality: "best",
		})
		if err != nil || streamURL == "" {
			continue
		}

		// Valida link (HEAD request rápido)
		if !linkVivo(streamURL) {
			continue
		}

		epLabel := fmt.Sprintf("%s - EP%s", anime.Name, ep.Number)

		entries = append(entries, M3UEntry{
			Name:      anime.Name,
			Group:     anime.Name,
			Logo:      anime.ImageURL,
			EpLabel:   epLabel,
			StreamURL: streamURL,
		})

		time.Sleep(time.Duration(REQUEST_DELAY) * time.Millisecond)
	}

	return entries
}

// ─── Validação de link ────────────────────────────────────────────────────────

func linkVivo(url string) bool {
	req, err := http.NewRequest("HEAD", url, nil)
	if err != nil {
		return false
	}
	req.Header.Set("User-Agent", "Mozilla/5.0 (compatible; SUGOIAPI/1.0)")
	resp, err := httpClient.Do(req)
	if err != nil {
		return false
	}
	defer resp.Body.Close()
	if resp.StatusCode == 405 {
		// Servidor não aceita HEAD — tenta GET parcial
		greq, _ := http.NewRequest("GET", url, nil)
		greq.Header.Set("Range", "bytes=0-0")
		greq.Header.Set("User-Agent", "Mozilla/5.0 (compatible; SUGOIAPI/1.0)")
		gresp, err2 := httpClient.Do(greq)
		if err2 != nil {
			return false
		}
		defer gresp.Body.Close()
		return gresp.StatusCode < 400
	}
	return resp.StatusCode < 400
}

// ─── Escrita da M3U ───────────────────────────────────────────────────────────

func writeM3U(entries []M3UEntry) error {
	if err := os.MkdirAll(filepath.Dir(OUTPUT_FILE), 0755); err != nil {
		return err
	}
	f, err := os.Create(OUTPUT_FILE)
	if err != nil {
		return err
	}
	defer f.Close()

	w := bufio.NewWriter(f)
	w.WriteString("#EXTM3U\n\n")

	for _, e := range entries {
		fmt.Fprintf(w,
			"#EXTINF:-1 tvg-name=%q tvg-logo=%q group-title=%q,%s\n%s\n\n",
			e.EpLabel, e.Logo, e.Group, e.EpLabel, e.StreamURL,
		)
	}

	return w.Flush()
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

func slugToName(slug string) string {
	parts := strings.Split(slug, "-")
	for i, p := range parts {
		if len(p) > 0 {
			parts[i] = strings.ToUpper(p[:1]) + p[1:]
		}
	}
	return strings.Join(parts, " ")
}

func dedupe(s []string) []string {
	seen := map[string]bool{}
	var out []string
	for _, v := range s {
		if !seen[v] {
			seen[v] = true
			out = append(out, v)
		}
	}
	return out
}

// ─── Worker pool ─────────────────────────────────────────────────────────────

func runWorkers(client *goanime.Client, slugs []string) []M3UEntry {
	jobs    := make(chan string, len(slugs))
	results := make(chan []M3UEntry, len(slugs))
	var wg sync.WaitGroup

	// Lança workers
	for w := 0; w < WORKERS; w++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for slug := range jobs {
				entries := processAnime(client, slug)
				if len(entries) > 0 {
					results <- entries
				}
			}
		}()
	}

	// Envia jobs
	for _, slug := range slugs {
		jobs <- slug
	}
	close(jobs)

	// Aguarda workers e fecha canal de resultados
	go func() {
		wg.Wait()
		close(results)
	}()

	// Coleta resultados
	var all []M3UEntry
	processed := 0
	for batch := range results {
		all = append(all, batch...)
		processed++
		if processed%50 == 0 {
			fmt.Printf("  → %d animes processados, %d entradas geradas\n", processed, len(all))
		}
	}
	return all
}

// ─── Main ─────────────────────────────────────────────────────────────────────

func main() {
	start := time.Now()
	fmt.Println("╔══════════════════════════════════════╗")
	fmt.Println("║  SUGOIAPI — GoAnime Scraper          ║")
	fmt.Printf( "║  %s                   ║\n", time.Now().Format("2006-01-02 15:04"))
	fmt.Println("╚══════════════════════════════════════╝")
	fmt.Println()

	// 1. Descobre catálogo completo
	slugs := crawlCatalog()
	fmt.Printf("📦 Total de animes no catálogo: %d\n\n", len(slugs))

	if len(slugs) == 0 {
		fmt.Println("⚠️  Nenhum anime encontrado — verificar conectividade com AnimeFire")
		os.Exit(1)
	}

	// 2. Inicializa cliente GoAnime
	client := goanime.NewClient()
	fmt.Printf("⚡ Processando com %d workers paralelos...\n\n", WORKERS)

	// 3. Processa todos os animes
	entries := runWorkers(client, slugs)

	// 4. Grava M3U
	if err := writeM3U(entries); err != nil {
		fmt.Fprintf(os.Stderr, "❌ Erro ao gravar M3U: %v\n", err)
		os.Exit(1)
	}

	elapsed := time.Since(start).Round(time.Second)
	fmt.Println()
	fmt.Println("─────────────────────────────────────────")
	fmt.Printf("  Animes no catálogo : %d\n", len(slugs))
	fmt.Printf("  Entradas válidas   : %d\n", len(entries))
	fmt.Printf("  Output             : %s\n", OUTPUT_FILE)
	fmt.Printf("  Tempo total        : %s\n", elapsed)
	fmt.Println("─────────────────────────────────────────")
}
