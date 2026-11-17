import json

from typing import Annotated

import typer

from pydantic import ValidationError
from sqlmodel import Session

from opname360.core.db import engine
from opname360.core.errors import AppError
from opname360.models import Role, UserCreate
from opname360.services import posting
from opname360.services import users as users_service


app = typer.Typer(no_args_is_help=True, help='Opname360 setup commands.')


@app.command()
def create_owner(
    username: Annotated[str, typer.Option(prompt=True)],
    full_name: Annotated[str, typer.Option(prompt=True)],
    password: Annotated[
        str,
        typer.Option(prompt=True, hide_input=True, confirmation_prompt=True),
    ],
) -> None:
    """Create an Owner account. Owners create every other account."""
    try:
        user_in = UserCreate(
            username=username,
            full_name=full_name,
            role=Role.owner,
            password=password,
        )
        with Session(engine) as session:
            user = users_service.create_user(session, user_in, actor=None)
    except ValidationError as error:
        for problem in error.errors():
            typer.echo(f'{problem["loc"][0]}: {problem["msg"]}', err=True)
        raise typer.Exit(code=1) from error
    except AppError as error:
        typer.echo(error.detail, err=True)
        raise typer.Exit(code=1) from error
    typer.echo(f'Owner "{user.username}" created.')


@app.command()
def ledger_backfill() -> None:
    """Post every document completed before the Ledger existed, dated when
    it happened. Safe to run again: nothing is posted twice."""
    try:
        with Session(engine) as session:
            written = posting.backfill(session)
    except AppError as error:
        typer.echo(error.detail, err=True)
        raise typer.Exit(code=1) from error
    typer.echo(f'{written} jurnal dibuat.')


@app.command()
def export_openapi() -> None:
    """Print the API's OpenAPI schema, for generating the frontend client."""
    from opname360.main import app as api

    typer.echo(json.dumps(api.openapi(), indent=2))
