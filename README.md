# omniQ support sandbox

A local support coordinator with provider-neutral tickets, fictional samples, a read-only Freshdesk connector, source-scoped chat, and separate customer drafts and internal records. No ticket updates, assignments, notes, customer emails, or device actions are implemented.

## Run locally

Requires Python 3.10 or newer; the application uses the standard library.

```sh
python init_sandbox.py
python -m unittest discover -v
python app.py --mode sample --port 8768
```

Open http://127.0.0.1:8768/ for ticket review, `/chat` for fictional technical questions, and `/dialogflow` for a local imported export review. Use a different unused port if needed. The server binds to loopback only. Do not expose this development server publicly.

## What is included

Source code, fictional tickets and coverage records, sandbox intake articles, tests and `.env.example`. These are not production-approved product instructions. Customer-specific overrides have been removed.

This public repository does **not** contain customer tickets, contacts, historical approvals, production coverage, credentials, the Dialogflow export, proprietary manuals, extracted manual passages, or private evaluation reports. `data/`, `library-review/`, and `local_reviews/` are ignored local directories. Initialization does not overwrite existing files.

Product-specific chat retrieval requires your own authorized local source inventory, reviewed guidance cards, and matching document hashes. Empty indexes return no approved evidence; absent or changed required files produce a retrieval error. Do not treat the public checkout as a fully trained support agent. Inspect `chat_retrieval.py`, `library_guidance.py`, and `dialogflow_knowledge.py` for the local review schema. Importing an export with `import_dialogflow.py` does not approve its answers.

## Read-only Freshdesk pilot

Copy `.env.example` to `.env` locally and set FRESHDESK_DOMAIN and FRESHDESK_API_KEY. Set a ticket-ID allowlist or test group; when both are set the intersection applies. Then run:

```sh
python app.py --mode freshdesk --port 8767
```

The connector permits reads only. Keep `.env` and private local data out of Git. Never paste keys into chat. Process environment overrides `.env`; restart after configuration changes. Freshdesk credentials do not configure the model.

## Optional model chat

Chat accepts fictional cases only. Ticket review remains deterministic. Default `CHAT_PROVIDER=local` produces an explicitly labeled source-only simulation. To permit real calls, locally set CHAT_PROVIDER=openai, OPENAI_API_KEY, an accessible OPENAI_MODEL, and CHAT_ALLOW_PRODUCT_EXCERPTS=true. This authorizes transmission of fictional chat and matched eligible reviewed excerpts to OpenAI. No full document upload occurs.

```sh
python verify_model.py
python verify_model.py --live
```

The live test needs a locally reviewed replay passage (`library-review/replay_guidance.json`) and its original verified document. It deliberately fails if this private evidence or model configuration is missing. It cannot demonstrate a live model response from an empty public knowledge library.

The UI distinguishes generated answers, simulations, no approved evidence, retrieval failures, model configuration problems, and API failures. Request trace displays exact submitted excerpts, or states that none were sent. Provider errors are sanitized; no raw credentials are logged. Structured output and citations do not guarantee factual correctness: human review remains required.

## Limits

Classification, routing and workflow checks are rule-based. Document extraction is not approval. Confirm product, version and symptoms before a procedure, avoid repeating completed checks, and escalate outages, security and public-safety issues. No full Dialogflow execution engine or Priority connector is included; `domain.py` defines the replaceable ticket-reader contract.

Run `python evaluate.py` for synthetic sample evaluation. Results are authored fixture checks, not production accuracy. Do not publish locally generated evaluation reports containing real cases.
