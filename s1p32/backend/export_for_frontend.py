import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from src.serving import dashboard_data


def run():
    return dashboard_data.export()


if __name__ == "__main__":
    run()
