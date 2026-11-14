from typing import Annotated

from fastapi import Depends
from sqlmodel import Session

from opname360.core.db import get_session

SessionDep = Annotated[Session, Depends(get_session)]
