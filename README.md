# NLP_OPS_proj

Микросервисное приложение для оценки киноновинок: FastAPI API, worker на очереди RabbitMQ и статичный фронтенд.

Пользовательские отзывы отправляются на ML-модерацию с помощью русскоязычных моделей токсичности и спама. Отклонённые отзывы не отображаются. Допущенные отзывы анализируются LSTM-моделью тональности и получают оценку от 1 до 3:

- `1` — негативный отзыв;
- `2` — нейтральный отзыв;
- `3` — позитивный отзыв.

На основе оценок опубликованных отзывов формируется рейтинг киноновинки.

## Структура проекта

- `api/` — FastAPI, REST CRUD для киноновинок и отзывов, продюсер сообщений в RabbitMQ. Общий код импортируется из `common/`.
- `worker/` — консюмер RabbitMQ. Проверяет отзывы моделями токсичности и спама, а для допущенных отзывов определяет тональность с помощью LSTM-модели и выставляет оценку.
- `worker/sentiment_lstm_artifacts/` — артефакты LSTM-модели и BPE-токенизатора.
- `frontend/` — HTML интерфейс. Содержит список киноновинок, форму добавления и карточку фильма с отзывами и рейтингом.
- `common/` — общие SQLAlchemy-модели, Pydantic-схемы, CRUD-функции, конфигурация и подключение к БД.

## Конфигурация

Перед запуском создайте файл `.env` в корне проекта:

```bash
echo "POSTGRES_USER=postgres" > .env
echo "POSTGRES_PASSWORD=postgres" >> .env
echo "POSTGRES_DB=reviews" >> .env
echo "" >> .env
echo "DB_USER=\${POSTGRES_USER}" >> .env
echo "DB_PASSWORD=\${POSTGRES_PASSWORD}" >> .env
echo "DB_NAME=\${POSTGRES_DB}" >> .env
echo "DB_HOST=db" >> .env
echo "DB_PORT=5432" >> .env
echo "" >> .env
echo "RABBIT_HOST=rabbitmq" >> .env
echo "RABBIT_PORT=5672" >> .env
echo "RABBIT_USER=guest" >> .env
echo "RABBIT_PASSWORD=guest" >> .env
echo "RABBIT_QUEUE=reviews" >> .env
```

Docker-сервисы автоматически используют эти переменные.

## Быстрый старт

Соберите и запустите проект:

```bash
docker compose up --build
```

Для запуска в фоновом режиме:

```bash
docker compose up --build -d
```

После запуска доступны:

- API: <http://localhost:8000>
- Swagger: <http://localhost:8000/docs>
- Frontend: <http://localhost:8080>
- RabbitMQ UI: <http://localhost:15672>
- Логин и пароль RabbitMQ: `guest` / `guest`

## Основные маршруты API

### Киноновинки

Во внутренней структуре API киноновинки представлены как `products`.

- `POST /products` — добавить киноновинку;
- `GET /products` — получить список киноновинок;
- `GET /products/{id}` — получить карточку киноновинки;
- `PUT /products/{id}` — обновить киноновинку;
- `DELETE /products/{id}` — удалить киноновинку.

### Отзывы

- `POST /reviews/publish` — создать отзыв со статусом `pending` и отправить его в RabbitMQ;
- `PUT /reviews/{id}` — обновить отзыв, вернуть ему статус `pending` и повторно отправить на обработку;
- `GET /reviews?product_id=...&published_only=true` — получить опубликованные отзывы выбранной киноновинки.

В ответах отзывов используются поля:

- `status` — состояние обработки;
- `moderation_reason` — причина отклонения;
- `rating` — оценка тональности от `1` до `3`.

## Обработка отзывов

После создания отзыв получает статус `pending` и отправляется в очередь RabbitMQ. Worker последовательно выполняет два этапа обработки.

### 1. ML-модерация

Worker загружает готовые русскоязычные модели с Hugging Face:

- токсичность — `s-nlp/russian_toxicity_classifier`;
- спам — `RUSpam/spam_deberta_v4`.

Если хотя бы одна модель сработала, отзыв отклоняется:

```text
status = rejected
rating = NULL
moderation_reason = причина отклонения
```

Причина сохраняется в PostgreSQL и записывается в логи worker. Отклонённый отзыв не отображается на странице киноновинки и не участвует в формировании её рейтинга.

### 2. Определение оценки

Если отзыв прошёл модерацию, его тональность определяется собственной LSTM-моделью:

| Класс модели | Оценка |
|---|---:|
| `Negative` | 1 |
| `Neutral` | 2 |
| `Positive` | 3 |


Опубликованный отзыв отображается на странице киноновинки. Из оценок опубликованных отзывов формируется её общий рейтинг.

## Схема обработки

![schema][https://github.com/Kotyga/NLP_OPS_proj/src/schema.png]

## Схема базы данных

Таблицы создаются при старте API или worker.

Основные поля отзыва:

- `status` — `pending`, `published` или `rejected`;
- `moderation_reason` — причина отклонения, `nullable`;
- `rating` — оценка от `1` до `3`, `nullable`.

Значение `rating` отсутствует у новых и отклонённых отзывов:

```text
pending   → rating = NULL
rejected  → rating = NULL
published → rating = 1, 2 или 3
```

В формировании рейтинга киноновинки участвуют только отзывы со статусом `published`.

## Остановка проекта

```bash
docker compose down
```

Остановка с удалением данных PostgreSQL:

```bash
docker compose down -v
```

Команда с флагом `-v` удаляет Docker volume вместе со всеми сохранёнными данными.
