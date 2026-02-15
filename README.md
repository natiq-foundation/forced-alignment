# Forced Alignment Service

A service for performing forced alignment between audio files and transcripts, providing word-level timestamps. The service can run in two modes: **HTTP API** (FastAPI) or **RabbitMQ Consumer**.

## Features

- **Forced Alignment**: Aligns audio files (MP3) with transcripts to generate word-level timestamps
- **Dual Mode Operation**: Run as an HTTP API server or as a RabbitMQ message consumer
- **Language Support**: Configurable language support (default: Arabic)
- **Optional Authentication**: Secure HTTP endpoints with secret key authentication
- **Docker Support**: Ready-to-use Docker container

## Setup

### Prerequisites

- Python 3.10+
- FFmpeg
- Git
- Perl
- Build tools (for compiling dependencies)

### Local Setup

1. **Create and activate a virtual environment:**

   ```bash
   python3 -m venv .env
   source .env/bin/activate
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

## Modes

The service supports two operational modes, controlled by the `MODE` environment variable:

### 1. HTTP Mode

Runs a FastAPI server that exposes a REST API endpoint for forced alignment.

**Start the HTTP server:**

```bash
export MODE=http
python main.py
```

The server will start on the configured host and port (default: `0.0.0.0:5000`).

### 2. RabbitMQ Mode

Consumes messages from a RabbitMQ queue, processes them, and publishes results to another queue.

**Start the RabbitMQ consumer:**

```bash
export MODE=rabbitmq
python main.py
```

The consumer will listen for messages on the configured queue and process them automatically.

## Environment Variables

### Mode Selection

| Variable | Description                          | Default    | Required |
| -------- | ------------------------------------ | ---------- | -------- |
| `MODE`   | Operation mode: `http` or `rabbitmq` | `rabbitmq` | No       |

### HTTP Mode Variables

| Variable           | Description                                                            | Default   | Required |
| ------------------ | ---------------------------------------------------------------------- | --------- | -------- |
| `HTTP_HOST`        | Host address to bind the HTTP server                                   | `0.0.0.0` | No       |
| `HTTP_PORT`        | Port number for the HTTP server                                        | `5000`    | No       |
| `ALIGN_SECRET_KEY` | Secret key for API authentication (if set, authentication is required) | `None`    | No       |
| `RELOAD`           | Enable auto-reload for development (`true`/`false`)                    | `false`   | No       |

### RabbitMQ Mode Variables

#### Consumer Configuration

| Variable              | Description                                | Default                               | Required |
| --------------------- | ------------------------------------------ | ------------------------------------- | -------- |
| `RABBITMQ_URL`        | RabbitMQ connection URL                    | `amqp://guest:guest@localhost:5672//` | No       |
| `CONSUME_QUEUE_NAME`  | Name of the queue to consume messages from | `forced_alignment`                    | No       |
| `CONSUME_ROUTING_KEY` | Routing key for the consume queue          | `forcedalignment.processing`          | No       |

#### Result Queue Configuration

| Variable                   | Description                             | Default                           | Required |
| -------------------------- | --------------------------------------- | --------------------------------- | -------- |
| `RESULT_QUEUE_NAME`        | Name of the queue to publish results to | `forced_alignment_done`           | No       |
| `RESULT_QUEUE_EXCHANGE`    | Exchange name for the result queue      | `forced_alignment_done`           | No       |
| `RESULT_QUEUE_ROUTING_KEY` | Routing key for the result queue        | `forcedalignment_done.processing` | No       |
| `RESULT_CELERY_TASK_NAME`  | Celery task name for result messages    | `forced-alignment-done`           | No       |

## Usage

### HTTP Mode

#### Starting the Server

```bash
export MODE=http
export HTTP_HOST=0.0.0.0
export HTTP_PORT=5000
export ALIGN_SECRET_KEY=your_secret_key_here  # Optional
python main.py
```

#### API Endpoint

**POST** `/align`

Performs forced alignment between an audio file and transcript.

**Request Body (JSON):**

```json
{
  "mp3_url": "https://example.com/audio.mp3",
  "text": "your transcript text here",
  "language": "ar", // Optional, defaults to "ar"
  "romanize": true, // Optional, defaults to true
  "batch_size": 4 // Optional, defaults to 4
}
```

**Response:**

```json
[
  {
    "word": "example",
    "start": 0.23,
    "end": 0.56,
    "score": 0.98
  },
  ...
]
```

- `word`: The word from the transcript
- `start`: Start time in seconds
- `end`: End time in seconds
- `score`: Alignment confidence score (0-1)

**Example Request (without authentication):**

```bash
curl -X POST "http://localhost:5000/align" \
  -H "Content-Type: application/json" \
  -d '{
    "mp3_url": "https://example.com/audio.mp3",
    "text": "your transcript here"
  }'
```

**Example Request (with authentication):**

```bash
curl -X POST "http://localhost:5000/align" \
  -H "Content-Type: application/json" \
  -H "Authorization: your_secret_key" \
  -d '{
    "mp3_url": "https://example.com/audio.mp3",
    "text": "your transcript here",
    "language": "ar",
    "romanize": true,
    "batch_size": 4
  }'
```

### RabbitMQ Mode

#### Starting the Consumer

```bash
export MODE=rabbitmq
export RABBITMQ_URL=amqp://user:password@rabbitmq-host:5672//
export CONSUME_QUEUE_NAME=forced_alignment
export CONSUME_ROUTING_KEY=forcedalignment.processing
export RESULT_QUEUE_NAME=forced_alignment_done
export RESULT_QUEUE_EXCHANGE=forced_alignment_done
export RESULT_QUEUE_ROUTING_KEY=forcedalignment_done.processing
export RESULT_CELERY_TASK_NAME=forced-alignment-done
python main.py
```

#### Message Format

The consumer expects messages in the following format:

```json
[
  [
    "https://example.com/audio.mp3", // audio_url
    "your transcript text here", // text
    {} // additional (optional metadata)
  ]
]
```

The consumer will:

1. Download and process the audio file
2. Perform forced alignment with the transcript
3. Publish results to the configured result queue in Celery-compatible format

**Result Message Format:**
The result is published as a Celery task message with:

- Task ID: UUID v4
- Task name: Value of `RESULT_CELERY_TASK_NAME`
- Arguments: `[words_timestamps, additional]`
- Headers: Standard Celery headers

## Running with Docker

### Build the Image

```bash
docker build -t forced-alignment .
```

### Run HTTP Mode

```bash
docker run -p 5000:5000 \
  -e MODE=http \
  -e HTTP_HOST=0.0.0.0 \
  -e HTTP_PORT=5000 \
  -e ALIGN_SECRET_KEY=your_secret_key \
  forced-alignment
```

### Run RabbitMQ Mode

```bash
docker run \
  -e MODE=rabbitmq \
  -e RABBITMQ_URL=amqp://user:password@rabbitmq-host:5672// \
  -e CONSUME_QUEUE_NAME=forced_alignment \
  -e CONSUME_ROUTING_KEY=forcedalignment.processing \
  -e RESULT_QUEUE_NAME=forced_alignment_done \
  -e RESULT_QUEUE_EXCHANGE=forced_alignment_done \
  -e RESULT_QUEUE_ROUTING_KEY=forcedalignment_done.processing \
  -e RESULT_CELERY_TASK_NAME=forced-alignment-done \
  forced-alignment
```

### Using Pre-built Image

If a pre-built image is available:

```bash
docker run -p 5000:5000 \
  -e MODE=http \
  -e HTTP_PORT=5000 \
  natiqquran/forced-alignment:latest
```

## Development

### Enable Auto-reload (HTTP Mode)

For development, you can enable auto-reload:

```bash
export MODE=http
export RELOAD=true
python main.py
```

Or with Docker:

```bash
docker run -p 5000:5000 \
  -e MODE=http \
  -e RELOAD=true \
  forced-alignment
```

## Project Structure

```
forced-alignment/
├── core/
│   └── align.py          # Core alignment logic
├── modes/
│   ├── http.py           # HTTP API mode implementation
│   └── rabbitmq.py       # RabbitMQ consumer mode implementation
├── main.py               # Entry point and mode selection
├── requirements.txt      # Python dependencies
├── Dockerfile           # Docker configuration
└── README.md            # This file
```

## Notes

- The service automatically uses CUDA if available, otherwise falls back to CPU
- Audio files are temporarily downloaded and converted to WAV format for processing
- The RabbitMQ consumer processes one message at a time (prefetch_count=1)
- Failed messages are rejected without requeueing
- Authentication is optional for HTTP mode; if `ALIGN_SECRET_KEY` is not set, the endpoint is publicly accessible

## License

See [LICENSE](LICENSE) file for details.
