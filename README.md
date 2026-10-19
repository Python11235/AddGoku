# AddGoku
A reddit bot that can add Goku to any image (.webp .jpeg .png)

Mention the bot (`u/<bot username>`) in a comment on an image post (single image, gallery, or a link Reddit shows a preview for) and it replies with a link to the image with Goku added.

## Setup

```
pip install -r requirements.txt
```

Environment variables:

| Variable | Required | Notes |
| --- | --- | --- |
| `REDDIT_CLIENT_ID` | yes | From a "script" app at https://www.reddit.com/prefs/apps |
| `REDDIT_CLIENT_SECRET` | yes | |
| `REDDIT_USERNAME` | yes | The bot account |
| `REDDIT_PASSWORD` | yes | |
| `REDDIT_USER_AGENT` | no | Defaults to a generic AddGoku user agent |
| `IMGUR_CLIENT_ID` | recommended | Uploads results to imgur so reply links keep working after restarts/redeploys. Register an app with "Anonymous usage without user authorization" at https://api.imgur.com/oauth2/addclient |
| `PUBLIC_URL` | if no imgur, on non-Render hosts | Public base URL for self-hosted result links (used when imgur isn't set up or an upload fails). On Render, `RENDER_EXTERNAL_HOSTNAME` is used automatically |

## Run

```
gunicorn app:app --workers 1 --threads 4
```

or `python app.py` for local testing. Keep it to **one** worker: every worker starts its own bot, so more workers means duplicate replies.

The dashboard is at `/`, and `/test` adds Goku to a random test image.
