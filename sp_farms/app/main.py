from collections.abc import Sequence

from sp_farms.bootstrap import create_application


def main(argv: Sequence[str] | None = None) -> int:
    del argv
    context = create_application()
    try:
        return 0
    finally:
        context.close()


if __name__ == "__main__":
    raise SystemExit(main())
