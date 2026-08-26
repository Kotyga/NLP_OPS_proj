from pathlib import Path
from typing import Any

import torch
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    pipeline,
)

from common.models import ReviewStatus
from worker.sentiment_model import SentimentPredictor

ARTIFACT_DIR = Path(__file__).resolve().parent / "sentiment_lstm_artifacts"

_toxic_pipe = pipeline(
    "text-classification",
    model="s-nlp/russian_toxicity_classifier",
    tokenizer="s-nlp/russian_toxicity_classifier",
    top_k=None,
)

_spam_tokenizer = AutoTokenizer.from_pretrained(
    "RUSpam/spam_deberta_v4"
)
_spam_model = AutoModelForSequenceClassification.from_pretrained(
    "RUSpam/spam_deberta_v4"
)
_spam_model.eval()

_sentiment_predictor = SentimentPredictor(
    artifact_dir=ARTIFACT_DIR,
    device="cpu",
)

def _is_spam(text: str) -> bool:
    inputs = _spam_tokenizer(
        text,
        return_tensors="pt",
        truncation=True,
        padding=True,
    )

    with torch.inference_mode():
        outputs = _spam_model(**inputs)
        label_id = int(outputs.logits.argmax(dim=1).item())

    return label_id == 1


def _is_toxic(text: str) -> bool:
    result = _toxic_pipe(
        text,
        truncation=True,
    )

    if not result:
        return False

    predictions: Any = result

    if (
        isinstance(predictions, list)
        and predictions
        and isinstance(predictions[0], list)
    ):
        predictions = predictions[0]

    if not isinstance(predictions, list):
        predictions = [predictions]

    valid_predictions = [
        prediction
        for prediction in predictions
        if isinstance(prediction, dict)
        and "label" in prediction
        and "score" in prediction
    ]

    if not valid_predictions:
        return False

    best_prediction = max(
        valid_predictions,
        key=lambda prediction: float(prediction["score"]),
    )

    label = str(best_prediction["label"]).strip().lower()

    return label == "toxic"


def _sentiment_to_rating(result: dict[str, Any]) -> int:

    label = str(result.get("label", "")).strip().lower()

    label_to_rating = {
        "neutral": 2,
        "positive": 3,
        "negative": 1,
    }

    if label in label_to_rating:
        return label_to_rating[label]

    label_id = result.get("label_id")

    label_id_to_rating = {
        0: 2,
        1: 3,
        2: 1,
    }

    if isinstance(label_id, int) and label_id in label_id_to_rating:
        return label_id_to_rating[label_id]

    raise ValueError(
        "Не удалось преобразовать класс тональности в оценку: "
        f"label={label!r}, label_id={label_id!r}"
    )

def _predict_rating(text: str) -> int:
    result = _sentiment_predictor.predict(text)
    rating = _sentiment_to_rating(result)

    if rating not in {1, 2, 3}:
        raise ValueError(
            f"Модель вернула недопустимую оценку: {rating}"
        )

    return rating


def moderate_text(
    text: str,
) -> tuple[ReviewStatus, str | None, int | None]:

    if _is_toxic(text):
        return (
            ReviewStatus.rejected,
            "Отклонено: токсичный текст",
            None,
        )

    if _is_spam(text):
        return (
            ReviewStatus.rejected,
            "Отклонено: спам",
            None,
        )

    rating = _predict_rating(text)

    return ReviewStatus.published, None, rating
