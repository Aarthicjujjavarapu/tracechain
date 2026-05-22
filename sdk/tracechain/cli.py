"""tracechain init — scaffold a new TraceChain project."""
from __future__ import annotations

import argparse
import os
import sys
import textwrap
from pathlib import Path


_ENV_TEMPLATE = textwrap.dedent("""\
    # TraceChain backend
    TRACECHAIN_API_URL=http://localhost:8000

    # LLM provider keys (uncomment the one you use)
    # OPENAI_API_KEY=sk-...
    # ANTHROPIC_API_KEY=sk-ant-...
""")

_COMPOSE_TEMPLATE = textwrap.dedent("""\
    version: "3.9"
    services:
      backend:
        image: ghcr.io/aarthicjujjavarapu/tracechain-backend:latest
        ports:
          - "8000:8000"
        environment:
          - DATABASE_URL=sqlite:////data/tracechain.db
        volumes:
          - tracechain_data:/data

      dashboard:
        image: ghcr.io/aarthicjujjavarapu/tracechain-dashboard:latest
        ports:
          - "3000:3000"
        environment:
          - NEXT_PUBLIC_API_URL=http://localhost:8000
        depends_on:
          - backend

    volumes:
      tracechain_data:
""")

_PIPELINE_TEMPLATE = textwrap.dedent("""\
    \"\"\"Starter TraceChain pipeline — edit to fit your workflow.\"\"\"
    from tracechain import workflow, step, llm_step

    @workflow(name="my_pipeline")
    def my_pipeline(query: str) -> str:
        docs   = retrieve(query)
        answer = generate(query, docs)
        return answer

    @step(name="retrieve", retries=1)
    def retrieve(query: str) -> list[str]:
        # Replace with your vector-store or search call
        return [f"Stub doc for: {query}"]

    @llm_step(name="generate", model="gpt-4o-mini", prompt_version="v1")
    def generate(query: str, docs: list[str]) -> str:
        return f"Answer based on docs:\\n{docs}\\n\\nQuery: {query}"

    if __name__ == "__main__":
        result = my_pipeline("What is TraceChain?")
        print(result)
""")


def _write(path: Path, content: str, *, overwrite: bool) -> bool:
    if path.exists() and not overwrite:
        print(f"  skip  {path}  (already exists — use --overwrite to replace)")
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print(f"  create {path}")
    return True


def cmd_init(args: argparse.Namespace) -> int:
    target = Path(args.directory).resolve()
    if not target.exists():
        target.mkdir(parents=True)
        print(f"Created directory {target}")

    overwrite = args.overwrite
    _write(target / ".env",              _ENV_TEMPLATE,      overwrite=overwrite)
    _write(target / "docker-compose.yml", _COMPOSE_TEMPLATE, overwrite=overwrite)
    _write(target / "pipeline.py",        _PIPELINE_TEMPLATE, overwrite=overwrite)

    print()
    print("TraceChain project ready!")
    print()
    print("  Next steps:")
    print("    1. Start the stack:   docker compose up -d")
    print("    2. Open dashboard:    http://localhost:3000")
    print("    3. Run your pipeline: python pipeline.py")
    print()
    print("  Docs: https://aarthicjujjavarapu.github.io/tracechain/docs/getting-started/quickstart")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="tracechain",
        description="TraceChain CLI — LLM workflow observability",
    )
    sub = parser.add_subparsers(dest="command", metavar="<command>")

    p_init = sub.add_parser("init", help="Scaffold a new TraceChain project")
    p_init.add_argument(
        "directory",
        nargs="?",
        default=".",
        help="Directory to initialise (default: current directory)",
    )
    p_init.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing files",
    )

    args = parser.parse_args()
    if args.command is None:
        parser.print_help()
        sys.exit(0)

    if args.command == "init":
        sys.exit(cmd_init(args))


if __name__ == "__main__":
    main()
