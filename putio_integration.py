"""
SUGOIAPI - putio_integration.py

Pipeline em duas fases:
  Fase A (enqueue): magnets do Nyaa RSS enviados ao Put.io
  Fase B (harvest): transfers concluidos gerando URLs de streaming

Estado persistido em sources/putio_state.json (commitado no repo).
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

PUTIO_API  = "https://api.put.io/v2"
STATE_PATH = "sources/putio_state.json"

_MAGNET_HASH_RE = re.compile(
    r"xt=urn:btih:([A-Fa-f0-9]{40}|[A-Za-z2-7]{32})"
)

VIDEO_EXTENSIONS = {".mkv", ".mp4", ".avi", ".mov", ".wmv", ".flv", ".m4v"}


def info_hash_from_magnet(magnet: str) -> str | None:
    m = _MAGNET_HASH_RE.search(magnet or "")
    return m.group(1).lower() if m else None


def is_video_file(filename: str) -> bool:
    return Path(filename).suffix.lower() in VIDEO_EXTENSIONS


# ======================================================================
# Cliente Put.io
# ======================================================================

class PutioClient:

    def __init__(self, token: str | None = None, timeout: int = 30):
        self.token = token or os.environ.get("PUTIO_TOKEN")
        if not self.token:
            raise RuntimeError("PUTIO_TOKEN nao definido.")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.token}",
            "Accept"       : "application/json",
        })

    def add_transfer(self, magnet: str) -> dict:
        r = self.session.post(
            f"{PUTIO_API}/transfers/add",
            data={"url": magnet},
            timeout=self.timeout,
        )
        r.raise_for_status()
        return r.json().get("transfer", {})

    def list_transfers(self) -> list[dict]:
        r = self.session.get(f"{PUTIO_API}/transfers/list", timeout=self.timeout)
        r.raise_for_status()
        return r.json().get("transfers", [])

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
        return f"{PUTIO_API}/files/{file_id}/stream?oauth_token={self.token}"


# ======================================================================
# Orquestrador de estado
# ======================================================================

class PutioOrchestrator:

    def __init__(self, state_path: str = STATE_PATH, client: PutioClient | None = None):
        self.state_path = Path(state_path)
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.client = client or PutioClient()
        self.state  = self._load()

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

    # ── Fase A: enqueue ─────────────────────────────────────────────────
    def enqueue(self, items: Iterable[dict]) -> int:
        novos = 0
        for item in items:
            magnet = item.get("magnet", "")
            ih     = info_hash_from_magnet(magnet)
            if not ih:
                print(f"  WARN magnet invalido em '{item.get('title', '')[:50]}'")
                continue

            if ih in self.state["items"]:
                continue

            try:
                transfer = self.client.add_transfer(magnet)
                self.state["items"][ih] = {
                    "title"      : item.get("title", ""),
                    "category"   : item.get("category", "Geral"),
                    "logo"       : item.get("logo", ""),
                    "transfer_id": transfer.get("id"),
                    "file_id"    : None,
                    "stream_urls": [],       # lista de todos os videos do torrent
                    "status"     : "pending",
                    "created_at" : datetime.now(timezone.utc).isoformat(),
                }
                novos += 1
                print(f"  OK enfileirado: {item.get('title', '')[:60]}")
                time.sleep(0.5)
            except requests.HTTPError as e:
                self.state["items"][ih] = {
                    "title" : item.get("title", ""),
                    "status": "error",
                    "error" : str(e),
                }
                print(f"  FAIL: {e}")

        self._save()
        return novos

    # ── Fase B: harvest ─────────────────────────────────────────────────
    def _resolver_videos(self, file_id: int) -> list[int]:
        """
        Retorna lista de file_ids de todos os videos de um transfer.
        Recursivo para pastas com sub-pastas (ex: season packs).
        """
        try:
            info = self.client.file_info(file_id)
        except requests.HTTPError:
            return []

        if info.get("file_type") == "VIDEO":
            if is_video_file(info.get("name", "")):
                return [file_id]
            return []

        if info.get("file_type") == "FOLDER":
            video_ids = []
            try:
                children = self.client.list_folder(file_id)
            except requests.HTTPError:
                return []

            for child in sorted(children, key=lambda c: c.get("name", "")):
                if child.get("file_type") == "VIDEO" and is_video_file(child.get("name", "")):
                    video_ids.append(child["id"])
                elif child.get("file_type") == "FOLDER":
                    # sub-pasta (ex: Season 01, Season 02)
                    video_ids.extend(self._resolver_videos(child["id"]))

            return video_ids

        return []

    def harvest(self) -> list[dict]:
        try:
            transfers = self.client.list_transfers()
        except requests.HTTPError as e:
            print(f"  FAIL erro ao listar transfers: {e}")
            return []

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

            file_id = t.get("file_id")
            if not file_id:
                continue

            # Resolve TODOS os videos do transfer (nao so o primeiro)
            video_ids = self._resolver_videos(file_id)
            if not video_ids:
                continue

            stream_urls = [self.client.stream_url(vid) for vid in video_ids]

            item["file_id"]    = file_id
            item["stream_urls"] = stream_urls
            # Compatibilidade retroativa: stream_url = primeiro video
            item["stream_url"] = stream_urls[0] if stream_urls else None
            item["status"]     = "ready"
            item["ready_at"]   = datetime.now(timezone.utc).isoformat()

            novos_ready.append(item)
            print(f"  OK pronto: {item.get('title','')[:55]} ({len(video_ids)} video(s))")

        self._save()
        return novos_ready

    # ── Export M3U ──────────────────────────────────────────────────────
    def ready_items(self) -> list[dict]:
        return [
            item for item in self.state["items"].values()
            if item.get("status") == "ready"
            and (item.get("stream_urls") or item.get("stream_url"))
        ]

    def export_m3u(self, output_path: str = "sources/putio_entries.m3u"):
        """
        Gera M3U com todos os itens prontos.
        Torrents com multiplos videos geram multiplas entradas.
        """
        items = self.ready_items()
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        total = 0

        with open(output_path, "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n\n")
            for item in items:
                title = item.get("title", "Anime")
                cat   = item.get("category", "Geral")
                logo  = item.get("logo", "")

                # Suporte a lista de URLs (novos) e URL unica (legado)
                urls = item.get("stream_urls") or []
                if not urls and item.get("stream_url"):
                    urls = [item["stream_url"]]

                for url in urls:
                    f.write(
                        f'#EXTINF:-1 tvg-name="{title}" tvg-logo="{logo}" '
                        f'group-title="{cat}",{title}\n'
                        f'{url}\n\n'
                    )
                    total += 1

        print(f"  M3U gerada: {output_path} ({total} entradas de {len(items)} torrents)")
        return output_path

    # ── Modo full scan: varre TODOS os arquivos do Put.io ────────────────
    def full_scan_export(self, output_path: str = "sources/putio_entries.m3u",
                         root_id: int = 0):
        """
        Varre recursivamente TODA a estrutura de arquivos do Put.io
        e gera M3U com todos os videos encontrados.

        Diferente de export_m3u(), nao depende do state. Funciona para
        arquivos baixados fora do pipeline ou apos perda de state.

        root_id=0 = pasta raiz do Put.io
        """
        print(f"  Full scan iniciando em pasta {root_id}...")
        videos = self._scan_recursivo(root_id)
        print(f"  Encontrados {len(videos)} videos no Put.io")

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n\n")
            for video in videos:
                title = video["name"]
                url   = self.client.stream_url(video["id"])
                # Sem categoria - pipeline.py classifica depois
                f.write(
                    f'#EXTINF:-1 tvg-name="{title}" tvg-logo="" '
                    f'group-title="Put.io",{title}\n'
                    f'{url}\n\n'
                )

        print(f"  M3U full scan: {output_path} ({len(videos)} entradas)")
        return output_path

    def _scan_recursivo(self, parent_id: int, depth: int = 0, max_depth: int = 5) -> list[dict]:
        """
        Lista recursivamente todos os videos a partir de parent_id.
        max_depth previne recursao infinita.
        """
        if depth > max_depth:
            return []

        try:
            children = self.client.list_folder(parent_id)
        except requests.HTTPError as e:
            print(f"    WARN erro listando pasta {parent_id}: {e}")
            return []

        videos = []
        for child in children:
            ftype = child.get("file_type")
            name  = child.get("name", "")

            if ftype == "VIDEO" and is_video_file(name):
                videos.append({
                    "id"  : child["id"],
                    "name": name,
                    "size": child.get("size", 0),
                })
            elif ftype == "FOLDER":
                # Recurse na sub-pasta
                videos.extend(self._scan_recursivo(child["id"], depth + 1, max_depth))

        return videos