from __future__ import annotations

from argparse import ArgumentParser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from typing import Any

from paper_analysis.api.evaluation_predictor import EvaluationPredictor
from paper_analysis.api.evaluation_protocol import (
    EvaluationProtocolError,
    EvaluationRequest,
    EvaluationResponse,
)
from paper_analysis.shared.encoding import configure_utf8_stdio


class EvaluationRequestHandler(BaseHTTPRequestHandler):
    predictor = EvaluationPredictor()
    server_version = "PaperAnalysisEvaluationAPI/1.0"
    error_content_type = "application/json; charset=utf-8"

    def do_GET(self) -> None:  # noqa: N802
        if self.path != "/healthz":
            self._write_json(
                HTTPStatus.NOT_FOUND,
                {"error": {"code": "not_found", "message": "未找到请求路径"}},
            )
            return
        self._write_json(HTTPStatus.OK, {"status": "ok"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/v1/evaluation/annotate":
            self._write_json(
                HTTPStatus.NOT_FOUND,
                {"error": {"code": "not_found", "message": "未找到请求路径"}},
            )
            return
        try:
            payload = self._read_json_body()
            request = EvaluationRequest.from_dict(payload)
            prediction = self.predictor.predict(request.paper)
            response = EvaluationResponse(
                request_id=request.request_id,
                prediction=prediction,
                algorithm_version=self.predictor.algorithm_version,
            )
        except EvaluationProtocolError as exc:
            self._write_json(
                HTTPStatus.BAD_REQUEST,
                {"error": {"code": "invalid_request", "message": str(exc)}},
            )
            return
        except json.JSONDecodeError:
            self._write_json(
                HTTPStatus.BAD_REQUEST,
                {"error": {"code": "invalid_json", "message": "请求体不是合法 JSON"}},
            )
            return
        self._write_json(HTTPStatus.OK, response.to_dict())

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _read_json_body(self) -> object:
        content_length = int(self.headers.get("Content-Length", "0"))
        if content_length <= 0:
            raise EvaluationProtocolError("请求体不能为空")
        raw_body = self.rfile.read(content_length)
        return json.loads(raw_body.decode("utf-8"))

    def _write_json(self, status: HTTPStatus, payload: dict[str, object]) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def build_parser() -> ArgumentParser:
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
    return parser


def main() -> None:
    configure_utf8_stdio()
    args = build_parser().parse_args()
    EvaluationRequestHandler.predictor = EvaluationPredictor(
        algorithm_version=args.algorithm_version
    )
    server = ThreadingHTTPServer((args.host, args.port), EvaluationRequestHandler)
    print(
        json.dumps(
            {
                "status": "serving",
                "host": args.host,
                "port": args.port,
                "algorithm_version": args.algorithm_version,
            },
            ensure_ascii=False,
        )
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
