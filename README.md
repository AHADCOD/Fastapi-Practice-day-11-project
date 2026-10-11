# Day 11 Practice Project — Library Lending API

A brand new app. Not a refactor. In-memory storage only — no database yet, that's Week 3.
Everything is `def`. The only `async def` allowed anywhere in this project is the logging middleware, because ASGI requires it.

---

## The domain

Three resources with real relationships between them:

- **Books** — title, author, ISBN, genre, total copies, available copies
- **Members** — name, email, membership type (`basic` / `premium`)
- **Loans** — a member borrowing a book: loan date, due date, return date, status

Business rules you must enforce:

- A book can only be loaned if `copies_available > 0`.
- Basic members can have at most **3** active loans at once. Premium members can have at most **10**.
- Basic members get a **14-day** loan period. Premium members get **30 days**.
- Returning a loan increments the book's `copies_available` and sets `status = returned`.
- ISBN must be a 10 or 13 digit string (validate it — don't just accept anything).
- Member email must be unique across all members. Book ISBN must be unique across all books.

---

## Required project structure

```
library_api/
├── main.py
├── core/
│   └── exceptions.py
├── routers/
│   ├── books.py
│   ├── members.py
│   └── loans.py
├── schemas/
│   ├── book.py
│   ├── member.py
│   └── loan.py
├── services/
│   ├── book_service.py
│   ├── member_service.py
│   └── loan_service.py
├── dependencies.py
└── middleware.py
```

Business logic (the rules above) lives in `services/`, not in the path operation functions. Path operations call services and handle HTTP concerns only (status codes, response shaping). This is the Day 9 principle — apply it from the start this time instead of retrofitting it.

`services/` hold the in-memory storage (plain dicts/lists at module level is fine) and the actual logic. Design them so that in Week 3 you could swap the storage backend for a real DB session without changing the router code. You don't have to prove this works — just don't write code that makes it obviously impossible.

---

## Endpoint spec

### Books (`routers/books.py`)

| Method | Path | Notes |
|---|---|---|
| POST | `/books` | Admin only (see auth dependency below). Body includes nested publisher info — see schema notes. |
| GET | `/books` | Query params: `genre` (enum, optional), `author` (str, optional, partial match), `available_only` (bool, default False). Pagination applies. |
| GET | `/books/available` | Must be registered **before** `/books/{book_id}` — you know why. Returns only books with `copies_available > 0`. |
| GET | `/books/{book_id}` | 404 if missing. |
| PATCH | `/books/{book_id}` | Partial update. Response must use `response_model_exclude_unset` correctly this time — meaning you need a `response_model` set. (Yes, this is the exact bug from Day 5's review. Don't repeat it.) |
| DELETE | `/books/{book_id}` | Admin only. Fail if the book has active loans — don't allow deleting a book someone currently has. |

**Genre** is an enum: `fiction`, `nonfiction`, `sci_fi`, `biography`, `reference`.

**Nested model requirement:** `BookCreate` must include a nested `Publisher` model (`name: str`, `country: str`) — practice nested Pydantic models again, this time as part of a create schema rather than a response.

### Members (`routers/members.py`)

| Method | Path | Notes |
|---|---|---|
| POST | `/members` | Public — anyone can register. |
| GET | `/members` | Query param: `membership_type` (enum, optional). Pagination applies. |
| GET | `/members/{member_id}` | 404 if missing. |
| PATCH | `/members/{member_id}` | Partial update, same `response_model_exclude_unset` requirement as books. |

### Loans (`routers/loans.py`)

| Method | Path | Notes |
|---|---|---|
| POST | `/loans` | See body requirement below. Enforce availability + loan limit rules. |
| GET | `/loans` | Query params: `member_id` (optional), `status` (enum, optional). Pagination applies. |
| GET | `/loans/overdue` | Before `/loans/{loan_id}`. A loan is overdue if `status == active` and `due_date < now`. |
| GET | `/loans/{loan_id}` | 404 if missing. |
| PATCH | `/loans/{loan_id}/return` | No body needed. Sets `return_date`, `status = returned`, increments book's `copies_available`. |

**Body requirement for POST `/loans`:** don't use a single Pydantic model here. Use two separate `Body(embed=True)` params — `member_id: int` and `book_id: int` — directly in the path operation signature. This is deliberately the Day 3 "multiple body params" pattern; you get one schema-based body (books/members) and one multi-param body (loans) in the same project.

**Loan status** enum: `active`, `returned`. ("Overdue" is not a stored status — it's derived. See computed fields below.)

---

## Pydantic v2 requirements (Day 6)

- `Loan` response schema: add a `computed_field` called `is_overdue` (bool), derived from `status` and `due_date`.
- `Book` response schema: add a `computed_field` called `is_available` (bool), derived from `copies_available`.
- ISBN validation on `BookCreate`: use `field_validator` to check it's all digits and length 10 or 13.
- Add one `model_validator` somewhere it actually makes sense — e.g. on loan creation input, if you take a raw due-date override anywhere, or on member update, cross-checking two fields together. Don't force it in artificially; if you can't find a natural spot, use it to validate that a `PATCH` body isn't completely empty (at least one field must be set).

---

## Dependency injection requirements (Day 7 & 8)

This is the section with the most new reps. Build all of these:

1. **Function-based dependency — pagination.** A `pagination_params` function taking `skip: int = Query(0, ge=0)` and `limit: int = Query(20, ge=1, le=100)`, reused across all three list endpoints.

2. **Class-based dependency — common list params.** Build a class (e.g. `CommonListParams`) that combines pagination with a `sort_by` and `order` (`asc`/`desc`) query param, with `__init__` taking the `Query(...)` defaults. Use this instead of the plain function version on at least one router, so you get reps on both styles.

3. **`yield` dependency — request-scoped store.** Build a dependency called something like `get_store` that, on entry, prints/logs "opening request scope" and on exit (after the response) prints/logs "closing request scope" (put it in a `try/finally`). It doesn't have to *do* anything real yet — the point is the setup/teardown shape, because this is exactly the shape your DB session dependency will take in Day 13. Wire it into at least the loan endpoints.

4. **Sub-dependency.** Build a dependency like `get_existing_book(book_id: int) -> Book` that depends on the book service, fetches the book, and raises `BookNotFoundError` if missing. Then use `Depends(get_existing_book)` in `GET /books/{book_id}`, `PATCH /books/{book_id}`, and `DELETE /books/{book_id}` instead of re-fetching the book manually in each one. Do the same for members if you want the extra rep — not required, but the pattern is the point.

5. **Class-based dependency — admin auth.** Build a simple `require_admin` dependency that reads an `X-API-Key` header (`Header(...)`) and compares it against a hardcoded constant (e.g. `"admin-secret-123"`). Raise 401 if the header is missing, 403 if it's wrong. This is *not* Week 4's OAuth2/JWT — it's just a header check, purely to practice the DI pattern. Apply it as a **router-level dependency** (via `APIRouter(dependencies=[...])` or `include_router(dependencies=[...])`) on whichever router/routes are admin-only, rather than adding `Depends(require_admin)` to each path operation individually. This is the "global/router-wide dependency" concept from Day 8.

---

## Middleware & error handling (Day 10, applying Day 4's exception patterns)

**Custom exceptions** (`core/exceptions.py`): define a base `LibraryError(Exception)` with `status_code` and `message` attributes, then subclass it for each specific error:

- `BookNotFoundError` → 404
- `MemberNotFoundError` → 404
- `LoanNotFoundError` → 404
- `BookUnavailableError` → 409
- `LoanLimitExceededError` → 409
- `DuplicateISBNError` → 409
- `DuplicateEmailError` → 409
- `BookHasActiveLoansError` → 409 (for the delete-with-active-loans case)

**Global exception handler:** one `@app.exception_handler(LibraryError)` registered on the base class, catching all subclasses. Response shape must be consistent:

```json
{
  "error": {
    "type": "BookUnavailableError",
    "message": "No copies of this book are currently available"
  }
}
```

Don't write a separate handler per exception type — one handler, reading `type(exc).__name__` and `exc.message`/`exc.status_code`.

**Logging middleware** (`middleware.py`): this is the one place `async def` is required. Log method, path, response status code, and time taken (wrap the `call_next` in a timer). Register it with `app.add_middleware` or `@app.middleware("http")`.

**CORS:** add `CORSMiddleware` too, even though you have no frontend calling this. Just get the registration syntax under your fingers again.

---

## What "done" looks like

- `uvicorn main:app --reload` starts clean.
- `/docs` shows all endpoints, grouped correctly by router tag.
- You can: register a member, create a book (with admin key), borrow it, hit the loan limit and get a proper 409, return it, and see `copies_available` go back up.
- Hitting `/books/available` and `/loans/overdue` works and doesn't get shadowed by the dynamic routes.
- A bad ISBN on book creation gets rejected by Pydantic before your code even runs.
- An unknown `book_id` anywhere returns your custom 404 shape, not FastAPI's default.
- Admin-only routes reject requests with a missing/wrong `X-API-Key` without you having added `Depends(require_admin)` to each one individually.

Bring me the code when it runs. I'll review it the same way I reviewed Day 5.
