"""Точка входа AudioPlayer."""
from app.main import main

if __name__ == "__main__":
    import sys
    if len(sys.argv) == 3 and sys.argv[1] == "--smoke-test":
        from app.smoke import run
        raise SystemExit(run(sys.argv[2]))
    raise SystemExit(main())
