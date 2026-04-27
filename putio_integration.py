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

import base64

import requests

PUTIO_API = "https://api.put.io/v2"

_MAGNET_HASH_RE = re.compile(
    r"xt=urn:btih:([A-Za-z0-9]{32,40})"
)


def info_hash_from_magnet(magnet: str) -> str | None:
    """
    Extrai o info_hash de um magnet link, sempre normalizado em hex lowercase
    (40 caracteres). Aceita as duas codificações que aparecem em magnets:
      • Hex 40 chars (formato canônico)
      • Base32 32 chars (usado por SubsPlease e alguns outros) — convertido
        para hex antes de retornar.

    Put.io rejeita magnets com info_hash em base32 com erro 400 'Invalid
    magnet link', então a conversão é obrigatória.
    """
    m = _MAGNET_HASH_RE.search(magnet or "")
    if not m:
        return None
    raw = m.group(1)

    if len(raw) == 40:
        # Já é hex — só normaliza pra lowercase.
        if all(c in "0123456789abcdefABCDEF" for c in raw):
            return raw.lower()
        return None  # 40 chars mas não-hex: malformado

    if len(raw) == 32:
        # Base32 → hex. base64.b32decode exige uppercase.
        try:
            decoded = base64.b32decode(raw.upper())
            return decoded.hex()
        except Exception:
            return None

    return None


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
        # Put.io só quer save_parent_id no payload se for diferente de 0.
        # Em algumas contas, enviar 0 explicitamente causa 400 BAD REQUEST.
        payload = {"url": magnet}
        if parent_id and parent_id > 0:
            payload["save_parent_id"] = parent_id

        r = self.session.post(
            f"{PUTIO_API}/transfers/add",
            data=payload,
            timeout=self.timeout,
        )
        if not r.ok:
            # Anexa o body da resposta no erro pra debug ficar visível.
            try:
                body = r.json()
            except Exception:
                body = r.text[:200]
            err = requests.HTTPError(
                f"{r.status_code} {r.reason} — body={body}",
                response=r,
            )
            raise err
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
        max_enqueue_per_run: int = 5,
        max_pending_total: int = 10,
    ):
        self.client = client or PutioClient()
        self.state = PutioState(state_path)
        self.parent_folder_id = parent_folder_id
        # Rate-limiting: evita saturar a fila do Put.io. Com 5/run a cada
        # 2h, ~60 transfers/dia. Plano básico costuma ter ~10 slots
        # concorrentes, então max_pending_total=10 mantém saudável.
        self.max_enqueue_per_run = max_enqueue_per_run
        self.max_pending_total = max_pending_total

    # ----- Fase A ----- #

    def _normalize_magnet_to_hex(self, magnet: str) -> str:
        """
        Reescreve o info_hash do magnet em hex (40 chars). Put.io rejeita
        info_hashes em base32 (32 chars) com 'Invalid magnet link', mesmo
        sendo formato válido pelo padrão BEP-9.

        Exemplo:
          magnet:?xt=urn:btih:GRXO3L27QJZC...     →  base32 32 chars
          magnet:?xt=urn:btih:34ee...lowercase     →  hex 40 chars (Put.io OK)
        """
        ih = info_hash_from_magnet(magnet)
        if not ih:
            return magnet  # não conseguiu extrair — devolve como veio
        # Substitui a primeira ocorrência do hash original pela versão hex.
        return _MAGNET_HASH_RE.sub(
            lambda m: f"xt=urn:btih:{ih}",
            magnet,
            count=1,
        )

    def _try_add_magnet(self, magnet: str) -> dict:
        """
        Tenta enviar o magnet ao Put.io. Se receber 400, refaz a requisição
        com versão minimalista do magnet (apenas xt=urn:btih:HASH, sem dn
        nem trackers) — Put.io adiciona trackers via DHT/PEX automaticamente.

        Antes de enviar, normaliza o info_hash pra hex se vier em base32.
        """
        normalized = self._normalize_magnet_to_hex(magnet)
        try:
            return self.client.add_magnet(
                normalized, parent_id=self.parent_folder_id
            )
        except requests.HTTPError as e:
            # Apenas 400 (BAD REQUEST) costuma ser por conteúdo do magnet.
            # 401/403/429 não fazem sentido tentar de novo.
            if not (e.response is not None and e.response.status_code == 400):
                raise
            ih = info_hash_from_magnet(normalized)
            if not ih:
                raise
            minimal = f"magnet:?xt=urn:btih:{ih}"
            print(f"  ↻ retry minimal magnet para {ih[:12]}...")
            return self.client.add_magnet(
                minimal, parent_id=self.parent_folder_id
            )

    def enqueue(self, items: Iterable[dict]) -> int:
        """
        items: iter de {magnet, title, category}.
        Idempotente: ignora info_hash já em state com status pending/done.
        Itens com status 'error' são RETENTADOS (Put.io pode ter recuperado
        de erros temporários — rate-limit, lentidão, manutenção).

        Rate-limiting:
          • Para de enfileirar se já há max_pending_total transfers pendentes.
          • Limita a max_enqueue_per_run novos transfers por execução.
        Isso evita saturar a fila do Put.io quando o RSS traz muitos itens
        de uma vez (ex: primeira sincronização ou release dump).

        Retorna a quantidade de novos transfers enviados.
        """
        added = 0
        retried = 0
        skipped_errors = 0

        # Conta pendentes globais ANTES de enfileirar — se já estourou o
        # limite, sai cedo e deixa a fila do Put.io escoar antes do próximo run.
        pending_count = sum(
            1 for _ih, rec in self.state._data["transfers"].items()
            if rec.get("status") == "pending"
        )

        if pending_count >= self.max_pending_total:
            print(
                f"  ⏸  Fila do Put.io saturada ({pending_count} pendentes ≥ "
                f"limite {self.max_pending_total}). Aguardando download "
                f"completar antes de adicionar novos."
            )
            return 0

        slots_disponiveis = min(
            self.max_enqueue_per_run,
            self.max_pending_total - pending_count,
        )
        print(
            f"  📊 Pendentes atuais: {pending_count} | "
            f"Slots disponíveis neste run: {slots_disponiveis}"
        )

        for it in items:
            if added >= slots_disponiveis:
                break

            magnet = it.get("magnet")
            ih = info_hash_from_magnet(magnet) if magnet else None
            if not ih:
                continue

            existing = self.state.get(ih)
            if existing:
                # Não retenta o que já é pending ou done — só recuperáveis.
                if existing.get("status") in ("pending", "done"):
                    continue
                # status == 'error' → vai retentar abaixo
                retried += 1

            try:
                t = self._try_add_magnet(magnet)
            except requests.HTTPError as e:
                # Loga visivelmente para diagnóstico; antes era silencioso.
                err_msg = f"add_magnet HTTP {e.response.status_code if e.response else '?'}: {e}"
                print(f"  ⚠️  enqueue erro [{it.get('title','?')[:50]}]: {err_msg}")
                skipped_errors += 1
                self.state.upsert(
                    ih,
                    status="error",
                    error=err_msg,
                    title=it.get("title"),
                    category=it.get("category"),
                )
                continue
            except Exception as e:
                print(f"  ⚠️  enqueue exceção [{it.get('title','?')[:50]}]: {e}")
                skipped_errors += 1
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
                error=None,  # limpa erro anterior se houver
                title=it.get("title"),
                category=it.get("category"),
            )
            added += 1

        if retried:
            print(f"  ↻ {retried} entradas em erro retentadas neste run.")
        if skipped_errors:
            print(f"  ⚠️  {skipped_errors} erros durante enqueue (ver detalhes acima).")

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