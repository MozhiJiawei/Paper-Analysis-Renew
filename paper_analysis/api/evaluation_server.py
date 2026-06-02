"""HTTP server exposing the evaluation predictor over a batched API."""

from __future__ import annotations

import json
import sys
import time
from argparse import ArgumentParser
from concurrent.futures import ThreadPoolExecutor, as_completed
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from paper_analysis.api.evaluation_predictor import EvaluationPredictor
from paper_analysis.api.evaluation_protocol import (
    EvaluationBatchRequest,
    EvaluationBatchResponse,
    EvaluationProtocolError,
    EvaluationResponse,
)
from paper_analysis.shared.encoding import configure_utf8_stdio

BATCH_PROGRESS_INTERVAL = 5


class EvaluationRequestHandler(BaseHTTPRequestHandler):
    """Serve health and batch annotation requests for the evaluation API."""

    predictor = EvaluationPredictor()
    server_version = "PaperAnalysisEvaluationAPI/1.0"
    error_content_type = "application/json; charset=utf-8"

    def do_GET(self) -> None:
        """Handle health-check requests."""
        if self.path != "/healthz":
            self._write_json(
                HTTPStatus.NOT_FOUND,
                {"error": {"code": "not_found", "message": "未找到请求路径"}},
            )
            return
        self._write_json(HTTPStatus.OK, {"status": "ok"})

    def do_POST(self) -> None:
        """Handle batched annotation requests."""
        if self.path != "/v1/evaluation/annotate":
            self._write_json(
                HTTPStatus.NOT_FOUND,
                {"error": {"code": "not_found", "message": "未找到请求路径"}},
            )
            return
        try:
            payload = self._read_json_body()
            batch_request = EvaluationBatchRequest.from_dict(payload)
            _emit_progress_line(
                "batch_received",
                path=self.path,
                request_count=len(batch_request.requests),
                algorithm_version=self.predictor.algorithm_version,
            )
            responses = self._predict_batch(batch_request)
            response = EvaluationBatchResponse(responses=responses)
        except json.JSONDecodeError:
            self._write_json(
                HTTPStatus.BAD_REQUEST,
                {"error": {"code": "invalid_json", "message": "请求体不是合法 JSON"}},
            )
            return
        except EvaluationProtocolError as exc:
            self._write_json(
                HTTPStatus.BAD_REQUEST,
                {"error": {"code": "invalid_request", "message": str(exc)}},
            )
            return
        self._write_json(HTTPStatus.OK, response.to_dict())

    def log_message(self, _message_format: str, *_args: object) -> None:
        """Silence the default HTTP access log for cleaner test output."""
        return

    def _read_json_body(self) -> object:
        content_length = int(self.headers.get("Content-Length", "0"))
        if content_length <= 0:
            raise EvaluationProtocolError("请求体不能为空")
        raw_body = self.rfile.read(content_length)
        return json.loads(raw_body.decode("utf-8"))

    def _predict_batch(
        self,
        batch_request: EvaluationBatchRequest,
    ) -> list[EvaluationResponse]:
        started_at = time.perf_counter()
        request_count = len(batch_request.requests)

        def elapsed_ms() -> int:
            return int((time.perf_counter() - started_at) * 1000)

        _emit_progress_line(
            "batch_predict_start",
            request_count=request_count,
            algorithm_version=self.predictor.algorithm_version,
        )
        try:
            responses: list[EvaluationResponse | None] = [None] * request_count
            with ThreadPoolExecutor(max_workers=request_count) as executor:
                future_indexes = {
                    executor.submit(self.predictor.predict, request.paper): index
                    for index, request in enumerate(batch_request.requests)
                }
                for completed_count, future in enumerate(as_completed(future_indexes), start=1):
                    index = future_indexes[future]
                    request = batch_request.requests[index]
                    responses[index] = EvaluationResponse(
                        request_id=request.request_id,
                        prediction=future.result(),
                        algorithm_version=self.predictor.algorithm_version,
                    )
                    self._emit_batch_progress(
                        completed_count=completed_count,
                        request_count=request_count,
                        elapsed_ms=elapsed_ms(),
                    )
            resolved_responses = [
                response for response in responses if response is not None
            ]
        except Exception as exc:
            _emit_progress_line(
                "batch_predict_failed",
                request_count=request_count,
                duration_ms=elapsed_ms(),
                algorithm_version=self.predictor.algorithm_version,
                error=str(exc),
            )
            raise
        _emit_progress_line(
            "batch_predict_done",
            request_count=request_count,
            duration_ms=elapsed_ms(),
            algorithm_version=self.predictor.algorithm_version,
        )
        return resolved_responses

    def _emit_batch_progress(
        self,
        *,
        completed_count: int,
        request_count: int,
        elapsed_ms: int,
    ) -> None:
        if completed_count < request_count and completed_count % BATCH_PROGRESS_INTERVAL != 0:
            return
        _emit_progress_line(
            "batch_predict_progress",
            completed_count=completed_count,
            request_count=request_count,
            duration_ms=elapsed_ms,
            algorithm_version=self.predictor.algorithm_version,
        )

    def _write_json(self, status: HTTPStatus, payload: dict[str, object]) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def build_parser() -> ArgumentParser:
    """Build the command-line parser for the evaluation API server."""
    parser = ArgumentParser(
        prog="paper-analysis-evaluation-api",
        description="本地论文评测标签服务，只提供只读 HTTP API。",
    )
    parser.add_argument("--host", default="127.0.0.1", help="监听地址，默认 127.0.0.1")
    parser.add_argument("--port", type=int, default=8765, help="监听端口，默认 8765")
    parser.add_argument(
        "--algorithm-version",
        default="heuristic-v1",
        help="响应中返回的算法版本标识",
    )
    parser.add_argument(
        "--ai-provider",
        choices=("doubao", "openrouter"),
        default="openrouter",
        help="评测复核使用的 AI provider，默认 openrouter；OpenRouter 失败时自动兜底 doubao。",
    )
    return parser


def _emit_progress_line(event: str, **payload: object) -> None:
    line_payload = {"component": "evaluation_api", "event": event, **payload}
    sys.stdout.write("[progress] " + json.dumps(line_payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def main() -> None:
    """Start the threaded evaluation API server."""
    configure_utf8_stdio()
    args = build_parser().parse_args()
    EvaluationRequestHandler.predictor = EvaluationPredictor(
        algorithm_version=args.algorithm_version,
        llm_hard_case_review=True,
        ai_provider=args.ai_provider,
    )
    server = ThreadingHTTPServer((args.host, args.port), EvaluationRequestHandler)
    sys.stdout.write(
        json.dumps(
            {
                "status": "serving",
                "host": args.host,
                "port": args.port,
                "algorithm_version": args.algorithm_version,
                "ai_provider": args.ai_provider,
            },
            ensure_ascii=False,
        )
        + "\n"
    )
    sys.stdout.flush()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
