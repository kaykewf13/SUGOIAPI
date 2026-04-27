"""
SUGOIAPI ↔ Put.io integration.

Two-phase pipeline:
  Phase A (enqueue): magnets vindos do Nyaa RSS são enviados ao Put.io.
  Phase B (harvest): transfers concluídos viram URLs de streaming
                     que podem ser injetadas no playlist_premium.m3u.

Estado persistido em putio_state.json (commitado no repo).

Uso típico:
    from putio_integration import PutioOrchestrator

    orch = PutioOrchestrator(state_path="putio_state.json")

    # Fase A — depois de parsear o RSS do Nyaa
    orch.enqueue([
        {"magnet": "magnet:?xt=...", "title": "[SubsPlease] X - 01", "category": "Anime"}
    ])

    # Fase B — em job separado / step seguinte
    novos = orch.harvest()
    # novos: [{"title": ..., "category": ..., "stream_url": ...}]

Requer env var PUTIO_TOKEN (OAuth token gerado em app.put.io).
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import requests

PUTIO_API = "https://api.put.io/v2"

_MAGNET_HASH_RE = re.compile(
    r"xt=urn:btih:([A-Fa-f0-9]{40}|[A-Za-z2-7]{32})"
)


def info_hash_from_magnet(magnet: str) -> str | None:
    """Extrai o info_hash de um magnet link, normalizado em lowercase."""
    m = _MAGNET_HASH_RE.search(magnet or "")
    return m.group(1).lower() if m else None


# --------------------------------------------------------------------------- #
# API client                                                                   #
# --------------------------------------------------------------------------- #

class PutioClient:
    """Wrapper minimalista da API REST do Put.io."""

    def __init__(self, token: str | None = None, timeout: int = 30):
        self.token = token or os.environ.get("PUTIO_TOKEN")
        if not self.token:
            raise RuntimeError("PUTIO_TOKEN não definido (env var ou parâmetro).")
        self.session = requests.Session()
        self.session.headers["Authorization"] = f"Bearer {self.token}"
        self.timeout = timeout

    # transfers ----------------------------------------------------------- #

    def add_magnet(self, magnet: str, parent_id: int = 0) -> dict:
        r = self.session.post(
            f"{PUTIO_API}/transfers/add",
            data={"url": magnet, "save_parent_id": parent_id},
            timeout=self.timeout,
        )
        r.raise_for_status()
        return r.json()["transfer"]

    def get_transfer(self, transfer_id: int) -> dict:
        r = self.session.get(
            f"{PUTIO_API}/transfers/{transfer_id}",
            timeout=self.timeout,
        )
        r.raise_for_status()
        return r.json()["transfer"]

    def list_transfers(self) -> list[dict]:
        r = self.session.get(
            f"{PUTIO_API}/transfers/list",
            timeout=self.timeout,
        )
        r.raise_for_status()
        return r.json()["transfers"]

    def cancel_transfer(self, transfer_id: int) -> None:
        r = self.session.post(
            f"{PUTIO_API}/transfers/cancel",
            data={"transfer_ids": str(transfer_id)},
            timeout=self.timeout,
        )
        r.raise_for_status()

    # files --------------------------------------------------------------- #

    def list_children(self, parent_id: int) -> list[dict]:
        r = self.session.get(
            f"{PUTIO_API}/files/list",
            params={"parent_id": parent_id},
            timeout=self.timeout,
        )
        r.raise_for_status()
        return r.json()["files"]

    def get_stream_url(self, file_id: int) -> str:
        """
        Retorna URL temporária de download/streaming do arquivo.
        Para URL permanente (que segue redirect), usar /files/{id}/stream.
        """
        r = self.session.get(
            f"{PUTIO_API}/files/{file_id}/url",
            timeout=self.timeout,
        )
        r.raise_for_status()
        return r.json()["url"]

    def delete_file(self, file_id: int) -> None:
        r = self.session.post(
            f"{PUTIO_API}/files/delete",
            data={"file_ids": str(file_id)},
            timeout=self.timeout,
        )
        r.raise_for_status()


# --------------------------------------------------------------------------- #
# State persistence                                                            #
# --------------------------------------------------------------------------- #

class PutioState:
    """
    Estado em JSON, indexado por info_hash. Estrutura:

        {
          "transfers": {
            "<info_hash>": {
              "transfer_id": int,
              "file_id": int | null,
              "status": "pending" | "done" | "error",
              "title": str,
              "category": str,
              "stream_url": str | null,
              "percent": float | null,
              "error": str | null,
              "first_seen": iso8601,
              "updated_at": iso8601
            }
          }
        }
    """

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._data: dict = {"transfers": {}}
        if self.path.exists():
            try:
                self._data = json.loads(self.path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                # arquivo corrompido — começa do zero, mas não apaga o original
                self._data = {"transfers": {}}
        self._data.setdefault("transfers", {})

    def has(self, info_hash: str) -> bool:
        return info_hash in self._data["transfers"]

    def get(self, info_hash: str) -> dict | None:
        return self._data["transfers"].get(info_hash)

    def upsert(self, info_hash: str, **fields) -> None:
        rec = self._data["transfers"].setdefault(info_hash, {})
        rec.update({k: v for k, v in fields.items() if v is not None})
        rec.setdefault("first_seen", datetime.now(timezone.utc).isoformat())
        rec["updated_at"] = datetime.now(timezone.utc).isoformat()

    def all_pending(self) -> list[tuple[str, dict]]:
        return [
            (h, r)
            for h, r in self._data["transfers"].items()
            if r.get("status") not in ("done", "error")
        ]

    def all_done(self) -> list[tuple[str, dict]]:
        return [
            (h, r)
            for h, r in self._data["transfers"].items()
            if r.get("status") == "done" and r.get("stream_url")
        ]

    def save(self) -> None:
        self.path.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )


# --------------------------------------------------------------------------- #
# Orchestrator                                                                 #
# --------------------------------------------------------------------------- #

# Mapeamento de status do Put.io para o estado interno.
_PUTIO_DONE_STATUSES = {"COMPLETED", "SEEDING"}
_PUTIO_ERROR_STATUSES = {"ERROR"}


class PutioOrchestrator:
    def __init__(
        self,
        state_path: str | Path = "putio_state.json",
        client: PutioClient | None = None,
        parent_folder_id: int = 0,
    ):
        self.client = client or PutioClient()
        self.state = PutioState(state_path)
        self.parent_folder_id = parent_folder_id

    # ----- Fase A ----- #

    def enqueue(self, items: Iterable[dict]) -> int:
        """
        items: iter de {magnet, title, category}.
        Idempotente: ignora info_hash já presente no state.
        Retorna a quantidade de novos transfers enviados.
        """
        added = 0
        for it in items:
            magnet = it.get("magnet")
            ih = info_hash_from_magnet(magnet) if magnet else None
            if not ih or self.state.has(ih):
                continue

            try:
                t = self.client.add_magnet(
                    magnet, parent_id=self.parent_folder_id
                )
            except requests.HTTPError as e:
                self.state.upsert(
                    ih,
                    status="error",
                    error=f"add_magnet: {e}",
                    title=it.get("title"),
                    category=it.get("category"),
                )
                continue

            self.state.upsert(
                ih,
                transfer_id=t["id"],
                file_id=t.get("file_id"),
                status="pending",
                title=it.get("title"),
                category=it.get("category"),
            )
            added += 1

        self.state.save()
        return added

    # ----- Fase B ----- #

    def harvest(self) -> list[dict]:
        """
        Atualiza pendentes; para os que concluíram, resolve URL de streaming.
        Retorna lista de entradas recém-prontas: {title, category, stream_url}.
        """
        new_done: list[dict] = []

        for ih, rec in self.state.all_pending():
            tid = rec.get("transfer_id")
            if not tid:
                continue

            try:
                t = self.client.get_transfer(tid)
            except requests.HTTPError as e:
                self.state.upsert(ih, error=f"get_transfer: {e}")
                continue

            status = (t.get("status") or "").upper()
            file_id = t.get("file_id") or rec.get("file_id")

            if status in _PUTIO_DONE_STATUSES and file_id:
                try:
                    stream_url = self._resolve_playable_url(file_id)
                except requests.HTTPError as e:
                    self.state.upsert(ih, error=f"resolve_url: {e}")
                    continue

                self.state.upsert(
                    ih,
                    status="done",
                    file_id=file_id,
                    stream_url=stream_url,
                    percent=100.0,
                )
                new_done.append({
                    "info_hash": ih,
                    "title": rec.get("title"),
                    "category": rec.get("category"),
                    "stream_url": stream_url,
                })
            elif status in _PUTIO_ERROR_STATUSES:
                self.state.upsert(
                    ih,
                    status="error",
                    error=t.get("error_message") or "transfer error",
                )
            else:
                self.state.upsert(
                    ih,
                    status="pending",
                    percent=t.get("percent_done"),
                    file_id=file_id,
                )

        self.state.save()
        return new_done

    # ----- helpers ----- #

    def _resolve_playable_url(self, file_id: int) -> str:
        """
        Se o transfer caiu como pasta (batch de episódios), escolhe o
        maior arquivo de vídeo dentro. Caso contrário, usa o próprio file_id.
        """
        try:
            children = self.client.list_children(file_id)
        except requests.HTTPError:
            children = []

        target = file_id
        if children:
            videos = [
                c for c in children
                if str(c.get("content_type", "")).startswith("video/")
            ]
            if videos:
                target = max(videos, key=lambda c: c.get("size", 0) or 0)["id"]
        return self.client.get_stream_url(target)

    # ----- output util ----- #

    def export_m3u_lines(self) -> list[str]:
        """
        Gera linhas M3U a partir de todos os transfers concluídos
        no state. Use isto pra mesclar com o gerador atual do
        playlist_premium.m3u (sem duplicar lógica de classificação).
        """
        lines: list[str] = []
        for _ih, rec in self.state.all_done():
            title = rec.get("title", "Unknown")
            category = rec.get("category", "Anime")
            url = rec["stream_url"]
            lines.append(
                f'#EXTINF:-1 group-title="{category}",{title}'
            )
            lines.append(url)
        return lines