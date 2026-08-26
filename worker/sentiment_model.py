import torch
import torch.nn as nn
from torch.nn.utils.rnn import pad_sequence
import youtokentome as yttm
from pathlib import Path

class LSTMClassifier(nn.Module):
    def __init__(
        self,
        vocab_size,
        embedding_dim=128,
        hidden_dim=128,
        dropout=0.3,
        num_classes=3,
        pad_index=0
    ):
        super().__init__()

        self.embedding = nn.Embedding(
            vocab_size,
            embedding_dim,
            padding_idx=pad_index
        )

        self.lstm = nn.LSTM(
            input_size=embedding_dim,
            hidden_size=hidden_dim,
            batch_first=True
        )

        self.dropout = nn.Dropout(dropout)

        self.linear = nn.Linear(
            hidden_dim,
            num_classes
        )

    def forward(self, sequences, lengths):
        embeddings = self.embedding(sequences)

        outputs, _ = self.lstm(embeddings)

        lengths = lengths.to(outputs.device)

        batch_indices = torch.arange(
            outputs.size(0),
            device=outputs.device
        )

        last_outputs = outputs[
            batch_indices,
            lengths - 1
        ]

        logits = self.linear(
            self.dropout(last_outputs)
        )

        return logits


class SentimentPredictor:
    def __init__(
        self,
        artifact_dir,
        device=None,
        max_length=512
    ):
        artifact_dir = Path(artifact_dir)

        if device is None:
            device = "cuda" if torch.cuda.is_available() else "cpu"

        self.device = torch.device(device)
        self.max_length = max_length

        checkpoint_path = artifact_dir / "model.pt"
        tokenizer_path = artifact_dir / "ru_bpe.model"

        if not checkpoint_path.exists():
            raise FileNotFoundError(
                f"Не найден файл модели: {checkpoint_path}"
            )

        if not tokenizer_path.exists():
            raise FileNotFoundError(
                f"Не найден токенизатор: {tokenizer_path}"
            )

        checkpoint = torch.load(
            checkpoint_path,
            map_location=self.device,
            weights_only=False
        )

        config = checkpoint["model_config"]

        self.pad_index = config["pad_index"]
        self.unk_index = config["unk_index"]

        self.label_names = {
            int(key): value
            for key, value in checkpoint["label_names"].items()
        }

        self.tokenizer = yttm.BPE(
            model=str(tokenizer_path)
        )

        self.model = LSTMClassifier(
            vocab_size=config["vocab_size"],
            embedding_dim=config["embedding_dim"],
            hidden_dim=config["hidden_dim"],
            dropout=config["dropout"],
            num_classes=config["num_classes"],
            pad_index=config["pad_index"]
        )

        self.model.load_state_dict(
            checkpoint["model_state_dict"]
        )

        self.model.to(self.device)
        self.model.eval()

    def encode(self, text):
        if not isinstance(text, str) or not text.strip():
            return [self.unk_index]

        token_ids = self.tokenizer.encode(
            [text],
            output_type=yttm.OutputType.ID
        )[0]

        if not token_ids:
            token_ids = [self.unk_index]

        if self.max_length is not None:
            token_ids = token_ids[:self.max_length]

        return token_ids

    def prepare_batch(self, texts):
        encoded = [
            torch.tensor(
                self.encode(text),
                dtype=torch.long
            )
            for text in texts
        ]

        lengths = torch.tensor(
            [len(sequence) for sequence in encoded],
            dtype=torch.long
        )

        sequences = pad_sequence(
            encoded,
            batch_first=True,
            padding_value=self.pad_index
        )

        return (
            sequences.to(self.device),
            lengths.to(self.device)
        )

    @torch.inference_mode()
    def predict_batch(self, texts):
        if isinstance(texts, str):
            texts = [texts]

        if not texts:
            return []

        sequences, lengths = self.prepare_batch(texts)

        logits = self.model(sequences, lengths)
        probabilities = torch.softmax(logits, dim=1)
        predicted_ids = probabilities.argmax(dim=1)

        probabilities = probabilities.cpu().numpy()
        predicted_ids = predicted_ids.cpu().numpy()

        results = []

        for text, class_id, class_probabilities in zip(
            texts,
            predicted_ids,
            probabilities
        ):
            class_id = int(class_id)

            scores = {
                self.label_names[index]: float(probability)
                for index, probability
                in enumerate(class_probabilities)
            }

            results.append({
                "text": text,
                "label_id": class_id,
                "label": self.label_names[class_id],
                "confidence": float(
                    class_probabilities[class_id]
                ),
                "probabilities": scores
            })

        return results

    def predict(self, text):
        return self.predict_batch([text])[0]
