"""Provider-neutral HTTP adapter for a hosted generation worker.

The JSON contract is documented in docs/deployment.md. This client does not
encode any hosting-vendor SDK or product names.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any
from urllib.parse import urljoin

from unity_ai_assets.core.error_codes import AppErrorCode
from unity_ai_assets.core.errors import AppError
from unity_ai_assets.domain.jobs import JobProgress, JobResult
from unity_ai_assets.services.job_executor import RemoteWorkerStatus, RemoteWorkerSubmission


class HttpRemoteWorkerClient:
    """POST/GET JSON worker using a stable request_id as the idempotency key."""

    def __init__(
        self,
        base_url: str,
        *,
        token: str | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        self._base_url = base_url.rstrip("/") + "/"
        self._token = token
        self._timeout = timeout_seconds

    def submit(self, submission: RemoteWorkerSubmission) -> str:
        payload = {
            "request_id": submission.request_id,
            "parameters": submission.parameters,
            "metadata": submission.metadata,
        }
        body = self._request("POST", "jobs", payload)
        return str(body.get("job_id") or submission.request_id)

    def get_status(self, remote_job_id: str) -> RemoteWorkerStatus:
        body = self._request("GET", f"jobs/{remote_job_id}")
        progress_payload = body.get("progress")
        result_payload = body.get("result")
        error_payload = body.get("error")
        error: Exception | None = None
        if isinstance(error_payload, dict):
            try:
                code = AppErrorCode(str(error_payload.get("code") or "INTERNAL_SERVER_ERROR"))
            except ValueError:
                code = AppErrorCode.INTERNAL_SERVER_ERROR
            error = AppError(
                str(error_payload.get("message") or "Remote worker failed."),
                code=code,
                details=error_payload.get("details")
                if isinstance(error_payload.get("details"), dict)
                else None,
            )
        return RemoteWorkerStatus(
            job_id=str(body.get("job_id") or remote_job_id),
            state=str(body.get("state") or "unknown"),
            progress=(
                JobProgress.from_dict(progress_payload)
                if isinstance(progress_payload, dict)
                else None
            ),
            result=_result_from_payload(result_payload),
            error=error,
        )

    def cancel(self, remote_job_id: str) -> None:
        self._request("POST", f"jobs/{remote_job_id}/cancel")

    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        headers = {"Accept": "application/json"}
        if data is not None:
            headers["Content-Type"] = "application/json"
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        request = urllib.request.Request(
            urljoin(self._base_url, path),
            data=data,
            headers=headers,
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            raise AppError(
                "The remote worker rejected the request.",
                code=AppErrorCode.INFERENCE_FAILED,
                details={"http_status": exc.code},
            ) from exc
        except urllib.error.URLError as exc:
            raise AppError(
                "The remote worker is unreachable.",
                code=AppErrorCode.JOB_SERVICE_UNAVAILABLE,
            ) from exc
        if not raw:
            return {}
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}


def _result_from_payload(payload: object) -> JobResult | None:
    if not isinstance(payload, dict):
        return None
    return JobResult.from_dict(payload)
