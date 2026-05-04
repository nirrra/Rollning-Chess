from __future__ import annotations

import argparse
import sys

from .selfplay import DEFAULT_MAX_PLIES, generate_selfplay_games
from .train import evaluate_model_against_normal, train_value_model


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Rolling Chess AI tools.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    selfplay = subparsers.add_parser("selfplay", help="Generate self-play JSONL data.")
    selfplay.add_argument("--games", type=int, default=100)
    selfplay.add_argument("--max-plies", type=int, default=DEFAULT_MAX_PLIES)
    selfplay.add_argument("--out", default="data/selfplay")
    selfplay.add_argument("--difficulty", default="normal", choices=["easy", "normal", "experimental"])
    selfplay.add_argument("--seed", type=int, default=None)

    train = subparsers.add_parser("train", help="Train a local value model from JSONL data.")
    train.add_argument("--data", default="data/selfplay")
    train.add_argument("--out", default="models/value.pt")
    train.add_argument("--epochs", type=int, default=5)
    train.add_argument("--batch-size", type=int, default=32)
    train.add_argument("--lr", type=float, default=1e-3)

    evaluate = subparsers.add_parser("evaluate", help="Pit experimental model evaluation against normal search.")
    evaluate.add_argument("--model", default="models/value.pt")
    evaluate.add_argument("--games", type=int, default=20)
    evaluate.add_argument("--max-plies", type=int, default=DEFAULT_MAX_PLIES)

    args = parser.parse_args(argv)

    try:
        if args.command == "selfplay":
            summary = generate_selfplay_games(
                games=args.games,
                out_dir=args.out,
                max_plies=args.max_plies,
                difficulty=args.difficulty,
                seed=args.seed,
            )
            print(
                f"wrote {summary.samples} samples from {summary.games} games to {summary.path}"
            )
            return 0
        if args.command == "train":
            summary = train_value_model(
                data_dir=args.data,
                out_path=args.out,
                epochs=args.epochs,
                batch_size=args.batch_size,
                learning_rate=args.lr,
            )
            print(
                f"trained {summary.samples} samples for {summary.epochs} epochs; "
                f"final_loss={summary.final_loss:.6f}; saved {summary.out_path}"
            )
            return 0
        if args.command == "evaluate":
            summary = evaluate_model_against_normal(
                model_path=args.model,
                games=args.games,
                max_plies=args.max_plies,
            )
            print(
                f"games={summary.games} model_wins={summary.model_wins} "
                f"normal_wins={summary.normal_wins} draws={summary.draws}"
            )
            return 0
    except (RuntimeError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
