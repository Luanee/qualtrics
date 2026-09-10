# Configuration

Offline parsing, reporting, combining, and semantic model creation need no credentials. Configure an API connection only for `qualtrics api ...` or `QualtricsClient`.

## Connection settings

| Environment variable | Python setting | Default | Meaning |
| --- | --- | --- | --- |
| `QUALTRICS_API_TOKEN` | `api_token` | Empty string | Required API token. |
| `QUALTRICS_DATA_CENTER` | `data_center` | `None` | Data center identifier used to construct the API URL. |
| `QUALTRICS_BASE_URL` | `base_url` | `None` | Complete API base URL, including `/API/v3`. Takes precedence over the data center. |

With a data center of `fra1`, the client constructs `https://fra1.qualtrics.com/API/v3`. Replace `fra1` with your account's data center. A configured base URL wins even when a data center is also present. The client removes a trailing slash before creating its HTTP connection.

### Environment variables

For a POSIX shell such as Bash or Zsh:

```bash
export QUALTRICS_API_TOKEN='your-token'
export QUALTRICS_DATA_CENTER='your-data-center'
uv run --extra cli qualtrics api surveys
```

For PowerShell:

```powershell
$env:QUALTRICS_API_TOKEN = 'your-token'
$env:QUALTRICS_DATA_CENTER = 'your-data-center'
uv run --extra cli qualtrics api surveys
```

Use your own values. Treat tokens as secrets and keep them out of source control and shared examples.

### A local `.env` file

`QualtricsSettings` reads a UTF-8 file named `.env` from the current working directory. Create it in the directory from which you run the command:

```dotenv
QUALTRICS_API_TOKEN=your-token
QUALTRICS_DATA_CENTER=your-data-center
```

Or replace the data center line with a complete base URL:

```dotenv
QUALTRICS_BASE_URL=https://your-data-center.qualtrics.com/API/v3
```

The settings loader ignores unrelated keys in `.env`. It does not search parent directories for the file. Restart a client after changing connection values; each new `QualtricsClient` reads its settings during construction.

## Credential priority

For Python clients, the order from highest to lowest priority is:

1. Non-`None` arguments to `QualtricsClient(...)`.
2. Environment variables.
3. Values in the current directory's `.env` file.
4. The defaults in the settings table.

Passing `None` leaves a setting available for environment or `.env` lookup. An explicit empty string overrides a stored value. An empty token raises `ValueError("api_token is required")`; missing both a usable base URL and data center raises `ValueError("provide data_center or base_url")`.

```python
from qualtrics import QualtricsClient

# Reads the environment and .env; construction does not make an API request.
client = QualtricsClient()
client.close()
```

### CLI overrides

The API commands accept `--api-token` and `--data-center`. The token option is hidden from help output. Explicit flags take priority over their corresponding environment variables.

!!! note "Keep CLI credentials in the same source"
    If you set `--data-center` or `QUALTRICS_DATA_CENTER`, also supply the token through `--api-token` or `QUALTRICS_API_TOKEN`. In this CLI path, a token available only in `.env` is replaced with an empty string. To use `.env` for both values, leave both credential flags and both credential environment variables unset.

The CLI reads `QUALTRICS_BASE_URL`; it has no `--base-url` option. A base URL in `.env` also remains available unless the environment supplies an override. Check for an old base URL if changing the data center appears to have no effect.

## Python settings and timeouts

Import the settings model without opening a network connection:

```python
from qualtrics.api import QualtricsSettings

settings = QualtricsSettings()
```

Use `QualtricsSettings(_env_file="path/to/local.env")` to load a different file, or `_env_file=None` to disable dotenv loading for that settings instance. To use a custom instance with a client, pass its connection fields:

```python
from qualtrics import QualtricsClient
from qualtrics.api import QualtricsSettings

settings = QualtricsSettings(_env_file="path/to/local.env")
with QualtricsClient(
    settings.api_token,
    data_center=settings.data_center,
    base_url=settings.base_url,
    timeout=60.0,
) as client:
    pass  # Add API calls here when needed.
```

`timeout` defaults to 30 seconds for HTTP requests. Export and import polling methods have a separate `timeout=900.0` and `poll_interval=1.0`, also in seconds. These values are method arguments, not `QUALTRICS_` environment settings. The client accepts an optional `httpx.BaseTransport` for a custom or mocked transport.

For method signatures and error handling, see the [Python reference](python.md). For a complete download workflow, see [API access](../guides/api-access.md).
