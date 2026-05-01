"""
SUGOIAPI ↔ Put.io integration

Pipeline em duas fases:
  Fase A (enqueue): magnets do Nyaa RSS → enviados ao Put.io
  Fase B (harvest): transfers concluídos → URLs de streaming permanentes

Estado persistido em sources/putio_state.json (commitado no repo).

Uso:
    from putio_integration import PutioOrchestrator

    orch = PutioOrchestrator()

    # Fase A — após parsear o RSS
    orch.enqueue([
        {"magnet": "magnet:?xt=...", "title": "[SubsPlease] Naruto - 01", "category": "Shounen"}
    ])

    # Fase B — em job/step separado
    novos = orch.harvest()

Requer env var PUTIO_TOKEN (OAuth token gerado em app.put.io).
"""

from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import requests

PUTIO_API   = "https://api.put.io/v2"
STATE_PATH  = "sources/putio_state.json"

_MAGNET_HASH_RE = re.compile(
    r"xt=urn:btih:([A-Fa-f0-9]{40}|[A-Za-z2-7]{32})"
)


def info_hash_from_magnet(magnet: str) -> str | None:
    """Extrai e normaliza o info_hash de um magnet link."""
    m = _MAGNET_HASH_RE.search(magnet or "")
    return m.group(1).lower() if m else None


# ──────────────────────────────────────────────────────────────────────────
# Cliente Put.io
# ──────────────────────────────────────────────────────────────────────────

class PutioClient:
    """Wrapper minimalista da REST API do Put.io."""

    def __init__(self, token: str | None = None, timeout: int = 30):
        self.token = token or os.environ.get("PUTIO_TOKEN")
        if not self.token:
            raise RuntimeError("PUTIO_TOKEN não definido (env var ou parâmetro).")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.token}",
            "Accept"       : "application/json",
        })

    # ── Transfers ────────────────────────────────────────────────────────
    def add_transfer(self, magnet: str) -> dict:
        """POST /transfers/add — envia magnet para download."""
        r = self.session.post(
            f"{PUTIO_API}/transfers/add",
            data={"url": magnet},
            timeout=self.timeout,
        )
        r.raise_for_status()
        return r.json().get("transfer", {})

    def list_transfers(self) -> list[dict]:
        """GET /transfers/list — lista todos os transfers."""
        r = self.session.get(f"{PUTIO_API}/transfers/list", timeout=self.timeout)
        r.raise_for_status()
        return r.json().get("transfers", [])

    # ── Files ────────────────────────────────────────────────────────────
    def file_info(self, file_id: int) -> dict:
        r = self.session.get(f"{PUTIO_API}/files/{file_id}", timeout=self.timeout)
        r.raise_for_status()
        return r.json().get("file", {})

    def list_folder(self, parent_id: int) -> list[dict]:
        r = self.session.get(
            f"{PUTIO_API}/files/list",
            params={"parent_id": parent_id},
            timeout=self.timeout,
        )
        r.raise_for_status()
        return r.json().get("files", [])

    def stream_url(self, file_id: int) -> str:
        """
        URL de streaming direta do arquivo.
        Token incluído na URL — funciona em qualquer player IPTV.
        """
        return f"{PUTIO_API}/files/{file_id}/stream?oauth_token={self.token}"


# ──────────────────────────────────────────────────────────────────────────
# Orquestrador de estado
# ──────────────────────────────────────────────────────────────────────────

class PutioOrchestrator:
    """
    Mantém um JSON com o estado de cada item enviado ao Put.io.

    Estados possíveis:
      pending    — magnet enviado, transfer ainda não completou
      ready      — transfer completou, stream_url disponível
      error      — falhou de forma persistente
    """

    def __init__(self, state_path: str = STATE_PATH, client: PutioClient | None = None):
        self.state_path = Path(state_path)
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.client = client or PutioClient()
        self.state  = self._load()

    # ── Persistência ─────────────────────────────────────────────────────
    def _load(self) -> dict:
        if self.state_path.exists():
            try:
                content = self.state_path.read_text(encoding="utf-8").strip()
                if content:
                    return json.loads(content)
            except (json.JSONDecodeError, OSError):
                pass
        return {"items": {}, "last_run": None}

    def _save(self):
        self.state["last_run"] = datetime.now(timezone.utc).isoformat()
        self.state_path.write_text(
            json.dumps(self.state, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    # ── Fase A: enqueue ──────────────────────────────────────────────────
    def enqueue(self, items: Iterable[dict]) -> int:
        """
        items: lista de dicts com chaves {magnet, title, category, [logo]}

        Retorna número de novos itens efetivamente enviados ao Put.io.
        Itens já enviados (info_hash conhecido) são ignorados.
        """
        novos = 0
        for item in items:
            magnet = item.get("magnet", "")
            ih     = info_hash_from_magnet(magnet)
            if not ih:
                print(f"  ⚠️  magnet inválido em '{item.get('title', '')[:50]}'")
                continue

            if ih in self.state["items"]:
                continue   # já enviado anteriormente

            try:
                transfer = self.client.add_transfer(magnet)
                self.state["items"][ih] = {
                    "title"      : item.get("title", ""),
                    "category"   : item.get("category", "Geral"),
                    "logo"       : item.get("logo", ""),
                    "transfer_id": transfer.get("id"),
                    "file_id"    : None,
                    "stream_url" : None,
                    "status"     : "pending",
                    "created_at" : datetime.now(timezone.utc).isoformat(),
                }
                novos += 1
                print(f"  ✅ enfileirado: {item.get('title', '')[:60]}")
                time.sleep(0.5)   # rate limit suave
            except requests.HTTPError as e:
                self.state["items"][ih] = {
                    "title" : item.get("title", ""),
                    "status": "error",
                    "error" : str(e),
                }
                print(f"  ❌ falha: {e}")

        self._save()
        return novos

    # ── Fase B: harvest ──────────────────────────────────────────────────
    def harvest(self) -> list[dict]:
        """
        Verifica quais transfers completaram, resolve file_id (recursivamente
        em pastas se necessário) e gera stream_url.

        Retorna lista de itens que mudaram para 'ready' nesta execução.
        """
        try:
            transfers = self.client.list_transfers()
        except requests.HTTPError as e:
            print(f"  ❌ erro ao listar transfers: {e}")
            return []

        # Index por transfer_id
        by_tid = {t.get("id"): t for t in transfers}
        novos_ready = []

        for ih, item in self.state["items"].items():
            if item.get("status") != "pending":
                continue

            tid = item.get("transfer_id")
            t   = by_tid.get(tid)
            if not t:
                continue

            status = t.get("status", "").upper()
            if status != "COMPLETED":
                continue

            # Transfer completou — resolver file_id
            file_id = t.get("file_id")
            if not file_id:
                continue

            # Se for pasta, pega o primeiro vídeo dentro
            try:
                info = self.client.file_info(file_id)
                if info.get("file_type") == "FOLDER":
                    children  = self.client.list_folder(file_id)
                    video     = next(
                        (c for c in children if c.get("file_type") == "VIDEO"),
                        None
                    )
                    if not video:
                        continue
                    file_id = video["id"]
            except requests.HTTPError:
                continue

            stream_url        = self.client.stream_url(file_id)
            item["file_id"]   = file_id
            item["stream_url"]= stream_url
            item["status"]    = "ready"
            item["ready_at"]  = datetime.now(timezone.utc).isoformat()

            novos_ready.append(item)
            print(f"  ✅ pronto: {item.get('title','')[:60]}")

        self._save()
        return novos_ready

    # ── Exporta itens prontos como entradas M3U ─────────────────────────
    def ready_items(self) -> list[dict]:
        """Retorna todos os itens com status 'ready'."""
        return [
            item for item in self.state["items"].values()
            if item.get("status") == "ready" and item.get("stream_url")
        ]

    def export_m3u(self, output_path: str = "sources/putio_entries.m3u"):
        """Gera arquivo M3U com todos os itens prontos."""
        items = self.ready_items()
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n\n")
            for item in items:
                title = item.get("title", "Anime")
                cat   = item.get("category", "Geral")
                logo  = item.get("logo", "")
                url   = item["stream_url"]
                f.write(
                    f'#EXTINF:-1 tvg-name="{title}" tvg-logo="{logo}" '
                    f'group-title="{cat}",{title}\n'
                    f'{url}\n\n'
                )
        print(f"  📝 M3U gerada: {output_path} ({len(items)} entradas)")
        return output_path